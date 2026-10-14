"""The applicants of one vacancy, as a spreadsheet (Sprint 60, BL-14.8, ADR-070).

It is built from the same function as the list, so everything the list withholds is withheld here
too, and every cell is safe to open: somebody else's words in a spreadsheet are a formula until
they are shown not to be.
"""

import csv
import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.text import csv_safe
from api.modules.analytics.models import AnalyticsEvent
from api.modules.marketplace import bulk
from api.modules.marketplace.bulk import RawRow
from tests.moderation_support import make_skill, organisation, person, published_job


async def _vacancy(client: AsyncClient, db: AsyncSession, applicants: int = 2):
    headers, org = await organisation(client, db)
    job = await published_job(client, headers, org, await make_skill(db))
    people = []
    for _ in range(applicants):
        who, _uid = await person(client)
        await client.post("/me/applications", headers=who, json={"job_slug": job["slug"]})
        people.append(who)
    return headers, org, job, people


async def _export(client: AsyncClient, headers, org, job):
    return await client.get(f"/org/{org}/jobs/{job['slug']}/applications/export", headers=headers)


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


class TestTheFile:
    async def test_it_is_a_csv_attachment_with_one_row_per_applicant_in_the_lists_order(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _ = await _vacancy(client, db, 3)
        response = await _export(client, headers, org, job)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        assert job["slug"] in response.headers["content-disposition"]
        rows = _rows(response.text)
        listed = (
            await client.get(f"/org/{org}/jobs/{job['slug']}/applications", headers=headers)
        ).json()["items"]
        assert [r["reference"] for r in rows] == [i["candidate"]["reference"] for i in listed]
        assert rows[0]["status"] == "applied" and rows[0]["phone"].startswith("+91")

    async def test_a_withdrawn_applicant_is_blank_exactly_as_in_the_list(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, people = await _vacancy(client, db, 2)
        mine = (await client.get("/me/applications", headers=people[0])).json()[0]
        await client.post(f"/me/applications/{mine['id']}/withdraw", headers=people[0])
        # A note is the employer's own, and stays.
        listed = (
            await client.get(f"/org/{org}/jobs/{job['slug']}/applications", headers=headers)
        ).json()["items"]
        gone = next(i for i in listed if i["status"] == "withdrawn")
        await client.put(
            f"/org/{org}/jobs/{job['slug']}/applications/{gone['application_id']}/notes",
            headers=headers,
            json={"notes": "Withdrew after the call."},
        )
        rows = _rows((await _export(client, headers, org, job)).text)
        row = next(r for r in rows if r["status"] == "withdrawn")
        assert (row["name"], row["phone"], row["email"], row["candidate_note"]) == ("", "", "", "")
        assert row["your_private_note"] == "Withdrew after the call."
        assert row["reference"] == gone["candidate"]["reference"]

    async def test_the_employers_message_and_note_are_in_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _ = await _vacancy(client, db, 1)
        listed = (
            await client.get(f"/org/{org}/jobs/{job['slug']}/applications", headers=headers)
        ).json()["items"][0]
        base = f"/org/{org}/jobs/{job['slug']}/applications/{listed['application_id']}"
        await client.patch(
            base, headers=headers, json={"status": "shortlisted", "message": "Tue, 11 am"}
        )
        await client.put(base + "/notes", headers=headers, json={"notes": "Strong."})
        (row,) = _rows((await _export(client, headers, org, job)).text)
        assert (row["status"], row["your_message_to_them"], row["your_private_note"]) == (
            "shortlisted",
            "Tue, 11 am",
            "Strong.",
        )

    async def test_every_formula_in_a_cell_is_neutralised(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _ = await _vacancy(client, db, 1)
        listed = (
            await client.get(f"/org/{org}/jobs/{job['slug']}/applications", headers=headers)
        ).json()["items"][0]
        base = f"/org/{org}/jobs/{job['slug']}/applications/{listed['application_id']}"
        await client.patch(
            base,
            headers=headers,
            json={"status": "shortlisted", "message": '=HYPERLINK("http://x")'},
        )
        await client.put(base + "/notes", headers=headers, json={"notes": "@SUM(A1:A9)"})
        (row,) = _rows((await _export(client, headers, org, job)).text)
        assert row["your_message_to_them"] == '\'=HYPERLINK("http://x")'
        assert row["your_private_note"] == "'@SUM(A1:A9)"


class TestWhoMayAndWhatIsRecorded:
    async def test_only_the_organisations_own_members_may(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, people = await _vacancy(client, db, 1)
        other, _ = await organisation(client, db)
        url = f"/org/{org}/jobs/{job['slug']}/applications/export"
        assert (await client.get(url, headers=other)).status_code == 404
        assert (await client.get(url, headers=people[0])).status_code == 404
        assert (await client.get(url)).status_code == 401

    async def test_a_vacancy_that_is_not_theirs_is_a_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org = await organisation(client, db)
        assert (
            await client.get(f"/org/{org}/jobs/no-such-job/applications/export", headers=headers)
        ).status_code == 404

    async def test_the_act_is_recorded_with_a_count_and_no_name(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _ = await _vacancy(client, db, 2)
        await _export(client, headers, org, job)
        event = await db.scalar(
            select(AnalyticsEvent).where(AnalyticsEvent.name == "applicants_exported")
        )
        assert event is not None and event.payload == {"count": 2}
        assert event.subject_type == "job"


class TestCsvSafe:
    @pytest.mark.parametrize(
        ("raw", "safe"),
        [
            ("=1+1", "'=1+1"),
            ("@SUM(A1)", "'@SUM(A1)"),
            ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
            ("-1+1", "'-1+1"),
            ("\tinjected", "'\tinjected"),
            ("\rinjected", "'\rinjected"),
            ("+91 98765 43210", "'+91 98765 43210"),
        ],
    )
    def test_a_cell_that_could_be_read_as_a_formula_is_prefixed(self, raw: str, safe: str) -> None:
        assert csv_safe(raw) == safe

    @pytest.mark.parametrize(
        "plain",
        ["", "Priya Sharma", "देवनागरी", "5 years", "a=b", "-5", "+919876543210", "3.5", "-0.5"],
    )
    def test_text_and_plain_numbers_are_left_alone(self, plain: str) -> None:
        assert csv_safe(plain) == plain

    def test_none_is_empty_and_numbers_are_text(self) -> None:
        assert csv_safe(None) == "" and csv_safe(42) == "42"

    def test_the_bulk_upload_errors_download_is_neutralised_too(self) -> None:
        rows = [RawRow(number=2, cells={"title": "=cmd()", "fee_inr": "-5"})]
        text = bulk.errors_csv(["title", "fee_inr"], rows, {2: "=bad"})
        assert text is not None
        (row,) = list(csv.DictReader(io.StringIO(text)))
        assert row["title"] == "'=cmd()" and row["fee_inr"] == "-5" and row["error"] == "'=bad"
