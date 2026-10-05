"""Who each route lets in, read from the route table (Sprint 49).

Every authorization guard in this product is a dependency a route must remember to
declare, and CLAUDE.md records how that goes: three of eight publishing writes shipped
without the tenant check, a candidate was walked into the employer console because
`owner` carried permissions no route had been asked about. Each was found by hand,
sprints later. This does the walk mechanically: it builds the list of operations from
the OpenAPI schema, so **a route added tomorrow is covered the day it exists**, and asks
the same four questions of every one.

* **Anonymous.** Every route not named in `PUBLIC_ROUTES` answers 401. A new route that
  forgot its guard answers 200, 404 or 422 instead, and the failure names it. Being
  public is a decision, so it is a line in a list, with the reason beside it.
* **A stranger to an organisation.** For every `/org/{slug}/...` route, someone who is not
  a member -- a candidate with no organisation, or the owner of a different one -- gets
  the **same** 404 for an organisation that exists as for one that does not (ADR-038).
  A 403 would confirm the slug; a different body would be just as good an oracle.
* **The back office.** A signed-in non-operator gets a 404 byte-identical to an unrouted
  path on every `/ops` route (ADR-042); an operator whose tier lacks the route's permission
  gets 403 and one whose tier has it does not (ADR-044). The permission is read **off the
  route**, not restated here.
* **A partner key.** A user's token is not an API key.

**What this does not check** is *whose row* a permitted caller reaches: another candidate
withdrawing somebody else's application. That needs a real resource per route, and is the
business of each module's own tests. This guards the doors; it says nothing about the
rooms behind them.
"""

import uuid
from collections.abc import Iterator

from fastapi.routing import APIRoute
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import TIER_PERMISSIONS, Permission
from tests.test_operations import _candidate, _operator, _register_org

BODY_METHODS = {"POST", "PUT", "PATCH"}

# Routes anybody may call without signing in, each with the reason. Adding to this
# list is the review; a route that is not here and answers an anonymous caller fails.
PUBLIC_ROUTES: dict[tuple[str, str], str] = {
    # --- liveness
    ("GET", "/health"): "load balancer probe",
    ("GET", "/health/deep"): "dependency probe, reports status only",
    # --- the public catalogue: what a visitor browses before they have an account
    ("GET", "/courses"): "public catalogue",
    ("GET", "/courses/{slug}"): "public catalogue",
    ("GET", "/jobs"): "public catalogue",
    ("GET", "/jobs/{slug}"): "public catalogue",
    ("GET", "/jobs/{job_slug}/poster-rating"): "an average over ratings; names nobody",
    ("GET", "/geography/districts"): "reference data",
    ("GET", "/geography/states"): "reference data",
    ("GET", "/marketplace/counts"): "aggregate counts on the homepage",
    ("GET", "/marketplace/stats"): "aggregate counts on the homepage",
    ("GET", "/roles/search"): "role search, the taxonomy",
    ("GET", "/roles/{slug}/standards"): "the taxonomy",
    ("GET", "/skills"): "the taxonomy",
    ("GET", "/skills/count"): "the taxonomy",
    ("GET", "/skills/facets"): "the taxonomy",
    ("GET", "/skills/search"): "the taxonomy",
    ("GET", "/skills/{slug}"): "the taxonomy",
    ("GET", "/skills/{slug}/courses"): "the taxonomy",
    ("GET", "/skills/{slug}/jobs"): "the taxonomy",
    ("GET", "/skills/{slug}/qualifications"): "the taxonomy",
    ("GET", "/skills/{slug}/requirements"): "the taxonomy",
    # --- how a person becomes signed in: these cannot require being signed in
    ("POST", "/auth/otp/request"): "sign-in by phone",
    ("POST", "/auth/otp/verify"): "sign-in by phone",
    ("POST", "/auth/email/otp/request"): "sign-in by email",
    ("POST", "/auth/email/otp/verify"): "sign-in by email",
    ("POST", "/auth/refresh"): "exchanges a refresh token, which is its own credential",
    (
        "POST",
        "/auth/logout",
    ): "presenting the refresh token is the credential; it revokes only that",
    ("POST", "/auth/org/register"): "registration; for a signed-in caller it adds a membership",
    # --- a capability token is the credential (Sprint 25)
    ("GET", "/invitations/{token}"): "the token is the capability",
    ("POST", "/invitations/{token}/claim"): "the token is the capability",
    ("POST", "/invitations/{token}/verify"): "the token is the capability",
    # --- local-environment demonstration surfaces (absent in production)
    ("POST", "/tasks/ping"): "demo endpoint; local environments only",
    ("GET", "/tasks/{job_id}"): "demo endpoint; local environments only",
    ("GET", "/employer/employers"): "demo console; local environments only",
    ("GET", "/employer/{slug}/overview"): "demo console; local environments only",
    ("GET", "/employer/{slug}/jobs/{job_slug}/candidates"): "demo console; local environments only",
}


def _operations() -> list[tuple[str, str]]:
    from api.main import app

    found = []
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                found.append((method.upper(), path))
    return sorted(found)


def _fill(path: str, **named: str) -> str:
    out = path
    for part in [seg for seg in path.split("/") if seg.startswith("{")]:
        name = part.strip("{}")
        if name in named:
            value = named[name]
        elif name.endswith("id") or name == "id":
            value = str(uuid.uuid4())
        elif name == "token":
            value = "matrix-probe-token"
        else:
            value = "matrix-probe"
        out = out.replace(part, value)
    return out


async def _call(
    client: AsyncClient, method: str, path: str, headers: dict[str, str] | None = None
) -> Response:
    kwargs = {"json": {}} if method in BODY_METHODS else {}
    return await client.request(method, path, headers=headers, **kwargs)


def _routes() -> Iterator[APIRoute]:
    from api.main import app

    def walk(routes):  # type: ignore[no-untyped-def]
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                yield from walk(inner.routes)
            elif isinstance(route, APIRoute):
                yield route

    yield from walk(app.routes)


def _operator_permission(route: APIRoute) -> Permission | None:
    def find(dependant):  # type: ignore[no-untyped-def]
        for sub in dependant.dependencies:
            permission = getattr(sub.call, "permission", None)
            if isinstance(permission, Permission):
                return permission
            found = find(sub)
            if found is not None:
                return found
        return None

    return find(route.dependant)


class TestTheTableIsRead:
    def test_it_found_the_routes(self) -> None:
        """A matcher that matches nothing reports a clean route table for ever."""
        operations = _operations()
        assert len(operations) > 100
        assert sum(1 for _, p in operations if p.startswith("/org/")) > 30
        assert sum(1 for _, p in operations if p.startswith("/ops/")) > 10

    def test_every_public_route_still_exists(self) -> None:
        """A stale entry is a hole nobody can see: it would keep granting a route that
        was removed, or renamed under a path the list no longer names."""
        existing = set(_operations())
        gone = sorted(set(PUBLIC_ROUTES) - existing)
        assert not gone, f"PUBLIC_ROUTES names routes that do not exist: {gone}"


class TestAnonymous:
    async def test_every_route_not_named_public_refuses_a_stranger_with_401(
        self, client: AsyncClient
    ) -> None:
        wrong = []
        checked = 0
        for method, path in _operations():
            if (method, path) in PUBLIC_ROUTES:
                continue
            response = await _call(client, method, _fill(path))
            checked += 1
            if response.status_code != 401:
                wrong.append(f"{method} {path} -> {response.status_code}")
        assert checked > 80
        assert not wrong, (
            "answers a caller who is not signed in with something other than 401. If it is "
            "meant to be public, add it to PUBLIC_ROUTES with the reason:\n  " + "\n  ".join(wrong)
        )

    async def test_the_public_routes_really_are_public(self, client: AsyncClient) -> None:
        """The non-vacuity guard for the test above: a listed route that answers 401
        is not public, and the list has drifted from the code in the other direction."""
        refused = []
        for method, path in PUBLIC_ROUTES:
            response = await _call(client, method, _fill(path))
            if response.status_code == 401:
                refused.append(f"{method} {path}")
        assert not refused, f"listed as public but answers 401: {refused}"


async def _two_orgs(client: AsyncClient) -> dict[str, object]:
    """Two organisations with different owners, and a candidate who belongs to neither."""
    owner_a, slug_a = await _register_org(client, "Matrix Alpha Ltd")
    owner_b, slug_b = await _register_org(client, "Matrix Beta Ltd")
    stranger = await _candidate(client)
    return {
        "owner_a": owner_a,
        "slug_a": slug_a,
        "owner_b": owner_b,
        "slug_b": slug_b,
        "stranger": stranger,
    }


class TestAStrangerToAnOrganisation:
    async def test_it_cannot_tell_a_real_organisation_from_one_that_does_not_exist(
        self, client: AsyncClient
    ) -> None:
        """For every organisation route, a caller with no standing in the organisation gets
        the same answer for one that exists as for one that does not (ADR-038): a 403
        would confirm the slug, and a different body would be as good an oracle. Two
        kinds of stranger -- a candidate with no organisation at all, and the owner of a
        *different* one, who is signed in and holds a membership, just not this one."""
        world = await _two_orgs(client)
        ghost = f"no-such-org-{uuid.uuid4().hex[:8]}"
        routes = [(m, p) for m, p in _operations() if p.startswith("/org/")]
        assert len(routes) > 30

        leaks = []
        for who, headers, real in (
            ("a candidate with no organisation", world["stranger"], world["slug_a"]),
            ("the owner of another organisation", world["owner_b"], world["slug_a"]),
        ):
            for method, path in routes:
                other = {"org_slug": str(real)}
                missing = {"org_slug": ghost}
                # Resource ids are fresh uuids per call, so a difference in the answer can
                # only be the organisation's.
                ids = {
                    seg.strip("{}"): str(uuid.uuid4())
                    for seg in path.split("/")
                    if seg.startswith("{") and seg != "{org_slug}"
                }
                a = await _call(client, method, _fill(path, **other, **ids), headers)  # type: ignore[arg-type]
                b = await _call(client, method, _fill(path, **missing, **ids), headers)  # type: ignore[arg-type]
                if (a.status_code, a.json()) != (b.status_code, b.json()) or a.status_code != 404:
                    leaks.append(
                        f"{who}: {method} {path} -> {a.status_code} for a real organisation, "
                        f"{b.status_code} for none"
                    )
        assert not leaks, "an organisation route reveals whether a slug exists:\n  " + "\n  ".join(
            leaks
        )

    async def test_the_owner_gets_in_by_the_same_door(self, client: AsyncClient) -> None:
        """The non-vacuity guard for the test above: without it a typo in the path
        would make every 404 assertion pass for ever."""
        world = await _two_orgs(client)
        response = await client.get(f"/org/{world['slug_a']}", headers=world["owner_a"])  # type: ignore[arg-type]
        assert response.status_code == 200


class TestTheBackOffice:
    async def test_a_signed_in_non_operator_gets_the_unrouted_404_on_every_ops_route(
        self, client: AsyncClient
    ) -> None:
        stranger = await _candidate(client)
        unrouted = await client.get("/ops/definitely-not-a-route", headers=stranger)
        routes = [(m, p) for m, p in _operations() if p.startswith("/ops/")]
        assert len(routes) > 10

        wrong = []
        for method, path in routes:
            response = await _call(client, method, _fill(path), stranger)
            if (response.status_code, response.json()) != (unrouted.status_code, unrouted.json()):
                wrong.append(f"{method} {path} -> {response.status_code} {response.json()}")
        assert not wrong, (
            "a non-operator can tell a back-office route from none:\n  " + "\n  ".join(wrong)
        )

    async def test_each_tier_gets_what_the_routes_own_permission_says(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The permission is read off the route. A support operator is refused with 403
        exactly where `TIER_PERMISSIONS["support"]` lacks it, and is not refused where it
        has it; an admin is never refused. If a route is added with the wrong dependency,
        or a permission moves between tiers, this says which."""
        support = await _operator(client, db, tier="support")
        admin = await _operator(client, db, tier="admin")
        ops = [r for r in _routes() if r.path.startswith("/ops/")]
        assert len(ops) > 10

        denied_to_support = allowed_to_support = 0
        wrong = []
        for route in ops:
            permission = _operator_permission(route)
            if permission is None:
                wrong.append(
                    f"{sorted(route.methods)} {route.path} asks for no operator permission"
                )
                continue
            method = sorted(route.methods - {"HEAD", "OPTIONS"})[0]
            path = _fill(route.path)
            as_support = await _call(client, method, path, support)
            as_admin = await _call(client, method, path, admin)
            if permission in TIER_PERMISSIONS["support"]:
                allowed_to_support += 1
                if as_support.status_code in (401, 403):
                    wrong.append(
                        f"{method} {route.path}: support refused ({as_support.status_code})"
                    )
            else:
                denied_to_support += 1
                if as_support.status_code != 403:
                    wrong.append(
                        f"{method} {route.path}: support got {as_support.status_code}, not 403"
                    )
            if as_admin.status_code in (401, 403):
                wrong.append(f"{method} {route.path}: admin refused ({as_admin.status_code})")
        assert allowed_to_support and denied_to_support, "the two tiers do not differ here"
        assert not wrong, "\n  ".join(wrong)


class TestAPartnerKey:
    async def test_a_users_token_is_not_an_api_key(self, client: AsyncClient) -> None:
        """A partner route takes a key in `X-API-Key`. A signed-in person's bearer token
        is a different credential for a different actor and must open nothing here."""
        user = await _candidate(client)
        partner = [(m, p) for m, p in _operations() if p.startswith("/partners/")]
        assert partner
        for method, path in partner:
            as_user = await _call(client, method, _fill(path), user)
            assert as_user.status_code == 401, f"{method} {path} accepted a user's token"
