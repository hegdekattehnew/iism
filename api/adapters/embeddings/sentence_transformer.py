"""The ADR-013/ADR-031-mandated embedding model, self-hosted.

`hashing.py`'s own docstring names this exact swap: a new provider
implementing the same protocol, the dependency added to `pyproject.toml`, and
`get_embedding_provider()` pointed at it -- no change anywhere else, because
nothing outside this module and `__init__.py` knows which provider is behind
`EmbeddingProvider`.

The model is loaded once per process, not per call: constructing a
`SentenceTransformer` reads (and on first use, downloads) the ~470 MB
multilingual model, which is exactly the cost this adapter's whole existence
warns about. `get_embedding_provider()` is `lru_cache`d for the same reason.
"""

from sentence_transformers import SentenceTransformer

from api.adapters.embeddings.base import EMBEDDING_DIMENSIONS

__all__ = ["SentenceTransformerEmbeddingProvider"]

# ADR-031's own choice: 384 dimensions (MiniLM's native size), CPU-only, free
# at inference, multilingual -- ADR-033 makes that last part load-bearing.
_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class SentenceTransformerEmbeddingProvider:
    name = "sentence_transformer"
    model = _MODEL_NAME

    def __init__(self) -> None:
        self._model = SentenceTransformer(_MODEL_NAME, device="cpu")
        actual_dim = self._model.get_embedding_dimension()
        if actual_dim != EMBEDDING_DIMENSIONS:
            # ADR-031's whole abstraction rests on every provider emitting the
            # platform dimension -- a mismatch here is a configuration error
            # to fail loudly on, not a vector to store and let corrupt every
            # cosine comparison downstream.
            raise ValueError(
                f"{_MODEL_NAME} produced {actual_dim}-dimension vectors, "
                f"expected {EMBEDDING_DIMENSIONS} (ADR-031)"
            )

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(v) for v in vector]
