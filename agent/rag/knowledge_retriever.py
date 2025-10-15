"""RAG-based knowledge retrieval using ChromaDB"""
import json, os
from typing import List, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from agent.planning.schemas import KnowledgeSchema


class KnowledgeRetriever:
    """Retrieves knowledge patterns using semantic search (ChromaDB + sentence-transformers)"""

    def __init__(
        self,
        knowledge_catalog_path: str = "agent/knowledge_base/json/knowledge_catalog_gpt5_mini.json",
        vector_db_path: str = "agent/knowledge_base/vector_store_gpt5_mini",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        self.knowledge_catalog_path = knowledge_catalog_path
        self.vector_db_path = vector_db_path
        self.embedding_model = SentenceTransformer(embedding_model)
        self.client = chromadb.PersistentClient(path=vector_db_path, settings=Settings(anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection(
            name="asammdf_knowledge",
            metadata={"description": "GUI knowledge patterns from docs"}
        )

    def load_knowledge(self) -> List[KnowledgeSchema]:
        if not os.path.exists(self.knowledge_catalog_path):
            raise FileNotFoundError(f"Catalog not found: {self.knowledge_catalog_path}")

        with open(self.knowledge_catalog_path, 'r', encoding='utf-8') as f:
            return [KnowledgeSchema(**item) for item in json.load(f)]

    def index_knowledge(self, knowledge_patterns: Optional[List[KnowledgeSchema]] = None):
        if knowledge_patterns is None:
            knowledge_patterns = self.load_knowledge()

        if not knowledge_patterns:
            print("No patterns to index")
            return

        existing_count = self.collection.count()
        if existing_count > 0:
            all_docs = self.collection.get()
            if all_docs['ids']:
                self.collection.delete(ids=all_docs['ids'])

        ids, documents, metadatas = [], [], []
        for k in knowledge_patterns:
            doc_text = f"{k.description}. Steps: {', '.join(k.action_sequence)}"
            ids.append(k.knowledge_id)
            documents.append(doc_text)
            metadatas.append({
                "knowledge_id": k.knowledge_id,
                "description": k.description,
                "ui_location": k.ui_location,
                "doc_citation": k.doc_citation,
                "full_knowledge": json.dumps(k.model_dump())
            })

        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"✓ Indexed {len(knowledge_patterns)} patterns")

    def retrieve(self, query: str, top_k: int = 5, filter_by: Optional[dict] = None) -> List[KnowledgeSchema]:
        if self.collection.count() == 0:
            self.index_knowledge()

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            where=filter_by
        )

        knowledge_patterns = []
        if results['metadatas'] and results['metadatas'][0]:
            for metadata in results['metadatas'][0]:
                knowledge_patterns.append(KnowledgeSchema(**json.loads(metadata['full_knowledge'])))

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
