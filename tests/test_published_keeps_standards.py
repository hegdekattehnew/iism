"""A published listing keeps at least one standard (Sprint 53, ADR-064).

"No standard, no publishing" was checked at one moment only, the instant of publishing, so a live
vacancy could be saved with every standard removed: still published, still on `/jobs`, and never
matchable. These pin the invariant at the write that could break it, and what must still work.
"""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.nsqf.importer import import_nsqf
from api.adapters.nsqf.jsonfile import JsonFileNsqfSource
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT

FIXTURE = Path(__file__).parent / "fixtures" / "nsqf_sample.json"
COLLECT = "collect-blood-samples-hc-n0001"
STERILE = "maintain-a-sterile-field-hc-n0002"


@pytest.fixture
async def corpus(db: AsyncSession) -> None:
    await import_nsqf(db, JsonFileNsqfSource(FIXTURE))
    await db.commit()


async def _org(client: AsyncClient, tenant_type: str) -> tuple[dict[str, str], str]:
    address = f"keeps-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": f"Keeps {uuid.uuid4().hex[:6]}",
                "tenant_type": tenant_type,
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/auth/me", headers=headers)).json()
    slug = next(
        m["tenant"]["slug"] for m in me["memberships"] if m["tenant"]["tenant_type"] == tenant_type
    )
    return headers, slug


def _titles(response: Response) -> tuple[str, list[str]]:
    body = response.json()
    return body["title"], sorted(s["skill"]["slug"] for s in body["skills"])


async def _job(client: AsyncClient, *, publish: bool) -> tuple[dict[str, str], str, str]:
    headers, org = await _org(client, "employer")
    made = await client.post(
        f"/org/{org}/jobs",
        headers=headers,
        json={"title": "Phlebotomist", "skills": [{"skill_slug": COLLECT}]},
    )
    slug = made.json()["slug"]
    if publish:
        assert (
            await client.post(f"/org/{org}/jobs/{slug}/publish", headers=headers)
        ).status_code == 200
    return headers, org, slug


async def _course(client: AsyncClient, *, publish: bool) -> tuple[dict[str, str], str, str]:
    headers, org = await _org(client, "course_provider")
    made = await client.post(
        f"/org/{org}/courses",
        headers=headers,
        json={"title": "Blood collection", "skills": [{"skill_slug": COLLECT, "level_taught": 4}]},
    )
    slug = made.json()["slug"]
    if publish:
        assert (
            await client.post(f"/org/{org}/courses/{slug}/publish", headers=headers)
        ).status_code == 200
    return headers, org, slug


class TestVacancies:
    async def test_a_live_vacancy_cannot_be_edited_down_to_no_standards(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org, slug = await _job(client, publish=True)

        refused = await client.put(
            f"/org/{org}/jobs/{slug}", headers=headers, json={"title": "Renamed", "skills": []}
        )

        assert refused.status_code == 422
        assert "must keep at least one required standard" in refused.json()["detail"]
        # Nothing changed, not even the title: the refusal comes before any field is touched.
        kept = await client.get(f"/org/{org}/jobs/{slug}", headers=headers)
        assert _titles(kept) == ("Phlebotomist", [COLLECT])
        assert kept.json()["status"] == "published"

    async def test_a_draft_may_still_be_saved_with_none(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org, slug = await _job(client, publish=False)
        saved = await client.put(
            f"/org/{org}/jobs/{slug}", headers=headers, json={"title": "Draft", "skills": []}
        )
        assert saved.status_code == 200
        assert _titles(saved) == ("Draft", [])

    async def test_a_live_vacancy_may_change_its_standards_while_it_keeps_one(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org, slug = await _job(client, publish=True)
        changed = await client.put(
            f"/org/{org}/jobs/{slug}",
            headers=headers,
            json={"title": "Phlebotomist", "skills": [{"skill_slug": STERILE}]},
        )
        assert changed.status_code == 200
        assert _titles(changed) == ("Phlebotomist", [STERILE])

    async def test_unpublishing_first_is_the_way_to_empty_it(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org, slug = await _job(client, publish=True)
        assert (
            await client.post(f"/org/{org}/jobs/{slug}/unpublish", headers=headers)
        ).status_code == 200
        emptied = await client.put(
            f"/org/{org}/jobs/{slug}", headers=headers, json={"title": "Phlebotomist", "skills": []}
        )
        assert emptied.status_code == 200
        # ... and the rule at the other end still holds: it cannot go live again like that.
        again = await client.post(f"/org/{org}/jobs/{slug}/publish", headers=headers)
        assert again.status_code == 422


class TestCourses:
    async def test_a_live_course_cannot_be_edited_down_to_teaching_nothing(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org, slug = await _course(client, publish=True)

        refused = await client.put(
            f"/org/{org}/courses/{slug}", headers=headers, json={"title": "Renamed", "skills": []}
        )

        assert refused.status_code == 422
        assert "must keep at least one standard it teaches" in refused.json()["detail"]
        kept = await client.get(f"/org/{org}/courses/{slug}", headers=headers)
        assert _titles(kept) == ("Blood collection", [COLLECT])
        assert kept.json()["status"] == "published"

    async def test_a_draft_course_may_still_be_saved_with_none(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org, slug = await _course(client, publish=False)
        saved = await client.put(
            f"/org/{org}/courses/{slug}", headers=headers, json={"title": "Draft", "skills": []}
        )
        assert saved.status_code == 200

    async def test_a_live_course_may_change_what_it_teaches_while_it_teaches_something(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org, slug = await _course(client, publish=True)
        changed = await client.put(
            f"/org/{org}/courses/{slug}",
            headers=headers,
            json={
                "title": "Blood collection",
                "skills": [{"skill_slug": STERILE, "level_taught": 4}],
            },
        )
        assert changed.status_code == 200
