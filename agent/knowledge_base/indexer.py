"""
Knowledge Base Indexer

Indexes parsed knowledge patterns into ChromaDB vector store for semantic search.
"""

import json
import os
from typing import List, Optional
import chromadb
from chromadb.config import Settings

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import KnowledgeSchema


class KnowledgeIndexer:
    """
    Indexes knowledge patterns into ChromaDB vector store
    """

    def __init__(
        self,
        vector_db_path: str = "agent/knowledge_base/vector_store",
        collection_name: str = "asammdf_knowledge"
    ):
        """
        Initialize indexer

        Args:
            vector_db_path: Path to ChromaDB vector store
            collection_name: Name of the collection
        """
        self.vector_db_path = vector_db_path
        self.collection_name = collection_name

        # Create vector DB directory if it doesn't exist
        os.makedirs(vector_db_path, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=vector_db_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "GUI knowledge patterns from asammdf documentation"}
        )

    def load_knowledge_catalog(self, catalog_path: str) -> List[KnowledgeSchema]:
        """
        Load knowledge catalog from JSON file

        Args:
            catalog_path: Path to knowledge catalog JSON file

        Returns:
            List of knowledge patterns
        """
        if not os.path.exists(catalog_path):
            raise FileNotFoundError(f"Knowledge catalog not found: {catalog_path}")

        with open(catalog_path, 'r', encoding='utf-8') as f:
            knowledge_data = json.load(f)

        knowledge_patterns = [KnowledgeSchema(**item) for item in knowledge_data]
        print(f"[Loaded] {len(knowledge_patterns)} knowledge patterns from {catalog_path}")

        return knowledge_patterns

    def index_knowledge(
        self,
        knowledge_patterns: Optional[List[KnowledgeSchema]] = None,
        catalog_path: Optional[str] = None,
        rebuild: bool = False
    ):
        """
        Index knowledge patterns into vector store

        Args:
            knowledge_patterns: List of knowledge patterns to index
            catalog_path: Path to knowledge catalog (if knowledge_patterns not provided)
            rebuild: If True, clear existing index before indexing
        """
        # Load from catalog if patterns not provided
        if knowledge_patterns is None:
            if catalog_path is None:
                catalog_path = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"
            knowledge_patterns = self.load_knowledge_catalog(catalog_path)

        if not knowledge_patterns:
            print("[Warning] No knowledge patterns to index")
            return

        # Rebuild if requested
        if rebuild:
            existing_count = self.collection.count()
            if existing_count > 0:
                print(f"[Rebuild] Clearing {existing_count} existing entries...")
                all_docs = self.collection.get()
                if all_docs['ids']:
                    self.collection.delete(ids=all_docs['ids'])

        # Prepare data for indexing
        ids = []
        documents = []
        metadatas = []

        for knowledge in knowledge_patterns:
            # Create rich document text for embedding
            doc_text = f"{knowledge.description}. Steps: {', '.join(knowledge.action_sequence)}"

            ids.append(knowledge.knowledge_id)
            documents.append(doc_text)

            # Store full KnowledgeSchema as JSON for consistency
            # This ensures retriever can reconstruct exact KnowledgeSchema objects
            knowledge_dict = knowledge.model_dump()
            metadatas.append({
                "full_knowledge": json.dumps(knowledge_dict),
                # Also store key fields for quick filtering (duplicated for convenience)
                "knowledge_id": knowledge.knowledge_id,
                "has_learnings": len(knowledge_dict.get('kb_learnings', [])) > 0,
                "learning_count": len(knowledge_dict.get('kb_learnings', [])),
                "trust_score": knowledge_dict.get('trust_score', 1.0)
            })

        # Index into ChromaDB
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(f"[Indexed] {len(knowledge_patterns)} knowledge patterns into {self.collection_name}")
        print(f"[Vector Store] Total entries: {self.collection.count()}")

    def get_index_stats(self) -> dict:
        """
        Get statistics about the index

        Returns:
            Dictionary with index statistics
        """
        count = self.collection.count()

        stats = {
            "collection_name": self.collection_name,
            "vector_db_path": self.vector_db_path,
            "total_entries": count,
            "metadata": self.collection.metadata
        }

        return stats

    def clear_index(self):
        """
        Clear all entries from the index
        """
        all_docs = self.collection.get()
        if all_docs['ids']:
            self.collection.delete(ids=all_docs['ids'])
            print(f"[Cleared] All entries from {self.collection_name}")
        else:
            print(f"[Info] Index already empty")


def rebuild_index(
    catalog_path: str = "agent/knowledge_base/parsed_knowledge/knowledge_catalog.json",
    vector_db_path: str = "agent/knowledge_base/vector_store"
):
    """
    Rebuild the knowledge base index from scratch

    Args:
        catalog_path: Path to knowledge catalog
        vector_db_path: Path to vector store
    """
    print("\n" + "="*80)
    print("Rebuilding Knowledge Base Index")
    print("="*80 + "\n")

    indexer = KnowledgeIndexer(vector_db_path=vector_db_path)

    # Load and index
    indexer.index_knowledge(catalog_path=catalog_path, rebuild=True)

    # Show stats
    stats = indexer.get_index_stats()
    print(f"\n[Stats] Index Statistics:")
    print(f"  Collection: {stats['collection_name']}")
    print(f"  Vector DB: {stats['vector_db_path']}")
    print(f"  Total Entries: {stats['total_entries']}")

    print("\n" + "="*80)
    print("[SUCCESS] Index rebuild complete")
    print("="*80 + "\n")


if __name__ == "__main__":
    """
    Run indexer as standalone script

    Usage: python agent/knowledge_base/indexer.py [--rebuild]
    """
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge base indexing utilities")
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
        "--rebuild",
        action="store_true",
        help="Rebuild index from scratch"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show index statistics"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the index"
    )

    args = parser.parse_args()

    indexer = KnowledgeIndexer(vector_db_path=args.vector_db)

    if args.clear:
        indexer.clear_index()
    elif args.rebuild:
        rebuild_index(catalog_path=args.catalog, vector_db_path=args.vector_db)
    elif args.stats:
        stats = indexer.get_index_stats()
        print(f"\nIndex Statistics:")
        print(f"  Collection: {stats['collection_name']}")
        print(f"  Vector DB: {stats['vector_db_path']}")
        print(f"  Total Entries: {stats['total_entries']}")
    else:
        # Default: just index (no rebuild)
        indexer.index_knowledge(catalog_path=args.catalog, rebuild=False)
