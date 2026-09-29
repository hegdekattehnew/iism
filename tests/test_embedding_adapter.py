"""The embedding-provider port (ADR-017, ADR-031, Sprint 36 BL-5.1).

`HashingEmbeddingProvider` is an honest placeholder, not the ADR-013/031
model -- see its own docstring. These tests pin the properties the rest of
the pipeline actually depends on: determinism, a fixed dimension, and *some*
non-random locality between texts that share vocabulary.
"""

import math

from api.adapters.embeddings import (
    EMBEDDING_DIMENSIONS,
    HashingEmbeddingProvider,
    get_embedding_provider,
)
from api.adapters.embeddings.base import EmbeddingProvider


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def test_embeds_to_the_pinned_dimension() -> None:
    vector = HashingEmbeddingProvider().embed("Follow infection control policies and procedures")
    assert len(vector) == EMBEDDING_DIMENSIONS == 384


def test_is_deterministic() -> None:
    provider = HashingEmbeddingProvider()
    text = "Maintain workplace health and safety standards"
    assert provider.embed(text) == provider.embed(text)


def test_is_l2_normalised() -> None:
    vector = HashingEmbeddingProvider().embed("Prepare and maintain the work area")
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == 0.0 or abs(norm - 1.0) < 1e-9


def test_empty_text_is_the_zero_vector() -> None:
    assert HashingEmbeddingProvider().embed("") == [0.0] * EMBEDDING_DIMENSIONS


def test_shared_vocabulary_lands_closer_than_unrelated_text() -> None:
    """Not a claim of semantic quality -- a claim that this is not random
    noise, which is the one property BL-5.2's bounded additive term relies on
    to ever produce a non-zero, non-arbitrary result."""
    provider = HashingEmbeddingProvider()
    a = provider.embed("maintain workplace health and safety standards for patients")
    b = provider.embed("maintain workplace health and safety standards for visitors")
    c = provider.embed("calculate compound interest on a fixed deposit account")
    assert _cosine(a, b) > _cosine(a, c)


def test_factory_returns_the_hashing_provider() -> None:
    get_embedding_provider.cache_clear()
    provider = get_embedding_provider()
    assert isinstance(provider, HashingEmbeddingProvider)
    assert isinstance(provider, EmbeddingProvider)
    assert provider.name and provider.model
