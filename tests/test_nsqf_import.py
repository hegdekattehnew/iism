"""The NSQF import, end to end, against a JSON fixture rather than MongoDB.

The corpus is the one dependency this project cannot spin up disposably, so the
importer is driven through the `NsqfSource` port (ADR-017) with a file-backed
implementation that shares its document parsing with the Mongo one. What is
tested here is therefore the real import path, not a rehearsal of it.

Every assertion below stands for a specific way the national data has already
misled this importer, or would have.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from api.adapters.nsqf.importer import import_nsqf
from api.adapters.nsqf.jsonfile import JsonFileNsqfSource
from api.adapters.nsqf.normalise import (
    NormalisationError,
    make_qp_slug,
    make_skill_slug,
    parse_credits,
    parse_hhmm_to_minutes,
    parse_level,
)
from api.modules.skills.hierarchy import (
    ModelCurriculum,
    QpSkill,
    QualificationPack,
    Sector,
    SubSector,
)
from api.modules.skills.models import Skill

FIXTURE = Path(__file__).parent / "fixtures" / "nsqf_sample.json"


@pytest.fixture
def source() -> JsonFileNsqfSource:
    return JsonFileNsqfSource(FIXTURE)


async def _import(db, source):
    report = await import_nsqf(db, source)
    await db.flush()
    return report


# --------------------------------------------------------------- normalisation


class TestNormalisation:
    def test_level_forms_that_mean_the_same_level_normalise_together(self) -> None:
        """'4' and '4.0' both appear in the corpus for the same level."""
        assert parse_level("4") == parse_level("4.0") == Decimal("4.0")

    def test_half_levels_survive(self) -> None:
        """1,369 real qualifications sit at a half-level. Rounding loses them."""
        assert parse_level("4.5") == Decimal("4.5")

    @pytest.mark.parametrize("value", ["0.5", "11", "not a number"])
    def test_levels_outside_the_framework_are_rejected(self, value: str) -> None:
        with pytest.raises(NormalisationError):
            parse_level(value)

    def test_durations_parse_to_minutes(self) -> None:
        """Hours are HH:MM strings; minutes is the only lossless target."""
        assert parse_hhmm_to_minutes("570:00") == 34200
        assert parse_hhmm_to_minutes("60:30") == 3630

    def test_zero_duration_is_a_real_answer_not_a_missing_one(self) -> None:
        """'00:00' means no OJT required, which is different from unknown."""
        assert parse_hhmm_to_minutes("00:00") == 0
        assert parse_hhmm_to_minutes(None) is None

    def test_unreadable_duration_raises_rather_than_defaulting_to_zero(self) -> None:
        with pytest.raises(NormalisationError):
            parse_hhmm_to_minutes("not a duration")

    def test_tbd_credits_are_unknown_not_zero(self) -> None:
        """`credits` is very often the literal string 'TBD'."""
        assert parse_credits("TBD") is None
        assert parse_credits("2.0") == Decimal("2.0")

    def test_qp_slug_keeps_the_code_when_the_name_is_long(self) -> None:
        """Truncating name-code once cut the code off and collided slugs."""
        a = make_qp_slug("A very long qualification name " * 8, "SSC/Q1111", "1.0")
        b = make_qp_slug("A very long qualification name " * 8, "SSC/Q2222", "1.0")
        assert a != b
        assert a.endswith("ssc-q1111-1-0")

    def test_a_unit_with_no_usable_code_cannot_be_slugged(self) -> None:
        with pytest.raises(NormalisationError):
            make_skill_slug("A title", "   ")


# ------------------------------------------------------------------ the import


class TestImport:
    async def test_imports_the_whole_shape(self, db, source) -> None:
        report = await _import(db, source)

        assert report.sectors == 2
        assert report.sub_sectors == 3
        # HC/Q0001 exists twice; only the newest version is kept.
        assert report.qualification_packs == 4
        assert report.skills == 5

    async def test_only_the_latest_version_of_a_qualification_is_kept(self, db, source) -> None:
        """Prior versions stay in the source of record; Postgres holds today's."""
        await _import(db, source)

        rows = (
            await db.execute(
                select(QualificationPack.version, QualificationPack.nsqf_level).where(
                    QualificationPack.qp_code == "HC/Q0001"
                )
            )
        ).all()
        assert rows == [("2.0", Decimal("4.5"))]

    async def test_half_levels_reach_the_database_intact(self, db, source) -> None:
        """The whole reason for Numeric(3,1). An Integer column rejects these."""
        await _import(db, source)

        levels = set(
            (await db.scalars(select(QualificationPack.nsqf_level))).all(),
        )
        assert Decimal("4.5") in levels
        assert Decimal("3.5") in levels

    async def test_one_sector_id_with_two_spellings_is_one_sector(self, db, source) -> None:
        """SEC01 appears as 'Healthcare' and 'Healthcare ' -- four such pairs
        exist in the real feed, and splitting them would fork the hierarchy."""
        await _import(db, source)

        refs = (await db.scalars(select(Sector.sector_ref))).all()
        assert sorted(refs) == ["SEC01", "SEC02"]

        sub_count = await db.scalar(
            select(func.count())
            .select_from(SubSector)
            .join(Sector, SubSector.sector_id == Sector.id)
            .where(Sector.sector_ref == "SEC01")
        )
        assert sub_count == 2

    async def test_trailing_whitespace_in_a_title_does_not_reach_the_slug(self, db, source) -> None:
        """1,050 NOS titles in the real corpus carry trailing whitespace."""
        await _import(db, source)

        slug = await db.scalar(select(Skill.slug).where(Skill.nos_code == "HC/N0001"))
        assert slug == "collect-blood-samples-hc-n0001"

    async def test_elective_units_keep_their_group(self, db, source) -> None:
        """An elective sits in a named 'choose one of these' bundle. Flattened
        into a bare link it reads as a requirement, which is a different claim."""
        await _import(db, source)

        row = (
            await db.execute(
                select(QpSkill.requirement, QpSkill.group_name)
                .join(Skill, QpSkill.skill_id == Skill.id)
                .where(Skill.nos_code == "RT/N0002")
            )
        ).one()
        assert row.requirement == "elective"
        assert row.group_name == "Customer service specialisation"

    async def test_optional_units_are_distinguished_from_elective_ones(self, db, source) -> None:
        await _import(db, source)

        requirement = await db.scalar(
            select(QpSkill.requirement)
            .join(Skill, QpSkill.skill_id == Skill.id)
            .where(Skill.nos_code == "RT/N0003")
        )
        assert requirement == "optional"

    async def test_a_units_contextual_level_comes_from_its_qualification(self, db, source) -> None:
        """A NOS carries no level of its own -- none of the 27,538 do."""
        await _import(db, source)

        levels = (
            await db.scalars(
                select(QpSkill.nsqf_level)
                .join(Skill, QpSkill.skill_id == Skill.id)
                .where(Skill.nos_code == "HC/N0002")
            )
        ).all()
        # Shared by a 4.5 qualification and a 4.0 one, and carries both.
        assert sorted(levels) == [Decimal("4.0"), Decimal("4.5")]

    async def test_displayed_level_is_the_modal_level_of_containing_packs(self, db, source) -> None:
        await _import(db, source)

        level = await db.scalar(select(Skill.nsqf_level).where(Skill.nos_code == "HC/N0001"))
        assert level == Decimal("4.5")

    async def test_qp_count_is_denormalised_for_the_browse_ordering(self, db, source) -> None:
        await _import(db, source)

        counts = dict(
            (
                await db.execute(
                    select(Skill.nos_code, Skill.qp_count).where(Skill.nos_code.isnot(None))
                )
            ).all()  # type: ignore[arg-type]
        )
        assert counts["HC/N0002"] == 2
        assert counts["HC/N0001"] == 1

    async def test_curriculum_hours_parse_to_minutes(self, db, source) -> None:
        await _import(db, source)

        total = await db.scalar(
            select(ModelCurriculum.total_minutes).where(ModelCurriculum.qp_code == "HC/Q0001")
        )
        assert total == 34200

    async def test_an_unreadable_grand_total_leaves_the_curriculum_importable(
        self, db, source
    ) -> None:
        """A bad duration is not a reason to lose the whole curriculum."""
        await _import(db, source)

        total = await db.scalar(
            select(ModelCurriculum.total_minutes).where(ModelCurriculum.qp_code == "RT/Q0001")
        )
        assert total is None

    async def test_blank_curriculum_unit_codes_are_counted_not_hidden(self, db, source) -> None:
        """2,399 entries in the real feed have a unitCode that is present but
        empty. Dropping them silently would understate the gap; raising on each
        would bury real failures."""
        report = await _import(db, source)
        assert report.mc_entries_without_code == 1

    async def test_a_qualification_with_an_unreadable_level_still_imports(self, db, source) -> None:
        """The level is unknown; the qualification is not invalid."""
        await _import(db, source)

        level = await db.scalar(
            select(QualificationPack.nsqf_level).where(QualificationPack.qp_code == "XX/Q9999")
        )
        assert level is None

    async def test_a_unit_with_no_usable_code_is_counted_not_silently_dropped(
        self, db, source
    ) -> None:
        """Nothing can refer to a unit with no code, so it cannot be imported --
        but it must still be visible in the report. No NOS in the corpus is
        missing its code today, which is precisely why a silent drop here would
        go unnoticed if a future re-issue introduced one."""
        report = await _import(db, source)

        assert report.skills == 5  # the sixth distinct code; the seventh had none
        assert report.documents_without_code == 1


class TestIdempotency:
    async def test_a_second_run_changes_no_counts(self, db, source) -> None:
        """Re-running must pick up revisions without duplicating anything --
        Qualification Packs are revised and re-issued, so this is the normal
        path, not an edge case."""
        first = await _import(db, source)
        second = await _import(db, JsonFileNsqfSource(FIXTURE))

        for field in (
            "sectors",
            "sub_sectors",
            "occupations",
            "skills",
            "qualification_packs",
            "qp_skills",
        ):
            assert getattr(first, field) == getattr(second, field), field

        for model in (Skill, QualificationPack, QpSkill, Sector, SubSector):
            assert await db.scalar(select(func.count()).select_from(model)) == await db.scalar(
                select(func.count()).select_from(model)
            )

    async def test_a_revised_title_updates_in_place(self, db, source) -> None:
        await _import(db, source)

        revised = JsonFileNsqfSource(FIXTURE)
        revised._docs["nos"][0] = {**revised._docs["nos"][0], "unitTitle": "Collect samples"}
        await _import(db, revised)

        titles = (await db.scalars(select(Skill.name_en).where(Skill.nos_code == "HC/N0001"))).all()
        assert titles == ["Collect samples"]


class TestApiSurface:
    """The half-level path through the API, which is where it broke in practice:
    the columns were widened but the response models still declared int, so 38%
    of the taxonomy returned 500 while every transliteration check still passed.
    """

    async def test_a_half_level_skill_serialises(self, db, client, source) -> None:
        await _import(db, source)

        response = await client.get("/skills", params={"nsqf_level": 4.5})
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    async def test_facets_offer_the_half_levels_that_exist(self, db, client, source) -> None:
        await _import(db, source)

        response = await client.get("/skills/facets")
        assert response.status_code == 200
        assert 4.5 in {facet["level"] for facet in response.json()["levels"]}

    async def test_a_skill_page_reports_its_qualifications(self, db, client, source) -> None:
        await _import(db, source)

        slug = await db.scalar(select(Skill.slug).where(Skill.nos_code == "HC/N0002"))
        response = await client.get(f"/skills/{slug}/qualifications")
        assert response.status_code == 200

        body = response.json()
        assert body["total"] == 2
        assert {item["nsqf_level"] for item in body["items"]} == {4.0, 4.5}
