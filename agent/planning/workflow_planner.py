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
from agent.prompts.planning_prompt import get_planning_system_prompt, get_planning_user_prompt, save_prompt_to_markdown
from agent.utils.cost_tracker import track_api_call

# HITL imports
try:
    from agent.learning.skill_library import SkillLibrary
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


def save_plan(
    task: str,
    plan: PlanSchema,
    plan_number: int = 0,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Save a plan to the plans directory with metadata about retrieved KB items

    Args:
        task: Task description
        plan: Plan to save
        plan_number: Plan iteration number (0 for initial, 1+ for replans)
        metadata: Optional metadata (e.g., retrieved KB items)

    Returns:
        Path to saved plan file
    """
    os.makedirs(PLANS_DIR, exist_ok=True)
    filename = _get_plan_filename(task, plan_number)
    filepath = os.path.join(PLANS_DIR, filename)

    # Add step numbers (1-indexed) to each action for human readability
    plan_dict = plan.model_dump()
    for idx, action in enumerate(plan_dict["plan"], 1):
        action["step_num"] = idx

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            "task": task,
            "plan": plan_dict,
            "metadata": metadata or {}
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
        knowledge_retriever = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize planner

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            mcp_client: MCPClient instance (creates new one if None)
            skill_library: Optional SkillLibrary for verified skills
            knowledge_retriever: Optional KnowledgeRetriever for dynamic doc retrieval
            session_id: Optional session ID for tracking
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
        self.knowledge_retriever = knowledge_retriever
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
            matched_skill = self.skill_library.find_matching_skill(task, similarity_threshold=0.7)
            if matched_skill:
                print(f"  ✓ [HITL] Found verified skill: '{matched_skill.task_description}' "
                      f"(success rate: {matched_skill.metadata.success_rate:.1%})")
                print(f"    Used {matched_skill.metadata.times_used} times")

                # Use the skill's action plan
                skill_plan = PlanSchema(
                    reasoning=f"Using verified skill: {matched_skill.skill_id}",
                    plan=matched_skill.action_plan,
                    estimated_duration=60  # Default estimate
                )

                # Update usage statistics - will be updated after execution
                # (success/failure tracked in workflow execution)

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

        # Format knowledge for prompt WITH learnings attached to KB items
        kb_formatted = self._format_kb_with_learnings(available_knowledge)

        # Build prompts using centralized templates (with KB learnings)
        system_prompt = get_planning_system_prompt(tools_description)
        user_prompt = get_planning_user_prompt(
            task=task,
            knowledge_json=kb_formatted,  # Use formatted KB with learnings
            context=context or "",
            latest_state=latest_state or "",
        )

        # Get plan number for this task
        plan_number = get_latest_plan_number(task) + 1

        # Save prompts to markdown for inspection
        prompt_file = save_prompt_to_markdown(
            task=task,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            plan_number=plan_number
        )
        if prompt_file:
            print(f"  📝 Prompt saved: {os.path.basename(prompt_file)}")

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
                task_context=task
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

            # Save the generated plan to cache as Plan_0 with KB metadata
            plan_metadata = {
                "retrieved_kb_ids": [kb.knowledge_id for kb in available_knowledge],
                "kb_count": len(available_knowledge)
            }
            saved_path = save_plan(task, plan, plan_number=0, metadata=plan_metadata)
            print(f"  ✓ Plan saved to: {os.path.basename(saved_path)}")

            return plan

        except Exception as e:
            print(f"Error generating plan: {e}")
            raise

    def _format_kb_with_learnings(self, kb_items: List[KnowledgeSchema]) -> str:
        """
        Format KB items with their attached learnings for LLM context

        For KB items with learnings, dynamically retrieves related docs to help solve errors

        Args:
            kb_items: List of knowledge base items with learnings

        Returns:
            Formatted string with KB items, learnings, and dynamically retrieved related docs
        """
        formatted_parts = []

        for kb in kb_items:
            # Basic KB info with knowledge_id prominent
            kb_section = f"""
---
KB ID: {kb.knowledge_id}
Description: {kb.description}
UI Location: {kb.ui_location}
Action Sequence:
{chr(10).join(f"  - {action}" for action in kb.action_sequence)}
"""
            if kb.shortcut:
                kb_section += f"Shortcut: {kb.shortcut}\n"

            kb_section += "---"

            # Add learnings if they exist
            if kb.kb_learnings and len(kb.kb_learnings) > 0:
                kb_section += f"\n\n⚠️ PAST FAILURES ({len(kb.kb_learnings)} failure(s)):\n"

                for idx, learning_dict in enumerate(kb.kb_learnings[:3], 1):  # Top 3
                    # Check if it's a failure learning (has original_error field)
                    if 'original_error' in learning_dict:
                        failed_tool = learning_dict.get('original_action', {}).get('tool_name', 'N/A')
                        failed_args = learning_dict.get('original_action', {}).get('tool_arguments', {})
                        error_msg = learning_dict.get('original_error', 'N/A')
                        step_num = learning_dict.get('step_num', 'N/A')

                        kb_section += f"""
{idx}. Failure at Step {step_num}:
   - Failed Action: {failed_tool} with args {failed_args}
   - Error: {error_msg}
   - Consider: Try alternative approach, different KB item, or use related docs below
"""
                        # Dynamically retrieve related docs to help solve the error
                        if self.knowledge_retriever:
                            try:
                                action_reasoning = learning_dict.get('original_action', {}).get('reasoning', '')
                                search_query = f"{action_reasoning} {error_msg} alternative solution"

                                # Retrieve related KB items (exclude current KB item)
                                related_kb_items = self.knowledge_retriever.retrieve(search_query, top_k=3)
                                related_kb_items = [item for item in related_kb_items if item.knowledge_id != kb.knowledge_id]

                                if related_kb_items:
                                    kb_section += f"   📚 Alternative Approaches ({len(related_kb_items)}):\n"
                                    for doc in related_kb_items[:2]:  # Limit to 2 for brevity
                                        kb_section += f"      • KB ID: {doc.knowledge_id}\n"
                                        kb_section += f"        {doc.description[:100]}\n"
                                        if doc.shortcut:
                                            kb_section += f"        Shortcut: {doc.shortcut}\n"
                                        if doc.action_sequence:
                                            kb_section += f"        Actions: {', '.join(doc.action_sequence[:3])}\n"
                            except Exception as e:
                                print(f"  [Warning] Could not retrieve related docs: {e}")

                    # Check if it's a human interrupt learning
                    elif 'human_reasoning' in learning_dict:
                        kb_section += f"""
{idx}. Human Correction:
   - Human Said: {learning_dict.get('human_reasoning', 'N/A')}...
   - Corrected To: {learning_dict.get('corrected_action', {}).get('tool_name', 'N/A')}
   - Task Context: {learning_dict.get('task', 'N/A')}...
"""

            # Trust score warning if low
            if kb.trust_score < 0.9:
                kb_section += f"\n⚠️ CAUTION: Trust score {kb.trust_score:.2f} (has {len(kb.kb_learnings)} known issue(s))\n"

            formatted_parts.append(kb_section)

        result = "\n".join(formatted_parts)

        # Add summary header
        total_learnings = sum(len(kb.kb_learnings) for kb in kb_items)
        if total_learnings > 0:
            header = f"""
KNOWLEDGE BASE PATTERNS WITH LEARNINGS
Total KB items: {len(kb_items)}
Total learnings: {total_learnings}

IMPORTANT: Each KB item shows its KB ID. When using a KB item in your plan,
set the action's kb_source field to that KB ID.

"""
            result = header + result

        return result

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
