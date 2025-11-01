"""
Test script for KB Recovery Approach Generator

This script tests the recovery approach generation without requiring
a full workflow execution.
"""

import json
from agent.knowledge_base.recovery_approach_generator import RecoveryApproachGenerator

def test_recovery_approach_generation():
    """Test recovery approach generation with sample data"""

    # Sample verified skill (matching the actual structure from SkillLibrary)
    verified_skill = {
        "skill_id": "test_skill_001",
        "task_description": "Concatenate all .MF4 files in a folder",
        "action_plan": [
            {
                "tool_name": "Click-Tool",
                "tool_arguments": {"loc": ["last_state:menu:File"]},
                "reasoning": "Open File menu"
            },
            {
                "tool_name": "Click-Tool",
                "tool_arguments": {"loc": ["last_state:menu_option:Open"]},
                "reasoning": "Select Open option"
            },
            {
                "tool_name": "Type-Tool",
                "tool_arguments": {
                    "text": "C:\\Users\\ADMIN\\Downloads\\folder\\00001026\\",
                    "press_enter": True
                },
                "reasoning": "Navigate to exact folder path"
            },
            {
                "tool_name": "Click-Tool",
                "tool_arguments": {"loc": ["last_state:file:*.MF4"]},
                "reasoning": "Select first MF4 file"
            },
            {
                "tool_name": "Keyboard-Tool",
                "tool_arguments": {"keys": ["ctrl", "a"]},
                "reasoning": "Select all files in folder"
            },
            {
                "tool_name": "Click-Tool",
                "tool_arguments": {"loc": ["last_state:button:Open"]},
                "reasoning": "Load all selected files"
            }
        ],
        "metadata": {
            "created_at": "2025-11-01T00:00:00",
            "session_id": "test_session"
        }
    }

    # Sample catalog with KB items having original_error
    catalog = [
        {
            "knowledge_id": "open_files",
            "description": "Open MDF files",
            "kb_learnings": [
                {
                    "task": "Concatenate all .MF4 files",
                    "step_num": 11,
                    "original_error": "Used wildcard path C:\\folder\\*.MF4 instead of exact folder. Suggestion: Use exact folder path, select one file, press Ctrl+A to select all.",
                    "timestamp": "2025-10-25T23:45:00"
                }
            ]
        },
        {
            "knowledge_id": "save_file",
            "description": "Save files",
            "kb_learnings": []
        }
    ]

    print("[Test] Testing Recovery Approach Generator")
    print("="*80)

    # Create generator
    generator = RecoveryApproachGenerator()

    # Generate recovery approaches
    print("\n[1/2] Generating recovery approaches...")
    recovery_approaches = generator.generate_recovery_approaches(
        verified_skill=verified_skill,
        knowledge_catalog=catalog
    )

    print(f"\n[Result] Generated {len(recovery_approaches)} recovery approaches:")
    for kb_id, approach in recovery_approaches.items():
        print(f"\n  KB ID: {kb_id}")
        print(f"  Recovery Approach: {approach}")

    # Test catalog update (using a temporary file)
    print("\n\n[2/2] Testing catalog update...")
    temp_catalog_path = "test_catalog_temp.json"

    try:
        # Write temp catalog
        with open(temp_catalog_path, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

        # Update catalog
        success = generator.update_knowledge_catalog(
            catalog_path=temp_catalog_path,
            recovery_approaches=recovery_approaches
        )

        if success:
            print("\n[Result] ✓ Catalog updated successfully!")

            # Read and display updated catalog
            with open(temp_catalog_path, 'r', encoding='utf-8') as f:
                updated_catalog = json.load(f)

            print("\n[Updated Catalog]")
            for item in updated_catalog:
                if item.get("kb_learnings"):
                    print(f"\n  KB ID: {item['knowledge_id']}")
                    for learning in item["kb_learnings"]:
                        if learning.get("recovery_approach"):
                            print(f"    Recovery Approach: {learning['recovery_approach']}")
        else:
            print("\n[Result] ✗ Catalog update failed")

    finally:
        # Cleanup
        import os
        if os.path.exists(temp_catalog_path):
            os.remove(temp_catalog_path)
            print("\n[Cleanup] Removed temporary catalog file")

    print("\n" + "="*80)
    print("[Test] Complete!")


if __name__ == "__main__":
    test_recovery_approach_generation()