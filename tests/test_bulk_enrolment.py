"""Government-agency bulk enrolment (Sprint 33, BL-7.1): the thin slice.

No script in this project has had a test before -- `seed_candidates.py` and
`grant_staff.py` are both exercised by hand. This one enrolls real people's
data from a partner-supplied CSV, so its idempotency and consent handling are
worth more than a manual run can prove.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION
from api.modules.geography.models import District, State
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile
from scripts.bulk_enrol_candidates import _enrol_one

ROW = {
    "phone": "9820000001",
    "full_name": "Test Candidate",
    "headline": "Trainee",
    "state": "Test State",
    "district": "Test District",
    "years_experience": "2",
}


async def _geography(db: AsyncSession) -> None:
    state = State(state_code=9001, slug="test-state-enrol", name="Test State")
    db.add(state)
    await db.flush()
    db.add(District(district_code=9001, name="Test District", state_id=state.id))
    await db.flush()


async def test_a_new_candidate_is_enrolled_with_consent_and_geography(
    db: AsyncSession,
) -> None:
    await _geography(db)

    outcome = await _enrol_one(db, ROW, "TEST-PROGRAMME", apply=True)
    assert outcome == "created"

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


async def test_a_second_run_is_a_no_op(db: AsyncSession) -> None:
    """Told once, enrolled once. The same shape as `JobAlert`'s uniqueness."""
    await _geography(db)

    first = await _enrol_one(db, ROW, "TEST-PROGRAMME", apply=True)
    second = await _enrol_one(db, ROW, "TEST-PROGRAMME", apply=True)

    assert first == "created"
    assert second == "already_enrolled"

    users = (await db.scalars(select(User).where(User.phone == "+919820000001"))).all()
    assert len(users) == 1


async def test_dry_run_writes_nothing(db: AsyncSession) -> None:
    await _geography(db)

    outcome = await _enrol_one(db, ROW, "TEST-PROGRAMME", apply=False)
    assert outcome == "created"

    assert await db.scalar(select(User).where(User.phone == "+919820000001")) is None


async def test_an_existing_self_registered_account_is_tagged_not_overwritten(
    db: AsyncSession,
) -> None:
    """An account that signed up on its own keeps its own profile data --
    enrolment only adds the programme tag, it never rewrites what someone
    already told the platform about themselves."""
    await _geography(db)

    user = User(phone="+919820000001", full_name="Self-Registered Name")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(user_id=user.id, headline="My own headline", years_experience=9)
    db.add(profile)
    await db.flush()

    outcome = await _enrol_one(db, ROW, "TEST-PROGRAMME", apply=True)
    assert outcome == "tagged"

    await db.refresh(profile)
    assert profile.headline == "My own headline"
    assert profile.years_experience == 9
    assert profile.enrolled_via_programme == "TEST-PROGRAMME"
    assert user.full_name == "Self-Registered Name"


async def test_an_account_with_no_profile_gets_one(db: AsyncSession) -> None:
    """Signed in once, never finished a profile. The programme tag needs
    somewhere to live, so enrolment creates the profile it is missing."""
    await _geography(db)

    user = User(phone="+919820000001")
    db.add(user)
    await db.flush()

    outcome = await _enrol_one(db, ROW, "TEST-PROGRAMME", apply=True)
    assert outcome == "tagged"

    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    assert profile is not None
    assert profile.enrolled_via_programme == "TEST-PROGRAMME"


async def test_a_malformed_row_raises_rather_than_silently_skipping(db: AsyncSession) -> None:
    await _geography(db)
    bad_row = dict(ROW, years_experience="not-a-number")
    try:
        await _enrol_one(db, bad_row, "TEST-PROGRAMME", apply=True)
        raised = False
    except ValueError:
        raised = True
    assert raised
