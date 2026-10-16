"""Sprint 69 (UI-04 to UI-11, UI-17): what a vacancy list has to be true to be scannable.

Three things are held here that a browser cannot show:

* the **state facet** is the catalogue's own fact, counted with the listing's predicate;
* the two shared test-vector files (pay and requirements) exist, are well formed, and are the ones
  *both* clients read -- a client that stopped reading its copy would pass on its own cases;
* the operator queue's total (in `tests/test_operations.py`, beside the queue's other tests).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity import Tenant
from api.modules.marketplace import Job

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent


async def _employer(db: AsyncSession) -> Tenant:
    tenant = Tenant(slug="facet-co", name="Facet Co", tenant_type="employer", city="Pune")
    db.add(tenant)
    await db.flush()
    return tenant


def _job(tenant: Tenant, slug: str, state: str | None, **extra: object) -> Job:
    return Job(
        slug=slug,
        tenant_id=tenant.id,
        title=slug.replace("-", " ").title(),
        location_state=state,
        employment_type="full_time",
        experience_min_years=0,
        **extra,
    )


class TestStateFacet:
    async def test_it_counts_open_vacancies_by_state_in_name_order(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        tenant = await _employer(db)
        db.add_all(
            [
                _job(tenant, "pune-a", "Maharashtra"),
                _job(tenant, "pune-b", "Maharashtra"),
                _job(tenant, "chennai-a", "Tamil Nadu"),
                _job(tenant, "anywhere", None),
            ]
        )
        await db.flush()
        body = (await client.get("/jobs/states")).json()
        facet = {row["name"]: row["count"] for row in body}
        assert facet["Maharashtra"] == 2 and facet["Tamil Nadu"] == 1
        assert [r["name"] for r in body] == sorted(r["name"] for r in body)
        assert None not in facet and "" not in facet

    async def test_a_draft_and_a_closed_vacancy_are_not_counted(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        """The option must have a result behind it: same predicate as the listing."""
        tenant = await _employer(db)
        db.add_all(
            [
                _job(tenant, "open-one", "Kerala"),
                _job(tenant, "draft-one", "Kerala", status="draft"),
                _job(
                    tenant,
                    "closed-one",
                    "Kerala",
                    closed_at=datetime.now(UTC),
                    close_reason="filled",
                ),
                _job(tenant, "only-draft", "Goa", status="draft"),
            ]
        )
        await db.flush()
        facet = {r["name"]: r["count"] for r in (await client.get("/jobs/states")).json()}
        assert facet["Kerala"] == 1
        assert "Goa" not in facet

    async def test_the_count_beside_a_state_is_the_total_the_listing_gives_for_it(
        self, db: AsyncSession, client: AsyncClient
    ) -> None:
        tenant = await _employer(db)
        db.add_all([_job(tenant, f"k-{n}", "Karnataka") for n in range(3)])
        await db.flush()
        facet = {r["name"]: r["count"] for r in (await client.get("/jobs/states")).json()}
        listed = (await client.get("/jobs", params={"location_state": "Karnataka"})).json()
        assert facet["Karnataka"] == listed["total"] == 3

    async def test_states_is_not_captured_as_a_vacancy_slug(self, client: AsyncClient) -> None:
        """`/jobs/{slug}` is declared after it. A route order mistake answers 404 here."""
        response = await client.get("/jobs/states")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestSharedVectors:
    """Both clients read these files; a test here keeps them honest and found."""

    def test_the_pay_cases_exist_and_are_well_formed(self) -> None:
        cases = json.loads((FIXTURES / "pay_cases.json").read_text())["cases"]
        assert len(cases) >= 10
        units = {c["expect"]["unit"] for c in cases}
        # Every unit the clients can render has a case that produces it.
        assert units == {"month", "year", "posted", "none"}
        shapes = {c["expect"]["shape"] for c in cases}
        assert shapes == {"range", "from", "exact", "none"}
        for c in cases:
            assert {"name", "min", "max", "type", "expect"} <= set(c)

    def test_the_requirement_cases_exist_and_are_well_formed(self) -> None:
        cases = json.loads((FIXTURES / "requirements_cases.json").read_text())["cases"]
        assert len(cases) >= 6
        for c in cases:
            assert {"name", "input", "expect"} <= set(c)
            assert set(c["expect"]) == {"main", "also"}

    def test_the_posted_cases_exist_and_cover_every_answer_and_boundary(self) -> None:
        data = json.loads((FIXTURES / "posted_cases.json").read_text())
        cases = data["cases"]
        assert data["now"] and len(cases) >= 12
        kinds = {c["expect"]["kind"] if c["expect"] else None for c in cases}
        assert kinds == {None, "today", "yesterday", "days", "month"}
        # The two edges that an off-by-one would cross: 1 -> 2 days and 29 -> 30 days.
        days = {c["expect"]["days"] for c in cases if c["expect"] and c["expect"]["kind"] == "days"}
        assert {2, 29} <= days
        names = {c["name"] for c in cases}
        assert {"exactly a day", "exactly thirty days"} <= names

    def test_both_clients_read_all_the_files(self) -> None:
        """If a client stopped reading the shared file it would pass on cases of its own."""
        readers = {
            "pay_cases.json": [
                "web/src/lib/pay.test.ts",
                "mobile/src/test/pay.test.ts",
            ],
            "requirements_cases.json": [
                "web/src/lib/requirements.test.ts",
                "mobile/src/test/requirements.test.ts",
            ],
            "posted_cases.json": [
                "web/src/lib/posted.test.ts",
                "mobile/src/test/posted.test.ts",
            ],
        }
        for fixture, tests in readers.items():
            for test in tests:
                source = (ROOT / test).read_text()
                assert fixture in source, f"{test} no longer reads tests/fixtures/{fixture}"
