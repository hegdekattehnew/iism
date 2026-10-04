"""Two operators adding the same alias at once (Sprint 47, ADR-052's pattern).

`add_alias` checks that the term is free and inserts afterwards. Two operators who press
"add" together both pass the check and the unique constraint refuses the second; that
must surface as a 409 naming the term, never a 500 -- and must write exactly one row and
one audit event. Committed rows and real requests, as in Sprint 45 (`tests/concurrency.py`).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from api.core.database import get_sessionmaker
from api.modules.identity.models import User
from api.modules.skills import RoleAlias, RoleAliasEvent
from api.modules.skills.hierarchy import QpSkill, QualificationPack, Sector
from api.modules.skills.models import Skill
from tests.concurrency import candidate, real_client


@pytest.fixture
async def world() -> AsyncIterator[tuple[AsyncClient, dict[str, str], str]]:
    tag = uuid.uuid4().hex[:8]
    role = f"Race Role {tag}"
    async with real_client() as client:
        async with get_sessionmaker()() as db:
            sector = Sector(sector_ref=f"race-{tag}", name="Race", slug=f"race-{tag}")
            skill = Skill(
                slug=f"race-alias-{tag}", name="Unit", skill_type="technical",
                nsqf_level=Decimal("3"), nos_code=f"RAC/N{int(tag, 16) % 9000 + 1000}",
                source="nsqf",
            )  # fmt: skip
            db.add_all([sector, skill])
            await db.flush()
            pack = QualificationPack(
                qp_code=f"RAC/Q{int(tag, 16) % 9000 + 1000}",
                version="1.0",
                slug=f"race-pack-{tag}",
                name=f"{role} qualification",
                job_role=role,
                nsqf_level=Decimal("3"),
                is_current=True,
                sector_id=sector.id,
            )
            db.add(pack)
            await db.flush()
            db.add(QpSkill(qp_id=pack.id, skill_id=skill.id, requirement="compulsory"))
            await db.commit()
            pack_id, skill_id, sector_id = pack.id, skill.id, sector.id
        operators = [await candidate(client), await candidate(client)]
        async with get_sessionmaker()() as db:
            for headers in operators:
                me = (await client.get("/auth/me", headers=headers)).json()
                user = await db.get(User, uuid.UUID(me["id"]))
                assert user is not None
                user.is_staff, user.staff_tier = True, "admin"
            await db.commit()
        try:
            yield client, operators[0] | {"x-second": operators[1]["authorization"]}, role
        finally:
            for headers in operators:
                await client.delete("/me/account", headers=headers)
            async with get_sessionmaker()() as db:
                await db.execute(delete(RoleAliasEvent).where(RoleAliasEvent.job_role == role))
                await db.execute(delete(RoleAlias).where(RoleAlias.job_role == role))
                await db.execute(delete(QpSkill).where(QpSkill.qp_id == pack_id))
                await db.execute(delete(QualificationPack).where(QualificationPack.id == pack_id))
                await db.execute(delete(Skill).where(Skill.id == skill_id))
                await db.execute(delete(Sector).where(Sector.id == sector_id))
                await db.commit()


async def test_two_operators_adding_one_term_at_once_is_a_201_and_a_409(
    world: tuple[AsyncClient, dict[str, str], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.modules.skills import alias_admin

    client, headers, role = world
    first = {"authorization": headers["authorization"]}
    second = {"authorization": headers["x-second"]}
    original = alias_admin.check_alias

    async def slow(*args: object, **kwargs: object) -> object:
        result = await original(*args, **kwargs)  # type: ignore[arg-type]
        await asyncio.sleep(0.4)  # both have passed the check before either inserts
        return result

    monkeypatch.setattr(alias_admin, "check_alias", slow)
    body = {"surface_form": "race term", "job_role": role}

    a, b = await asyncio.gather(
        client.post("/ops/role-aliases", headers=first, json=body),
        client.post("/ops/role-aliases", headers=second, json=body),
    )

    assert sorted([a.status_code, b.status_code]) == [201, 409], (a.text, b.text)
    async with get_sessionmaker()() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(RoleAlias).where(RoleAlias.job_role == role)
            )
        ) == 1
        assert (
            await db.scalar(
                select(func.count())
                .select_from(RoleAliasEvent)
                .where(RoleAliasEvent.job_role == role)
            )
        ) == 1
