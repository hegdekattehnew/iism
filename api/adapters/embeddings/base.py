"""The embedding-provider port (ADR-017, ADR-013, ADR-031, Sprint 36 BL-5.1).

Business logic must depend on this protocol, never on a specific model
library -- ADR-031's whole reason for pinning every implementation to 384
dimensions is that a provider swap must never be a schema migration.
"""

from typing import Protocol, runtime_checkable

# ADR-031: pinned so every implementation is interchangeable with no schema
# change. Changing this number is changing the platform embedding provider,
# not a local tuning knob.
EMBEDDING_DIMENSIONS = 384


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turns text into a fixed-length vector. Pure with respect to the rest of
    the platform: no database access, no clock -- `embed` is deterministic for
    a given provider and model, which is what lets a stored vector's meaning
    outlive the request that computed it.

    Synchronous, unlike `NotificationProvider`/`PaymentProvider`: those call an
    external vendor over the network; this calls a model in-process. Kept
    off the request path regardless (ADR-036) -- see
    `api/modules/matching/tasks.py`.
    """

    #: The identifier recorded beside every vector this provider produces
    #: (ADR-031: "every stored vector records the provider, model identifier
    #: and model version... no vector's provenance is ever ambiguous").
    name: str
    model: str

    def embed(self, text: str) -> list[float]: ...
