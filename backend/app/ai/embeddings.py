"""Embedding generation via Ollama local models."""

import logging
from typing import List

import ollama as ollama_client
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text using Ollama."""
    try:
        response = ollama_client.embed(
            model=settings.embedding_model,
            input=text,
        )
        return response["embeddings"][0]
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        # Return zero vector as fallback
        return [0.0] * settings.embedding_dimensions


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    try:
        response = ollama_client.embed(
            model=settings.embedding_model,
            input=texts,
        )
        return response["embeddings"]
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        return [[0.0] * settings.embedding_dimensions for _ in texts]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
