"""Reports about listings, and the operator's queue (Sprint 59, BL-14.4, ADR-069).

Who may report and how often, that an operator decides about a listing and not a report, that a
reporter is masked from the operator and absent everywhere else, and that a report is kept exactly
as long as it is useful.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.cache import get_redis
from api.core.config import get_settings
from api.modules.analytics.models import AnalyticsEvent
from api.modules.marketplace.models import Job
from api.modules.moderation import ListingReport, purge_expired
from tests.moderation_support import (
    make_skill,
    operator,
    organisation,
    person,
    published_course,
    published_job,
)

DETAIL = "They asked me to send a deposit on WhatsApp before any interview."


async def _report(client: AsyncClient, who: dict[str, str], kind: str, slug: str, **over: object):
    body = {"reason": "asks_for_money", "detail": DETAIL, **over}
    return await client.post(f"/{kind}s/{slug}/report", headers=who, json=body)


async def _listing(client: AsyncClient, db: AsyncSession) -> tuple[dict, dict, str]:
    headers, org = await organisation(client, db)
    return await published_job(client, headers, org, await make_skill(db)), headers, org


class TestWhoMayReport:
    async def test_a_signed_in_person_may_report_a_vacancy_and_a_course(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, _, _ = await _listing(client, db)
        provider, org = await organisation(client, db, "course_provider")
        course = await published_course(client, provider, org, await make_skill(db))
        who, _ = await person(client)
        assert (await _report(client, who, "job", job["slug"])).status_code == 201
        assert (
            await _report(client, who, "course", course["slug"], reason="other")
        ).status_code == 201
        rows = (
            await db.scalars(
                select(ListingReport).where(ListingReport.target_id == uuid.UUID(job["id"]))
            )
        ).all()
        assert [(r.reason, r.detail, r.target_title, r.status) for r in rows] == [
            ("asks_for_money", DETAIL, job["title"], "open")
        ]

    async def test_a_stranger_may_not(self, client: AsyncClient, db: AsyncSession) -> None:
        job, _, _ = await _listing(client, db)
        response = await client.post(f"/jobs/{job['slug']}/report", json={"reason": "other"})
        assert response.status_code == 401

    async def test_a_draft_or_an_unknown_listing_is_a_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, headers, org = await _listing(client, db)
        await client.post(f"/org/{org}/jobs/{job['slug']}/unpublish", headers=headers)
        who, _ = await person(client)
        assert (await _report(client, who, "job", job["slug"])).status_code == 404
        assert (await _report(client, who, "job", "no-such-vacancy")).status_code == 404

    async def test_a_member_of_the_organisation_may_not_report_its_listing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, owner, _ = await _listing(client, db)
        refused = await _report(client, owner, "job", job["slug"])
        assert refused.status_code == 409 and "manage" in refused.json()["detail"]

    async def test_a_second_report_by_the_same_person_is_a_409_and_another_person_may(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, _, _ = await _listing(client, db)
        first, _ = await person(client)
        second, _ = await person(client)
        assert (await _report(client, first, "job", job["slug"])).status_code == 201
        again = await _report(client, first, "job", job["slug"], reason="other")
        assert again.status_code == 409 and "already" in again.json()["detail"]
        assert (await _report(client, second, "job", job["slug"])).status_code == 201
        count = await db.scalar(
            select(func.count())
            .select_from(ListingReport)
            .where(ListingReport.target_id == uuid.UUID(job["id"]))
        )
        assert count == 2

    @pytest.mark.parametrize(
        "body",
        [{"reason": "rude"}, {}, {"reason": "other", "detail": "x" * 1001}],
    )
    async def test_the_reason_is_from_a_fixed_list_and_the_detail_is_bounded(
        self, client: AsyncClient, db: AsyncSession, body: dict
    ) -> None:
        job, _, _ = await _listing(client, db)
        who, _ = await person(client)
        response = await client.post(f"/jobs/{job['slug']}/report", headers=who, json=body)
        assert response.status_code == 422

    async def test_a_blank_detail_is_no_detail(self, client: AsyncClient, db: AsyncSession) -> None:
        job, _, _ = await _listing(client, db)
        who, _ = await person(client)
        await _report(client, who, "job", job["slug"], detail="   ")
        row = await db.scalar(
            select(ListingReport).where(ListingReport.target_id == uuid.UUID(job["id"]))
        )
        assert row is not None and row.detail is None

    async def test_a_person_has_a_daily_budget(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPORT_SUBMISSIONS_PER_DAY", "2")
        get_settings.cache_clear()
        redis = get_redis()
        try:
            who, _ = await person(client)
            codes = []
            for _ in range(3):
                job, _, _ = await _listing(client, db)
                codes.append((await _report(client, who, "job", job["slug"])).status_code)
            assert codes == [201, 201, 429]
        finally:
            for key in await redis.keys("budget:listing-report*"):
                await redis.delete(key)
            monkeypatch.delenv("REPORT_SUBMISSIONS_PER_DAY")
            get_settings.cache_clear()

    async def test_the_event_names_the_listing_and_a_reason_never_the_reporter_or_the_words(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, _, _ = await _listing(client, db)
        who, user_id = await person(client)
        await _report(client, who, "job", job["slug"])
        event = await db.scalar(
            select(AnalyticsEvent).where(
                AnalyticsEvent.name == "listing_reported",
                AnalyticsEvent.subject_id == uuid.UUID(job["id"]),
            )
        )
        assert event is not None and event.payload == {"reason": "asks_for_money"}
        assert DETAIL not in str(event.payload) and str(user_id) not in str(event.payload)


async def _queue(client: AsyncClient, ops: dict[str, str], view: str = "open") -> dict:
    response = await client.get("/ops/reports", headers=ops, params={"view": view})
    assert response.status_code == 200, response.text
    return response.json()


class TestTheQueue:
    async def test_it_is_for_operators_of_either_tier_and_nobody_else(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        for tier in ("support", "admin"):
            ops = await operator(client, db, tier)
            assert (await client.get("/ops/reports", headers=ops)).status_code == 200
        stranger, _ = await person(client)
        refused = await client.get("/ops/reports", headers=stranger)
        nowhere = await client.get("/ops/definitely-not-a-route", headers=stranger)
        assert refused.status_code == 404 and refused.text == nowhere.text

    async def test_it_groups_by_listing_most_reporters_first_and_masks_the_reporter(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        busy, _, busy_org = await _listing(client, db)
        quiet, _, _ = await _listing(client, db)
        first, first_id = await person(client)
        second, _ = await person(client)
        me = (await client.get("/auth/me", headers=first)).json()
        await _report(client, first, "job", quiet["slug"], reason="other")
        await _report(client, first, "job", busy["slug"], reason="asks_for_money")
        await _report(client, second, "job", busy["slug"], reason="fake_or_misleading")

        ops = await operator(client, db)
        raw = await client.get("/ops/reports", headers=ops)
        body = raw.json()
        mine = [i for i in body["items"] if i["target_id"] in (busy["id"], quiet["id"])]
        assert [i["target_id"] for i in mine] == [busy["id"], quiet["id"]]
        group = mine[0]
        assert group["open_reports"] == 2
        assert group["reasons"] == {"asks_for_money": 1, "fake_or_misleading": 1}
        assert group["organisation"]["slug"] == busy_org and group["title"] == busy["title"]
        assert me["phone"] not in raw.text, "an operator sees a reporter only masked"
        assert all("*" in (r["reporter"]["phone"] or "") for r in group["reports"])
        assert body["open_listings"] >= 2

    async def test_a_listing_deleted_since_is_not_shown(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, headers, org = await _listing(client, db)
        who, _ = await person(client)
        await _report(client, who, "job", job["slug"])
        await client.delete(f"/org/{org}/jobs/{job['slug']}", headers=headers)
        ops = await operator(client, db)
        assert job["id"] not in {i["target_id"] for i in (await _queue(client, ops))["items"]}


class TestDecisions:
    async def test_a_dismissal_closes_every_open_report_on_the_listing_and_is_recorded(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, _, _ = await _listing(client, db)
        for _ in range(2):
            who, _ = await person(client)
            await _report(client, who, "job", job["slug"])
        support = await operator(client, db, "support")
        done = await client.post(
            f"/ops/reports/job/{job['id']}/dismiss",
            headers=support,
            json={"note": "Checked: the fee is refundable and stated up front."},
        )
        assert done.status_code == 200 and done.json()["reports_closed"] == 2
        statuses = (
            await db.scalars(
                select(ListingReport.status).where(ListingReport.target_id == uuid.UUID(job["id"]))
            )
        ).all()
        assert set(statuses) == {"dismissed"}
        assert (await client.get(f"/jobs/{job['slug']}")).status_code == 200
        event = await db.scalar(
            select(AnalyticsEvent).where(
                AnalyticsEvent.name == "listing_reports_dismissed",
                AnalyticsEvent.subject_id == uuid.UUID(job["id"]),
            )
        )
        assert event is not None and event.payload == {"reports": 2}

    async def test_dismissing_with_nothing_open_or_without_a_real_note_is_refused(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, _, _ = await _listing(client, db)
        support = await operator(client, db, "support")
        none = await client.post(
            f"/ops/reports/job/{job['id']}/dismiss",
            headers=support,
            json={"note": "Nothing to see here."},
        )
        assert none.status_code == 409
        short = await client.post(
            f"/ops/reports/job/{job['id']}/dismiss", headers=support, json={"note": "no"}
        )
        assert short.status_code == 422

    async def test_a_takedown_actions_the_reports_removes_the_listing_and_records_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, _, _ = await _listing(client, db)
        who, _ = await person(client)
        await _report(client, who, "job", job["slug"], reason="asks_for_money")
        admin = await operator(client, db, "admin")
        done = await client.post(
            f"/ops/listings/job/{job['id']}/takedown",
            headers=admin,
            json={"reason": "It asked applicants to pay a fee before an interview."},
        )
        assert done.status_code == 200 and done.json()["reports_closed"] == 1
        row = await db.scalar(
            select(ListingReport).where(ListingReport.target_id == uuid.UUID(job["id"]))
        )
        assert row is not None
        await db.refresh(row)
        assert row.status == "actioned" and row.handled_at is not None
        assert job["id"] not in {i["target_id"] for i in (await _queue(client, admin))["items"]}
        taken = await _queue(client, admin, "taken_down")
        assert job["id"] in {i["target_id"] for i in taken["items"]}
        event = await db.scalar(
            select(AnalyticsEvent).where(
                AnalyticsEvent.name == "listing_taken_down",
                AnalyticsEvent.subject_id == uuid.UUID(job["id"]),
            )
        )
        assert event is not None
        assert event.payload == {"reports": 1, "reasons": ["asks_for_money"]}

    async def test_a_refused_takedown_leaves_the_reports_open(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """One transaction: the second takedown is a 409 and must not close anything."""
        job, _, _ = await _listing(client, db)
        admin = await operator(client, db, "admin")
        reason = {"reason": "It asked applicants to pay a fee before an interview."}
        await client.post(f"/ops/listings/job/{job['id']}/takedown", headers=admin, json=reason)
        late, _ = await person(client)
        # A report filed after the takedown cannot be made (the listing is a draft), so file one
        # directly, as a stale open report would be.
        db.add(
            ListingReport(
                target_type="job",
                target_id=uuid.UUID(job["id"]),
                target_slug=job["slug"],
                target_title=job["title"],
                reporter_id=(await client.get("/auth/me", headers=late)).json()["id"],
                reason="other",
            )
        )
        await db.commit()
        again = await client.post(
            f"/ops/listings/job/{job['id']}/takedown", headers=admin, json=reason
        )
        assert again.status_code == 409
        # No rollback here: the suite's session is one outer transaction, so a rollback would
        # take the set-up with it. Nothing was flushed, so the database still says "open"; in
        # production the request's session closes without committing.
        still_open = await db.scalar(
            select(func.count())
            .select_from(ListingReport)
            .where(ListingReport.target_id == uuid.UUID(job["id"]), ListingReport.status == "open")
        )
        assert still_open == 1


class TestRetentionAndTheRightsOfTheReporter:
    async def test_a_closed_report_goes_after_its_retention_an_open_one_on_a_live_listing_never(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        old = datetime.now(UTC) - timedelta(days=400)
        recent = datetime.now(UTC) - timedelta(days=30)
        made: dict[str, ListingReport] = {}
        for label, status, handled in (
            ("old_closed", "dismissed", old),
            ("recent_closed", "actioned", recent),
            ("open", "open", None),
        ):
            job, _, _ = await _listing(client, db)
            who, uid = await person(client)
            report = ListingReport(
                target_type="job",
                target_id=uuid.UUID(job["id"]),
                target_slug=job["slug"],
                target_title=job["title"],
                reporter_id=uid,
                reason="other",
                status=status,
                handled_at=handled,
            )
            db.add(report)
            made[label] = report
        await db.commit()
        removed = await purge_expired(db, retention_days=365)
        assert removed >= 1
        left = {r.id for r in (await db.scalars(select(ListingReport))).all()}
        assert made["old_closed"].id not in left
        assert made["recent_closed"].id in left and made["open"].id in left

    async def test_a_report_about_a_deleted_listing_is_removed_even_if_open(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, headers, org = await _listing(client, db)
        who, _ = await person(client)
        await _report(client, who, "job", job["slug"])
        await client.delete(f"/org/{org}/jobs/{job['slug']}", headers=headers)
        assert await db.get(Job, uuid.UUID(job["id"])) is None
        await purge_expired(db, retention_days=365)
        left = await db.scalar(
            select(func.count())
            .select_from(ListingReport)
            .where(ListingReport.target_id == uuid.UUID(job["id"]))
        )
        assert left == 0

    async def test_the_export_lists_a_persons_own_reports_and_erasure_removes_them(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, _, _ = await _listing(client, db)
        mine, _ = await person(client)
        theirs, _ = await person(client)
        await _report(client, mine, "job", job["slug"])
        await _report(client, theirs, "job", job["slug"], reason="other")
        ops = await operator(client, db, "support")
        await client.post(
            f"/ops/reports/job/{job['id']}/dismiss",
            headers=ops,
            json={"note": "Internal: this applicant is the competitor's cousin."},
        )

        export = (await client.get("/me/account/export", headers=mine)).json()
        reports = export["listing_reports_made"]
        assert [(r["about"], r["reason"], r["detail"]) for r in reports] == [
            (job["title"], "asks_for_money", DETAIL)
        ]
        assert "competitor" not in str(export), "the operator's note is not the reporter's data"

        assert (await client.delete("/me/account", headers=mine)).status_code in (200, 204)
        left = (
            await db.scalars(
                select(ListingReport.reason).where(ListingReport.target_id == uuid.UUID(job["id"]))
            )
        ).all()
        assert list(left) == ["other"], "only the erased person's report goes"
