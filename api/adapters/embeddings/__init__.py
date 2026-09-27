"""Embedding adapters (ADR-017, Sprint 36 BL-5.1). Import a factory, not an
implementation."""

from functools import lru_cache

from api.adapters.embeddings.base import EMBEDDING_DIMENSIONS, EmbeddingProvider
from api.adapters.embeddings.hashing import HashingEmbeddingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Chosen by configuration, once there is a real model behind the port to
    choose (see `hashing.py`'s docstring for why there is not yet)."""
    return HashingEmbeddingProvider()


__all__ = [
    "EMBEDDING_DIMENSIONS",
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "get_embedding_provider",
]
