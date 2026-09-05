"""MongoDB implementation of the NSQF source (ADR-017, ADR-034).

Reads `iism_nsqf_master_data` and streams it as normalised records. Document
parsing lives in `documents.py` so that every source interprets the corpus
identically; this module is only responsible for getting documents out of Mongo.
"""

from collections.abc import AsyncIterator

from pymongo import AsyncMongoClient

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
from api.core.config import get_settings

BATCH = 1000


class MongoNsqfSource(NsqfSource):
    def __init__(self, url: str | None = None, database: str | None = None) -> None:
        settings = get_settings()
        self._client: AsyncMongoClient = AsyncMongoClient(url or settings.mongo_url)
        self._db = self._client[database or settings.mongo_database]
        self.skipped_documents = 0

    async def close(self) -> None:
        await self._client.close()

    async def iter_nos(self) -> AsyncIterator[NosRecord]:
        async for doc in self._db.nos.find({}, batch_size=BATCH):
            record = nos_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_qps(self) -> AsyncIterator[QpRecord]:
        async for doc in self._db.qps.find({}, batch_size=BATCH):
            record = qp_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_model_curricula(self) -> AsyncIterator[McRecord]:
        async for doc in self._db.modelcurriculum.find({}, batch_size=BATCH):
            record = mc_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_states(self) -> AsyncIterator[StateRecord]:
        async for doc in self._db.state.find({}, batch_size=BATCH):
            record = state_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_districts(self) -> AsyncIterator[DistrictRecord]:
        async for doc in self._db.district.find({}, batch_size=BATCH):
            record = district_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record

    async def iter_sectors(self) -> AsyncIterator[SectorRecord]:
        async for doc in self._db.sectors.find({}, batch_size=BATCH):
            record = sector_from_doc(doc)
            if record is None:
                self.skipped_documents += 1
                continue
            yield record
