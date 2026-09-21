"""File-backed NSQF source (ADR-017, ADR-034).

Reads the same document shapes as `MongoNsqfSource` from a JSON file:

    {"nos": [...], "qps": [...], "modelcurriculum": [...]}

Two uses. It lets the test suite exercise the importer end to end with no Mongo
container -- the corpus is the one thing in this system that cannot be spun up
disposably. And it makes a file drop a first-class way to receive the corpus, so
a revised Qualification Pack release does not have to arrive through a database.

Parsing is shared with the Mongo source, so a fixture proves something about the
real import path rather than about a second reader written to agree with it.
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from api.adapters.nsqf.base import NsqfSource
from api.adapters.nsqf.documents import (
    district_from_doc,
    mc_from_doc,
    nos_from_doc,
    qp_from_doc,
    sector_from_doc,
    state_from_doc,
)
from api.adapters.nsqf.records import (
    DistrictRecord,
    McRecord,
    NosRecord,
    QpRecord,
    SectorRecord,
    StateRecord,
)


class JsonFileNsqfSource(NsqfSource):
    def __init__(self, path: str | Path) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("NSQF JSON must be an object keyed by collection name")
        self._docs: dict[str, list[dict[str, Any]]] = {
            key: list(raw.get(key) or [])
            for key in ("nos", "qps", "modelcurriculum", "state", "district", "sectors")
        }
        self.skipped_documents = 0

    async def close(self) -> None:
        return None

    async def iter_nos(self) -> AsyncIterator[NosRecord]:
        for doc in self._docs["nos"]:
            record = nos_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_qps(self) -> AsyncIterator[QpRecord]:
        for doc in self._docs["qps"]:
            record = qp_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_model_curricula(self) -> AsyncIterator[McRecord]:
        for doc in self._docs["modelcurriculum"]:
            record = mc_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_states(self) -> AsyncIterator[StateRecord]:
        for doc in self._docs["state"]:
            record = state_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_districts(self) -> AsyncIterator[DistrictRecord]:
        for doc in self._docs["district"]:
            record = district_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_sectors(self) -> AsyncIterator[SectorRecord]:
        for doc in self._docs["sectors"]:
            record = sector_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record
