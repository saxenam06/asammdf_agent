"""
Knowledge Base Retriever

Semantic search and retrieval of knowledge patterns using ChromaDB vector store.
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
    Retrieves knowledge patterns using semantic search (ChromaDB + sentence-transformers)
    """

    def __init__(
        self,
        catalog_path: str = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json",
        vector_db_path: str = "agent/knowledge_base/vector_store",
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: str = "asammdf_knowledge"
    ):
        """
        Initialize retriever

        Args:
            catalog_path: Path to knowledge catalog JSON file
            vector_db_path: Path to ChromaDB vector store
            embedding_model: Sentence transformer model for embeddings
            collection_name: Name of the ChromaDB collection
        """
        self.catalog_path = catalog_path
        self.vector_db_path = vector_db_path
        self.collection_name = collection_name

        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=vector_db_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # Get collection (create if doesn't exist)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "GUI knowledge patterns from asammdf documentation"}
        )

        # Auto-index if collection is empty
        if self.collection.count() == 0:
            print(f"[Warning] Vector store is empty, indexing from {catalog_path}...")
            self._auto_index()

    def _auto_index(self):
        """
        Auto-index knowledge catalog if vector store is empty
        """
        try:
            from agent.knowledge_base.indexer import KnowledgeIndexer

            indexer = KnowledgeIndexer(
                vector_db_path=self.vector_db_path,
                collection_name=self.collection_name
            )
            indexer.index_knowledge(catalog_path=self.catalog_path, rebuild=False)

        except Exception as e:
            print(f"[Error] Failed to auto-index: {e}")

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_by: Optional[dict] = None
    ) -> List[KnowledgeSchema]:
        """
        Retrieve relevant knowledge patterns using semantic search

        Args:
            query: Search query (natural language)
            top_k: Number of results to return
            filter_by: Optional metadata filters

        Returns:
            List of relevant knowledge patterns
        """
        if self.collection.count() == 0:
            print("[Warning] Vector store is empty")
            return []

        # Perform semantic search
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            where=filter_by
        )

        # Parse results into KnowledgeSchema objects
        knowledge_patterns = []
        if results['metadatas'] and results['metadatas'][0]:
            for metadata in results['metadatas'][0]:
                knowledge_data = json.loads(metadata['full_knowledge'])
                knowledge_patterns.append(KnowledgeSchema(**knowledge_data))

        return knowledge_patterns

    def get_by_id(self, knowledge_id: str) -> Optional[KnowledgeSchema]:
        """
        Retrieve a specific knowledge pattern by ID

        Args:
            knowledge_id: Knowledge pattern identifier

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

    def list_all(self) -> List[KnowledgeSchema]:
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

    def get_stats(self) -> dict:
        """
        Get retriever statistics

        Returns:
            Dictionary with statistics
        """
        return {
            "collection_name": self.collection_name,
            "vector_db_path": self.vector_db_path,
            "catalog_path": self.catalog_path,
            "total_entries": self.collection.count(),
            "embedding_model": self.embedding_model.get_sentence_embedding_dimension()
        }


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
        "open an MF4 file",
        "filter channel data"
    ]

    print("\n" + "="*80)
    print("Testing Knowledge Retrieval")
    print("="*80 + "\n")

    # Show stats
    stats = retriever.get_stats()
    print(f"[Stats] Total indexed patterns: {stats['total_entries']}\n")

    for query in test_queries:
        print(f"\n[Query] '{query}'")
        print("-" * 60)

        knowledge_patterns = retriever.retrieve(query, top_k=3)

        if knowledge_patterns:
            for i, knowledge in enumerate(knowledge_patterns, 1):
                print(f"\n{i}. {knowledge.knowledge_id}")
                print(f"   Description: {knowledge.description}")
                print(f"   UI Location: {knowledge.ui_location}")
                print(f"   Steps: {len(knowledge.action_sequence)}")
        else:
            print("   No knowledge patterns found")

    print("\n" + "="*80)


if __name__ == "__main__":
    """
    Test retrieval or get stats

    Usage: python agent/knowledge_base/retriever.py [--test] [--stats]
    """
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge retrieval utilities")
    parser.add_argument(
        "--catalog",
        default="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json",
        help="Path to knowledge catalog JSON file"
    )
    parser.add_argument(
        "--vector-db",
        default="agent/knowledge_base/vector_store",
        help="Path to vector database"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run test queries"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show retriever statistics"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Custom query to search"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return"
    )

    args = parser.parse_args()

    retriever = KnowledgeRetriever(
        catalog_path=args.catalog,
        vector_db_path=args.vector_db
    )

    if args.stats:
        stats = retriever.get_stats()
        print(f"\nRetriever Statistics:")
        print(f"  Collection: {stats['collection_name']}")
        print(f"  Vector DB: {stats['vector_db_path']}")
        print(f"  Catalog: {stats['catalog_path']}")
        print(f"  Total Entries: {stats['total_entries']}")
        print(f"  Embedding Dimensions: {stats['embedding_model']}")

    elif args.query:
        print(f"\n[Query] '{args.query}'")
        print("-" * 60)

        results = retriever.retrieve(args.query, top_k=args.top_k)

        if results:
            for i, knowledge in enumerate(results, 1):
                print(f"\n{i}. {knowledge.knowledge_id}")
                print(f"   Description: {knowledge.description}")
                print(f"   UI Location: {knowledge.ui_location}")
        else:
            print("No results found")

    elif args.test:
        test_retrieval()

    else:
        # Default: show stats
        stats = retriever.get_stats()
        print(f"\nKnowledge Retriever Ready")
        print(f"  Indexed Patterns: {stats['total_entries']}")
        print(f"\nUsage: --test, --stats, or --query \"your query\"")
