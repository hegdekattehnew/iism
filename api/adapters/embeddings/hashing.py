"""Reference implementation: deterministic feature hashing, not a trained model.

**This is not the ADR-013/031-mandated model.** That decision already fixes
the real implementation -- self-hosted sentence-transformers,
`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions -- but `sentence-
transformers` pulls in torch (100-500+ MB depending on platform) and a
~470 MB multilingual model download on first use. Adding that dependency is
an infrastructure decision with real weight in CI time and image size, not a
one-line adapter swap, so it is deliberately not made silently inside this
story. This provider exists so BL-5.1's actual acceptance criteria -- the
port, the columns, the worker task, all computed at write time and never in
a request -- can be built, tested and demonstrated today, honestly labelled
as a placeholder.

It is still a real embedding in one sense that matters for testing the rest
of the pipeline: same text always hashes to the same vector (reproducible,
which a stored vector's meaning depends on), and two texts sharing vocabulary
land closer together than two sharing none (real, if weak, locality) --
character n-grams are avoided in favour of whole lower-cased word tokens, so
"OJT" and "ojt" collide but "hygiene" and "higher" do not, which a naive
n-gram hash would get wrong.

**Swapping in the real model** is: a new `SentenceTransformerEmbeddingProvider`
implementing the same protocol, `sentence-transformers` added to
`pyproject.toml`, and `get_embedding_provider()` pointed at it -- no change to
`api/modules/matching/tasks.py`, `Job.embedding` or `CandidateProfile.embedding`,
because none of that code knows which provider is behind the protocol.
"""

import hashlib
import math
import re

from api.adapters.embeddings.base import EMBEDDING_DIMENSIONS

__all__ = ["HashingEmbeddingProvider"]

_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbeddingProvider:
    name = "hashing"
    model = "feature-hash-word-v1"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            # Empty or entirely unrecognised text -- the zero vector. Cosine
            # similarity against it is defined as 0 by `scoring.py`'s own
            # guard, never a division by zero.
            return vector
        return [v / norm for v in vector]
