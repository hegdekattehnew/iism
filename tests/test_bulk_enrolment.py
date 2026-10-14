"""The enrolment script (Sprint 33, BL-7.1) and the engine it now calls (Sprint 61).

No script in this project had a test before this one. It enrols real people's data from a
partner-supplied file, so its idempotency and consent handling are worth more than a manual run can
prove. The behaviours below are the script's original ones, kept as the baseline the shared engine
has to match; `tests/test_enrolment_upload.py` covers the same engine through the back office.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION
from api.modules.geography.models import District, State
from api.modules.identity.models import User
from api.modules.marketplace.bulk import BulkFileError
from api.modules.marketplace.models import CandidateProfile
from api.modules.operations.models import EnrolmentBatch
from scripts.bulk_enrol_candidates import enrol_file

HEADER = "phone,full_name,headline,state,district,years_experience\n"
ROW = "9820000001,Test Candidate,Trainee,Test State,Test District,2\n"


async def _geography(db: AsyncSession) -> None:
    state = State(state_code=9001, slug="test-state-enrol", name="Test State")
    db.add(state)
    await db.flush()
    db.add(District(district_code=9001, name="Test District", state_id=state.id))
    await db.flush()


async def _admin(db: AsyncSession, email: str = "ops-admin@iism-fixtures.co.in") -> User:
    admin = User(email=email, is_staff=True, staff_tier="admin")
    db.add(admin)
    await db.flush()
    return admin


def _file(tmp_path: Path, body: str = ROW) -> Path:
    path = tmp_path / "enrol.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


async def _enrol(db: AsyncSession, path: Path, **kwargs):  # type: ignore[no-untyped-def]
    return await enrol_file(
        db,
        path,
        "TEST-PROGRAMME",
        apply=kwargs.get("apply", True),
        attest=kwargs.get("attest", True),
        operator_email=kwargs.get("operator_email", "ops-admin@iism-fixtures.co.in"),
    )


async def test_a_new_candidate_is_enrolled_with_consent_and_geography(
    db: AsyncSession, tmp_path: Path
) -> None:
    await _geography(db)
    await _admin(db)

    report = await _enrol(db, _file(tmp_path))
    assert report.count("new") == 1

    user = await db.scalar(select(User).where(User.phone == "+919820000001"))
    assert user is not None
    assert user.full_name == "Test Candidate"
    assert user.consent_version == PRIVACY_NOTICE_VERSION
    assert user.consented_at is not None

    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    assert profile is not None
    assert profile.headline == "Trainee"
    assert profile.years_experience == 2
    assert profile.enrolled_via_programme == "TEST-PROGRAMME"
    assert profile.state_id is not None
    assert profile.district_id is not None


async def test_a_second_run_is_a_no_op(db: AsyncSession, tmp_path: Path) -> None:
    """Told once, enrolled once. The same shape as `JobAlert`'s uniqueness."""
    await _geography(db)
    await _admin(db)
    path = _file(tmp_path)

    first = await _enrol(db, path)
    second = await _enrol(db, path)

    assert (first.count("new"), second.count("new"), second.count("already")) == (1, 0, 1)
    users = (await db.scalars(select(User).where(User.phone == "+919820000001"))).all()
    assert len(users) == 1


async def test_dry_run_writes_nothing(db: AsyncSession, tmp_path: Path) -> None:
    await _geography(db)

    report = await _enrol(db, _file(tmp_path), apply=False, attest=False, operator_email=None)
    assert report.count("new") == 1

    assert await db.scalar(select(User).where(User.phone == "+919820000001")) is None
    assert await db.scalar(select(func.count()).select_from(EnrolmentBatch)) == 0


async def test_an_existing_self_registered_account_is_tagged_not_overwritten(
    db: AsyncSession, tmp_path: Path
) -> None:
    """An account that signed up on its own keeps its own profile data --
    enrolment only adds the programme tag, it never rewrites what someone
    already told the platform about themselves."""
    await _geography(db)
    await _admin(db)

    user = User(phone="+919820000001", full_name="Self-Registered Name")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(user_id=user.id, headline="My own headline", years_experience=9)
    db.add(profile)
    await db.flush()

    report = await _enrol(db, _file(tmp_path))
    assert report.count("tag") == 1

    await db.refresh(profile)
    assert profile.headline == "My own headline"
    assert profile.years_experience == 9
    assert profile.enrolled_via_programme == "TEST-PROGRAMME"
    assert user.full_name == "Self-Registered Name"


async def test_an_account_with_no_profile_gets_one(db: AsyncSession, tmp_path: Path) -> None:
    """Signed in once, never finished a profile. The programme tag needs
    somewhere to live, so enrolment creates the profile it is missing."""
    await _geography(db)
    await _admin(db)

    user = User(phone="+919820000001")
    db.add(user)
    await db.flush()

    report = await _enrol(db, _file(tmp_path))
    assert report.count("tag") == 1

    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    assert profile is not None
    assert profile.enrolled_via_programme == "TEST-PROGRAMME"


async def test_a_malformed_row_is_reported_rather_than_silently_skipped(
    db: AsyncSession, tmp_path: Path
) -> None:
    await _geography(db)
    await _admin(db)

    report = await _enrol(
        db, _file(tmp_path, "9820000001,Test,Trainee,Test State,Test District,not-a-number\n")
    )
    assert report.count("error") == 1
    assert "years_experience" in report.rows[0].errors[0]
    assert await db.scalar(select(User).where(User.phone == "+919820000001")) is None


class TestTheScriptsOwnRules:
    """What the command line adds to the engine: it will not enrol without a named admin and an
    attestation."""

    async def test_apply_needs_the_attestation(self, db: AsyncSession, tmp_path: Path) -> None:
        await _admin(db)
        with pytest.raises(BulkFileError, match="privacy notice"):
            await _enrol(db, _file(tmp_path), attest=False)
        assert await db.scalar(select(User).where(User.phone == "+919820000001")) is None

    async def test_apply_needs_an_admin_tier_operator(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        db.add(User(email="support@iism-fixtures.co.in", is_staff=True, staff_tier="support"))
        db.add(User(email="nobody@iism-fixtures.co.in"))
        await db.flush()
        for email in (
            None,
            "missing@iism-fixtures.co.in",
            "support@iism-fixtures.co.in",
            "nobody@iism-fixtures.co.in",
        ):
            with pytest.raises(BulkFileError, match="admin-tier"):
                await _enrol(db, _file(tmp_path), operator_email=email)
        assert await db.scalar(select(User).where(User.phone == "+919820000001")) is None

    async def test_the_batch_names_the_operator_who_ran_it(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        await _geography(db)
        admin = await _admin(db)
        report = await _enrol(db, _file(tmp_path))
        batch = await db.get(EnrolmentBatch, report.batch_id)
        assert batch is not None and batch.actor_user_id == admin.id
        assert batch.file_name == "enrol.csv"
