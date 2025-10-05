"""
RAG-based knowledge retrieval using ChromaDB and sentence transformers
Retrieves documentation-extracted knowledge patterns (not verified skills)
"""

import json
import os
from typing import List, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import KnowledgeSchema


class KnowledgeRetriever:
    """
    Retrieves relevant knowledge patterns from documentation catalog using semantic search
    Note: This retrieves documentation-extracted patterns, not verified skills
    """

    def __init__(
        self,
        knowledge_catalog_path: str = "agent/knowledge_base/json/knowledge_catalog_gpt5_mini.json",
        vector_db_path: str = "agent/knowledge_base/vector_store_gpt5_mini",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize knowledge retriever

        Args:
            knowledge_catalog_path: Path to knowledge catalog JSON
            vector_db_path: Path to ChromaDB storage
            embedding_model: Sentence transformer model name
        """
        self.knowledge_catalog_path = knowledge_catalog_path
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
            name="asammdf_knowledge",
            metadata={"description": "GUI knowledge patterns extracted from asammdf documentation"}
        )

    def load_knowledge(self, force_reload: bool = False) -> List[KnowledgeSchema]:
        """
        Load knowledge patterns from catalog file

        Args:
            force_reload: Force reload even if already indexed

        Returns:
            List of knowledge patterns
        """
        if not os.path.exists(self.knowledge_catalog_path):
            raise FileNotFoundError(
                f"Knowledge catalog not found at {self.knowledge_catalog_path}. "
                f"Run 'python agent/rag/doc_parser.py' first."
            )

        with open(self.knowledge_catalog_path, 'r', encoding='utf-8') as f:
            knowledge_data = json.load(f)

        knowledge_patterns = [KnowledgeSchema(**item) for item in knowledge_data]
        return knowledge_patterns

    def index_knowledge(self, knowledge_patterns: Optional[List[KnowledgeSchema]] = None):
        """
        Index knowledge patterns in vector database

        Args:
            knowledge_patterns: Knowledge patterns to index (loads from file if None)
        """
        if knowledge_patterns is None:
            knowledge_patterns = self.load_knowledge()

        if len(knowledge_patterns) == 0:
            print("Warning: No knowledge patterns to index")
            return

        # Check if already indexed
        existing_count = self.collection.count()
        if existing_count > 0:
            print(f"Collection already contains {existing_count} knowledge patterns. Clearing...")
            # Delete all documents by getting all IDs first
            all_docs = self.collection.get()
            if all_docs['ids']:
                self.collection.delete(ids=all_docs['ids'])

        print(f"Indexing {len(knowledge_patterns)} knowledge patterns...")

        # Prepare data for ChromaDB
        ids = []
        documents = []
        metadatas = []

        for knowledge in knowledge_patterns:
            # Create searchable text combining description and action sequence
            doc_text = f"{knowledge.description}. Steps: {', '.join(knowledge.action_sequence)}"

            ids.append(knowledge.knowledge_id)
            documents.append(doc_text)
            metadatas.append({
                "knowledge_id": knowledge.knowledge_id,
                "description": knowledge.description,
                "ui_location": knowledge.ui_location,
                "doc_citation": knowledge.doc_citation,
                # Store full knowledge as JSON for retrieval
                "full_knowledge": json.dumps(knowledge.model_dump())
            })

        # Add to collection (ChromaDB will auto-generate embeddings if we provide documents)
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(f"✓ Indexed {len(knowledge_patterns)} knowledge patterns in vector database")

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_by: Optional[dict] = None
    ) -> List[KnowledgeSchema]:
        """
        Retrieve relevant knowledge patterns for a query

        Args:
            query: Natural language task description
            top_k: Number of knowledge patterns to retrieve
            filter_by: Optional metadata filters

        Returns:
            List of relevant knowledge patterns
        """
        # Check if collection is empty
        if self.collection.count() == 0:
            print("Vector database is empty. Indexing knowledge patterns...")
            self.index_knowledge()

        # Query collection
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            where=filter_by
        )

        # Parse results back to KnowledgeSchema
        knowledge_patterns = []
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            for metadata in results['metadatas'][0]:
                knowledge_data = json.loads(metadata['full_knowledge'])
                knowledge_patterns.append(KnowledgeSchema(**knowledge_data))

        return knowledge_patterns

    def get_knowledge_by_id(self, knowledge_id: str) -> Optional[KnowledgeSchema]:
        """
        Retrieve a specific knowledge pattern by ID

        Args:
            knowledge_id: Knowledge identifier

        Returns:
            Knowledge pattern if found, None otherwise
        """
        try:
            result = self.collection.get(ids=[knowledge_id])
            if result['metadatas'] and len(result['metadatas']) > 0:
                knowledge_data = json.loads(result['metadatas'][0]['full_knowledge'])
                return KnowledgeSchema(**knowledge_data)
        except Exception:
            pass

        return None

    def list_all_knowledge(self) -> List[KnowledgeSchema]:
        """
        List all indexed knowledge patterns

        Returns:
            List of all knowledge patterns
        """
        if self.collection.count() == 0:
            return []

        result = self.collection.get()
        knowledge_patterns = []

        if result['metadatas']:
            for metadata in result['metadatas']:
                knowledge_data = json.loads(metadata['full_knowledge'])
                knowledge_patterns.append(KnowledgeSchema(**knowledge_data))

        return knowledge_patterns


def test_retrieval():
    """
    Test knowledge retrieval with sample queries
    """
    retriever = KnowledgeRetriever()

    # Test queries
    test_queries = [
        "concatenate multiple MF4 files",
        "export data to Excel",
        "plot a signal",
        "open an MF4 file"
    ]

    print("\n" + "="*80)
    print("Testing Knowledge Retrieval")
    print("="*80 + "\n")

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 40)

        knowledge_patterns = retriever.retrieve(query, top_k=3)

        if knowledge_patterns:
            for i, knowledge in enumerate(knowledge_patterns, 1):
                print(f"{i}. {knowledge.knowledge_id}")
                print(f"   Description: {knowledge.description}")
                print(f"   UI Location: {knowledge.ui_location}")
        else:
            print("No knowledge patterns found")


if __name__ == "__main__":
    """
    Test retrieval or rebuild index
    """
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge retrieval utilities")
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        default=True,
        help="Rebuild vector database index"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=True,
        help="Run test queries"
    )
    args = parser.parse_args()

    retriever = KnowledgeRetriever()

    # Rebuild --rebuild-index is True
    if args.rebuild_index:
        print("Rebuilding index...")
        retriever.index_knowledge()

    if args.test or (not args.rebuild_index):
        test_retrieval()
