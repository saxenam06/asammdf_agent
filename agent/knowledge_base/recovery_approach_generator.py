"""
Recovery Approach Generator

Uses LLM to analyze verified skills and generate recovery approaches
for knowledge base items that have original_error field.
"""

import json
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

from agent.prompts.kb_recovery_approach_prompt import KB_RECOVERY_APPROACH_PROMPT


class RecoveryApproachGenerator:
    """Generates recovery approaches for KB items using verified skills"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the recovery approach generator

        Args:
            api_key: OpenAI API key (if not provided, uses environment variable)
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"  # Cost-effective model for this task

    def generate_recovery_approaches(
        self,
        verified_skill: Dict[str, Any],
        knowledge_catalog: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Generate recovery approaches for KB items with original_error

        Args:
            verified_skill: The verified skill dictionary
            knowledge_catalog: Full knowledge catalog

        Returns:
            Dictionary mapping knowledge_id to recovery_approach
        """
        # Filter KB items that have original_error
        kb_items_with_errors = []
        for item in knowledge_catalog:
            kb_learnings = item.get("kb_learnings", [])
            for learning in kb_learnings:
                if learning.get("original_error"):
                    kb_items_with_errors.append({
                        "knowledge_id": item.get("knowledge_id"),
                        "description": item.get("description"),
                        "original_error": learning.get("original_error"),
                        "original_action": learning.get("original_action")
                    })

        if not kb_items_with_errors:
            print("[Recovery Generator] No KB items with original_error found")
            return {}

        print(f"[Recovery Generator] Processing {len(kb_items_with_errors)} KB items with errors")

        # Prepare the prompt
        prompt = KB_RECOVERY_APPROACH_PROMPT.format(
            verified_skill=json.dumps(verified_skill, indent=2),
            kb_items_with_errors=json.dumps(kb_items_with_errors, indent=2)
        )

        try:
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing workflows and extracting actionable recovery approaches from successful executions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Low temperature for consistent, focused output
                response_format={"type": "json_object"}
            )

            # Parse response
            result_text = response.choices[0].message.content

            # Handle both array and object responses
            try:
                result = json.loads(result_text)

                # If it's wrapped in an object, extract the array
                if isinstance(result, dict):
                    # Try common keys
                    if "recovery_approaches" in result:
                        result = result["recovery_approaches"]
                    elif "results" in result:
                        result = result["results"]
                    elif "items" in result:
                        result = result["items"]
                    else:
                        # Take the first array value
                        for value in result.values():
                            if isinstance(value, list):
                                result = value
                                break

                if not isinstance(result, list):
                    print(f"[Recovery Generator] Unexpected response format: {type(result)}")
                    return {}

            except json.JSONDecodeError as e:
                print(f"[Recovery Generator] Failed to parse LLM response: {e}")
                print(f"Response: {result_text}")
                return {}

            # Convert to dictionary
            recovery_approaches = {}
            for item in result:
                if isinstance(item, dict):
                    knowledge_id = item.get("knowledge_id")
                    recovery_approach = item.get("recovery_approach")

                    if knowledge_id and recovery_approach:
                        recovery_approaches[knowledge_id] = recovery_approach

            print(f"[Recovery Generator] Generated {len(recovery_approaches)} recovery approaches")
            return recovery_approaches

        except Exception as e:
            print(f"[Recovery Generator] Error calling LLM: {e}")
            return {}

    def update_knowledge_catalog(
        self,
        catalog_path: str,
        recovery_approaches: Dict[str, str]
    ) -> bool:
        """
        Update knowledge catalog with recovery approaches

        Args:
            catalog_path: Path to knowledge catalog JSON file
            recovery_approaches: Dictionary mapping knowledge_id to recovery_approach

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load catalog
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog = json.load(f)

            updated_count = 0

            # Update items
            for item in catalog:
                knowledge_id = item.get("knowledge_id")
                if knowledge_id in recovery_approaches:
                    # Add recovery_approach to kb_learnings that have original_error
                    kb_learnings = item.get("kb_learnings", [])
                    for learning in kb_learnings:
                        if learning.get("original_error") and not learning.get("recovery_approach"):
                            learning["recovery_approach"] = recovery_approaches[knowledge_id]
                            updated_count += 1

            # Save updated catalog
            with open(catalog_path, 'w', encoding='utf-8') as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)

            print(f"[Recovery Generator] Updated {updated_count} KB learnings with recovery approaches")
            return True

        except Exception as e:
            print(f"[Recovery Generator] Error updating catalog: {e}")
            return False


def generate_and_update_kb_recovery_approaches(
    verified_skill_path: str,
    catalog_path: str = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"
) -> bool:
    """
    Convenience function to generate and update KB recovery approaches

    Args:
        verified_skill_path: Path to verified skill JSON file
        catalog_path: Path to knowledge catalog JSON file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Load verified skill
        with open(verified_skill_path, 'r', encoding='utf-8') as f:
            verified_skill = json.load(f)

        # Load catalog
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

        # Generate recovery approaches
        generator = RecoveryApproachGenerator()
        recovery_approaches = generator.generate_recovery_approaches(verified_skill, catalog)

        if not recovery_approaches:
            print("[Recovery Generator] No recovery approaches generated")
            return False

        # Update catalog
        return generator.update_knowledge_catalog(catalog_path, recovery_approaches)

    except Exception as e:
        print(f"[Recovery Generator] Error: {e}")
        return False