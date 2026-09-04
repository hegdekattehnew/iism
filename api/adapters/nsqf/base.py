"""The NSQF source port (ADR-017, ADR-034).

The importer depends on this protocol, never on a MongoDB driver. That is what
lets the test suite run against a JSON fixture with no container, and what
would let the corpus move to a file drop or an API without touching the
importer.
"""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from api.adapters.nsqf.records import McRecord, NosRecord, QpRecord


@runtime_checkable
class NsqfSource(Protocol):
    """Streams the corpus. Async iterators rather than lists: the real data is
    ~35,000 documents and holding it all in memory buys nothing."""

    def iter_nos(self) -> AsyncIterator[NosRecord]: ...
    def iter_qps(self) -> AsyncIterator[QpRecord]: ...
    def iter_model_curricula(self) -> AsyncIterator[McRecord]: ...
    async def close(self) -> None: ...
