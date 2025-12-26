"""
Knowledge Base Module

Provides documentation parsing, indexing, and retrieval for the asammdf agent.

Components:
- doc_parser: Parse documentation and extract knowledge patterns
- indexer: Index knowledge patterns into ChromaDB vector store
- retriever: Semantic search and retrieval of knowledge patterns
"""

from agent.knowledge_base.doc_parser import DocumentationParser, build_knowledge_catalog
from agent.knowledge_base.indexer import KnowledgeIndexer, rebuild_index
from agent.knowledge_base.retriever import KnowledgeRetriever

__all__ = [
    'DocumentationParser',
    'build_knowledge_catalog',
    'KnowledgeIndexer',
    'rebuild_index',
    'KnowledgeRetriever',
]
