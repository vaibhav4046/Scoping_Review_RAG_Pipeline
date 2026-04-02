"""Vector store abstraction - supports pgvector and ChromaDB."""

from .chroma_store import ChromaStore, ChromaSearchResult

__all__ = ["ChromaStore", "ChromaSearchResult"]
