"""A provider says which qualification a course counts toward (Sprint 75, BL-12.8, ADR-085).

`Course.qualification_pack_code` was a free string nothing could write, so no course had one and the
credit chip could not be built. It is written now, and what this holds is the part that is easy to
get wrong: the code is checked **before** anything changes, what it stands for is read when shown
(a re-import cannot leave a stale name or credit), and a number of credits a person cannot make
sense of (zero, not-a-number) is no chip rather than a wrong one.
"""

import itertools
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.marketplace.models import Course
from api.modules.skills.hierarchy import QpSkill, QualificationPack
from tests.moderation_support import make_skill, organisation

_n = itertools.count(1)


async def _pack(
    db: AsyncSession,
    role: str,
    *,
    credits: Decimal | None = Decimal("14"),
    current: bool = True,
    standard: str | None = None,
) -> QualificationPack:
    """A qualification with one standard (role search never offers one with none)."""
    i = next(_n)
    pack = QualificationPack(
        qp_code=f"QLF/Q{i:04d}{uuid.uuid4().hex[:4].upper()}",
        version="1.0",
        slug=f"qlf-pack-{i}-{uuid.uuid4().hex[:6]}",
        name=f"{role} qualification",
        job_role=role,
        nsqf_level=Decimal("4"),
        credits=credits,
        is_current=current,
    )
    db.add(pack)
    await db.flush()
    if standard:
        from api.modules.skills.models import Skill

        skill = await db.scalar(select(Skill).where(Skill.slug == standard))
        assert skill is not None
        db.add(
            QpSkill(
                qp_id=pack.id,
                skill_id=skill.id,
                requirement="compulsory",
                nsqf_level=Decimal("4"),
            )
        )
    await db.commit()
    return pack


async def _provider(client: AsyncClient, db: AsyncSession) -> tuple[dict[str, str], str, str]:
    headers, org = await organisation(client, db, kind="course_provider")
    return headers, org, await make_skill(db)


def _body(skill: str, code: str | None = None, **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "title": f"Qualification course {uuid.uuid4().hex[:6]}",
        "skills": [{"skill_slug": skill, "level_taught": 4}],
    }
    if code is not None:
        body["qualification_pack_code"] = code
    return {**body, **extra}


async def _make(
    client: AsyncClient,
    headers: dict[str, str],
    org: str,
    skill: str,
    code: str | None,
    *,
    publish: bool = True,
) -> dict:
    created = await client.post(f"/org/{org}/courses", headers=headers, json=_body(skill, code))
    assert created.status_code == 201, created.text
    slug = created.json()["slug"]
    if publish:
        published = await client.post(f"/org/{org}/courses/{slug}/publish", headers=headers)
        assert published.status_code == 200, published.text
        return published.json()
    return created.json()


class TestLinking:
    async def test_a_provider_links_a_course_and_everyone_reads_what_it_stands_for(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, skill = await _provider(client, db)
        pack = await _pack(db, "Ward Attendant Prime", credits=Decimal("14"))

        course = await _make(client, headers, org, skill, pack.qp_code)

        assert course["qualification_pack_code"] == pack.qp_code
        assert (course["qualification_name"], course["qualification_credits"]) == (
            "Ward Attendant Prime",
            14.0,
        )
        slug = course["slug"]
        detail = (await client.get(f"/courses/{slug}")).json()
        assert (detail["qualification_name"], detail["qualification_credits"]) == (
            "Ward Attendant Prime",
            14.0,
        )
        listed = (await client.get("/courses", params={"q": course["title"]})).json()["items"]
        assert [(c["qualification_name"], c["qualification_credits"]) for c in listed] == [
            ("Ward Attendant Prime", 14.0)
        ]
        by_skill = (await client.get(f"/skills/{skill}/courses")).json()
        assert [c["qualification_name"] for c in by_skill if c["slug"] == slug] == [
            "Ward Attendant Prime"
        ]
        own = (await client.get(f"/org/{org}/courses/{slug}", headers=headers)).json()
        assert own["qualification_credits"] == 14.0

    async def test_an_unknown_code_is_refused_in_words_and_nothing_is_created(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, skill = await _provider(client, db)
        before = await db.scalar(select(func.count()).select_from(Course))

        refused = await client.post(
            f"/org/{org}/courses", headers=headers, json=_body(skill, "NOPE/Q9999")
        )

        assert refused.status_code == 422
        assert "could not find that qualification" in refused.json()["detail"]
        assert await db.scalar(select(func.count()).select_from(Course)) == before

    async def test_a_retired_qualification_cannot_be_linked(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, skill = await _provider(client, db)
        retired = await _pack(db, "Retired Attendant", current=False)

        refused = await client.post(
            f"/org/{org}/courses", headers=headers, json=_body(skill, retired.qp_code)
        )

        assert refused.status_code == 422

    async def test_a_refused_update_changes_nothing_not_even_the_title(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The check runs before the first field is set (Sprint 55): the person was told 'no', so
        nothing of the edit may be saved by the next commit."""
        headers, org, skill = await _provider(client, db)
        pack = await _pack(db, "Kept Role")
        course = await _make(client, headers, org, skill, pack.qp_code)
        slug = course["slug"]

        refused = await client.put(
            f"/org/{org}/courses/{slug}",
            headers=headers,
            json=_body(skill, "NOPE/Q1", title="A different title entirely"),
        )

        assert refused.status_code == 422
        again = (await client.get(f"/org/{org}/courses/{slug}", headers=headers)).json()
        assert again["title"] == course["title"]
        assert again["qualification_pack_code"] == pack.qp_code

    async def test_blank_means_none_and_none_clears_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, skill = await _provider(client, db)
        pack = await _pack(db, "Cleared Role")
        course = await _make(client, headers, org, skill, pack.qp_code)
        slug = course["slug"]

        blank = await client.put(
            f"/org/{org}/courses/{slug}", headers=headers, json=_body(skill, "   ")
        )
        assert blank.status_code == 200
        assert blank.json()["qualification_pack_code"] is None
        assert blank.json()["qualification_name"] is None

        relinked = await client.put(
            f"/org/{org}/courses/{slug}", headers=headers, json=_body(skill, pack.qp_code)
        )
        assert relinked.json()["qualification_name"] == "Cleared Role"
        cleared = await client.put(
            f"/org/{org}/courses/{slug}",
            headers=headers,
            json={**_body(skill), "qualification_pack_code": None},
        )
        assert cleared.json()["qualification_pack_code"] is None

    async def test_an_update_that_leaves_the_field_out_clears_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`update_course` replaces every plain field, so omission is a clear. Pinned so a future
        client that does a full PUT without it knows (the web editor sends the saved value)."""
        headers, org, skill = await _provider(client, db)
        pack = await _pack(db, "Omitted Role")
        course = await _make(client, headers, org, skill, pack.qp_code)

        omitted = await client.put(
            f"/org/{org}/courses/{course['slug']}", headers=headers, json=_body(skill)
        )

        assert omitted.json()["qualification_pack_code"] is None


class TestReadingItBack:
    @pytest.mark.parametrize(
        ("credits", "shown"),
        [
            (Decimal("0"), None),
            (Decimal("NaN"), None),
            (None, None),
            (Decimal("0.5"), 0.5),
            (Decimal("99"), 99.0),
        ],
    )
    async def test_only_a_finite_positive_number_of_credits_is_shown(
        self,
        client: AsyncClient,
        db: AsyncSession,
        credits: Decimal | None,
        shown: float | None,
    ) -> None:
        headers, org, skill = await _provider(client, db)
        pack = await _pack(db, f"Credit Role {credits}", credits=credits)

        course = await _make(client, headers, org, skill, pack.qp_code)

        assert course["qualification_credits"] == shown
        # The name is still the provider's statement, with or without a credit figure.
        assert course["qualification_name"] == f"Credit Role {credits}"

    async def test_a_pack_that_has_gone_shows_nothing_and_does_not_fail(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, skill = await _provider(client, db)
        pack = await _pack(db, "Vanishing Role")
        course = await _make(client, headers, org, skill, pack.qp_code)
        pack.is_current = False
        await db.commit()

        detail = await client.get(f"/courses/{course['slug']}")

        assert detail.status_code == 200
        body = detail.json()
        assert body["qualification_pack_code"] == pack.qp_code  # what the provider said is kept
        assert (body["qualification_name"], body["qualification_credits"]) == (None, None)

    async def test_a_changed_figure_shows_at_once_because_nothing_is_copied(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, skill = await _provider(client, db)
        pack = await _pack(db, "Reissued Role", credits=Decimal("10"))
        course = await _make(client, headers, org, skill, pack.qp_code)
        pack.credits = Decimal("12")
        await db.commit()

        detail = (await client.get(f"/courses/{course['slug']}")).json()

        assert detail["qualification_credits"] == 12.0

    async def test_each_course_on_a_page_gets_its_own_qualification(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, skill = await _provider(client, db)
        a = await _pack(db, "Role Alpha", credits=Decimal("3"))
        b = await _pack(db, "Role Beta", credits=Decimal("7"))
        one = await _make(client, headers, org, skill, a.qp_code)
        two = await _make(client, headers, org, skill, b.qp_code)
        three = await _make(client, headers, org, skill, None)

        items = (await client.get(f"/skills/{skill}/courses")).json()
        got = {c["slug"]: c["qualification_name"] for c in items}

        assert got == {
            one["slug"]: "Role Alpha",
            two["slug"]: "Role Beta",
            three["slug"]: None,
        }


class TestRoleSearchShowsWhatItIsWorth:
    async def test_a_hit_carries_credits_and_not_a_nonsense_figure(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        skill = await make_skill(db)
        good = await _pack(db, "Zebra Wrangler Special", credits=Decimal("6"), standard=skill)
        nan = await _pack(db, "Quokka Handler Special", credits=Decimal("NaN"), standard=skill)

        hit = (await client.get("/roles/search", params={"q": "Zebra Wrangler Special"})).json()
        odd = (await client.get("/roles/search", params={"q": "Quokka Handler Special"})).json()

        assert [(h["qp_code"], h["credits"]) for h in hit][:1] == [(good.qp_code, 6.0)]
        assert [(h["qp_code"], h["credits"]) for h in odd][:1] == [(nan.qp_code, None)]


class TestTheSeed:
    def test_every_seeded_link_names_a_seeded_course(self) -> None:
        """A typo'd slug in the seed's table would link nothing and say nothing."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import seed_marketplace

        slugs = {course[0] for course in seed_marketplace.COURSES}
        assert seed_marketplace.COURSE_QUALIFICATIONS  # found the table before judging it
        assert set(seed_marketplace.COURSE_QUALIFICATIONS) <= slugs


class TestWhatCountsAsCredits:
    @pytest.mark.parametrize(
        ("value", "shown"),
        [
            (None, None),
            (Decimal("NaN"), None),
            (float("nan"), None),
            (float("inf"), None),
            (Decimal("Infinity"), None),
            (Decimal("0"), None),
            (Decimal("-2"), None),
            (Decimal("0.5"), 0.5),
            (Decimal("30.00"), 30.0),
        ],
    )
    def test_only_a_finite_positive_figure_is_credits(
        self, value: Decimal | float | None, shown: float | None
    ) -> None:
        """Held directly because the JSON layer would hide a `NaN` that got through (pydantic writes
        it as null), and the next caller might not serialise."""
        from api.modules.skills import usable_credits

        assert usable_credits(value) == shown


class TestARefusedUpdateIsNotSavedByTheNextCommit:
    async def test_the_edit_a_person_was_told_no_about_does_not_land(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Sprint 55's rule, at the service: a writer that can refuse refuses *before* it changes a
        field, because the next commit on this session (a bulk loop's next row) would save a field
        that was set and then refused."""
        from fastapi import HTTPException

        from api.modules.identity import Tenant
        from api.modules.marketplace import course_publishing
        from api.modules.marketplace.schemas import CourseIn, CourseSkillIn

        headers, org, skill = await _provider(client, db)
        course = await _make(client, headers, org, skill, None, publish=False)
        tenant_id = await db.scalar(select(Tenant.id).where(Tenant.slug == org))
        assert tenant_id is not None

        with pytest.raises(HTTPException) as refused:
            await course_publishing.update_course(
                db,
                tenant_id,
                course["slug"],
                CourseIn(
                    title="Changed then refused",
                    qualification_pack_code="NOPE/Q1",
                    skills=[CourseSkillIn(skill_slug=skill, level_taught=4)],
                ),
            )
        assert refused.value.status_code == 422
        await db.commit()  # the next row of a bulk loop

        saved = await db.scalar(select(Course.title).where(Course.slug == course["slug"]))
        assert saved == course["title"]
