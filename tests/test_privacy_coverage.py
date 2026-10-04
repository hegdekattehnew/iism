"""What we erase, we can show (Sprint 48).

Erasure and export are two halves of the DPDP rights of access and of erasure, and for
seven sprints only one half was kept in step with the schema. Job alerts (Sprint 27),
ratings (Sprint 37), sponsorship offers (Sprint 41) and the notices addressed to a person
were all added, all correctly erased by their foreign keys, and none of them ever exported:
"we delete it but cannot show it".

A scan found the gap; a **guard** keeps it closed, in the project's usual pattern (the
route-delegation guard, the enumeration test, the boundary test). It walks the schema and
fails on any table holding a person's data that the export neither covers nor is excused
from, with the reason written down.

`notifications` has no foreign key -- the row names a recipient and holds no address, so no
schema walk finds it -- and is listed by name for that reason.
"""

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import api.main  # noqa: F401 - registers every model's table on the metadata
from api.core.database import Base
from api.modules.alerts.models import JobAlert, SponsorIntent
from api.modules.applications.models import Application, ApplicationReview
from api.modules.identity import Membership, Tenant, User
from api.modules.marketplace.models import CandidateProfile, Job
from api.modules.notifications.models import Notification
from api.modules.skills import Skill
from tests.test_privacy import _candidate, _organisation

# Tables that reference a person, and the key of the export document that shows them.
EXPORTED: dict[str, str] = {
    "candidate_profiles": "candidate_profile",
    "candidate_educations": "candidate_profile",
    "candidate_experiences": "candidate_profile",
    "candidate_certifications": "candidate_profile",
    "candidate_languages": "candidate_profile",
    "candidate_preferred_locations": "candidate_profile",
    "candidate_preferred_roles": "candidate_profile",
    "candidate_skills": "candidate_profile",
    "memberships": "memberships",
    "applications": "applications",
    "saved_jobs": "saved_jobs",
    "course_interests": "course_interests",
    "invitations": "invitations_sent",
    "analytics_events": "activity",
    "job_alerts": "job_alerts",
    "sponsor_intents": "sponsorship_offers",
    "application_reviews": "ratings_received",
    # No foreign key, so named rather than discovered.
    "notifications": "notices",
}

# Tables that reference a person and are **deliberately** not exported to them, each with the
# reason. A column here is an operator's or an organisation's act, never the data subject's.
EXEMPT: dict[str, str] = {
    "tenants": "`verified_by` is the operator who verified an organisation -- an operator's act "
    "on the organisation's record, not data held about the operator as a data subject.",
    "tenant_verification_events": "The operator's audit trail of decisions about an organisation. "
    "`actor_user_id` is `SET NULL` on erasure so the record outlives its author.",
    "role_alias_events": "The operator's audit trail of decisions about role aliases (Sprint 47); "
    "`actor_user_id` is `SET NULL` on erasure for the same reason.",
}

# Foreign keys into these tables mean "a person's data".
PERSON_TABLES = {"users", "candidate_profiles"}
# Referenced by no foreign key but addressed to a person.
NON_FK_PERSONAL = {"notifications"}


def person_tables(tables: Iterable[Table]) -> set[str]:
    """Every table with a foreign key into a person, plus the by-name ones."""
    found = set(NON_FK_PERSONAL)
    for table in tables:
        for fk in table.foreign_keys:
            if fk.column.table.name in PERSON_TABLES and table.name not in PERSON_TABLES:
                found.add(table.name)
    # A person's own tables are the profile and the account; the account is the export's
    # `account` block and the profile its `candidate_profile`, both asserted elsewhere.
    return found | {"candidate_profiles"}


def uncovered(found: set[str], exported: dict[str, str], exempt: dict[str, str]) -> set[str]:
    """Tables holding a person's data that the export neither shows nor is excused from."""
    return found - set(exported) - set(exempt)


class TestTheGuard:
    def test_it_finds_the_tables_that_hold_a_persons_data(self) -> None:
        """Asserts it **found** them before asserting anything about them: a walk that
        matches nothing would report a clean schema for ever."""
        found = person_tables(Base.metadata.tables.values())
        assert {"applications", "job_alerts", "sponsor_intents", "application_reviews"} <= found
        assert len(found) >= 15

    def test_every_such_table_is_exported_or_excused(self) -> None:
        found = person_tables(Base.metadata.tables.values())
        assert uncovered(found, EXPORTED, EXEMPT) == set(), (
            "A table holds a person's data and the export neither shows it nor excuses it. "
            "Export it in `privacy.service.export_account` and add it to EXPORTED, or add it to "
            "EXEMPT with the reason."
        )

    def test_nothing_listed_is_stale(self) -> None:
        """A renamed or dropped table must not linger in the lists as a false assurance."""
        known = set(Base.metadata.tables)
        assert set(EXPORTED) <= known, set(EXPORTED) - known
        assert set(EXEMPT) <= known, set(EXEMPT) - known

    def test_it_would_catch_a_new_table(self) -> None:
        """The detector fed a case it must reject, as the route-delegation guard is."""
        found = person_tables(Base.metadata.tables.values()) | {"a_future_table"}
        assert uncovered(found, EXPORTED, EXEMPT) == {"a_future_table"}

    def test_an_exemption_has_a_reason(self) -> None:
        assert all(len(reason) > 40 for reason in EXEMPT.values())

    def test_every_exported_key_is_a_real_key_of_the_document(self) -> None:
        """The names in EXPORTED are the document's actual keys: renaming one in the service
        without updating this file fails here rather than silently un-exporting a table."""
        import inspect

        from api.modules.privacy import service

        source = inspect.getsource(service.export_account)
        for key in set(EXPORTED.values()) - {"candidate_profile"}:
            assert f'"{key}"' in source, key
        assert '"candidate_profile"' in source


# ---------------------------------------------------------------- the data itself


async def _world(client: AsyncClient, db: AsyncSession) -> dict:
    """A candidate with one of everything, and the employer on the other side of it."""
    cand_headers, phone = await _candidate(client)
    emp_headers, slug = await _organisation(client, "Rating Hospital")
    cand_me = (await client.get("/auth/me", headers=cand_headers)).json()
    emp_me = (await client.get("/auth/me", headers=emp_headers)).json()
    await client.put("/me/profile", headers=cand_headers, json={"headline": "Export all of me"})
    cand_id, emp_id = uuid.UUID(cand_me["id"]), uuid.UUID(emp_me["id"])
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == cand_id))
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
    assert profile is not None and tenant is not None

    skill = Skill(
        slug=f"cov-{uuid.uuid4().hex[:8]}", name="Operate a coverage standard",
        skill_type="technical", nsqf_level=Decimal("3"),
        nos_code=f"COV/N{uuid.uuid4().int % 9000 + 1000}", source="nsqf",
    )  # fmt: skip
    job = Job(
        slug=f"cov-job-{uuid.uuid4().hex[:8]}", tenant_id=tenant.id, title="Coverage Cashier",
        employment_type="gig", status="published",
    )  # fmt: skip
    db.add_all([skill, job])
    await db.flush()
    application = Application(job_id=job.id, profile_id=profile.id, status="completed")
    db.add(application)
    await db.flush()
    db.add_all(
        [
            JobAlert(job_id=job.id, profile_id=profile.id),
            SponsorIntent(
                job_id=job.id,
                profile_id=profile.id,
                skill_id=skill.id,
                offered_by_user_id=emp_id,
                notified_at=datetime.now(UTC),
            ),  # fmt: skip
            # About the candidate, written by the employer.
            ApplicationReview(
                application_id=application.id,
                subject_role="worker",
                rating=4,
                comment="Reliable and quick",
                author_user_id=emp_id,
            ),  # fmt: skip
            # About the organisation, written by the candidate.
            ApplicationReview(
                application_id=application.id,
                subject_role="poster",
                rating=5,
                comment="Paid on time",
                author_user_id=cand_id,
            ),  # fmt: skip
            Notification(
                recipient_kind="user",
                recipient_id=cand_id,
                channel="in_app",
                template="job_alert",
                payload={"vacancy": "Coverage Cashier"},
            ),  # fmt: skip
        ]
    )
    await db.commit()
    return {
        "candidate": cand_headers, "employer": emp_headers, "phone": phone,
        "profile_id": profile.id, "application_id": application.id,
        "cand_id": cand_id, "emp_id": emp_id,
    }  # fmt: skip


class TestTheExportShowsWhatErasureDeletes:
    async def test_a_candidate_sees_each_of_them(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        w = await _world(client, db)
        body = (await client.get("/me/account/export", headers=w["candidate"])).json()

        assert [(a["vacancy"], a["organisation"]) for a in body["job_alerts"]] == [
            ("Coverage Cashier", "Rating Hospital")
        ]
        (offer,) = body["sponsorship_offers"]
        assert offer["standard"] == "Operate a coverage standard"
        assert offer["organisation"] == "Rating Hospital" and offer["told_at"] is not None
        # Said about them: the rating and the comment, and who it was by only as the organisation.
        (received,) = body["ratings_received"]
        assert (received["rating"], received["comment"]) == (4, "Reliable and quick")
        assert received["organisation"] == "Rating Hospital"
        # What they wrote, about the organisation.
        (given,) = body["ratings_given"]
        assert (given["rating"], given["comment"], given["about"]) == (
            5,
            "Paid on time",
            "the organisation",
        )
        assert [(n["template"], n["channel"], n["detail"]) for n in body["notices"]] == [
            ("job_alert", "in_app", {"vacancy": "Coverage Cashier"})
        ]

    async def test_it_names_nobody_else(self, client: AsyncClient, db: AsyncSession) -> None:
        """No employer address, no author id, no user id of the person who made an offer or
        wrote the rating about this candidate."""
        w = await _world(client, db)
        text = (await client.get("/me/account/export", headers=w["candidate"])).text
        assert str(w["emp_id"]) not in text
        assert "author" not in text and "offered_by" not in text
        employer_email = (await db.get(User, w["emp_id"])).email  # type: ignore[union-attr]
        assert employer_email and employer_email not in text

    async def test_an_employer_sees_what_they_wrote_without_the_workers_name(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        w = await _world(client, db)
        response = await client.get("/me/account/export", headers=w["employer"])
        body = response.json()
        assert [(r["rating"], r["about"]) for r in body["ratings_given"]] == [(4, "a worker")]
        # A rating about the organisation is the organisation's, not the employer-person's.
        assert body["ratings_received"] == []
        assert w["phone"] not in response.text
        assert str(w["cand_id"]) not in response.text

    async def test_an_empty_account_exports_empty_lists_not_missing_keys(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await _candidate(client)
        body = (await client.get("/me/account/export", headers=headers)).json()
        for key in (
            "job_alerts",
            "sponsorship_offers",
            "ratings_received",
            "ratings_given",
            "notices",
        ):
            assert body[key] == [], key


class TestWhatIsShownIsDeleted:
    async def test_erasure_takes_every_one_of_them(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The two halves, held to each other: every record the export now shows is gone
        after the account is."""
        w = await _world(client, db)

        async def counts() -> dict[str, int]:
            async def n(model: type, *where: object) -> int:
                return (await db.scalar(select(func.count()).select_from(model).where(*where))) or 0

            return {
                "job_alerts": await n(JobAlert, JobAlert.profile_id == w["profile_id"]),
                "sponsor_intents": await n(
                    SponsorIntent, SponsorIntent.profile_id == w["profile_id"]
                ),
                "reviews": await n(
                    ApplicationReview, ApplicationReview.application_id == w["application_id"]
                ),
                "notices": await n(Notification, Notification.recipient_id == w["cand_id"]),
                "memberships": await n(Membership, Membership.user_id == w["cand_id"]),
            }

        before = await counts()
        assert all(v > 0 for v in before.values()), before
        assert (await client.delete("/me/account", headers=w["candidate"])).status_code == 204
        assert await counts() == dict.fromkeys(before, 0)
