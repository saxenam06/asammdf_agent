"""
Verified Skill Library

Stores and retrieves human-verified workflows that succeeded.
When a similar task arrives, use the verified skill instead of planning from scratch.

Features:
- Fuzzy task matching
- Success rate tracking
- Metadata storage (human feedbacks, agent recoveries used)
- JSON persistence
"""

import json
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from difflib import SequenceMatcher
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, PlanSchema
from agent.feedback.schemas import VerifiedSkillMetadata


class VerifiedSkill:
    """A single verified skill (proven workflow)"""

    def __init__(
        self,
        skill_id: str,
        task_description: str,
        action_plan: List[ActionSchema],
        metadata: VerifiedSkillMetadata,
        tags: Optional[List[str]] = None
    ):
        """
        Initialize verified skill

        Args:
            skill_id: Unique skill identifier
            task_description: Task this skill solves
            action_plan: Proven sequence of actions
            metadata: Verification metadata
            tags: Optional tags for categorization
        """
        self.skill_id = skill_id
        self.task_description = task_description
        self.action_plan = action_plan
        self.metadata = metadata
        self.tags = tags or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "skill_id": self.skill_id,
            "task_description": self.task_description,
            "action_plan": [action.model_dump() for action in self.action_plan],
            "metadata": self.metadata.model_dump(),
            "tags": self.tags,
            "created_at": self.metadata.verified_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VerifiedSkill':
        """Load from dictionary"""
        return cls(
            skill_id=data["skill_id"],
            task_description=data["task_description"],
            action_plan=[ActionSchema(**action) for action in data["action_plan"]],
            metadata=VerifiedSkillMetadata(**data["metadata"]),
            tags=data.get("tags", [])
        )

    def similarity_score(self, task: str) -> float:
        """
        Calculate similarity between this skill's task and another task

        Args:
            task: Task description to compare

        Returns:
            Similarity score (0.0-1.0)
        """
        return SequenceMatcher(None, self.task_description.lower(), task.lower()).ratio()

    def update_usage_stats(self, success: bool):
        """
        Update usage statistics

        Args:
            success: Whether skill execution succeeded
        """
        self.metadata.times_used += 1
        if success:
            self.metadata.success_count += 1

        # Recalculate success rate
        self.metadata.success_rate = self.metadata.success_count / self.metadata.times_used


class SkillLibrary:
    """
    Library of verified skills

    Stores human-verified workflows and matches them to new tasks
    """

    def __init__(self, library_path: str = "agent/learning/verified_skills/skills.json"):
        """
        Initialize skill library

        Args:
            library_path: Path to skills JSON file
        """
        self.library_path = library_path
        self.skills: List[VerifiedSkill] = []

        # Ensure directory exists
        os.makedirs(os.path.dirname(library_path), exist_ok=True)

        # Load existing skills
        self.load()

        print(f"[SkillLibrary] Initialized with {len(self.skills)} verified skills")

    def add_skill(
        self,
        task_description: str,
        action_plan: List[ActionSchema],
        session_id: str,
        human_feedbacks_count: int = 0,
        agent_recoveries_count: int = 0,
        tags: Optional[List[str]] = None
    ) -> VerifiedSkill:
        """
        Add a new verified skill

        Args:
            task_description: Task description
            action_plan: Proven action sequence
            session_id: Session where skill was verified
            human_feedbacks_count: Number of human corrections used
            agent_recoveries_count: Number of self-recoveries used
            tags: Optional categorization tags

        Returns:
            Created VerifiedSkill
        """
        # Generate skill ID
        skill_id = f"skill_{len(self.skills) + 1:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create metadata
        metadata = VerifiedSkillMetadata(
            session_id=session_id,
            human_feedbacks_count=human_feedbacks_count,
            agent_recoveries_count=agent_recoveries_count
        )

        # Create skill
        skill = VerifiedSkill(
            skill_id=skill_id,
            task_description=task_description,
            action_plan=action_plan,
            metadata=metadata,
            tags=tags
        )

        # Add to library
        self.skills.append(skill)

        # Save
        self.save()

        print(f"[SkillLibrary] Added verified skill: {skill_id}")
        print(f"  Task: {task_description}")
        print(f"  Actions: {len(action_plan)} steps")
        print(f"  Human feedbacks: {human_feedbacks_count}, Agent recoveries: {agent_recoveries_count}")

        return skill

    def find_matching_skill(
        self,
        task: str,
        similarity_threshold: float = 0.75,
        min_success_rate: float = 0.8
    ) -> Optional[VerifiedSkill]:
        """
        Find best matching verified skill for a task

        Args:
            task: Task description
            similarity_threshold: Minimum similarity score (0.0-1.0)
            min_success_rate: Minimum skill success rate

        Returns:
            Best matching skill or None
        """
        if not self.skills:
            return None

        # Find skills above threshold
        candidates = []
        for skill in self.skills:
            similarity = skill.similarity_score(task)
            if similarity >= similarity_threshold and skill.metadata.success_rate >= min_success_rate:
                candidates.append((skill, similarity))

        if not candidates:
            return None

        # Return best match
        best_skill, best_score = max(candidates, key=lambda x: x[1])

        print(f"[SkillLibrary] Found matching skill: {best_skill.skill_id}")
        print(f"  Similarity: {best_score:.2f}")
        print(f"  Success rate: {best_skill.metadata.success_rate:.2f}")
        print(f"  Times used: {best_skill.metadata.times_used}")

        return best_skill

    def get_skill(self, skill_id: str) -> Optional[VerifiedSkill]:
        """
        Get skill by ID

        Args:
            skill_id: Skill identifier

        Returns:
            Skill or None
        """
        for skill in self.skills:
            if skill.skill_id == skill_id:
                return skill
        return None

    def update_skill_stats(self, skill_id: str, success: bool):
        """
        Update skill usage statistics

        Args:
            skill_id: Skill identifier
            success: Whether execution succeeded
        """
        skill = self.get_skill(skill_id)
        if skill:
            skill.update_usage_stats(success)
            self.save()
            print(f"[SkillLibrary] Updated stats for {skill_id}: {skill.metadata.success_count}/{skill.metadata.times_used} successes")

    def save(self):
        """Save skill library to JSON"""
        # Ensure directory exists before saving
        os.makedirs(os.path.dirname(self.library_path), exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "total_skills": len(self.skills),
            "skills": [skill.to_dict() for skill in self.skills]
        }

        with open(self.library_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"[SkillLibrary] Saved {len(self.skills)} skills to {self.library_path}")

    def load(self):
        """Load skill library from JSON"""
        if not os.path.exists(self.library_path):
            print(f"[SkillLibrary] No existing library found, starting fresh")
            return

        try:
            with open(self.library_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.skills = [VerifiedSkill.from_dict(skill_data) for skill_data in data.get("skills", [])]
            print(f"[SkillLibrary] Loaded {len(self.skills)} verified skills")

        except Exception as e:
            print(f"[SkillLibrary] Error loading library: {e}")
            self.skills = []

    def list_all_skills(self) -> List[Dict[str, Any]]:
        """
        Get summary of all skills

        Returns:
            List of skill summaries
        """
        return [
            {
                "skill_id": skill.skill_id,
                "task": skill.task_description,
                "actions": len(skill.action_plan),
                "success_rate": skill.metadata.success_rate,
                "times_used": skill.metadata.times_used,
                "tags": skill.tags
            }
            for skill in self.skills
        ]


if __name__ == "__main__":
    """Test skill library"""

    print("Testing Skill Library\n")

    # Initialize
    library = SkillLibrary(library_path="agent/learning/verified_skills/test_skills.json")

    # Test 1: Add a verified skill
    print("Test 1: Add verified skill\n")
    test_actions = [
        ActionSchema(tool_name="State-Tool", tool_arguments={"use_vision": False}, reasoning="Get UI state"),
        ActionSchema(tool_name="Switch-Tool", tool_arguments={"name": "asammdf"}, reasoning="Activate window"),
        ActionSchema(tool_name="Shortcut-Tool", tool_arguments={"shortcut": ["ctrl", "o"]}, reasoning="Open file dialog"),
    ]

    skill = library.add_skill(
        task_description="Concatenate MF4 files in folder C:\\data",
        action_plan=test_actions,
        session_id="test_session_001",
        human_feedbacks_count=2,
        agent_recoveries_count=1,
        tags=["mf4", "concatenate", "file_operations"]
    )

    # Test 2: Find matching skill (exact match)
    print("\nTest 2: Find exact match\n")
    match = library.find_matching_skill("Concatenate MF4 files in folder C:\\data")
    if match:
        print(f"  Found: {match.skill_id}")
    else:
        print("  No match found")

    # Test 3: Find matching skill (similar task)
    print("\nTest 3: Find similar match\n")
    match = library.find_matching_skill("Concatenate MF4 files in folder C:\\logs", similarity_threshold=0.7)
    if match:
        print(f"  Found: {match.skill_id}")
        print(f"  Original task: {match.task_description}")
    else:
        print("  No match found")

    # Test 4: Update skill stats
    print("\nTest 4: Update skill stats\n")
    library.update_skill_stats(skill.skill_id, success=True)
    library.update_skill_stats(skill.skill_id, success=True)
    library.update_skill_stats(skill.skill_id, success=False)

    # Test 5: List all skills
    print("\nTest 5: List all skills\n")
    all_skills = library.list_all_skills()
    for s in all_skills:
        print(f"  {s['skill_id']}: {s['task']} ({s['success_rate']:.0%} success, {s['times_used']} uses)")

    # Test 6: Save and reload
    print("\nTest 6: Save and reload\n")
    library.save()
    library2 = SkillLibrary(library_path="agent/learning/verified_skills/test_skills.json")
    print(f"  Reloaded: {len(library2.skills)} skills")

    print("\n[SUCCESS] Skill library tests completed!")
