# Knowledge Base Module

Documentation parsing, indexing, and retrieval for the asammdf agent.

---

## Quick Start

```python
from agent.knowledge_base import KnowledgeRetriever

# Auto-loads and indexes knowledge
retriever = KnowledgeRetriever()

# Semantic search
results = retriever.retrieve("concatenate MF4 files", top_k=5)
for pattern in results:
    print(f"{pattern.knowledge_id}: {pattern.description}")
```

---

## Components

### 1. Document Parser (`doc_parser.py`)

Extracts knowledge patterns from asammdf documentation using GPT.

```python
from agent.knowledge_base import DocumentationParser, build_knowledge_catalog

# Parse documentation
patterns = build_knowledge_catalog(
    doc_url="https://asammdf.readthedocs.io/en/stable/gui.html",
    output_path="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json"
)
```

**CLI:**
```bash
python agent/knowledge_base/doc_parser.py --doc-url <url> --output <path>
```

---

### 2. Knowledge Indexer (`indexer.py`)

Indexes knowledge patterns into ChromaDB vector store.

```python
from agent.knowledge_base import KnowledgeIndexer, rebuild_index

# Rebuild index from scratch
rebuild_index()

# Or use indexer directly
indexer = KnowledgeIndexer()
indexer.index_knowledge(rebuild=True)
```

**CLI:**
```bash
# Rebuild index
python agent/knowledge_base/indexer.py --rebuild

# Show statistics
python agent/knowledge_base/indexer.py --stats

# Clear index
python agent/knowledge_base/indexer.py --clear
```

---

### 3. Knowledge Retriever (`retriever.py`)

Semantic search and retrieval using ChromaDB.

```python
from agent.knowledge_base import KnowledgeRetriever

retriever = KnowledgeRetriever()

# Semantic search
results = retriever.retrieve("export to Excel", top_k=3)

# Get by ID
pattern = retriever.get_by_id("open_mf4_files")

# List all
all_patterns = retriever.list_all()

# Statistics
stats = retriever.get_stats()
print(f"Total patterns: {stats['total_entries']}")
```

**CLI:**
```bash
# Test queries
python agent/knowledge_base/retriever.py --test

# Custom query
python agent/knowledge_base/retriever.py --query "plot signal" --top-k 5

# Statistics
python agent/knowledge_base/retriever.py --stats
```

---

## Folder Structure

```
knowledge_base/
├── __init__.py                    # Module exports
├── doc_parser.py                  # Documentation parsing with GPT
├── indexer.py                     # ChromaDB indexing
├── retriever.py                   # Semantic search & retrieval
├── parsed_knowledge/              # Parsed documentation
│   └── knowledge_catalog.json     # Knowledge patterns (JSON)
└── vector_store/                  # ChromaDB vector database
    └── (auto-generated)
```

---

## Workflow

1. **Parse** documentation → Extract knowledge patterns → Save to `parsed_knowledge/`
2. **Index** knowledge patterns → Create embeddings → Store in `vector_store/`
3. **Retrieve** relevant patterns → Semantic search → Return top-k results

---

## Default Paths

- **Parsed Knowledge:** `agent/knowledge_base/parsed_knowledge/knowledge_catalog.json`
- **Vector Store:** `agent/knowledge_base/vector_store/`

---

## Auto-Indexing

The retriever auto-indexes if the vector store is empty:

```python
# First run - auto-indexes from parsed_knowledge/
retriever = KnowledgeRetriever()  # Indexes automatically

# Subsequent runs - uses existing index
retriever = KnowledgeRetriever()  # Fast, no indexing
```

---

## Advanced Usage

### Custom Paths

```python
retriever = KnowledgeRetriever(
    catalog_path="custom/path/knowledge.json",
    vector_db_path="custom/vector_store",
    embedding_model="all-MiniLM-L6-v2"
)
```

### Filtered Search

```python
results = retriever.retrieve(
    query="concatenate files",
    top_k=5,
    filter_by={"ui_location": "File menu"}
)
```

### Rebuild Index

```python
from agent.knowledge_base import rebuild_index

rebuild_index(
    catalog_path="agent/knowledge_base/parsed_knowledge/knowledge_catalog.json",
    vector_db_path="agent/knowledge_base/vector_store"
)
```

---

## Dependencies

- **ChromaDB** - Vector database
- **sentence-transformers** - Embeddings (`all-MiniLM-L6-v2`)
- **OpenAI API** - Document parsing (GPT-5-mini)
- **BeautifulSoup** - HTML parsing
- **Pydantic** - Schema validation

---

## Example: Full Pipeline

```python
from agent.knowledge_base import (
    build_knowledge_catalog,
    rebuild_index,
    KnowledgeRetriever
)

# 1. Parse documentation
patterns = build_knowledge_catalog(
    doc_url="https://asammdf.readthedocs.io/en/stable/gui.html"
)

# 2. Rebuild index
rebuild_index()

# 3. Retrieve knowledge
retriever = KnowledgeRetriever()
results = retriever.retrieve("concatenate MF4 files", top_k=5)

for pattern in results:
    print(f"\n{pattern.knowledge_id}")
    print(f"Description: {pattern.description}")
    print(f"Location: {pattern.ui_location}")
```

---

## See Also

- **KNOWLEDGE_BASE_REORGANIZATION.md** - Migration guide
- **agent/planning/workflow_planner.py** - Uses retriever for planning
- **agent/workflows/autonomous_workflow.py** - Integrates with workflow
