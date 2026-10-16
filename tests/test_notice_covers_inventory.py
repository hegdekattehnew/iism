"""The privacy notice says what is stored, and a new column cannot slip past it (Sprint 72).

The notice used to say employers never see a name or contact, omitted the date of birth, gender,
salary and application messages, and nobody noticed for months, because nothing compared it with
the data. This walks the models that hold a person's data and fails on any column that is neither
**covered** (a phrase the English notice must contain) nor **excused** with a reason. A new personal
column therefore fails here until somebody decides how the notice should say it, which is the same
move `test_privacy_coverage.py` makes for the data export.

Only the English text is checked for the phrase; the Hindi and Malay catalogues are held to the same
shape by the messages parity test, and the Hindi is flagged for a native reader.
"""

import json
from pathlib import Path

from api.modules.applications.models import Application
from api.modules.identity.models import User
from api.modules.interests.models import CourseInterest
from api.modules.marketplace.models import CandidateProfile
from api.modules.notifications.models import DeviceToken

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = ROOT / "web" / "src" / "messages"

# column -> a phrase (lower case) the notice's "what we hold" or "why we hold it" must contain.
COVERED: dict[type, dict[str, str]] = {
    User: {
        "phone": "mobile number",
        "email": "email address",
        "full_name": "your name",
        "preferred_locale": "your language",
        "consent_version": "which version of this notice",
        "consented_at": "which version of this notice",
        "consent_withdrawn_at": "when you withdrew consent",
    },
    CandidateProfile: {
        "headline": "a headline",
        "location_state": "state and district",
        "location_district": "state and district",
        "years_experience": "experience",
        "education_level": "education",
        "date_of_birth": "date of birth",
        "gender": "your gender",
        "willing_to_relocate": "relocate",
        "job_alerts_enabled": "you can turn these off in your profile",
        "preferred_employment_type": "kind of work you want",
        "expected_salary_min_inr": "salary you expect",
        "expected_salary_max_inr": "salary you expect",
        "notice_period": "your notice period",
        "current_role_slug": "the role you say you do now",
        "enrolled_via_programme": "agency programme",
        "embedding": "numeric summary of your skills",
    },
    Application: {
        "message": "any message you write",
        "status_message": "what the employer or training provider replies",
        "employer_notes": "private note about an application",
        "contact_shared_at": "shared with that employer",
    },
    CourseInterest: {
        "message": "any message you write",
        "contact_shared_at": "shared with that training provider",
    },
    DeviceToken: {
        "token": "the code your phone gives us",
        "platform": "the code your phone gives us",
        "locale": "the code your phone gives us",
    },
}

# Columns that hold no personal data, or that are the notice's subject only in aggregate, with why.
EXCUSED: dict[type, dict[str, str]] = {
    User: {
        "id": "a random identifier",
        "phone_verified_at": "a stamp on the mobile number the notice already names",
        "email_verified_at": "a stamp on the email address the notice already names",
        "is_active": "account state",
        "is_staff": "operator authority, read-only for ever (ADR-042)",
        "staff_tier": "operator authority, read-only for ever (ADR-044)",
        "created_at": "a row stamp",
        "updated_at": "a row stamp",
    },
    CandidateProfile: {
        "id": "a random identifier",
        "user_id": "the link to the account",
        "state_id": "the resolved key beside the typed place the notice names",
        "district_id": "the resolved key beside the typed place the notice names",
        "onboarding_completed_at": "a stamp on the profile the notice names",
        "created_at": "a row stamp",
        "updated_at": "a row stamp",
        "embedding_provider": "which model made the summary the notice names",
        "embedding_model": "which model made the summary the notice names",
        "embedding_computed_at": "when the summary the notice names was made",
    },
    Application: {
        "id": "a random identifier",
        "job_id": "the vacancy",
        "profile_id": "the link to the person",
        "status": "the state of an application the notice names",
        "contact_revoked_at": "the withdrawal the notice names",
        "status_message_at": "a stamp on a reply the notice names",
        "employer_notes_at": "a stamp on a note the notice names",
        "created_at": "a row stamp",
        "updated_at": "a row stamp",
    },
    CourseInterest: {
        "id": "a random identifier",
        "course_id": "the course",
        "profile_id": "the link to the person",
        "status": "the state of an interest the notice names",
        "contact_revoked_at": "the withdrawal the notice names",
        "created_at": "a row stamp",
        "updated_at": "a row stamp",
    },
    DeviceToken: {
        "id": "a random identifier",
        "user_id": "the link to the account",
        "created_at": "a row stamp",
        "last_seen_at": "a row stamp",
    },
}


def _notice_text() -> str:
    """The sections that say what is held and why, lower-cased and joined."""
    catalogue = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))
    sections = catalogue["legal"]["privacy"]["sections"]
    wanted = [s for s in sections if s["title"] in ("What we hold", "Why we hold it")]
    assert len(wanted) == 2, [s["title"] for s in sections]
    return " ".join(line for s in wanted for line in s["body"]).lower()


def test_every_personal_column_is_in_the_notice_or_excused_with_a_reason() -> None:
    text = _notice_text()
    walked = 0
    problems: list[str] = []
    for model in COVERED.keys() | EXCUSED.keys():
        for column in model.__table__.columns:
            walked += 1
            name = column.name
            phrase = COVERED.get(model, {}).get(name)
            if phrase is not None:
                if phrase not in text:
                    problems.append(f"{model.__name__}.{name}: the notice does not say {phrase!r}")
            elif name not in EXCUSED.get(model, {}):
                problems.append(
                    f"{model.__name__}.{name}: new column. Say it in the notice and add it to "
                    "COVERED, or excuse it in EXCUSED with the reason"
                )
    assert walked > 60, "found almost no columns; the walk is wrong"
    assert problems == [], "\n".join(problems)


def test_a_column_cannot_be_both_covered_and_excused() -> None:
    for model in COVERED.keys() & EXCUSED.keys():
        assert COVERED[model].keys().isdisjoint(EXCUSED[model].keys()), model.__name__


def test_the_check_can_fail() -> None:
    """The phrase lookup has to say no when the notice lacks the words."""
    assert "date of birth" in _notice_text()
    assert "a column the notice never mentions" not in _notice_text()


def test_the_notice_no_longer_says_employers_never_see_contact() -> None:
    """The sentence that was false: applying shares name and contact, and the notice says so."""
    text = _notice_text()
    assert "never your name, number or email" in text  # of the candidate list, which is true
    assert "your name, phone number, email" in text  # of an application, which is also true
    assert "that employer" in text
