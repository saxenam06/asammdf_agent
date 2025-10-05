# Verified Skills

This directory contains **verified skills** - human-approved, proven workflows that have been tested and confirmed to work.

## Distinction Between Knowledge Base and Verified Skills

### Knowledge Base (`agent/knowledge_base/`)
- **Source**: Automatically extracted from documentation
- **Purpose**: Provides general information and patterns about GUI capabilities
- **Verification**: None - directly parsed from docs
- **Usage**: Reference material for planning workflows
- **Format**: `KnowledgeSchema` objects

### Verified Skills (`agent/verified_skills/`)
- **Source**: Human-verified workflows that have been tested
- **Purpose**: Proven, reusable workflows for specific tasks
- **Verification**: Human-tested and approved
- **Usage**: Direct execution of known-working workflows
- **Format**: `VerifiedSkillSchema` objects with action plans

## Structure

```
agent/verified_skills/
├── json/                    # JSON files containing verified skills
│   └── verified_skills.json # Catalog of all verified skills
└── README.md               # This file
```

## Verified Skill Schema

Each verified skill contains:

```json
{
  "skill_id": "unique_identifier",
  "task_description": "What this skill accomplishes",
  "action_plan": [
    {
      "skill_id": "reference_id",
      "tool_name": "MCP-Tool-Name",
      "tool_arguments": {...},
      "doc_citation": "documentation reference",
      "expected_state": "expected GUI state"
    }
  ],
  "knowledge_references": ["knowledge_id_1", "knowledge_id_2"],
  "verification_metadata": {
    "verified_by": "operator_name",
    "verified_date": "2025-01-15",
    "test_cases": ["Test case 1", "Test case 2"]
  },
  "success_rate": 1.0
}
```

## Creating Verified Skills

To create a new verified skill:

1. Execute a workflow using knowledge patterns
2. Verify it completes successfully
3. Record the exact action sequence
4. Add metadata about verification
5. Save to `json/verified_skills.json`

## Retrieval and Usage

Verified skills can be:
- Retrieved by task similarity
- Executed directly without planning
- Used as templates for similar tasks
- Combined to create complex workflows

Skills should be preferred over knowledge patterns when available.
