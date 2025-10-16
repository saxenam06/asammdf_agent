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
from agent.prompts.planning_prompt import get_planning_system_prompt, get_planning_user_prompt
from agent.utils.cost_tracker import track_api_call

# HITL imports
try:
    from agent.learning.skill_library import SkillLibrary
    from agent.feedback.memory_manager import LearningMemoryManager
    HITL_AVAILABLE = True
except ImportError:
    HITL_AVAILABLE = False
    print("[Warning] HITL components not available")

load_dotenv()

# Plan cache directory
PLANS_DIR = os.path.join(os.path.dirname(__file__), "plans")


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

    def __init__(
        self,
        api_key: Optional[str] = None,
        mcp_client: MCPClient = None,
        skill_library: Optional['SkillLibrary'] = None,
        memory_manager: Optional['LearningMemoryManager'] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize planner

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            mcp_client: MCPClient instance (creates new one if None)
            skill_library: Optional SkillLibrary for verified skills
            memory_manager: Optional LearningMemoryManager for learnings
            session_id: Optional session ID for memory retrieval
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable or api_key parameter required")

        self.client = OpenAI(api_key=self.api_key, timeout=120.0)
        self.model = "gpt-5-mini"
        self.mcp_client = mcp_client or MCPClient()
        self.available_tools = None

        # HITL components
        self.skill_library = skill_library
        self.memory_manager = memory_manager
        self.session_id = session_id or "default_session"

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
        # Step 1: Check SkillLibrary for verified skill (highest priority)
        if HITL_AVAILABLE and self.skill_library and not force_regenerate:
            print("  [HITL] Checking for verified skills...")
            matched_skills = self.skill_library.find_similar_skills(task, threshold=0.7)
            if matched_skills:
                best_skill = matched_skills[0]  # Highest similarity
                print(f"  ✓ [HITL] Found verified skill: '{best_skill.original_task}' "
                      f"(similarity: {best_skill.similarity_score:.2f}, "
                      f"success rate: {best_skill.success_rate:.1%})")
                print(f"    Used {best_skill.usage_count} times")

                # Use the skill's plan
                skill_plan = PlanSchema(**best_skill.plan)

                # Update usage statistics
                self.skill_library.record_usage(best_skill.skill_id)

                return skill_plan
            else:
                print("  [HITL] No matching verified skills found")

        # Step 2: Check for cached plan (unless force regenerate)
        if not force_regenerate:
            cached_plan = load_plan(task)
            if cached_plan is not None:
                print(f"  ✓ Using cached plan from: {_get_plan_filename(task)}")
                return cached_plan

        # Fetch MCP tools if not already cached
        if self.available_tools is None:
            print("Fetching available MCP tools...")
            self.available_tools = self.mcp_client.list_tools_sync()
            print(f"Found {len(self.available_tools)} MCP tools")

        # Format tools description using MCPClient
        tools_description = self.mcp_client.get_tools_description_sync(self.available_tools)
        valid_tool_names = self.mcp_client.get_valid_tool_names_sync(self.available_tools)

        # Format knowledge for prompt
        knowledge_json = json.dumps(
            [knowledge.model_dump() for knowledge in available_knowledge],
            indent=2
        )

        # Step 3: Retrieve learnings from memory
        learnings_context = ""
        if HITL_AVAILABLE and self.memory_manager:
            print("  [HITL] Retrieving learnings from memory...")
            try:
                learnings = self.memory_manager.retrieve_all_learnings_for_task(
                    task=task,
                    session_id=self.session_id
                )

                # Format learnings for context
                learnings_parts = []
                if learnings.get("human_proactive"):
                    learnings_parts.append(f"\n**Human Guidance ({len(learnings['human_proactive'])} items)**:")
                    for learning in learnings["human_proactive"][:3]:  # Top 3
                        learnings_parts.append(f"  - {learning.get('memory', 'No details')}")

                if learnings.get("human_interrupt"):
                    learnings_parts.append(f"\n**Human Corrections ({len(learnings['human_interrupt'])} items)**:")
                    for learning in learnings["human_interrupt"][:3]:  # Top 3
                        learnings_parts.append(f"  - {learning.get('memory', 'No details')}")

                if learnings.get("agent_self_exploration"):
                    learnings_parts.append(f"\n**Agent Self-Recovery ({len(learnings['agent_self_exploration'])} items)**:")
                    for learning in learnings["agent_self_exploration"][:2]:  # Top 2
                        learnings_parts.append(f"  - {learning.get('memory', 'No details')}")

                if learnings_parts:
                    learnings_context = "\n\n## Past Learnings\n" + "\n".join(learnings_parts)
                    print(f"  [HITL] Retrieved {sum(len(v) for v in learnings.values())} learnings")
                else:
                    print("  [HITL] No learnings found for this task")
            except Exception as e:
                print(f"  [Warning] Failed to retrieve learnings: {e}")

        # Build prompts using centralized templates (with learnings context appended)
        system_prompt = get_planning_system_prompt(tools_description)
        user_prompt = get_planning_user_prompt(task, knowledge_json, context or "", latest_state or "")

        # Append learnings to user prompt if available
        if learnings_context:
            user_prompt += learnings_context

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

            # Track API cost
            usage = response.usage
            cost = track_api_call(
                model=self.model,
                component="planning",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                task_context=task[:100]
            )
            print(f"  💰 Planning cost: ${cost:.4f} ({usage.prompt_tokens:,} in + {usage.completion_tokens:,} out tokens)")

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
            self.available_tools = self.mcp_client.list_tools_sync()

        # Get valid tool names
        valid_tool_names = self.mcp_client.get_valid_tool_names_sync(self.available_tools)

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
    from agent.knowledge_base.retriever import KnowledgeRetriever

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
