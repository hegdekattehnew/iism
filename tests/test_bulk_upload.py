"""Bulk upload of vacancies and courses (Sprint 51, ADR-063).

A spreadsheet is a lot of rows at once, so the rules worth pinning are the ones that stop a wrong
file doing wrong at volume: nothing is written by a check, a row that fails never blocks one that
passes, re-uploading a corrected file creates only what is new, a role expands to exactly what the
qualification says and never to a guess, and nothing a file creates is public until the separate
publish step.

The standards are the NSQF fixture's (`tests/fixtures/nsqf_sample.json`), imported into the test's
transaction, so the role and code resolution run against the real importer's output.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.nsqf.importer import import_nsqf
from api.adapters.nsqf.jsonfile import JsonFileNsqfSource
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.config import get_settings
from api.modules.analytics.models import AnalyticsEvent
from api.modules.geography.models import District, State
from api.modules.identity.models import Membership, Tenant
from api.modules.marketplace import bulk, course_publishing, publishing
from api.modules.marketplace.models import Course, Job
from api.modules.marketplace.schemas import CourseIn, CourseSkillIn, JobIn, JobSkillIn
from api.modules.skills.hierarchy import RoleAlias
from api.modules.skills.models import Skill

FIXTURE = Path(__file__).parent / "fixtures" / "nsqf_sample.json"

# What the importer makes of the fixture (checked, not assumed): Phlebotomy Technician requires
# HC/N0001 and HC/N0002 (both compulsory); General Duty Assistant requires HC/N0002; Retail Sales
# Associate has one compulsory (RT/N0001), one elective (RT/N0002) and one optional (RT/N0003).
HEADER = "external_ref,title,description,state,district,employment_type,standards,job_role"


@pytest.fixture
async def corpus(db: AsyncSession) -> None:
    await import_nsqf(db, JsonFileNsqfSource(FIXTURE))
    for code, (state_name, district) in enumerate(
        [("Tamil Nadu", "Chennai"), ("Maharashtra", "Pune")], start=9100
    ):
        state = State(state_code=code, slug=state_name.lower().replace(" ", "-"), name=state_name)
        db.add(state)
        await db.flush()
        db.add(District(district_code=code, name=district, state_id=state.id))
    await db.commit()


def _email() -> str:
    return f"bulk-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"


async def _org(client: AsyncClient, name: str, tenant_type: str = "employer") -> tuple[dict, str]:
    address = _email()
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": name,
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


async def _post(client: AsyncClient, path: str, text: str, headers: dict) -> Response:
    return await client.post(
        path, content=text.encode("utf-8"), headers={**headers, "content-type": "text/csv"}
    )


def _csv(*rows: str, header: str = HEADER) -> str:
    return "\n".join([header, *rows]) + "\n"


async def _count(db: AsyncSession, model: type[Job] | type[Course], tenant: str) -> int:
    tenant_id = await db.scalar(select(Tenant.id).where(Tenant.slug == tenant))
    return (
        await db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id))
    ) or 0


# ============================================================================= the file itself


class TestReadingTheFile:
    def test_a_byte_order_mark_and_windows_line_endings_are_tolerated(self) -> None:
        text = "﻿title,standards\r\nWard attendant,HC/N0001\r\n"
        rows, _notes, header = bulk.parse_file(text, "jobs")
        assert header == ["title", "standards"]
        assert rows[0].cells["title"] == "Ward attendant"

    def test_a_quoted_comma_and_a_quoted_newline_stay_in_one_cell(self) -> None:
        text = 'title,description\n"Ward attendant","Day shift,\nweekends off"\nCleaner,x\n'
        rows, _, _ = bulk.parse_file(text, "jobs")
        assert rows[0].cells["description"] == "Day shift,\nweekends off"
        # Rows are records, not lines: the cleaner is row 3 in the person's spreadsheet.
        assert [r.number for r in rows] == [2, 3]

    def test_devanagari_survives(self) -> None:
        rows, _, _ = bulk.parse_file("title,description\nवार्ड अटेंडेंट,दिन की पाली\n", "jobs")
        assert rows[0].cells["title"] == "वार्ड अटेंडेंट"

    def test_headers_are_forgiving_about_case_and_spaces(self) -> None:
        rows, _, header = bulk.parse_file("Title, Experience Min Years\nCook,2\n", "jobs")
        assert header == ["title", "experience_min_years"]
        assert rows[0].cells["experience_min_years"] == "2"

    def test_an_unknown_column_is_a_note_and_is_ignored(self) -> None:
        _rows, notes, _ = bulk.parse_file("title,colour\nCook,red\n", "jobs")
        assert notes == ["The column 'colour' is not recognised and was ignored."]

    def test_a_blank_record_is_skipped_and_numbering_still_matches_the_sheet(self) -> None:
        rows, _, _ = bulk.parse_file("title\nCook\n,\nCleaner\n", "jobs")
        assert [r.number for r in rows] == [2, 4]

    def test_a_missing_title_column_is_a_file_error(self) -> None:
        with pytest.raises(bulk.BulkFileError, match="must include: title"):
            bulk.parse_file("name,standards\nCook,x\n", "jobs")

    def test_a_repeated_column_is_a_file_error(self) -> None:
        with pytest.raises(bulk.BulkFileError, match="more than once"):
            bulk.parse_file("title,title\nA,B\n", "jobs")

    @pytest.mark.parametrize("text", ["", "   \n", "title\n"])
    def test_an_empty_file_is_a_file_error(self, text: str) -> None:
        with pytest.raises(bulk.BulkFileError):
            bulk.parse_file(text, "jobs")

    def test_more_rows_than_the_limit_is_refused_whole(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(get_settings(), "bulk_max_rows", 3)
        with pytest.raises(bulk.BulkFileError, match="At most 3 rows") as caught:
            bulk.parse_file("title\n" + "\n".join(f"Job {i}" for i in range(4)), "jobs")
        assert caught.value.status_code == 413
        # At the limit is fine.
        assert len(bulk.parse_file("title\nA\nB\nC\n", "jobs")[0]) == 3

    def test_a_file_that_is_not_utf8_says_how_to_save_it(self) -> None:
        with pytest.raises(bulk.BulkFileError, match="CSV UTF-8"):
            bulk.decode("title\nCafé".encode("latin-1"))

    def test_the_template_is_readable_by_the_parser_it_teaches(self) -> None:
        for kind in ("jobs", "courses"):
            rows, notes, header = bulk.parse_file(bulk.template_csv(kind), kind)  # type: ignore[arg-type]
            assert header == list(bulk.COLUMNS[kind])
            assert notes == []
            assert len(rows) == 2


# ============================================================================== checking vacancies


class TestCheckingVacancies:
    async def test_a_valid_row_is_ok_and_nothing_is_written(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Check Hospital")
        text = _csv("R1,Phlebotomist,Draws blood,Tamil Nadu,Chennai,full_time,HC/N0001:4:M,")

        response = await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)

        assert response.status_code == 200
        body = response.json()
        assert (body["ok"], body["errors"], body["created"], body["applied"]) == (1, 0, 0, False)
        (row,) = body["rows"]
        assert row["status"] == "ok" and row["row"] == 2
        assert row["standards"] == [
            {
                "code": "HC/N0001",
                "name": "Collect blood samples",
                "origin": "listed",
                "importance": 4,
                "mandatory": True,
                "level": None,
            }
        ]
        assert await _count(db, Job, org) == 0, "a check wrote something"

    async def test_a_code_in_the_wrong_case_still_resolves(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Case Hospital")
        body = (
            await _post(
                client, f"/org/{org}/jobs/bulk/check", _csv(",Phlebotomist,,,,,hc/n0001,"), headers
            )
        ).json()
        assert body["rows"][0]["status"] == "ok"
        assert body["rows"][0]["standards"][0]["code"] == "HC/N0001"

    async def test_an_unknown_code_is_that_rows_error_and_names_it(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Unknown Hospital")
        text = _csv(",Good,,,,,HC/N0001,", ",Bad,,,,,HC/N9999,")
        body = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()
        good, bad = body["rows"]
        assert good["status"] == "ok"
        assert bad["status"] == "error" and "HC/N9999" in bad["messages"][0]
        assert body["errors_csv"].splitlines()[0].endswith(",error")
        assert "Bad" in body["errors_csv"] and "Good" not in body["errors_csv"]

    async def test_a_retired_standard_is_refused(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        db.add(
            Skill(
                slug="retired-x",
                name="Retired",
                skill_type="technical",
                nos_code="OLD/N0001",
                source="legacy",
            )
        )
        await db.commit()
        headers, org = await _org(client, "Retired Hospital")
        body = (
            await _post(
                client, f"/org/{org}/jobs/bulk/check", _csv(",Cook,,,,,OLD/N0001,"), headers
            )
        ).json()
        assert body["rows"][0]["status"] == "error"
        assert "retired" in body["rows"][0]["messages"][0]

    @pytest.mark.parametrize(
        "token,fragment",
        [
            ("HC/N0001:9", "importance for HC/N0001 must be 1 to 5"),
            ("HC/N0001:3:X", "must be M"),
            ("HC/N0001:3:M:1", "too many parts"),
            (":3", "has no code"),
        ],
    )
    async def test_a_malformed_standard_token_says_what_is_wrong(
        self, client: AsyncClient, corpus: None, token: str, fragment: str
    ) -> None:
        headers, org = await _org(client, "Token Hospital")
        row = f'1,Cook,,,,,"{token}",'
        body = (await _post(client, f"/org/{org}/jobs/bulk/check", _csv(row), headers)).json()
        assert body["rows"][0]["status"] == "error"
        assert fragment in " ".join(body["rows"][0]["messages"])

    async def test_a_row_without_standards_is_a_warning_not_an_error(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Bare Hospital")
        body = (
            await _post(client, f"/org/{org}/jobs/bulk/check", _csv(",Receptionist,,,,,,"), headers)
        ).json()
        assert body["rows"][0]["status"] == "warning"
        assert "cannot be published" in body["rows"][0]["messages"][0]

    async def test_the_forms_own_rules_apply_to_a_row(
        self, client: AsyncClient, corpus: None
    ) -> None:
        """Every cell goes through `JobIn`, so the limits cannot drift from the form's."""
        headers, org = await _org(client, "Rules Hospital")
        header = "title,positions,experience_min_years,experience_max_years,employment_type"
        text = _csv(
            "Hi,1,0,0,full_time",
            "Cook,0,0,0,full_time",
            "Cook,1,5,2,full_time",
            "Cook,1,0,0,freelance",
            "Cook,x,0,0,full_time",
            header=header,
        )
        rows = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()["rows"]
        assert all(r["status"] == "error" for r in rows)
        joined = [" ".join(r["messages"]) for r in rows]
        assert "title" in joined[0]
        assert "positions" in joined[1]
        assert "experience_max_years" in joined[2]
        assert "freelance" in joined[3] and "full_time" in joined[3]
        assert "'x' is not a number" in joined[4]

    async def test_a_gig_needs_a_date_and_a_place(self, client: AsyncClient, corpus: None) -> None:
        headers, org = await _org(client, "Gig Hospital")
        header = "title,employment_type,district,closes_at,standards"
        text = _csv(
            "Shift,gig,,2999-01-01,HC/N0001",  # no place
            "Shift,gig,Chennai,,HC/N0001",  # no end
            "Shift,gig,Chennai,2999-01-01,HC/N0001",
            header=header,
        )
        rows = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()["rows"]
        assert [r["status"] for r in rows] == ["error", "error", "ok"]
        assert "needs a place" in rows[0]["messages"][0]
        assert "closes_at" in rows[1]["messages"][0]

    async def test_an_unrecognised_district_is_a_warning_for_a_vacancy_and_an_error_for_a_gig(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Place Hospital")
        header = "title,employment_type,district,closes_at,standards"
        text = _csv(
            "Cook,full_time,Nowhereville,,HC/N0001",
            "Shift,gig,Nowhereville,2999-01-01,HC/N0001",
            header=header,
        )
        rows = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()["rows"]
        assert rows[0]["status"] == "warning" and "not recognised" in rows[0]["messages"][0]
        assert rows[1]["status"] == "error"

    async def test_a_description_with_a_phone_or_email_is_warned_not_blocked(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Contact Hospital")
        text = _csv(
            ',Cook,"Call 98765 43210 now",,,,HC/N0001,',
            ",Cook2,Write to hr@example.com,,,,HC/N0001,",
            ",Cook3,Plain text,,,,HC/N0001,",
        )
        rows = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()["rows"]
        assert [r["status"] for r in rows] == ["warning", "warning", "ok"]
        assert "public once published" in rows[0]["messages"][0]

    async def test_an_unquoted_comma_in_a_text_cell_is_named_as_the_cause(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Comma Hospital")
        text = f"{HEADER}\n1,Cook,Cooks, bakes and serves,Tamil Nadu,Chennai,full_time,HC/N0001,\n"
        row = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()["rows"][0]
        assert row["status"] == "error"
        assert "double quotes" in row["messages"][0]

    async def test_a_date_means_the_end_of_that_day_in_india(self) -> None:
        problems: list[str] = []
        value = bulk._closes_at({"closes_at": "2026-12-31"}, problems)
        assert value is not None and not problems
        assert value.utcoffset().total_seconds() == 5.5 * 3600  # type: ignore[union-attr]
        assert (value.hour, value.minute) == (23, 59)
        bulk._closes_at({"closes_at": "31/12/2026"}, problems)
        assert "YYYY-MM-DD" in problems[0]


# ================================================================================ job roles


class TestJobRoles:
    async def test_a_role_expands_to_exactly_its_compulsory_standards(
        self, client: AsyncClient, corpus: None
    ) -> None:
        """Retail Sales Associate lists RT/N0001 (compulsory), RT/N0002 (elective) and RT/N0003
        (optional). An elective is "choose one of these", so folding it in would turn that into
        "all of these are required" -- the same distinction `course_role_alignment` draws."""
        headers, org = await _org(client, "Role Store")
        body = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/check",
                _csv(",Sales,,,,,,Retail Sales Associate"),
                headers,
            )
        ).json()
        (row,) = body["rows"]
        assert row["status"] == "ok"
        assert [s["code"] for s in row["standards"]] == ["RT/N0001"]
        assert row["standards"][0]["origin"] == "role"
        assert row["standards"][0]["importance"] == 3

    async def test_mandatory_defaults_to_no_and_yes_opts_in(
        self, client: AsyncClient, corpus: None
    ) -> None:
        """Making every compulsory unit mandatory would cap every candidate missing one at 45
        (ADR-036); a role's units are rarely all an employer's real must-haves."""
        headers, org = await _org(client, "Mandatory Hospital")
        header = "title,job_role,role_standards_mandatory"
        text = _csv(
            "A,Phlebotomy Technician,",
            "B,Phlebotomy Technician,no",
            "C,Phlebotomy Technician,yes",
            "D,Phlebotomy Technician,maybe",
            header=header,
        )
        rows = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()["rows"]
        assert [s["mandatory"] for s in rows[0]["standards"]] == [False, False]
        assert [s["mandatory"] for s in rows[1]["standards"]] == [False, False]
        assert [s["mandatory"] for s in rows[2]["standards"]] == [True, True]
        assert rows[3]["status"] == "error" and "yes or no" in rows[3]["messages"][0]

    async def test_a_listed_standard_wins_over_the_expansion(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Win Hospital")
        header = "title,standards,job_role,role_standards_mandatory"
        text = _csv("A,HC/N0001:5:M,Phlebotomy Technician,no", header=header)
        (row,) = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()["rows"]
        by_code = {s["code"]: s for s in row["standards"]}
        assert set(by_code) == {"HC/N0001", "HC/N0002"}
        assert (by_code["HC/N0001"]["importance"], by_code["HC/N0001"]["mandatory"]) == (5, True)
        assert by_code["HC/N0001"]["origin"] == "listed"
        assert by_code["HC/N0002"]["origin"] == "role"

    async def test_an_exact_title_resolves_in_any_case_and_spacing(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Case Role Hospital")
        (row,) = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/check",
                _csv(",Alpha,,,,,,  general   DUTY assistant "),
                headers,
            )
        ).json()["rows"]
        assert row["status"] == "ok"
        assert [s["code"] for s in row["standards"]] == ["HC/N0002"]

    async def test_a_near_miss_is_not_a_role_and_the_hint_is_never_applied(
        self, client: AsyncClient, corpus: None
    ) -> None:
        """ "phlebotomy tech" reaches the real role by *prefix*. Role search would offer it; a
        spreadsheet must not take it, because a guess about a role is a claim about every
        vacancy built from it."""
        headers, org = await _org(client, "Guess Hospital")
        (row,) = (
            await _post(
                client, f"/org/{org}/jobs/bulk/check", _csv(",Alpha,,,,,,phlebotomy tech"), headers
            )
        ).json()["rows"]
        assert row["status"] == "error"
        assert "no role is titled 'phlebotomy tech'" in row["messages"][0]
        assert "Phlebotomy Technician" in row["messages"][0], "the hint should be offered"
        assert row["standards"] == [], "the hint must not be applied"

    async def test_an_alias_resolves_only_when_it_is_the_cells_own_words(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        db.add(RoleAlias(surface_form="ward boy", job_role="General Duty Assistant"))
        await db.commit()
        headers, org = await _org(client, "Alias Hospital")
        rows = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/check",
                _csv(",Alpha,,,,,,ward boy", ",Beta,,,,,,ward"),
                headers,
            )
        ).json()["rows"]
        assert rows[0]["status"] == "ok"
        assert [s["code"] for s in rows[0]["standards"]] == ["HC/N0002"]
        assert rows[1]["status"] == "error", "a prefix of an alias is a guess about a guess"

    async def test_too_many_resulting_standards_is_an_error(
        self, client: AsyncClient, corpus: None, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """The largest real role has 65 compulsory standards; a listing carries at most 50."""
        monkeypatch.setattr(bulk, "MAX_STANDARDS", 1)
        headers, org = await _org(client, "Big Hospital")
        (row,) = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/check",
                _csv(",Alpha,,,,,,Phlebotomy Technician"),
                headers,
            )
        ).json()["rows"]
        assert row["status"] == "error"
        assert "more than the 1" in row["messages"][0]

    async def test_the_standards_cap_is_the_vacancy_forms_own(self) -> None:
        """A bulk row may not carry more standards than `JobIn` accepts; both say 50."""
        assert bulk.MAX_STANDARDS == 50
        fields = JobIn.model_fields["skills"]
        limits = [m.max_length for m in fields.metadata if hasattr(m, "max_length")]
        assert limits == [bulk.MAX_STANDARDS]

    async def test_a_disability_track_only_role_is_a_warning(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """ADR-050: a PwD pack's standards are specific to that track."""
        from api.modules.skills.service import RoleHit

        hit = RoleHit(
            slug="pwd-x",
            qp_code="PWD/Q0001",
            job_role="Cook (Divyangjan)",
            nsqf_level=3.0,
            sector_name=None,
            standards_count=1,
            variants=1,
            matched_on="Cook (Divyangjan)",
            match_kind="exact",
        )

        async def fake_search(db, query, *, limit=20):  # type: ignore[no-untyped-def]
            return [hit]

        class _Standard:
            requirement = "compulsory"

            class skill:  # noqa: N801
                nos_code = "PWD/N0001"
                name = "Prepare food"
                slug = "prepare-food"
                source = "nsqf"
                nsqf_level = None

        class _Role:
            standards = [_Standard]

        async def fake_standards(db, slug):  # type: ignore[no-untyped-def]
            return _Role()

        monkeypatch.setattr(bulk, "search_roles", fake_search)
        monkeypatch.setattr(bulk, "standards_for_role", fake_standards)

        role = await bulk._resolve_role(None, "Cook (Divyangjan)")  # type: ignore[arg-type]

        assert role.error is None
        assert role.warning is not None and "disability-track" in role.warning


# ============================================================================== applying vacancies


class TestApplyingVacancies:
    async def test_valid_rows_become_drafts_and_nothing_is_published(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Apply Hospital")
        text = _csv(
            "R1,Phlebotomist,Draws blood,Tamil Nadu,Chennai,full_time,HC/N0001:4:M,",
            "R2,Sales,,,,part_time,,Retail Sales Associate",
        )

        body = (await _post(client, f"/org/{org}/jobs/bulk/apply", text, headers)).json()

        assert (body["created"], body["errors"], body["applied"]) == (2, 0, True)
        jobs = (
            await db.scalars(
                select(Job).join(Tenant, Tenant.id == Job.tenant_id).where(Tenant.slug == org)
            )
        ).all()
        assert {j.status for j in jobs} == {"draft"}, "an upload must never publish"
        assert {j.external_ref for j in jobs} == {"R1", "R2"}
        public = (await client.get("/jobs")).json()
        assert all(j["slug"] not in {r["slug"] for r in body["rows"]} for j in public["items"])

    async def test_a_row_applied_in_bulk_equals_the_same_row_through_the_single_writer(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        """The oracle: bulk goes *through* `create_job`, so it equals the one-at-a-time result."""
        headers, org = await _org(client, "Oracle Hospital")
        headers2, org2 = await _org(client, "Oracle Hospital Two")
        await _post(
            client,
            f"/org/{org}/jobs/bulk/apply",
            _csv(
                "R1,Phlebotomist,Draws blood,Tamil Nadu,Chennai,part_time,HC/N0001:4:M; HC/N0002,"
            ),
            headers,
        )
        tenant2 = await db.scalar(select(Tenant).where(Tenant.slug == org2))
        assert tenant2 is not None
        direct = await publishing.create_job(
            db,
            tenant2.id,
            JobIn(
                title="Phlebotomist",
                description="Draws blood",
                location_state="Tamil Nadu",
                location_district="Chennai",
                employment_type="part_time",
                skills=[
                    JobSkillIn(
                        skill_slug="collect-blood-samples-hc-n0001", importance=4, is_mandatory=True
                    ),
                    JobSkillIn(skill_slug="maintain-a-sterile-field-hc-n0002"),
                ],
            ),
        )
        via_file = await db.scalar(
            select(Job).join(Tenant, Tenant.id == Job.tenant_id).where(Tenant.slug == org)
        )
        assert via_file is not None
        for field in (
            "title",
            "description",
            "location_state",
            "location_district",
            "employment_type",
            "state_id",
            "district_id",
            "status",
            "positions",
            "experience_min_years",
        ):
            assert getattr(via_file, field) == getattr(direct, field), field
        got = {(s.skill.nos_code, s.importance, s.is_mandatory) for s in via_file.skills}
        want = {(s.skill.nos_code, s.importance, s.is_mandatory) for s in direct.skills}
        assert got == want
        assert via_file.slug == "phlebotomist-chennai" and direct.slug == "phlebotomist-chennai-2"

    async def test_a_bad_row_never_blocks_a_good_one(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Mixed Hospital")
        text = _csv(",Good one,,,,,HC/N0001,", ",Bad one,,,,,NOPE/N1,", ",Good two,,,,,HC/N0002,")
        body = (await _post(client, f"/org/{org}/jobs/bulk/apply", text, headers)).json()
        assert [r["status"] for r in body["rows"]] == ["ok", "error", "ok"]
        assert body["created"] == 2
        assert await _count(db, Job, org) == 2

    async def test_re_uploading_the_same_file_creates_nothing(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Again Hospital")
        text = _csv("R1,Phlebotomist,,,,,HC/N0001,", ",Cleaner,,Tamil Nadu,Chennai,,HC/N0002,")
        first = (await _post(client, f"/org/{org}/jobs/bulk/apply", text, headers)).json()
        second = (await _post(client, f"/org/{org}/jobs/bulk/apply", text, headers)).json()

        assert first["created"] == 2
        assert (second["created"], second["skipped"]) == (0, 2)
        assert await _count(db, Job, org) == 2
        assert "R1" in second["rows"][0]["messages"][0], "a skip must say why"
        assert second["rows"][0]["slug"] == first["rows"][0]["slug"], "and which one it matched"

    async def test_the_fix_and_upload_again_loop_creates_only_the_repaired_rows(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Loop Hospital")
        broken = _csv("A,Alpha,,,,,HC/N0001,", "B,Beta,,,,,WRONG/N1,", "C,Gamma,,,,,HC/N0002,")
        first = (await _post(client, f"/org/{org}/jobs/bulk/apply", broken, headers)).json()
        assert (first["created"], first["errors"]) == (2, 1)

        fixed = _csv("A,Alpha,,,,,HC/N0001,", "B,Beta,,,,,HC/N0001,", "C,Gamma,,,,,HC/N0002,")
        second = (await _post(client, f"/org/{org}/jobs/bulk/apply", fixed, headers)).json()

        assert [r["status"] for r in second["rows"]] == ["skip", "ok", "skip"]
        assert second["created"] == 1
        assert await _count(db, Job, org) == 3

    async def test_the_error_report_is_the_original_rows_plus_a_reason(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Report Hospital")
        text = _csv("A,Alpha,,,,,HC/N0001,", 'B,"Be, ta",,,,,WRONG/N1,')
        body = (await _post(client, f"/org/{org}/jobs/bulk/apply", text, headers)).json()
        lines = body["errors_csv"].strip().splitlines()
        assert lines[0] == HEADER + ",error"
        assert len(lines) == 2
        assert lines[1].startswith('B,"Be, ta"'), "the row comes back exactly as it was uploaded"
        assert "WRONG/N1" in lines[1].split(",")[-1] or "WRONG/N1" in lines[1]

    async def test_external_ref_is_unique_per_organisation_not_globally(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        h1, o1 = await _org(client, "Ref One")
        h2, o2 = await _org(client, "Ref Two")
        text = _csv("SAME-1,Phlebotomist,,,,,HC/N0001,")
        a = (await _post(client, f"/org/{o1}/jobs/bulk/apply", text, h1)).json()
        b = (await _post(client, f"/org/{o2}/jobs/bulk/apply", text, h2)).json()
        assert (a["created"], b["created"]) == (1, 1)

    async def test_the_same_title_in_another_organisation_is_not_a_duplicate(
        self, client: AsyncClient, corpus: None
    ) -> None:
        h1, o1 = await _org(client, "Title One")
        h2, o2 = await _org(client, "Title Two")
        text = _csv(",Phlebotomist,,Tamil Nadu,Chennai,,HC/N0001,")
        await _post(client, f"/org/{o1}/jobs/bulk/apply", text, h1)
        second = (await _post(client, f"/org/{o2}/jobs/bulk/check", text, h2)).json()
        assert second["rows"][0]["status"] == "ok"

    async def test_a_different_district_is_a_different_vacancy(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "District Hospital")
        await _post(
            client,
            f"/org/{org}/jobs/bulk/apply",
            _csv(",Nurse,,Tamil Nadu,Chennai,,HC/N0001,"),
            headers,
        )
        body = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/check",
                _csv(
                    ",Nurse,,Tamil Nadu,Chennai,,HC/N0001,", ",Nurse,,Maharashtra,Pune,,HC/N0001,"
                ),
                headers,
            )
        ).json()
        assert [r["status"] for r in body["rows"]] == ["skip", "ok"]

    async def test_a_repeated_row_in_one_file_is_skipped_and_points_at_the_first(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Repeat Hospital")
        text = _csv(
            "X,Alpha,,,,,HC/N0001,",
            "X,Alpha again,,,,,HC/N0001,",
            ",Beta,,,,,HC/N0001,",
            ",Beta,,,,,HC/N0002,",
        )
        body = (await _post(client, f"/org/{org}/jobs/bulk/apply", text, headers)).json()
        assert [r["status"] for r in body["rows"]] == ["ok", "skip", "ok", "skip"]
        assert "row 2" in body["rows"][1]["messages"][0]
        assert "row 4" in body["rows"][3]["messages"][0]
        assert await _count(db, Job, org) == 2

    async def test_the_upload_is_recorded_with_counts_and_no_content(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Event Hospital")
        await _post(
            client,
            f"/org/{org}/jobs/bulk/apply",
            _csv(",Secret title,,,,,HC/N0001,", ",Broken,,,,,NOPE/N1,"),
            headers,
        )
        tenant_id = await db.scalar(select(Tenant.id).where(Tenant.slug == org))
        event = await db.scalar(
            select(AnalyticsEvent).where(
                AnalyticsEvent.name == "jobs_bulk_uploaded", AnalyticsEvent.subject_id == tenant_id
            )
        )
        assert event is not None
        assert event.payload == {"rows": 2, "created": 1, "skipped": 0, "rejected": 1}
        assert "Secret" not in str(event.payload)

    async def test_a_check_records_nothing(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Quiet Hospital")
        await _post(client, f"/org/{org}/jobs/bulk/check", _csv(",Alpha,,,,,HC/N0001,"), headers)
        tenant_id = await db.scalar(select(Tenant.id).where(Tenant.slug == org))
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(AnalyticsEvent.subject_id == tenant_id)
            )
        ) == 0


# ================================================================================= the daily cap


class TestTheDailyCap:
    async def test_rows_past_the_cap_are_refused_in_file_order_by_check_and_apply_alike(
        self, client: AsyncClient, db: AsyncSession, corpus: None, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(get_settings(), "bulk_rows_per_day_unverified", 2)
        headers, org = await _org(client, "Cap Hospital")
        text = _csv(",Alpha,,,,,HC/N0001,", ",Beta,,,,,HC/N0001,", ",Gamma,,,,,HC/N0001,")

        checked = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()
        applied = (await _post(client, f"/org/{org}/jobs/bulk/apply", text, headers)).json()

        for body in (checked, applied):
            assert [r["status"] for r in body["rows"]] == ["ok", "ok", "error"]
            assert "daily limit" in body["rows"][2]["messages"][0]
            assert body["daily_limit"] == 2
        assert checked["remaining_today"] == 2 and applied["remaining_today"] == 0
        assert await _count(db, Job, org) == 2

    async def test_hand_made_listings_count_toward_the_cap(
        self, client: AsyncClient, corpus: None, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(get_settings(), "bulk_rows_per_day_unverified", 2)
        headers, org = await _org(client, "Hand Hospital")
        made = await client.post(
            f"/org/{org}/jobs", headers=headers, json={"title": "Made by hand", "skills": []}
        )
        assert made.status_code == 201
        body = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/check",
                _csv(",Alpha,,,,,HC/N0001,", ",Beta,,,,,HC/N0001,"),
                headers,
            )
        ).json()
        assert [r["status"] for r in body["rows"]] == ["ok", "error"]

    async def test_the_window_is_a_rolling_day(
        self, client: AsyncClient, db: AsyncSession, corpus: None, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """A listing from two days ago is free again; one from an hour ago still counts."""
        monkeypatch.setattr(get_settings(), "bulk_rows_per_day_unverified", 2)
        headers, org = await _org(client, "Old Hospital")
        for title, age in (
            ("Made last week", timedelta(days=2)),
            ("Made lately", timedelta(hours=1)),
        ):
            made = await client.post(
                f"/org/{org}/jobs", headers=headers, json={"title": title, "skills": []}
            )
            assert made.status_code == 201
            await db.execute(
                update(Job)
                .where(Job.slug == made.json()["slug"])
                .values(created_at=datetime.now(UTC).replace(tzinfo=None) - age)
            )
        await db.commit()
        body = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/check",
                _csv(",Alpha,,,,,HC/N0001,", ",Beta,,,,,HC/N0001,"),
                headers,
            )
        ).json()
        assert [r["status"] for r in body["rows"]] == ["ok", "error"]
        assert body["remaining_today"] == 1

    async def test_a_verified_organisation_gets_the_higher_cap(
        self, client: AsyncClient, db: AsyncSession, corpus: None, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(get_settings(), "bulk_rows_per_day_unverified", 1)
        monkeypatch.setattr(get_settings(), "bulk_rows_per_day_verified", 3)
        headers, org = await _org(client, "Verified Hospital")
        text = _csv(",Alpha,,,,,HC/N0001,", ",Beta,,,,,HC/N0001,", ",Gamma,,,,,HC/N0001,")
        before = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == org))
        assert tenant is not None
        tenant.verified_at = datetime.now(UTC)
        tenant.verified_by = await db.scalar(
            select(Membership.user_id).where(Membership.tenant_id == tenant.id)
        )
        tenant.verification_note = "Checked the registration certificate"
        await db.commit()
        after = (await _post(client, f"/org/{org}/jobs/bulk/check", text, headers)).json()

        assert (before["daily_limit"], before["errors"]) == (1, 2)
        assert (after["daily_limit"], after["errors"]) == (3, 0)

    async def test_a_file_over_the_row_limit_is_refused_whole_with_413(
        self, client: AsyncClient, db: AsyncSession, corpus: None, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(get_settings(), "bulk_max_rows", 2)
        headers, org = await _org(client, "Long Hospital")
        response = await _post(
            client,
            f"/org/{org}/jobs/bulk/apply",
            _csv(",Alpha,,,,,HC/N0001,", ",Beta,,,,,HC/N0001,", ",Gamma,,,,,HC/N0001,"),
            headers,
        )
        assert response.status_code == 413
        assert await _count(db, Job, org) == 0, "a file past the limit must write nothing at all"


# ================================================================================== publishing


class TestPublishingABatch:
    async def test_publish_applies_the_single_routes_own_rules_per_row(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Publish Hospital")
        applied = (
            await _post(
                client,
                f"/org/{org}/jobs/bulk/apply",
                _csv(",Has standards,,,,,HC/N0001,", ",No standards,,,,,,"),
                headers,
            )
        ).json()
        slugs = [r["slug"] for r in applied["rows"]]

        response = await client.post(
            f"/org/{org}/jobs/bulk/publish", headers=headers, json={"slugs": [*slugs, "not-mine"]}
        )

        assert response.status_code == 200
        body = response.json()
        assert (body["published"], body["refused"]) == (1, 2)
        by_slug = {r["slug"]: r for r in body["results"]}
        assert by_slug[slugs[0]]["published"] is True
        assert "at least one required standard" in by_slug[slugs[1]]["message"]
        assert by_slug["not-mine"]["message"] == "Job not found"
        listing = (await client.get("/jobs")).json()
        public = {j["slug"] for j in listing["items"]}
        assert slugs[0] in public and slugs[1] not in public

    async def test_another_organisations_slug_is_not_found_never_published(
        self, client: AsyncClient, corpus: None
    ) -> None:
        h1, o1 = await _org(client, "Owner Hospital")
        h2, o2 = await _org(client, "Thief Hospital")
        made = (
            await _post(client, f"/org/{o1}/jobs/bulk/apply", _csv(",Mine,,,,,HC/N0001,"), h1)
        ).json()
        slug = made["rows"][0]["slug"]
        stolen = await client.post(
            f"/org/{o2}/jobs/bulk/publish", headers=h2, json={"slugs": [slug]}
        )
        assert stolen.json()["results"][0] == {
            "slug": slug,
            "published": False,
            "message": "Job not found",
        }

    async def test_the_bulk_publish_route_is_not_captured_by_the_single_slug_route(
        self, client: AsyncClient, corpus: None
    ) -> None:
        """`POST /jobs/{slug}/publish` exists, so `/jobs/bulk/publish` would be taken for a job
        called `bulk` if the routers were declared the other way round."""
        headers, org = await _org(client, "Route Hospital")
        response = await client.post(
            f"/org/{org}/jobs/bulk/publish", headers=headers, json={"slugs": ["x"]}
        )
        assert response.status_code == 200
        assert "results" in response.json()

    async def test_publish_is_capped_at_two_hundred_slugs(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Big Publish")
        response = await client.post(
            f"/org/{org}/jobs/bulk/publish",
            headers=headers,
            json={"slugs": [f"s{i}" for i in range(201)]},
        )
        assert response.status_code == 422


# ===================================================================================== the routes


class TestTheRoutes:
    async def test_the_template_is_served_as_csv(self, client: AsyncClient, corpus: None) -> None:
        headers, org = await _org(client, "Template Hospital")
        response = await client.get(f"/org/{org}/jobs/bulk/template", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        assert response.text.splitlines()[0] == ",".join(bulk.COLUMNS["jobs"])

    async def test_the_body_limit_is_larger_for_the_two_upload_routes_and_only_those(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Limit Hospital")
        big = _csv(*[f',Job {i},"{"x" * 1500}",,,,HC/N0001,' for i in range(190)])
        assert len(big) > 256 * 1024, "the fixture must exceed the ordinary limit"

        upload = await _post(client, f"/org/{org}/jobs/bulk/check", big, headers)
        ordinary = await client.post(
            f"/org/{org}/jobs", headers=headers, json={"title": "x", "description": "y" * 300_000}
        )

        assert upload.status_code == 200
        assert ordinary.status_code == 413

    async def test_a_body_past_even_the_upload_limit_is_413(
        self, client: AsyncClient, corpus: None, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(get_settings(), "max_bulk_body_bytes", 1000)
        headers, org = await _org(client, "Huge Hospital")
        response = await _post(
            client, f"/org/{org}/jobs/bulk/check", "title\n" + "x" * 2000, headers
        )
        assert response.status_code == 413

    async def test_a_file_error_is_a_422_with_the_reason(
        self, client: AsyncClient, corpus: None
    ) -> None:
        headers, org = await _org(client, "Bad File Hospital")
        response = await _post(client, f"/org/{org}/jobs/bulk/check", "name,x\nCook,1\n", headers)
        assert response.status_code == 422
        assert "must include: title" in response.json()["detail"]

    async def test_a_provider_cannot_upload_vacancies_nor_an_employer_courses(
        self, client: AsyncClient, corpus: None
    ) -> None:
        provider, p_org = await _org(client, "A Provider", "course_provider")
        employer, e_org = await _org(client, "An Employer")
        text = _csv(",Alpha,,,,,HC/N0001,")
        assert (
            await _post(client, f"/org/{p_org}/jobs/bulk/check", text, provider)
        ).status_code == 403
        assert (
            await _post(client, f"/org/{e_org}/courses/bulk/check", text, employer)
        ).status_code == 403

    async def test_a_stranger_gets_the_same_404_as_for_an_organisation_that_does_not_exist(
        self, client: AsyncClient, corpus: None
    ) -> None:
        stranger, _ = await _org(client, "Stranger")
        _, org = await _org(client, "Someone Else")
        text = _csv(",Alpha,,,,,HC/N0001,")
        real = await _post(client, f"/org/{org}/jobs/bulk/apply", text, stranger)
        ghost = await _post(
            client, f"/org/no-such-org-{uuid.uuid4().hex[:6]}/jobs/bulk/apply", text, stranger
        )
        assert (
            (real.status_code, real.json())
            == (ghost.status_code, ghost.json())
            == (404, ghost.json())
        )


# ================================================================================= courses


COURSE_HEADER = (
    "external_ref,title,description,mode,language,duration_hours,fee_inr,nsqf_level,"
    "standards,job_role"
)


class TestCourses:
    async def test_a_course_check_apply_and_publish_round_trip(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Course Academy", "course_provider")
        text = _csv(
            "C1,Phlebotomy basics,Eight weeks,offline,both,320,12000,4,HC/N0001:4; HC/N0002,",
            "C2,Retail course,,online,en,,,,,Retail Sales Associate",
            header=COURSE_HEADER,
        )

        checked = (await _post(client, f"/org/{org}/courses/bulk/check", text, headers)).json()
        assert [r["status"] for r in checked["rows"]] == ["ok", "ok"]
        assert {s["code"]: s["level"] for s in checked["rows"][0]["standards"]} == {
            "HC/N0001": 4.0,
            "HC/N0002": 4.0,  # unlisted level: the standard's own
        }
        assert [s["code"] for s in checked["rows"][1]["standards"]] == ["RT/N0001"]
        assert await _count(db, Course, org) == 0

        applied = (await _post(client, f"/org/{org}/courses/bulk/apply", text, headers)).json()
        assert applied["created"] == 2
        courses = (
            await db.scalars(
                select(Course).join(Tenant, Tenant.id == Course.tenant_id).where(Tenant.slug == org)
            )
        ).all()
        assert {c.status for c in courses} == {"draft"}
        assert {c.external_ref for c in courses} == {"C1", "C2"}

        published = (
            await client.post(
                f"/org/{org}/courses/bulk/publish",
                headers=headers,
                json={"slugs": [r["slug"] for r in applied["rows"]]},
            )
        ).json()
        assert published["published"] == 2

    async def test_a_course_row_equals_the_same_row_through_the_single_writer(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Course Oracle", "course_provider")
        _h2, org2 = await _org(client, "Course Oracle Two", "course_provider")
        await _post(
            client,
            f"/org/{org}/courses/bulk/apply",
            _csv(",Phlebotomy,Notes,hybrid,hi,100,5000,4,HC/N0001:4.5,", header=COURSE_HEADER),
            headers,
        )
        tenant2 = await db.scalar(select(Tenant).where(Tenant.slug == org2))
        assert tenant2 is not None
        direct = await course_publishing.create_course(
            db,
            tenant2.id,
            CourseIn(
                title="Phlebotomy",
                description="Notes",
                mode="hybrid",
                language="hi",
                duration_hours=100,
                fee_inr=5000,
                nsqf_level=4.0,
                skills=[
                    CourseSkillIn(skill_slug="collect-blood-samples-hc-n0001", level_taught=4.5)
                ],
            ),
        )
        via_file = await db.scalar(
            select(Course).join(Tenant, Tenant.id == Course.tenant_id).where(Tenant.slug == org)
        )
        assert via_file is not None
        for field in (
            "title",
            "description",
            "mode",
            "language",
            "duration_hours",
            "fee_inr",
            "status",
        ):
            assert getattr(via_file, field) == getattr(direct, field), field
        assert {(s.skill.nos_code, float(s.level_taught)) for s in via_file.skills} == {
            (s.skill.nos_code, float(s.level_taught)) for s in direct.skills
        }

    async def test_a_course_is_a_duplicate_on_its_title_alone(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Dup Academy", "course_provider")
        text = _csv(
            ",Same course,,,,,,,HC/N0001,",
            ",  same   COURSE ,,,,,,,HC/N0002,",
            header=COURSE_HEADER,
        )
        body = (await _post(client, f"/org/{org}/courses/bulk/apply", text, headers)).json()
        assert [r["status"] for r in body["rows"]] == ["ok", "skip"]
        again = (await _post(client, f"/org/{org}/courses/bulk/apply", text, headers)).json()
        assert again["created"] == 0
        assert await _count(db, Course, org) == 1

    @pytest.mark.parametrize(
        "row,fragment",
        [
            ("A,Course A,,,,,,,HC/N0001:11,", "must be 1 to 10"),
            ("A,Course A,,,,,,,HC/N0001:4.2,", "steps of 0.5"),
            ("A,Course A,,,,,,,HC/N0001:x,", "must be a number"),
            ("A,Course A,,evening,,,,,HC/N0001,", "mode"),
            ("A,Course A,,,,0,,,HC/N0001,", "duration_hours"),
            ("A,Course A,,,,,-5,,HC/N0001,", "fee_inr"),
        ],
    )
    async def test_course_cells_are_held_to_the_forms_rules(
        self, client: AsyncClient, corpus: None, row: str, fragment: str
    ) -> None:
        headers, org = await _org(client, "Rule Academy", "course_provider")
        body = (
            await _post(
                client, f"/org/{org}/courses/bulk/check", _csv(row, header=COURSE_HEADER), headers
            )
        ).json()
        assert body["rows"][0]["status"] == "error", row
        assert fragment in " ".join(body["rows"][0]["messages"])

    async def test_the_course_event_is_its_own(
        self, client: AsyncClient, db: AsyncSession, corpus: None
    ) -> None:
        headers, org = await _org(client, "Event Academy", "course_provider")
        await _post(
            client,
            f"/org/{org}/courses/bulk/apply",
            _csv(",A course,,,,,,,HC/N0001,", header=COURSE_HEADER),
            headers,
        )
        tenant_id = await db.scalar(select(Tenant.id).where(Tenant.slug == org))
        names = (
            await db.scalars(
                select(AnalyticsEvent.name).where(AnalyticsEvent.subject_id == tenant_id)
            )
        ).all()
        assert list(names) == ["courses_bulk_uploaded"]


class TestTheSampleFiles:
    """The two files that ship in `scripts/fixtures/` are what a person is told to start from."""

    @pytest.mark.parametrize(
        ("kind", "name", "rows"),
        [("jobs", "sample_vacancies.csv", 4), ("courses", "sample_courses.csv", 2)],
    )
    def test_they_carry_exactly_the_columns_the_engine_reads(
        self, kind: str, name: str, rows: int
    ) -> None:
        text = (Path(__file__).parent.parent / "scripts" / "fixtures" / name).read_text("utf-8")
        parsed, notes, header = bulk.parse_file(text, kind)  # type: ignore[arg-type]
        assert tuple(header) == bulk.COLUMNS[kind]
        assert (len(parsed), notes) == (rows, [])
