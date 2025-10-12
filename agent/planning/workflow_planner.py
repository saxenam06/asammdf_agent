"""
Workflow planner using OpenAI API to generate action plans from skills
"""

import json
import os
import hashlib
from typing import List, Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import KnowledgeSchema, PlanSchema
from agent.execution.mcp_client import MCPClient

# Load environment variables
load_dotenv()

# Plan cache directory
PLANS_DIR = os.path.join(os.path.dirname(__file__), "..", "plans")


def _get_plan_filename(task: str, plan_number: int = 0) -> str:
    """Generate a safe filename from task name with plan number

    Args:
        task: Task description
        plan_number: Plan iteration number (0 for initial, 1+ for replans)

    Returns:
        Filename like: task_hash_Plan_0.json, task_hash_Plan_1.json, etc.
    """
    # Create a hash of the task for unique identification
    task_hash = hashlib.md5(task.encode()).hexdigest()[:8]
    # Create a safe filename from task (first 50 chars)
    safe_task = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in task[:50])
    safe_task = safe_task.strip().replace(' ', '_')
    return f"{safe_task}_{task_hash}_Plan_{plan_number}.json"


def get_latest_plan_number(task: str) -> int:
    """
    Get the highest plan number for a task

    Args:
        task: Task description

    Returns:
        Highest plan number found, or -1 if no plans exist
    """
    # Get task hash for matching files
    task_hash = hashlib.md5(task.encode()).hexdigest()[:8]
    safe_task = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in task[:50])
    safe_task = safe_task.strip().replace(' ', '_')

    pattern_prefix = f"{safe_task}_{task_hash}_Plan_"

    if not os.path.exists(PLANS_DIR):
        return -1

    max_plan_num = -1
    for filename in os.listdir(PLANS_DIR):
        if filename.startswith(pattern_prefix) and filename.endswith('.json'):
            # Extract plan number from filename
            try:
                plan_num_str = filename.replace(pattern_prefix, '').replace('.json', '')
                plan_num = int(plan_num_str)
                max_plan_num = max(max_plan_num, plan_num)
            except ValueError:
                continue

    return max_plan_num


def save_plan(task: str, plan: PlanSchema, plan_number: int = 0) -> str:
    """
    Save a plan to the plans directory

    Args:
        task: Task description
        plan: Plan to save
        plan_number: Plan iteration number (0 for initial, 1+ for replans)

    Returns:
        Path to saved plan file
    """
    os.makedirs(PLANS_DIR, exist_ok=True)
    filename = _get_plan_filename(task, plan_number)
    filepath = os.path.join(PLANS_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            "task": task,
            "plan": plan.model_dump()
        }, f, indent=2)

    return filepath


def load_plan(task: str, plan_number: Optional[int] = None) -> Optional[PlanSchema]:
    """
    Load a cached plan for a task

    Args:
        task: Task description
        plan_number: Specific plan number to load, or None to load latest

    Returns:
        Cached plan if exists, None otherwise
    """
    # If no plan number specified, get the latest
    if plan_number is None:
        plan_number = get_latest_plan_number(task)
        if plan_number == -1:
            return None

    filename = _get_plan_filename(task, plan_number)
    filepath = os.path.join(PLANS_DIR, filename)

    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return PlanSchema(**data["plan"])
    except Exception as e:
        print(f"Error loading cached plan: {e}")
        return None


def get_latest_plan_filepath(task: str) -> Optional[str]:
    """
    Get the filepath of the latest plan for a task

    Args:
        task: Task description

    Returns:
        Path to latest plan file, or None if no plans exist
    """
    plan_number = get_latest_plan_number(task)
    if plan_number == -1:
        return None

    filename = _get_plan_filename(task, plan_number)
    return os.path.join(PLANS_DIR, filename)


def plan_exists(task: str) -> bool:
    """
    Check if a plan exists for a task

    Args:
        task: Task description

    Returns:
        True if plan exists, False otherwise
    """
    return get_latest_plan_number(task) >= 0


class WorkflowPlanner:
    """
    Generates execution plans using OpenAI and retrieved knowledge patterns
    """

    def __init__(self, api_key: Optional[str] = None, mcp_client: MCPClient = None):
        """
        Initialize planner

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            mcp_client: MCPClient instance (creates new one if None)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable or api_key parameter required")

        self.client = OpenAI(api_key=self.api_key, timeout=120.0)
        self.model = "gpt-5-mini"
        self.mcp_client = mcp_client or MCPClient()
        self.available_tools = None

    def generate_plan(
        self,
        task: str,
        available_knowledge: List[KnowledgeSchema],
        context: Optional[str] = None,
        force_regenerate: bool = False,
        latest_state: Optional[str] = None
    ) -> PlanSchema:
        """
        Generate an execution plan for a task

        Args:
            task: Natural language task description
            available_knowledge: Knowledge patterns retrieved from documentation
            context: Optional additional context
            force_regenerate: If True, regenerate even if cached plan exists
            latest_state: Optional current UI state from State-Tool to help with planning

        Returns:
            Validated execution plan
        """
        # Check for cached plan first (unless force regenerate)
        if not force_regenerate:
            cached_plan = load_plan(task)
            if cached_plan is not None:
                print(f"  ✓ Using cached plan from: {_get_plan_filename(task)}")
                return cached_plan

        # Fetch MCP tools if not already cached
        if self.available_tools is None:
            print("Fetching available MCP tools...")
            self.available_tools = self.mcp_client.list_tools()
            print(f"Found {len(self.available_tools)} MCP tools")

        # Format tools description using MCPClient
        tools_description = self.mcp_client.get_tools_description(self.available_tools)
        valid_tool_names = self.mcp_client.get_valid_tool_names(self.available_tools)

        # Format knowledge for prompt
        knowledge_json = json.dumps(
            [knowledge.model_dump() for knowledge in available_knowledge],
            indent=2
        )

        # Build system prompt with dynamic tools
        # Using raw f-string to preserve single backslashes for Windows paths
        system_prompt = rf"""You are an expert GUI automation planner for the asammdf application.

═══════════════════════════════════════════════════════════════════════════════
YOUR ROLE
═══════════════════════════════════════════════════════════════════════════════
Generate step-by-step execution plans to accomplish user tasks by orchestrating MCP tools for GUI automation.

═══════════════════════════════════════════════════════════════════════════════
AVAILABLE MCP TOOLS
═══════════════════════════════════════════════════════════════════════════════
{tools_description}

═══════════════════════════════════════════════════════════════════════════════
PLANNING RULES & BEST PRACTICES
═══════════════════════════════════════════════════════════════════════════════

1. KNOWLEDGE-BASED PLANNING
   • Use provided knowledge patterns from documentation as your PRIMARY reference
   • Knowledge patterns contain proven workflows - follow them closely
   • Adapt patterns to specific task details (paths, filenames, etc.)

2. TOOL USAGE REQUIREMENTS
   • Use ONLY the tool names listed above - no custom or made-up tools
   • Follow tool argument schemas exactly as specified
   • Include reasoning for each step to explain WHY that action is needed

3. STATE MANAGEMENT (CRITICAL)
   • ALWAYS call State-Tool BEFORE clicking/typing on UI elements
   • State-Tool argument: {{"use_vision": false}}
   • DO NOT hardcode coordinates - discover them dynamically via State-Tool
   • Reference elements using: ["last_state:element_type:element_name"]
   • For files selection: ["last_state:file name:xyz.MF4"] or ["last_state:file name:*.MF4"]

4. WINDOW ACTIVATION
   • Start plans with Switch-Tool to activate the asammdf window
   • Switch-Tool argument: {{"name": "asammdf"}}
   • This ensures subsequent actions target the correct application

5. ELEMENT REFERENCE FORMAT
   When referencing UI elements discovered by State-Tool:
   • Menus: ["last_state:menu:Mode"]
   • Buttons: ["last_state:button:Save"]
   • File name: ["last_state:edit:File name"]
   • Select Files: ["last_state:file name:data.MF4"]
   • Wildcards: ["last_state:file name:*.MF4"] for any matching file

6. PATH FORMATTING (CRITICAL FOR WINDOWS)
   • ALWAYS use single backslash (\) in Windows paths
   • Example: C:\Users\ADMIN\Downloads\file.mf4
   • NEVER use double backslashes (\\) - this will cause GUI typing errors
   • When specifying paths in Type-Tool arguments, use exactly ONE backslash between path components

7. PLANNING WORKFLOW
   Step 1: Activate application (Switch-Tool)
   Step 2: Get current UI state (State-Tool)
   Step 3: Interact with discovered elements (Click-Tool, Type-Tool, etc.)
   Step 4: Repeat State-Tool → Interact cycle as needed
   Step 5: Complete task and verify

8. OUTPUT REQUIREMENTS
   • Return ONLY valid JSON matching the schema below
   • No explanatory text outside the JSON structure
   • Include clear reasoning for each step
   • Provide realistic estimated_duration in seconds

═══════════════════════════════════════════════════════════════════════════════
REQUIRED JSON SCHEMA
═══════════════════════════════════════════════════════════════════════════════

{{
  "task": "Brief restatement of the user's task",
  "plan": [
    {{
      "tool_name": "Switch-Tool",
      "tool_arguments": {{ "name": "asammdf" }},
      "reasoning": "Activate the asammdf window so subsequent queries/clicks target it"
    }},
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{ "use_vision": false }},
      "reasoning": "Get current desktop state to discover available UI elements"
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{ "loc": ["last_state:menu:Mode"], "button": "left", "clicks": 1 }},
      "reasoning": "Open the Mode menu using coordinates from most recent State-Tool"
    }},
    {{
        "tool_name": "Type-Tool",
        "tool_arguments": {{
          "text": "C:\Users\ADMIN\Downloads\output.mf4",
          "clear": true,
          "press_enter": false
        }},
        "reasoning": "Enter the full output path and filename"
      }},
    ... additional steps following the same pattern ...
  ],
  "reasoning": "High-level strategy explaining the overall approach and why this sequence of steps will accomplish the task",
  "estimated_duration": 60
}}

═══════════════════════════════════════════════════════════════════════════════
EXAMPLE (Reference for structure, not content)
═══════════════════════════════════════════════════════════════════════════════

Task: "Concatenate all MF4 files in C:\\data\\logs folder and save output.mf4"

{{
  "task": "Concatenate all MF4 files in C:\\data\\logs folder and save output.mf4",
  "plan": [
    {{"tool_name": "Switch-Tool", "tool_arguments": {{"name": "asammdf"}}, "reasoning": "Activate asammdf window"}},
    {{"tool_name": "State-Tool", "tool_arguments": {{"use_vision": false}}, "reasoning": "Discover UI elements"}},
    {{"tool_name": "Click-Tool", "tool_arguments": {{"loc": ["last_state:menu:Mode"], "button": "left", "clicks": 1}}, "reasoning": "Open Mode menu"}},
    {{"tool_name": "State-Tool", "tool_arguments": {{"use_vision": false}}, "reasoning": "Find Batch option"}},
    {{"tool_name": "Click-Tool", "tool_arguments": {{"loc": ["last_state:menu item:Batch"], "button": "left", "clicks": 1}}, "reasoning": "Switch to Batch mode"}}
  ],
  "reasoning": "Use Batch mode to concatenate multiple MF4 files by selecting folder, choosing operation, and executing",
  "estimated_duration": 45
}}

═══════════════════════════════════════════════════════════════════════════════
Now generate your plan following these guidelines.
═══════════════════════════════════════════════════════════════════════════════
"""

        # Build user prompt
        context_str = f"\n\nAdditional context: {context}" if context else ""

        # Get initial UI state by calling State-Tool
        state_context = ""
        
        # Include latest UI state if available to help planner understand state format
        if latest_state:
            state_context = f"""

CURRENT UI STATE (for reference - understand the state format and available elements):
```
{latest_state}  # Truncate to avoid token overflow
```

Use this state to:
- Understand what UI elements are currently available
- See the format of State-Tool output (this is what you'll reference in your plan)
- Make informed decisions about which elements to interact with
"""

        user_prompt = f"""User task: "{task}"{context_str}{state_context}

Available knowledge patterns from documentation:
{knowledge_json}

Generate a complete execution plan using ONLY these knowledge patterns.

Consider:
- What prerequisite steps are needed (e.g., opening files before processing)
- The correct order of operations
- What arguments each action needs
- Expected GUI state after each action

Return ONLY valid JSON matching the schema. No explanatory text outside JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=120000,
                timeout=600.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Extract JSON from response
            content = response.choices[0].message.content

            # Parse JSON
            if content.strip().startswith('{'):
                plan_data = json.loads(content)
            else:
                # Try to extract from code block
                if '```json' in content:
                    json_start = content.find('```json') + 7
                    json_end = content.find('```', json_start)
                    json_str = content[json_start:json_end].strip()
                    plan_data = json.loads(json_str)
                elif '```' in content:
                    json_start = content.find('```') + 3
                    json_end = content.find('```', json_start)
                    json_str = content[json_start:json_end].strip()
                    plan_data = json.loads(json_str)
                else:
                    plan_data = json.loads(content)

            # Validate with Pydantic
            plan = PlanSchema(**plan_data)

            # Save the generated plan to cache as Plan_0
            saved_path = save_plan(task, plan, plan_number=0)
            print(f"  ✓ Plan saved to: {os.path.basename(saved_path)}")

            return plan

        except Exception as e:
            print(f"Error generating plan: {e}")
            raise

    def validate_plan(self, plan: PlanSchema) -> tuple[bool, Optional[str]]:
        """
        Validate a plan's tool names against available MCP tools

        Args:
            plan: Plan to validate

        Returns:
            (is_valid, error_message)
        """
        # Fetch MCP tools if not already cached
        if self.available_tools is None:
            self.available_tools = self.mcp_client.list_tools()

        # Get valid tool names
        valid_tool_names = self.mcp_client.get_valid_tool_names(self.available_tools)

        # Validate each action's tool name
        for i, action in enumerate(plan.plan, 1):
            if action.tool_name not in valid_tool_names:
                return False, (
                    f"Step {i}: Invalid MCP tool '{action.tool_name}'. "
                    f"Must use one of: {', '.join(valid_tool_names)}"
                )

        return True, None

if __name__ == "__main__":
    """
    Test plan generation
    """
    from agent.rag.knowledge_retriever import KnowledgeRetriever

    # Test task
    task = r"Concatenate all MF4 files in C:\Users\ADMIN\Downloads\ev-data-pack-v10\ev-data-pack-v10\electric_cars\log_files\Tesla Model 3\LOG\3F78A21D\00000001 folder save the concatenated MF4 file with name Tesla_Model_3_3F78A21D.mf4 in the same folder path"

    print("="*80)
    print(f"Task: {task}")
    print("="*80 + "\n")

    # Retrieve knowledge patterns
    print("Retrieving relevant knowledge patterns...")
    retriever = KnowledgeRetriever()
    knowledge_patterns = retriever.retrieve(task, top_k=5)

    print(f"Retrieved {len(knowledge_patterns)} knowledge patterns:")
    for knowledge in knowledge_patterns:
        print(f"  - {knowledge.knowledge_id}")
    print()

    # Generate plan
    print("Generating plan with GPT...")
    planner = WorkflowPlanner()
    plan = planner.generate_plan(task, knowledge_patterns)

    print("Generated plan:")
    print(f"Reasoning: {plan.reasoning}")
    print(f"Estimated duration: {plan.estimated_duration}s")
    print(f"\nSteps ({len(plan.plan)}):")
    for i, action in enumerate(plan.plan, 1):
        print(f"{i}. {action.tool_name}({action.tool_arguments})")
        if action.reasoning:
            print(f"   Reasoning: {action.reasoning}")
        print()

    print("✓ Plan generated and validated successfully")
