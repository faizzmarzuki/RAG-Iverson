"""
RAG MCP server (STDIO).

RAG = Retrieval-Augmented Generation. Here it works like this:
1. Each row of the uploaded dataset becomes a sentence, e.g. "name: Ali | age: 21 | city: KL".
2. Each sentence is turned into a list of numbers (an embedding) by a sentence-transformer model.
3. FAISS stores those numbers, so we can find the rows closest in meaning to a question.

RAG finds relevant text. It does NOT calculate exact numbers; use the Pandas tools for that.
Like the Pandas server, the aggregator starts this file for you.
"""
import sys
from pathlib import Path

# Add the project root to Python's search path so "config" and "pandas_mcp" can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faiss
import numpy as np
from fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

from config.settings import EMBEDDING_MODEL
from pandas_mcp.analytics import active_dataset_path, load_dataset

mcp = FastMCP("rag-retrieval")

# Loaded once and kept in memory, because loading the model is slow.
_embedder = None
# One search index per user, kept by dataset_id: {dataset_id: {"key", "texts", "index"}}.
# shortcut: kept in memory only, so it is rebuilt after a restart; upgrade: save the FAISS index to disk.
_indexes = {}


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def _ensure_index(dataset_id, force=False):
    """Build the search index for one user's dataset (if not built yet) and return it."""
    path = active_dataset_path(dataset_id)
    # The key includes the file's modified time, so re-uploading the same file rebuilds the index.
    key = (str(path), path.stat().st_mtime)
    state = _indexes.get(dataset_id)
    if not force and state and state["key"] == key:
        return state

    df = load_dataset(path)
    # Each row becomes one text: "column: value | column: value | ..."
    texts = [" | ".join(f"{col}: {val}" for col, val in row.items()) for row in df.to_dict("records")]
    if not texts:
        raise ValueError("The dataset has no rows to index")

    embeddings = _get_embedder().encode(texts, convert_to_numpy=True).astype("float32")
    index = faiss.IndexFlatL2(embeddings.shape[1])  # simple exact search, fine for small files
    index.add(embeddings)
    state = {"key": key, "texts": texts, "index": index}
    _indexes[dataset_id] = state
    return state


@mcp.tool()
def rag_load_dataset(dataset_id: str) -> dict:
    """Load (or reload) the uploaded dataset into the search index. Returns how many rows were indexed."""
    state = _ensure_index(dataset_id, force=True)
    return {"indexed_rows": len(state["texts"]), "file": active_dataset_path(dataset_id).name}


@mcp.tool()
def rag_search_dataset(dataset_id: str, query: str, top_k: int = 5) -> dict:
    """Find the rows whose meaning is closest to the query. top_k is how many rows to return (1 to 20)."""
    if not query.strip():
        raise ValueError("Query cannot be empty")
    state = _ensure_index(dataset_id)

    top_k = max(1, min(int(top_k), 20, len(state["texts"])))
    query_vector = _get_embedder().encode([query], convert_to_numpy=True).astype("float32")
    distances, positions = state["index"].search(query_vector, top_k)

    # distances: smaller number = closer match
    results = [
        {"row_text": state["texts"][pos], "distance": float(dist)}
        for dist, pos in zip(distances[0], positions[0])
    ]
    return {"query": query, "results": results}


@mcp.tool()
def rag_get_dataset_info(dataset_id: str) -> dict:
    """Return the name of the indexed file, how many rows are indexed and the embedding model used."""
    state = _ensure_index(dataset_id)
    return {
        "file": active_dataset_path(dataset_id).name,
        "indexed_rows": len(state["texts"]),
        "embedding_model": EMBEDDING_MODEL,
    }


if __name__ == "__main__":
    mcp.run()  # default transport is STDIO
