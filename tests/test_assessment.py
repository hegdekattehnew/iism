"""BL-3.1: an assessment provider's result becomes a `CandidateSkill`
(Sprint 35, Epic B3). No new table -- see `api/modules/assessment/service.py`'s
docstring for why (ADR-023's encryption path is unbuilt, and this deliberately
never stores anything a plain `CandidateSkill.source='assessed'` row would not
already have stored)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.security import hash_secret
from api.modules.assessment import service
from api.modules.identity.models import ServiceAccount
from api.modules.marketplace.models import CandidateSkill
from api.modules.skills.models import Skill

RAW_KEY = "an-assessment-partner-key"
CANDIDATE_PHONE = "+919812340001"


async def _write_scoped_account(db: AsyncSession, *, scope: str = "assessment:write") -> None:
    db.add(
        ServiceAccount(name="ssc-assessment-partner", hashed_key=hash_secret(RAW_KEY), scope=scope)
    )
    await db.commit()


async def _candidate(client: AsyncClient, phone: str) -> dict[str, str]:
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _skill(db: AsyncSession, *, nos_code: str) -> Skill:
    skill = Skill(
        slug=f"assessed-{uuid.uuid4().hex[:8]}",
        name="Handle patient records",
        skill_type="technical",
        nos_code=nos_code,
    )
    db.add(skill)
    await db.flush()
    return skill


class TestTheWebhookRoute:
    async def test_requires_an_api_key(self, client: AsyncClient) -> None:
        res = await client.post(
            "/partners/assessment-results",
            json={"phone": CANDIDATE_PHONE, "standard_code": "HSS/N9001", "outcome": "pass"},
        )
        assert res.status_code == 401

    async def test_a_read_only_key_is_refused_with_403_not_401(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The key is real -- 401 would misreport an authenticated caller as
        unauthenticated (ADR-038's rule, applied to a service account)."""
        await _write_scoped_account(db, scope="read")
        res = await client.post(
            "/partners/assessment-results",
            headers={"X-API-Key": RAW_KEY},
            json={"phone": CANDIDATE_PHONE, "standard_code": "HSS/N9001", "outcome": "pass"},
        )
        assert res.status_code == 403

    async def test_an_unknown_candidate_is_404(self, client: AsyncClient, db: AsyncSession) -> None:
        await _write_scoped_account(db)
        await _skill(db, nos_code="HSS/N9001")
        res = await client.post(
            "/partners/assessment-results",
            headers={"X-API-Key": RAW_KEY},
            json={"phone": "+919812349999", "standard_code": "HSS/N9001", "outcome": "pass"},
        )
        assert res.status_code == 404

    async def test_an_unknown_standard_is_404(self, client: AsyncClient, db: AsyncSession) -> None:
        await _write_scoped_account(db)
        await _candidate(client, CANDIDATE_PHONE)
        res = await client.post(
            "/partners/assessment-results",
            headers={"X-API-Key": RAW_KEY},
            json={"phone": CANDIDATE_PHONE, "standard_code": "NO/SUCH/CODE", "outcome": "pass"},
        )
        assert res.status_code == 404

    async def test_a_pass_writes_an_assessed_skill(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _write_scoped_account(db)
        skill = await _skill(db, nos_code="HSS/N9002")
        await _candidate(client, "+919812340002")

        res = await client.post(
            "/partners/assessment-results",
            headers={"X-API-Key": RAW_KEY},
            json={"phone": "+919812340002", "standard_code": "HSS/N9002", "outcome": "pass"},
        )
        assert res.status_code == 200
        assert res.json() == {"written": True, "added": 1, "updated": 0}

        row = await db.scalar(select(CandidateSkill).where(CandidateSkill.skill_id == skill.id))
        assert row is not None
        assert row.source == "assessed"

    async def test_a_fail_writes_nothing(self, client: AsyncClient, db: AsyncSession) -> None:
        await _write_scoped_account(db)
        skill = await _skill(db, nos_code="HSS/N9003")
        await _candidate(client, "+919812340003")

        res = await client.post(
            "/partners/assessment-results",
            headers={"X-API-Key": RAW_KEY},
            json={"phone": "+919812340003", "standard_code": "HSS/N9003", "outcome": "fail"},
        )
        assert res.status_code == 200
        assert res.json() == {"written": False, "added": 0, "updated": 0}
        assert (
            await db.scalar(select(CandidateSkill).where(CandidateSkill.skill_id == skill.id))
        ) is None

    async def test_a_malformed_payload_is_422(self, client: AsyncClient, db: AsyncSession) -> None:
        await _write_scoped_account(db)
        res = await client.post(
            "/partners/assessment-results",
            headers={"X-API-Key": RAW_KEY},
            json={"phone": CANDIDATE_PHONE},
        )
        assert res.status_code == 422


class TestIngestResultDirectly:
    async def test_unknown_candidate_raises_by_name(self, db: AsyncSession) -> None:
        await _skill(db, nos_code="HSS/N9004")
        with pytest.raises(service.UnknownCandidate):
            await service.ingest_result(
                db,
                {"phone": "+919812349998", "standard_code": "HSS/N9004", "outcome": "pass"},
            )

    async def test_unknown_standard_raises_by_name(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _candidate(client, "+919812340004")
        with pytest.raises(service.UnknownStandard):
            await service.ingest_result(
                db,
                {
                    "phone": "+919812340004",
                    "standard_code": "NOTHING/HERE",
                    "outcome": "pass",
                },
            )
