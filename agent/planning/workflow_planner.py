"""
Workflow planner using OpenAI API to generate action plans from skills
"""

import json
import os
from typing import List, Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import KnowledgeSchema, PlanSchema
from agent.execution.mcp_executor import MCPExecutor

# Load environment variables
load_dotenv()


class WorkflowPlanner:
    """
    Generates execution plans using OpenAI and retrieved knowledge patterns
    """

    def __init__(self, api_key: Optional[str] = None, mcp_executor: MCPExecutor = None):
        """
        Initialize planner

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            mcp_executor: MCPExecutor instance (creates new one if None)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable or api_key parameter required")

        self.client = OpenAI(api_key=self.api_key, timeout=120.0)
        self.model = "gpt-5-mini"
        self.mcp_executor = mcp_executor or MCPExecutor()
        self.available_tools = None

    def generate_plan(
        self,
        task: str,
        available_knowledge: List[KnowledgeSchema],
        context: Optional[str] = None
    ) -> PlanSchema:
        """
        Generate an execution plan for a task

        Args:
            task: Natural language task description
            available_knowledge: Knowledge patterns retrieved from documentation
            context: Optional additional context

        Returns:
            Validated execution plan
        """
        # Fetch MCP tools if not already cached
        if self.available_tools is None:
            print("Fetching available MCP tools...")
            self.available_tools = self.mcp_executor.list_tools()
            print(f"Found {len(self.available_tools)} MCP tools")

        # Format tools description using MCPExecutor
        tools_description = self.mcp_executor.get_tools_description(self.available_tools)
        valid_tool_names = self.mcp_executor.get_valid_tool_names(self.available_tools)

        # Format knowledge for prompt
        knowledge_json = json.dumps(
            [knowledge.model_dump() for knowledge in available_knowledge],
            indent=2
        )

        # Build system prompt with dynamic tools
        system_prompt = f"""You are a GUI automation planner for the asammdf application.

Your task is to generate a step-by-step execution plan to accomplish user tasks using MCP tools.

You have access to the following MCP tools for GUI automation:

{tools_description}

Rules:
1. Use the provided knowledge patterns from documentation as reference for what actions to take
2. Generate a plan as a sequence of MCP tool calls (tool_name, tool_arguments, and optional reasoning)
3. Use State-Tool to get UI element coordinates before clicking/typing
4. Use Switch-Tool to activate the application window before other actions
5. Use ONLY the tool names and arguments exactly as specified above
6. Output valid JSON matching the required schema

IMPORTANT: You cannot hardcode coordinates. Your plan should:
1. Use State-Tool to discover UI elements dynamically
2. Parse the state output to find element coordinates
3. Use those coordinates in Click-Tool/Type-Tool calls

Output format:
{{
  "plan": [
    {{
      "tool_name": "State-Tool",
      "tool_arguments": {{"use_vision": false}},
      "reasoning": "Get current desktop state to find UI elements"
    }},
    {{
      "tool_name": "Switch-Tool",
      "tool_arguments": {{"name": "asammdf"}},
      "reasoning": "Activate the asammdf application window"
    }},
    {{
      "tool_name": "Click-Tool",
      "tool_arguments": {{"loc": [450, 300], "button": "left", "clicks": 1}},
      "reasoning": "Click the File menu button"
    }}
  ],
  "reasoning": "Overall explanation of why this plan achieves the task",
  "estimated_duration": 30
}}

Note: For coordinates, you'll need to reference them from previous State-Tool calls or use placeholder descriptions that will be resolved at execution time."""

        # Build user prompt
        context_str = f"\n\nAdditional context: {context}" if context else ""

        user_prompt = f"""User task: "{task}"{context_str}

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
            self.available_tools = self.mcp_executor.list_tools()

        # Get valid tool names
        valid_tool_names = self.mcp_executor.get_valid_tool_names(self.available_tools)

        # Validate each action's tool name
        for i, action in enumerate(plan.plan, 1):
            if action.tool_name not in valid_tool_names:
                return False, (
                    f"Step {i}: Invalid MCP tool '{action.tool_name}'. "
                    f"Must use one of: {', '.join(valid_tool_names)}"
                )

        return True, None

    def refine_plan(
        self,
        task: str,
        current_plan: PlanSchema,
        error_feedback: str,
        available_knowledge: List[KnowledgeSchema]
    ) -> PlanSchema:
        """
        Refine a plan based on error feedback

        Args:
            task: Original task
            current_plan: Current plan that failed
            error_feedback: Error message or feedback
            available_knowledge: Available knowledge patterns

        Returns:
            Refined plan
        """
        knowledge_json = json.dumps(
            [knowledge.model_dump() for knowledge in available_knowledge],
            indent=2
        )

        prompt = f"""The previous plan failed. Generate an improved plan.

Original task: "{task}"

Previous plan:
{json.dumps(current_plan.model_dump(), indent=2)}

Error feedback: {error_feedback}

Available knowledge patterns:
{knowledge_json}

Generate a corrected plan that addresses the error. Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=120000,
                timeout=600.0,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.choices[0].message.content

            # Parse JSON (same logic as generate_plan)
            if content.strip().startswith('{'):
                plan_data = json.loads(content)
            else:
                if '```json' in content:
                    json_start = content.find('```json') + 7
                    json_end = content.find('```', json_start)
                    json_str = content[json_start:json_end].strip()
                    plan_data = json.loads(json_str)
                else:
                    plan_data = json.loads(content)

            refined_plan = PlanSchema(**plan_data)
            return refined_plan

        except Exception as e:
            print(f"Error refining plan: {e}")
            raise


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
