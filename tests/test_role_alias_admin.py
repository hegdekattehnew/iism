"""An operator edits role aliases (Sprint 47, BL-12.15, ADR-054).

Role-alias coverage is the product's weakest point and the people who can improve it are
not engineers. This is the surface that lets them, so the tests are about three things
going wrong: *who* may change what every candidate's search finds, *what* may be added
(the Sprint 43 rules, from the one place that holds them), and above all that **the seed
never overwrites an operator's work** -- the old seed deleted the whole table, which is
exactly why nobody but an engineer could edit it.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import (
    OPERATOR_PERMISSIONS,
    TIER_PERMISSIONS,
    Permission,
)
from api.modules.skills import (
    RoleAlias,
    RoleAliasEvent,
    check_alias,
    search_roles,
    sync_seed_aliases,
)
from api.modules.skills.service import alias_problems
from tests.test_operations import _candidate, _operator
from tests.test_role_search_trust import _pack, _roles, _sector


@pytest.fixture
async def corpus(db: AsyncSession) -> dict[str, str]:
    """A general role, a disability-track one, and a role whose title is a lay term."""
    sector = await _sector(db)
    await _pack(db, sector, "SSC/Q4001", "General Duty Assistant")
    await _pack(db, sector, "PWD/SSC/Q4002", "Hotel Steward")
    await _pack(db, sector, "SSC/Q4003", "Welder")
    await _pack(db, sector, "SSC/Q4004", "Cook Helper")
    return {"gda": "General Duty Assistant", "pwd": "Hotel Steward", "welder": "Welder"}


async def _count(db: AsyncSession, model: type) -> int:
    return (await db.scalar(select(func.count()).select_from(model))) or 0


def _body(term: str, role: str, note: str | None = None) -> dict:
    return {"surface_form": term, "job_role": role, **({"note": note} if note else {})}


class TestWhoMayEdit:
    def test_it_is_an_admin_permission_and_not_a_support_one(self) -> None:
        """The same public blast radius that kept `OPS_ORG_VERIFY` off the support tier."""
        assert Permission.OPS_ALIAS_EDIT in OPERATOR_PERMISSIONS
        assert Permission.OPS_ALIAS_EDIT in TIER_PERMISSIONS["admin"]
        assert Permission.OPS_ALIAS_EDIT not in TIER_PERMISSIONS["support"]

    async def test_anonymous_is_401(self, client: AsyncClient) -> None:
        assert (await client.get("/ops/role-aliases")).status_code == 401

    async def test_a_signed_in_stranger_gets_the_unrouted_404(self, client: AsyncClient) -> None:
        """Byte-identical to a path that does not exist (ADR-042): a 403 would confirm
        that one flag on their row is all that stands between them and every search."""
        headers = await _candidate(client)
        refused = await client.get("/ops/role-aliases", headers=headers)
        unrouted = await client.get("/ops/definitely-not-a-route", headers=headers)
        assert refused.status_code == unrouted.status_code == 404
        assert refused.json() == unrouted.json()

    async def test_a_support_operator_is_refused_every_one_with_403(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db, tier="support")
        assert (await client.get("/ops/role-aliases", headers=headers)).status_code == 403
        assert (await client.get("/ops/role-aliases/history", headers=headers)).status_code == 403
        body = _body("ward boy", corpus["gda"])
        assert (
            await client.post("/ops/role-aliases/check", headers=headers, json=body)
        ).status_code == 403
        assert (
            await client.post("/ops/role-aliases", headers=headers, json=body)
        ).status_code == 403
        assert await _count(db, RoleAlias) == 0

    async def test_an_admin_may(self, client: AsyncClient, db: AsyncSession) -> None:
        headers = await _operator(client, db, tier="admin")
        assert (await client.get("/ops/role-aliases", headers=headers)).status_code == 200


class TestChecking:
    async def test_a_good_alias_names_the_role_as_the_corpus_spells_it(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        response = await client.post(
            "/ops/role-aliases/check",
            headers=headers,
            json=_body("  Ward   BOY ", "general  duty ASSISTANT"),
        )
        body = response.json()
        assert response.status_code == 200 and body["ok"] is True
        assert body["surface_form"] == "ward boy"
        assert body["target"]["job_role"] == "General Duty Assistant"
        assert body["target"]["qp_code"] == "SSC/Q4001"
        assert body["target"]["standards_count"] == 1
        assert body["problems"] == []

    async def test_a_dry_run_writes_nothing(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases/check", headers=headers, json=_body("ward boy", corpus["gda"])
        )
        assert await _count(db, RoleAlias) == 0
        assert await _count(db, RoleAliasEvent) == 0

    @pytest.mark.parametrize(
        ("term", "role", "fragment"),
        [
            ("ward boy", "No Such Role", "No current qualification"),
            ("steward", "Hotel Steward", "disability-track"),
            ("welder", "General Duty Assistant", "exact title"),
            ("50% off", "General Duty Assistant", "cannot contain"),
        ],
    )
    async def test_each_way_an_alias_is_wrong_is_named(
        self,
        client: AsyncClient,
        db: AsyncSession,
        corpus: dict[str, str],
        term: str,
        role: str,
        fragment: str,
    ) -> None:
        headers = await _operator(client, db)
        body = (
            await client.post("/ops/role-aliases/check", headers=headers, json=_body(term, role))
        ).json()
        assert body["ok"] is False
        assert any(fragment in problem for problem in body["problems"]), body["problems"]

    async def test_a_term_that_is_taken_says_so(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["gda"])
        )
        body = (
            await client.post(
                "/ops/role-aliases/check", headers=headers, json=_body("ward boy", corpus["welder"])
            )
        ).json()
        assert body["existing"] == "active" and body["ok"] is False
        assert any("already points at" in p for p in body["problems"])

    async def test_an_ambiguous_prefix_is_a_warning_not_a_refusal(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        """Role search is a typeahead, so another role claiming `wel...` is allowed. It has
        to be *known*, which is all this does."""
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases", headers=headers, json=_body("weld helper", corpus["welder"])
        )
        body = (
            await client.post(
                "/ops/role-aliases/check",
                headers=headers,
                json=_body("welfare aide", corpus["gda"]),
            )
        ).json()
        assert body["ok"] is True
        assert any("'wel'" in w and "welder" in w for w in body["warnings"]), body["warnings"]


class TestAdding:
    async def test_it_is_stored_normalised_and_owned_by_the_operator(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        response = await client.post(
            "/ops/role-aliases",
            headers=headers,
            json=_body("  Ward   BOY ", "general duty assistant", "heard on a ward in Kanpur"),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["surface_form"] == "ward boy"
        assert body["job_role"] == "General Duty Assistant"
        assert body["source"] == "operator"
        row = await db.scalar(select(RoleAlias).where(RoleAlias.surface_form == "ward boy"))
        assert row is not None and row.retired_at is None

    async def test_search_finds_it_at_once(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        assert await _roles(db, "ward boy") == []
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["gda"])
        )
        hits = await search_roles(db, "ward boy")
        assert [h.job_role for h in hits][:1] == ["General Duty Assistant"]
        assert hits[0].match_kind == "alias"

    async def test_it_is_recorded_with_who_and_why(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["gda"], "  heard  ")
        )
        event = await db.scalar(select(RoleAliasEvent))
        assert event is not None
        assert (event.action, event.surface_form, event.job_role, event.note) == (
            "added",
            "ward boy",
            "General Duty Assistant",
            "heard",
        )
        assert event.actor_user_id is not None

    @pytest.mark.parametrize(
        ("term", "role", "status_code"),
        [
            ("ward boy", "No Such Role", 422),
            ("steward", "Hotel Steward", 422),
            ("welder", "General Duty Assistant", 422),
        ],
    )
    async def test_a_wrong_alias_is_refused_and_nothing_is_written(
        self,
        client: AsyncClient,
        db: AsyncSession,
        corpus: dict[str, str],
        term: str,
        role: str,
        status_code: int,
    ) -> None:
        headers = await _operator(client, db)
        refused = await client.post("/ops/role-aliases", headers=headers, json=_body(term, role))
        assert refused.status_code == status_code
        assert refused.json()["detail"]
        assert await _count(db, RoleAlias) == 0
        assert await _count(db, RoleAliasEvent) == 0

    async def test_a_taken_term_is_a_409_naming_where_it_points(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["gda"])
        )
        again = await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["welder"])
        )
        assert again.status_code == 409
        assert "General Duty Assistant" in again.json()["detail"]
        assert await _count(db, RoleAliasEvent) == 1

    async def test_the_list_filters_by_term_or_target_and_reports_the_total(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        for term, role in (("ward boy", "gda"), ("weld helper", "welder"), ("ayah", "gda")):
            await client.post("/ops/role-aliases", headers=headers, json=_body(term, corpus[role]))
        everything = (await client.get("/ops/role-aliases", headers=headers)).json()
        assert everything["total"] == 3
        assert [i["surface_form"] for i in everything["items"]] == [
            "ayah",
            "ward boy",
            "weld helper",
        ]
        by_target = (await client.get("/ops/role-aliases?q=duty", headers=headers)).json()
        assert [i["surface_form"] for i in by_target["items"]] == ["ayah", "ward boy"]
        assert by_target["total"] == 3  # the whole table, not the filter
        wildcard = (await client.get("/ops/role-aliases?q=%25", headers=headers)).json()
        assert wildcard["items"] == []  # a literal %, not a wildcard


class TestRetiring:
    async def _added(self, client: AsyncClient, headers: dict[str, str], role: str) -> str:
        response = await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", role)
        )
        return response.json()["id"]

    async def test_it_is_kept_not_deleted_and_search_stops_finding_it(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        alias_id = await self._added(client, headers, corpus["gda"])
        retired = await client.post(
            f"/ops/role-aliases/{alias_id}/retire", headers=headers, json={"note": "wrong role"}
        )
        assert retired.status_code == 200
        assert await _roles(db, "ward boy") == []
        rows = (await db.scalars(select(RoleAlias))).all()
        assert [(r.surface_form, r.retired_at is not None, r.source) for r in rows] == [
            ("ward boy", True, "operator")
        ]
        events = (
            await db.scalars(select(RoleAliasEvent).order_by(RoleAliasEvent.created_at))
        ).all()
        assert [e.action for e in events] == ["added", "retired"]
        assert events[1].note == "wrong role"

    async def test_it_leaves_the_live_list(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        alias_id = await self._added(client, headers, corpus["gda"])
        await client.post(f"/ops/role-aliases/{alias_id}/retire", headers=headers, json={})
        listing = (await client.get("/ops/role-aliases", headers=headers)).json()
        assert listing == {"items": [], "total": 0}

    async def test_an_unknown_or_already_retired_alias_is_404(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        alias_id = await self._added(client, headers, corpus["gda"])
        await client.post(f"/ops/role-aliases/{alias_id}/retire", headers=headers, json={})
        again = await client.post(f"/ops/role-aliases/{alias_id}/retire", headers=headers, json={})
        unknown = await client.post(
            "/ops/role-aliases/00000000-0000-0000-0000-000000000000/retire",
            headers=headers,
            json={},
        )
        assert again.status_code == unknown.status_code == 404
        assert await _count(db, RoleAliasEvent) == 2  # added, retired -- nothing for the 404s

    async def test_adding_the_term_again_revives_the_same_row(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        alias_id = await self._added(client, headers, corpus["gda"])
        await client.post(f"/ops/role-aliases/{alias_id}/retire", headers=headers, json={})
        revived = await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["welder"])
        )
        assert revived.status_code == 201
        assert revived.json()["id"] == alias_id
        assert revived.json()["job_role"] == "Welder"
        assert await _count(db, RoleAlias) == 1
        assert [h.job_role for h in await search_roles(db, "ward boy")][:1] == ["Welder"]


class TestHistory:
    async def test_newest_first_and_it_names_nobody(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        alias_id = (
            await client.post(
                "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["gda"])
            )
        ).json()["id"]
        await client.post(f"/ops/role-aliases/{alias_id}/retire", headers=headers, json={})
        history = (await client.get("/ops/role-aliases/history", headers=headers)).json()
        assert [e["action"] for e in history] == ["retired", "added"]
        # Who did it is in the table for an auditor; it is not in this payload.
        assert all("actor" not in key for e in history for key in e)


class TestTheSeedNeverOvertakesAnOperator:
    """The property the whole sprint rests on. The old seed was `DELETE FROM role_aliases`."""

    async def test_it_inserts_what_is_missing_and_updates_its_own(self, db: AsyncSession) -> None:
        await sync_seed_aliases(db, {"ward boy": "General Duty Assistant"})
        result = await sync_seed_aliases(
            db, {"ward boy": "Hospital Attendant", "ayah": "General Duty Assistant"}
        )
        assert (result.added, result.updated, result.removed) == (1, 1, 0)
        rows = {
            r.surface_form: (r.job_role, r.source)
            for r in (await db.scalars(select(RoleAlias))).all()
        }
        assert rows == {
            "ward boy": ("Hospital Attendant", "seed"),
            "ayah": ("General Duty Assistant", "seed"),
        }

    async def test_it_removes_a_seed_row_the_dict_no_longer_names(self, db: AsyncSession) -> None:
        await sync_seed_aliases(db, {"ward boy": "General Duty Assistant", "ayah": "Welder"})
        result = await sync_seed_aliases(db, {"ward boy": "General Duty Assistant"})
        assert result.removed == 1
        assert [r.surface_form for r in (await db.scalars(select(RoleAlias))).all()] == ["ward boy"]

    async def test_an_operators_row_survives_a_seed_that_does_not_name_it(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["gda"])
        )
        result = await sync_seed_aliases(db, {})
        assert result.removed == 0 and result.left_alone == 1
        assert await _roles(db, "ward boy") == ["General Duty Assistant"]

    async def test_an_operators_row_is_not_overwritten_by_a_seed_that_names_it(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        headers = await _operator(client, db)
        await client.post(
            "/ops/role-aliases", headers=headers, json=_body("ward boy", corpus["gda"])
        )
        await sync_seed_aliases(db, {"ward boy": "Welder"})
        row = await db.scalar(select(RoleAlias).where(RoleAlias.surface_form == "ward boy"))
        assert row is not None and row.job_role == "General Duty Assistant"

    async def test_a_retired_alias_is_not_revived_by_a_seed_that_still_names_it(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        """An operator withdrew a seed alias. The dict still says it. The operator wins."""
        await sync_seed_aliases(db, {"ward boy": corpus["gda"]})
        seeded = await db.scalar(select(RoleAlias).where(RoleAlias.surface_form == "ward boy"))
        assert seeded is not None and seeded.source == "seed"
        headers = await _operator(client, db)
        await client.post(f"/ops/role-aliases/{seeded.id}/retire", headers=headers, json={})

        await sync_seed_aliases(db, {"ward boy": corpus["gda"]})

        assert await _roles(db, "ward boy") == []
        row = await db.scalar(select(RoleAlias).where(RoleAlias.surface_form == "ward boy"))
        assert row is not None and row.retired_at is not None and row.source == "operator"


class TestTheCheckerReadsTheTable:
    async def test_it_checks_live_rows_including_an_operators_and_not_retired_ones(
        self, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        """`make check-role-aliases` used to read the dict, which now only seeds -- exactly
        what a check of the dict would miss is the operator's edits."""
        db.add_all(
            [
                RoleAlias(surface_form="steward", job_role="Hotel Steward", source="operator"),
                RoleAlias(surface_form="old", job_role="Hotel Steward", source="seed"),
            ]
        )
        await db.flush()
        await db.execute(
            RoleAlias.__table__.update()
            .where(RoleAlias.surface_form == "old")
            .values(retired_at=func.now())
        )
        report = await alias_problems(db)
        assert [(key, target) for key, target, _ in report.disability_track] == [
            ("steward", "Hotel Steward")
        ]


class TestTheRulesAreTheCheckersRules:
    async def test_the_service_and_the_script_agree(
        self, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        """`check_alias` calls `alias_problems`; it does not restate it."""
        check = await check_alias(db, "steward", "Hotel Steward")
        report = await alias_problems(db, {"steward": "Hotel Steward"})
        assert bool(report.disability_track) and not check.ok

    async def test_a_one_character_term_is_refused_by_the_schema_and_by_the_service(
        self, client: AsyncClient, db: AsyncSession, corpus: dict[str, str]
    ) -> None:
        """Two layers, because the service is also reached without the route (the seed's
        sibling, scripts): the schema says it first, with FastAPI's own 422 body."""
        headers = await _operator(client, db)
        over_http = await client.post(
            "/ops/role-aliases/check", headers=headers, json=_body("x", corpus["gda"])
        )
        assert over_http.status_code == 422
        direct = await check_alias(db, "x", corpus["gda"])
        assert not direct.ok and "at least 2" in direct.problems[0]
