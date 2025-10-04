"""
RAG-based skill retrieval using ChromaDB and sentence transformers
"""

import json
import os
from typing import List, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import SkillSchema


class SkillRetriever:
    """
    Retrieves relevant skills from catalog using semantic search
    """

    def __init__(
        self,
        skill_catalog_path: str = "agent/skills/json/skill_catalog_gpt5.json",
        vector_db_path: str = "agent/skills/vector_store",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize skill retriever

        Args:
            skill_catalog_path: Path to skill catalog JSON
            vector_db_path: Path to ChromaDB storage
            embedding_model: Sentence transformer model name
        """
        self.skill_catalog_path = skill_catalog_path
        self.vector_db_path = vector_db_path

        # Initialize embedding model
        print(f"Loading embedding model: {embedding_model}...")
        self.embedding_model = SentenceTransformer(embedding_model)

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=vector_db_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="asammdf_skills",
            metadata={"description": "GUI skills extracted from asammdf documentation"}
        )

    def load_skills(self, force_reload: bool = False) -> List[SkillSchema]:
        """
        Load skills from catalog file

        Args:
            force_reload: Force reload even if already indexed

        Returns:
            List of skills
        """
        if not os.path.exists(self.skill_catalog_path):
            raise FileNotFoundError(
                f"Skill catalog not found at {self.skill_catalog_path}. "
                f"Run 'python agent/rag/doc_parser.py' first."
            )

        with open(self.skill_catalog_path, 'r', encoding='utf-8') as f:
            skills_data = json.load(f)

        skills = [SkillSchema(**skill) for skill in skills_data]
        return skills

    def index_skills(self, skills: Optional[List[SkillSchema]] = None):
        """
        Index skills in vector database

        Args:
            skills: Skills to index (loads from file if None)
        """
        if skills is None:
            skills = self.load_skills()

        if len(skills) == 0:
            print("Warning: No skills to index")
            return

        # Check if already indexed
        existing_count = self.collection.count()
        if existing_count > 0:
            print(f"Collection already contains {existing_count} skills. Clearing...")
            self.collection.delete(where={})

        print(f"Indexing {len(skills)} skills...")

        # Prepare data for ChromaDB
        ids = []
        documents = []
        metadatas = []

        for skill in skills:
            # Create searchable text combining description and action sequence
            doc_text = f"{skill.description}. Steps: {', '.join(skill.action_sequence)}"

            ids.append(skill.skill_id)
            documents.append(doc_text)
            metadatas.append({
                "skill_id": skill.skill_id,
                "description": skill.description,
                "ui_location": skill.ui_location,
                "doc_citation": skill.doc_citation,
                # Store full skill as JSON for retrieval
                "full_skill": json.dumps(skill.model_dump())
            })

        # Add to collection (ChromaDB will auto-generate embeddings if we provide documents)
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(f"✓ Indexed {len(skills)} skills in vector database")

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_by: Optional[dict] = None
    ) -> List[SkillSchema]:
        """
        Retrieve relevant skills for a query

        Args:
            query: Natural language task description
            top_k: Number of skills to retrieve
            filter_by: Optional metadata filters

        Returns:
            List of relevant skills
        """
        # Check if collection is empty
        if self.collection.count() == 0:
            print("Vector database is empty. Indexing skills...")
            self.index_skills()

        # Query collection
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            where=filter_by
        )

        # Parse results back to SkillSchema
        skills = []
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            for metadata in results['metadatas'][0]:
                skill_data = json.loads(metadata['full_skill'])
                skills.append(SkillSchema(**skill_data))

        return skills

    def get_skill_by_id(self, skill_id: str) -> Optional[SkillSchema]:
        """
        Retrieve a specific skill by ID

        Args:
            skill_id: Skill identifier

        Returns:
            Skill if found, None otherwise
        """
        try:
            result = self.collection.get(ids=[skill_id])
            if result['metadatas'] and len(result['metadatas']) > 0:
                skill_data = json.loads(result['metadatas'][0]['full_skill'])
                return SkillSchema(**skill_data)
        except Exception:
            pass

        return None

    def list_all_skills(self) -> List[SkillSchema]:
        """
        List all indexed skills

        Returns:
            List of all skills
        """
        if self.collection.count() == 0:
            return []

        result = self.collection.get()
        skills = []

        if result['metadatas']:
            for metadata in result['metadatas']:
                skill_data = json.loads(metadata['full_skill'])
                skills.append(SkillSchema(**skill_data))

        return skills


def test_retrieval():
    """
    Test skill retrieval with sample queries
    """
    retriever = SkillRetriever()

    # Test queries
    test_queries = [
        "concatenate multiple MF4 files",
        "export data to Excel",
        "plot a signal",
        "open an MF4 file"
    ]

    print("\n" + "="*80)
    print("Testing Skill Retrieval")
    print("="*80 + "\n")

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 40)

        skills = retriever.retrieve(query, top_k=3)

        if skills:
            for i, skill in enumerate(skills, 1):
                print(f"{i}. {skill.skill_id}")
                print(f"   Description: {skill.description}")
                print(f"   UI Location: {skill.ui_location}")
        else:
            print("No skills found")


if __name__ == "__main__":
    """
    Test retrieval or rebuild index
    """
    import argparse

    parser = argparse.ArgumentParser(description="Skill retrieval utilities")
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        default=False,  
        help="Rebuild vector database index"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=True,
        help="Run test queries"
    )
    args = parser.parse_args()

    retriever = SkillRetriever()

    # Rebuild --rebuild-index is True
    if args.rebuild_index:
        print("Rebuilding index...")
        retriever.index_skills()

    if args.test or (not args.rebuild_index):
        test_retrieval()
