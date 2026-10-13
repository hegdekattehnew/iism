"""An operator removes a listing, and nobody puts it back by themselves (Sprint 59, ADR-069).

The takedown is `status="draft"` plus a stamp, not a third status: every public query already
excludes a draft. What this pins is the part that is easy to leave a hole in -- **every writer of
"published"** refuses while the stamp is there -- and that the right people are told, and only they.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.marketplace.models import Course, Job
from api.modules.notifications.models import Notification
from tests.moderation_support import (
    make_skill,
    operator,
    organisation,
    person,
    published_course,
    published_job,
)

REASON = "The vacancy asked applicants to pay a registration fee before an interview."


async def _take_down(
    client: AsyncClient, ops: dict[str, str], kind: str, listing_id: str, reason: str = REASON
):
    return await client.post(
        f"/ops/listings/{kind}/{listing_id}/takedown", headers=ops, json={"reason": reason}
    )


class TestARemovedVacancy:
    async def test_it_leaves_every_public_list_and_closes_with_its_own_reason(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        slug = job["slug"]
        assert (await client.get(f"/jobs/{slug}")).status_code == 200

        ops = await operator(client, db, "admin")
        assert (await _take_down(client, ops, "job", job["id"])).status_code == 200

        assert (await client.get(f"/jobs/{slug}")).status_code == 404
        listed = (await client.get("/jobs", params={"limit": 50})).json()["items"]
        assert slug not in {j["slug"] for j in listed}

        owner = (await client.get(f"/org/{org}/jobs/{slug}", headers=headers)).json()
        assert owner["status"] == "draft" and owner["is_open"] is False
        assert owner["close_reason"] == "taken_down"
        assert owner["takedown_reason"] == REASON and owner["taken_down_at"]

    async def test_the_owner_cannot_publish_reopen_or_bulk_publish_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        slug = job["slug"]
        ops = await operator(client, db, "admin")
        await _take_down(client, ops, "job", job["id"])

        publish = await client.post(f"/org/{org}/jobs/{slug}/publish", headers=headers)
        assert publish.status_code == 409 and REASON in publish.json()["detail"]
        reopen = await client.post(f"/org/{org}/jobs/{slug}/reopen", headers=headers)
        assert reopen.status_code == 409
        bulk = await client.post(
            f"/org/{org}/jobs/bulk/publish", headers=headers, json={"slugs": [slug]}
        )
        assert bulk.status_code == 200
        (row,) = bulk.json()["results"]
        assert row["published"] is False and REASON in row["message"]
        assert (await client.get(f"/jobs/{slug}")).status_code == 404

    async def test_the_owner_may_still_edit_it(self, client: AsyncClient, db: AsyncSession) -> None:
        skill = await make_skill(db)
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, skill)
        ops = await operator(client, db, "admin")
        await _take_down(client, ops, "job", job["id"])
        edited = await client.put(
            f"/org/{org}/jobs/{job['slug']}",
            headers=headers,
            json={
                "title": "Ward assistant, corrected",
                "skills": [{"skill_slug": skill, "importance": 4, "is_mandatory": True}],
            },
        )
        assert edited.status_code == 200 and edited.json()["title"] == "Ward assistant, corrected"
        assert edited.json()["taken_down_at"]

    async def test_a_restore_returns_a_draft_the_owner_publishes_themselves(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        slug = job["slug"]
        ops = await operator(client, db, "admin")
        await _take_down(client, ops, "job", job["id"])

        restored = await client.post(f"/ops/listings/job/{job['id']}/restore", headers=ops)
        assert restored.status_code == 200
        assert (await client.get(f"/jobs/{slug}")).status_code == 404  # nothing goes live by itself
        owner = (await client.get(f"/org/{org}/jobs/{slug}", headers=headers)).json()
        assert owner["taken_down_at"] is None and owner["close_reason"] is None
        assert owner["status"] == "draft" and owner["closed_at"] is None

        assert (
            await client.post(f"/org/{org}/jobs/{slug}/publish", headers=headers)
        ).status_code == 200
        assert (await client.get(f"/jobs/{slug}")).status_code == 200

    async def test_a_restore_keeps_a_closure_the_takedown_did_not_make(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        await client.post(
            f"/org/{org}/jobs/{job['slug']}/close", headers=headers, json={"reason": "filled"}
        )
        ops = await operator(client, db, "admin")
        await _take_down(client, ops, "job", job["id"])
        await client.post(f"/ops/listings/job/{job['id']}/restore", headers=ops)
        owner = (await client.get(f"/org/{org}/jobs/{job['slug']}", headers=headers)).json()
        assert owner["close_reason"] == "filled"

    async def test_taking_it_down_twice_or_restoring_what_is_up_is_a_409(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        ops = await operator(client, db, "admin")
        assert (
            await client.post(f"/ops/listings/job/{job['id']}/restore", headers=ops)
        ).status_code == 409
        await _take_down(client, ops, "job", job["id"])
        assert (await _take_down(client, ops, "job", job["id"])).status_code == 409

    async def test_an_unknown_listing_is_a_404(self, client: AsyncClient, db: AsyncSession) -> None:
        ops = await operator(client, db, "admin")
        assert (await _take_down(client, ops, "job", str(uuid.uuid4()))).status_code == 404

    @pytest.mark.parametrize("reason", ["", "too short", "x" * 1001])
    async def test_the_reason_has_a_floor_and_a_ceiling(
        self, client: AsyncClient, db: AsyncSession, reason: str
    ) -> None:
        ops = await operator(client, db, "admin")
        assert (await _take_down(client, ops, "job", str(uuid.uuid4()), reason)).status_code == 422


class TestARemovedCourse:
    async def test_it_leaves_the_public_list_and_cannot_be_republished(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db, "course_provider")
        course = await published_course(client, headers, org, await make_skill(db))
        slug = course["slug"]
        ops = await operator(client, db, "admin")
        assert (await _take_down(client, ops, "course", course["id"])).status_code == 200

        assert (await client.get(f"/courses/{slug}")).status_code == 404
        refused = await client.post(f"/org/{org}/courses/{slug}/publish", headers=headers)
        assert refused.status_code == 409 and REASON in refused.json()["detail"]
        bulk = await client.post(
            f"/org/{org}/courses/bulk/publish", headers=headers, json={"slugs": [slug]}
        )
        assert bulk.json()["results"][0]["published"] is False

        await client.post(f"/ops/listings/course/{course['id']}/restore", headers=ops)
        assert (
            await client.post(f"/org/{org}/courses/{slug}/publish", headers=headers)
        ).status_code == 200


class TestWhoIsTold:
    async def test_only_the_applicants_still_waiting_hear_it_and_the_organisation_is_emailed(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        waiting, _ = await person(client)
        withdrawn, _ = await person(client)
        for who in (waiting, withdrawn):
            assert (
                await client.post("/me/applications", headers=who, json={"job_slug": job["slug"]})
            ).status_code == 201
        applications = (await client.get("/me/applications", headers=withdrawn)).json()
        await client.post(f"/me/applications/{applications[0]['id']}/withdraw", headers=withdrawn)

        ops = await operator(client, db, "admin")
        before = (await client.get("/me/applications", headers=waiting)).json()
        assert before[0]["job"]["removed"] is False
        await _take_down(client, ops, "job", job["id"])
        after = (await client.get("/me/applications", headers=waiting)).json()
        assert after[0]["job"]["removed"] is True, "the list says so rather than link to a 404"
        assert "taken_down_at" not in after[0]["job"]

        closed = (
            await db.scalars(select(Notification).where(Notification.template == "vacancy_closed"))
        ).all()
        mine = [n for n in closed if n.payload.get("vacancy") == job["title"]]
        assert len(mine) == 1, "the withdrawn applicant is not told"
        removed = (
            await db.scalars(select(Notification).where(Notification.template == "listing_removed"))
        ).all()
        (email,) = [n for n in removed if n.payload["listing"] == job["title"]]
        assert email.channel == "email" and email.recipient_kind == "tenant"
        assert email.payload["reason"] == REASON
        assert set(email.payload) == {"listing", "reason", "path"}, "nothing about any person"

    async def test_a_restore_emails_the_organisation_too(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        ops = await operator(client, db, "admin")
        await _take_down(client, ops, "job", job["id"])
        await client.post(f"/ops/listings/job/{job['id']}/restore", headers=ops)
        restored = (
            await db.scalars(
                select(Notification).where(Notification.template == "listing_restored")
            )
        ).all()
        assert [n for n in restored if n.payload["listing"] == job["title"]]


class TestWhoMayDoIt:
    async def test_support_may_not_take_down_or_restore_and_a_stranger_finds_nothing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        support = await operator(client, db, "support")
        assert (await _take_down(client, support, "job", job["id"])).status_code == 403
        assert (
            await client.post(f"/ops/listings/job/{job['id']}/restore", headers=support)
        ).status_code == 403
        stranger, _ = await person(client)
        refused = await _take_down(client, stranger, "job", job["id"])
        nowhere = await client.get("/ops/definitely-not-a-route", headers=stranger)
        assert refused.status_code == 404 and refused.text == nowhere.text
        assert (await client.get(f"/jobs/{job['slug']}")).status_code == 200  # nothing happened

    async def test_an_organisation_owner_cannot_take_down_their_own_or_anyone_elses(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        assert (await _take_down(client, headers, "job", job["id"])).status_code == 404

    async def test_the_models_agree_on_what_is_taken_down(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        job = await published_job(client, headers, org, await make_skill(db))
        ops = await operator(client, db, "admin")
        await _take_down(client, ops, "job", job["id"])
        row = await db.get(Job, uuid.UUID(job["id"]), populate_existing=True)
        assert row is not None and row.taken_down_at is not None and row.status == "draft"
        assert Course.__table__.c.taken_down_at is not None
