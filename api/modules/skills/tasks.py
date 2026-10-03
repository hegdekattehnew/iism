"""Semantic-similarity embeddings for role search (Sprint 40, foundation).

Mirrors `api/modules/matching/tasks.py`'s exact shape: a sweep, never inline
in a request (ADR-036), computed at write time and read at search time.
`QualificationPack.embedding` is `NULL` until this runs -- the same "needs
(re)computing" convention `_EmbeddingColumns` documents for `Job`/
`CandidateProfile` in `api/modules/marketplace/models.py`.

Embeds every current, standards-bearing qualification pack, not only the one
row `_ROLE_SEARCH_SQL`'s own `pick=1` window function treats as the
"representative" for its role -- replaying that exact ranking here would
duplicate logic that already lives in one place (`api/modules/skills/
service.py`), and a few redundant embeddings on `-SI` variants and reissues
cost nothing a search ever notices, since `search_roles()` still collapses to
one row per role at query time regardless of which rows carry a vector.
"""

from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_sessionmaker

log = structlog.get_logger("iism.skills")

# One sweep's worth, the same bound `matching/tasks.py`'s own `BATCH_SIZE`
# uses and for the same reason: a backlog after `make import-nsqf` must not
# make one worker tick run for minutes.
BATCH_SIZE = 100


async def refresh_role_embeddings(ctx: dict[str, Any]) -> dict[str, int]:
    """Never raises: a cron that throws takes the worker's next tick with it,
    and a stale or missing embedding is a role-search quality issue, never a
    correctness one -- search already works via the literal/alias/fuzzy tiers
    with no embedding at all (BL-5.2's own bound, restated here: this can only
    ever refine a ranking)."""
    try:
        async with get_sessionmaker()() as db:
            return {"qualification_packs": await _refresh_packs(db)}
    except Exception as error:  # noqa: BLE001 - a cron must not kill the worker
        log.warning("skills.role_embedding_refresh_failed", error=str(error)[:300])
        return {"qualification_packs": 0}


async def _refresh_packs(db: AsyncSession) -> int:
    from api.adapters.embeddings import get_embedding_provider
    from api.modules.skills.hierarchy import QpSkill, QualificationPack
    from api.modules.skills.service import embedding_text_for_skills

    provider = get_embedding_provider()
    if provider.name == "hashing":
        # `search_roles` never reads a role vector under the placeholder
        # provider (its "similarity" is word overlap, which the literal tiers
        # already cover), so embedding 4,400 packs would be work for nothing.
        return 0

    packs = list(
        await db.scalars(
            select(QualificationPack)
            .where(
                QualificationPack.is_current,
                QualificationPack.embedding.is_(None)
                | QualificationPack.embedding_model.is_distinct_from(provider.model),
            )
            .limit(BATCH_SIZE)
        )
    )
    if not packs:
        return 0

    for pack in packs:
        skill_ids = list(await db.scalars(select(QpSkill.skill_id).where(QpSkill.qp_id == pack.id)))
        criteria_text = await embedding_text_for_skills(db, skill_ids)
        # The role name itself, prefixed on: unlike a bare skill's title (which
        # embeds to noise on its own, per `embedding_text_for_skills`'s own
        # docstring), a role's name is exactly what a candidate's query is
        # compared against, and a pack with no recorded performance criteria
        # at all should still get something rather than being skipped the way
        # a job or profile with no declared skills is.
        text = f"{pack.job_role or pack.name}. {criteria_text}".strip()
        if not text:
            continue
        pack.embedding = provider.embed(text)
        pack.embedding_provider = provider.name
        pack.embedding_model = provider.model
        pack.embedding_computed_at = func.now()
    await db.commit()
    return len(packs)
