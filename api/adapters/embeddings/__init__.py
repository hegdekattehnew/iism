"""Embedding adapters (ADR-017, Sprint 36 BL-5.1). Import a factory, not an
implementation."""

from functools import lru_cache

from api.adapters.embeddings.base import EMBEDDING_DIMENSIONS, EmbeddingProvider
from api.adapters.embeddings.hashing import HashingEmbeddingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Chosen by configuration (`api.core.config.Settings.embedding_provider`).

    Defaults to the placeholder everywhere -- turning on the real,
    ADR-mandated model (`SentenceTransformerEmbeddingProvider`) is a
    deliberate, per-environment choice, not this factory's default. `lru_cache`d
    because constructing the real provider loads a model into memory; this
    must happen once per process, not once per call.
    """
    from api.core.config import get_settings

    if get_settings().embedding_provider == "sentence_transformer":
        from api.adapters.embeddings.sentence_transformer import (
            SentenceTransformerEmbeddingProvider,
        )

        return SentenceTransformerEmbeddingProvider()
    return HashingEmbeddingProvider()


__all__ = [
    "EMBEDDING_DIMENSIONS",
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "get_embedding_provider",
]
