"""
Automatic skill extraction from asammdf GUI documentation
Uses OpenAI GPT-4 API to parse documentation and extract structured skills
"""

import json
import os
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import SkillSchema

# Load environment variables from .env file
load_dotenv()


class DocumentationParser:
    """
    Automatically extracts GUI skills from asammdf documentation
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize parser with OpenAI API

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable or api_key parameter required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-5"

    def fetch_documentation(self, url: str) -> str:
        """
        Fetch documentation HTML from URL

        Args:
            url: Documentation URL

        Returns:
            Cleaned text content
        """
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text and clean up
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text

    def extract_skills(self, doc_content: str, doc_url: str) -> List[SkillSchema]:
        """
        Use GPT-4 to extract structured skills from documentation

        Args:
            doc_content: Documentation text content
            doc_url: URL of documentation (for citations)

        Returns:
            List of extracted skills
        """
        prompt = f"""
        
You are a GUI automation expert analyzing asammdf application documentation. The documentation describes all the interactive options and workflows of the asammdf GUI.

Your task: Extract ALL GUI capabilities, actions, workflows, and Knowledge from the documentation into a structured JSON Knowledge Base. 
This Knowledge Base will later be used to provide all the information and step-by-step instructions for automating tasks in asammdf GUI. 

Extraction Requirements

Focus on capturing every possible GUI capability, including but not limited to:
1. File operations (open, save, export, convert, extract attachments)
2. Single & Multiple file operations (concatenate, stack, comparison)
3. Plotting & Visualization of channels (create plots, numeric views, tabular views, cursor/range usage, statistics, computed signals)
4. Data manipulation (cut, filter, resample, search, pattern-based selection)
5. Navigation (tabs, menus, dialogs, channel trees, layouts, drag & drop)
6. Shortcuts (general shortcuts, plot shortcuts for zoom, fit, alignment, representation, layout, saving, toggles, shifting signals)
6. Step-by-step tasks (e.g., “Open Folder”, “Create Plot from selected channels”, “Save all channels”, “Insert computed signal”, etc.)

For each capability, identify:
- skill_id: short snake_case identifier (e.g., "concatenate_files", "export_csv", "open_folder")
- description: clear human-readable explanation of what it does
- ui_location: where in GUI it is accessed (e.g., "File menu", "Plot window", "Batch processing tab")
- action_sequence: ordered list of high-level GUI steps (e.g., ["click_menu('File')", "select('Open Folder')", "choose_folder"])
- shortcut: keyboard shortcut if available (e.g., "Ctrl+O", "F2", null if none)
- prerequisites: list of required conditions before action (e.g., ["app_open"], ["file_loaded"])
- output_state: expected result after performing action (e.g., "file_opened", "plot_created", "concatenated_file_loaded")
- doc_citation: relative section citation string (e.g., "GUI#File-operations")
- Return ONLY a JSON array of skills. No explanatory text.

Example format:
[{
{
  "skill_id": "concatenate_files",
  "description": "Concatenate multiple MDF files into a single continuous measurement file. The files must share the same internal structure (identical channel groups and matching channels in each group). Samples are appended in the given order, optionally synchronized by timestamps.",
  "ui_location": "Batch processing tab → Batch operations",
  "action_sequence": [
    "click_menu('Mode')",
    "select_option('Batch processing')",
    "click_menu('File')",
    "select_option('Open')",
    "multi_select_files_in_dialog('Ctrl + A' or 'Select Files with Ctrl')",
    "click_button('Open')",
    "arrange_files_in_list(order='desired sequence')",
    "select_operation('Concatenate')",
    "set_option('Sync using measurement timestamps', true/false)",
    "enter_filename('Concatenated.mf4')",
    "click_button('Save')"
  ],
  "shortcut": None,
  "prerequisites": ["app_open", "multiple_files_available"],
  "output_state": "concatenated_file_created",
  "doc_citation": "GUI#Batch-processing",
}}
]

<documentation>
{doc_content}
</documentation>

Extract ALL skills as JSON array:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=16000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract JSON from response
            content = response.choices[0].message.content

            print(f"DEBUG: Response content length: {len(content) if content else 0}")
            print(f"DEBUG: First 500 chars of response:\n{content[:500] if content else 'None'}\n")

            # Try to find JSON array in response
            if content.strip().startswith('['):
                skills_data = json.loads(content)
            else:
                # Try to extract JSON from markdown code block
                if '```json' in content:
                    json_start = content.find('```json') + 7
                    json_end = content.find('```', json_start)
                    json_str = content[json_start:json_end].strip()
                    skills_data = json.loads(json_str)
                elif '```' in content:
                    json_start = content.find('```') + 3
                    json_end = content.find('```', json_start)
                    json_str = content[json_start:json_end].strip()
                    skills_data = json.loads(json_str)
                else:
                    skills_data = json.loads(content)

            # Validate with Pydantic
            skills = [SkillSchema(**skill) for skill in skills_data]

            return skills

        except Exception as e:
            print(f"Error extracting skills: {e}")
            raise

    def save_skills(self, skills: List[SkillSchema], output_path: str):
        """
        Save extracted skills to JSON file

        Args:
            skills: List of skills
            output_path: Output file path
        """
        skills_dict = [skill.model_dump() for skill in skills]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(skills_dict, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(skills)} skills to {output_path}")


def build_skill_catalog(
    doc_url: str = "https://asammdf.readthedocs.io/en/stable/gui.html",
    output_path: str = "agent/skills/skill_catalog_gpt5.json",
    api_key: Optional[str] = None
) -> List[SkillSchema]:
    """
    Main function to build skill catalog from documentation

    Args:
        doc_url: Documentation URL
        output_path: Where to save skill catalog
        api_key: OpenAI API key

    Returns:
        List of extracted skills
    """
    parser = DocumentationParser(api_key=api_key)

    print(f"Fetching documentation from {doc_url}...")
    doc_content = parser.fetch_documentation(doc_url)

    print(f"Extracting skills using {parser.model}...")
    skills = parser.extract_skills(doc_content, doc_url)

    print(f"Extracted {len(skills)} skills:")
    for skill in skills:
        print(f"  - {skill.skill_id}: {skill.description}")

    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    parser.save_skills(skills, output_path)

    return skills


if __name__ == "__main__":
    """
    Run skill extraction as standalone script
    Usage: python agent/rag/doc_parser.py
    """
    import argparse

    parser = argparse.ArgumentParser(description="Extract skills from asammdf documentation")
    parser.add_argument(
        "--doc-url",
        default="https://asammdf.readthedocs.io/en/stable/gui.html",
        help="Documentation URL"
    )
    parser.add_argument(
        "--output",
        default="agent/skills/skill_catalog.json",
        help="Output file path"
    )

    args = parser.parse_args()

    try:
        skills = build_skill_catalog(
            doc_url=args.doc_url,
            output_path=args.output
        )
        print(f"\n✓ Successfully built skill catalog with {len(skills)} skills")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
