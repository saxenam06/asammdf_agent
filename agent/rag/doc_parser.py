"""
Automatic knowledge extraction from asammdf GUI documentation
Uses OpenAI GPT-5-MINI API to parse documentation and extract structured knowledge patterns
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

from agent.planning.schemas import KnowledgeSchema
from agent.prompts.doc_parsing_prompt import get_doc_parsing_prompt
from agent.utils.cost_tracker import track_api_call

load_dotenv()


class DocumentationParser:
    """
    Automatically extracts GUI knowledge patterns from asammdf documentation
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

        self.client = OpenAI(api_key=self.api_key, timeout=3000.0)
        self.model = "gpt-5-mini"

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

    def extract_knowledge(self, doc_content: str, doc_url: str) -> List[KnowledgeSchema]:
        """
        Use GPT to extract structured knowledge patterns from documentation

        Args:
            doc_content: Documentation text content
            doc_url: URL of documentation (for citations)

        Returns:
            List of extracted knowledge patterns
        """
        prompt = get_doc_parsing_prompt(doc_content)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=120000,
                timeout=600.0,
            )

            # Track API cost
            usage = response.usage
            cost = track_api_call(
                model=self.model,
                component="doc_parsing",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                task_context=doc_url
            )
            print(f"💰 Doc parsing cost: ${cost:.4f} ({usage.prompt_tokens:,} in + {usage.completion_tokens:,} out tokens)")

            # Extract JSON from response
            content = response.choices[0].message.content

            print(f"DEBUG: Response content length: {len(content) if content else 0}")
            print(f"DEBUG: First 500 chars of response:\n{content[:500] if content else 'None'}\n")

            # Try to find JSON array in response
            if content.strip().startswith('['):
                knowledge_data = json.loads(content)
            else:
                # Try to extract JSON from markdown code block
                if '```json' in content:
                    json_start = content.find('```json') + 7
                    json_end = content.find('```', json_start)
                    json_str = content[json_start:json_end].strip()
                    knowledge_data = json.loads(json_str)
                elif '```' in content:
                    json_start = content.find('```') + 3
                    json_end = content.find('```', json_start)
                    json_str = content[json_start:json_end].strip()
                    knowledge_data = json.loads(json_str)
                else:
                    knowledge_data = json.loads(content)

            # Validate with Pydantic
            knowledge_patterns = [KnowledgeSchema(**item) for item in knowledge_data]

            return knowledge_patterns

        except Exception as e:
            print(f"Error extracting knowledge patterns: {e}")
            raise

    def save_knowledge(self, knowledge_patterns: List[KnowledgeSchema], output_path: str):
        """
        Save extracted knowledge patterns to JSON file

        Args:
            knowledge_patterns: List of knowledge patterns
            output_path: Output file path
        """
        knowledge_dict = [knowledge.model_dump() for knowledge in knowledge_patterns]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_dict, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(knowledge_patterns)} knowledge patterns to {output_path}")


def build_knowledge_catalog(
    doc_url: str = "https://asammdf.readthedocs.io/en/stable/gui.html",
    output_path: str = "agent/knowledge_base/json/knowledge_catalog_gpt5.json",
    api_key: Optional[str] = None
) -> List[KnowledgeSchema]:
    """
    Main function to build knowledge catalog from documentation

    Args:
        doc_url: Documentation URL
        output_path: Where to save knowledge catalog
        api_key: OpenAI API key

    Returns:
        List of extracted knowledge patterns
    """
    parser = DocumentationParser(api_key=api_key)

    print(f"Fetching documentation from {doc_url}...")
    doc_content = parser.fetch_documentation(doc_url)

    print(f"Extracting knowledge patterns using {parser.model}...")
    knowledge_patterns = parser.extract_knowledge(doc_content, doc_url)

    print(f"Extracted {len(knowledge_patterns)} knowledge patterns:")
    for knowledge in knowledge_patterns:
        print(f"  - {knowledge.knowledge_id}: {knowledge.description}")

    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    parser.save_knowledge(knowledge_patterns, output_path)

    return knowledge_patterns


if __name__ == "__main__":
    """
    Run knowledge extraction as standalone script
    Usage: python agent/rag/doc_parser.py
    """
    import argparse

    parser = argparse.ArgumentParser(description="Extract knowledge patterns from asammdf documentation")
    parser.add_argument(
        "--doc-url",
        default="https://asammdf.readthedocs.io/en/stable/gui.html",
        help="Documentation URL"
    )
    parser.add_argument(
        "--output",
        default="agent/knowledge_base/json/knowledge_catalog_gpt5_mini.json",
        help="Output file path"
    )

    args = parser.parse_args()

    try:
        knowledge_patterns = build_knowledge_catalog(
            doc_url=args.doc_url,
            output_path=args.output
        )
        print(f"\n✓ Successfully built knowledge catalog with {len(knowledge_patterns)} patterns")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
