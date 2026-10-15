"""The store-facing documents in `docs/release/` (Sprint 66, ADR-077).

They are drafts for people to confirm, and a draft that is wrong in a checkable way should not
need a person to find it. Held here:

* every listing field within its store's limit, in **both** languages;
* no claim the product cannot back;
* the data-safety inventory naming every section of the data export;
* no secret in the reviewer notes;
* the runbook mentioning the steps that must not be forgotten.

Each test asserts it found what it is checking before it judges it.
"""

import re
from pathlib import Path

import pytest

from tests.test_privacy_coverage import EXPORTED

RELEASE = Path(__file__).resolve().parent.parent / "docs" / "release"

# Apple and Google, as understood on 2026-10-15; the consoles are the authority at submission.
LIMITS = {
    "Title": 30,
    "Subtitle": 30,
    "Short description": 80,
    "Promotional text": 170,
    "Keywords": 100,
    "Full description": 4000,
    "What's new": 500,
}
# What the listing may never promise. The product computes a match score and nothing about outcomes.
FORBIDDEN = re.compile(
    r"guarante|assured|100\s*%|\bno\.?\s*1\b|\bbest\b|placement|government[- ]approved|"
    r"गारंटी|पक्की नौकरी|सर्वश्रेष्ठ|प्लेसमेंट",
    re.IGNORECASE,
)
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _listing() -> dict[str, dict[str, str]]:
    text = (RELEASE / "store-listing.md").read_text(encoding="utf-8")
    locales: dict[str, dict[str, str]] = {}
    for block in re.split(r"\n## ", text)[1:]:
        heading = block.split("\n", 1)[0]
        if not heading.startswith(("English", "Hindi")):
            continue
        fields = {
            m.group(1): m.group(2).strip()
            for m in re.finditer(r"### (.+?)\n(.*?)(?=\n### |\Z)", block, re.S)
        }
        locales[heading.split()[0]] = fields
    return locales


def test_the_listing_is_found_in_both_languages_with_every_field() -> None:
    locales = _listing()
    assert set(locales) == {"English", "Hindi"}
    for language, fields in locales.items():
        assert set(fields) == set(LIMITS), (language, set(LIMITS) ^ set(fields))
        assert all(value for value in fields.values()), language


@pytest.mark.parametrize("language", ["English", "Hindi"])
def test_every_field_is_within_its_limit(language: str) -> None:
    fields = _listing()[language]
    assert fields  # found before judged
    for name, limit in LIMITS.items():
        assert len(fields[name]) <= limit, f"{language} {name}: {len(fields[name])} > {limit}"


def test_keywords_are_comma_separated_with_no_padding() -> None:
    for language, fields in _listing().items():
        keywords = fields["Keywords"].split(",")
        assert len(keywords) >= 5, language
        assert all(k == k.strip() and k for k in keywords), (
            f"{language}: stray space or empty keyword"
        )
        assert len({k.lower() for k in keywords}) == len(keywords), f"{language}: a keyword twice"


def test_the_hindi_listing_is_in_hindi_and_the_english_is_not() -> None:
    locales = _listing()
    for name in ("Title", "Short description", "Full description", "Promotional text"):
        assert DEVANAGARI.search(locales["Hindi"][name]), name
        assert not DEVANAGARI.search(locales["English"][name]), name


def test_the_listing_promises_nothing_the_product_cannot_back() -> None:
    text = (RELEASE / "store-listing.md").read_text(encoding="utf-8")
    body = text.split("## English", 1)[1]  # the "never claim" preface names the words on purpose
    assert FORBIDDEN.search(body) is None, FORBIDDEN.search(body)
    assert FORBIDDEN.search("a guaranteed job"), "the detector must be able to fail"
    assert FORBIDDEN.search("पक्की नौकरी पाएँ")


def test_the_listing_says_who_the_app_is_for() -> None:
    for language, fields in _listing().items():
        description = fields["Full description"]
        assert "IISM" in description, language
        assert ("website" in description) or ("वेबसाइट" in description), language


def test_the_data_inventory_names_every_section_of_the_export() -> None:
    """A new section in `export_account` must reach the stores' answers (`EXPORTED` is kept equal to
    the schema by `test_privacy_coverage`)."""
    text = (RELEASE / "privacy-and-data-safety.md").read_text(encoding="utf-8")
    keys = set(EXPORTED.values()) | {"account", "memberships", "candidate_profile"}
    assert len(keys) >= 15, keys  # found them before judging any
    missing = sorted(k for k in keys if f"`{k}`" not in text)
    assert missing == [], f"the data-safety inventory does not name: {missing}"


def test_the_privacy_answers_state_the_commitments_the_code_keeps() -> None:
    text = (RELEASE / "privacy-and-data-safety.md").read_text(encoding="utf-8")
    for needle in (
        "no advertising",
        "HTTPS",
        "DELETE /me/account",
        "push vendor",
        "ITSAppUsesNonExemptEncryption",
    ):
        assert needle in text, needle


def test_the_reviewer_notes_hold_no_secret() -> None:
    text = (RELEASE / "review-notes.md").read_text(encoding="utf-8")
    assert "REVIEWER_CODE" in text  # it names the variable, so the omission is deliberate
    assert re.search(r"\b\d{6}\b", text) is None, "a six-digit code in the reviewer notes"
    assert re.search(r"\+?\d[\d ]{9,}", text) is None, "a phone number in the reviewer notes"


def test_the_runbook_keeps_the_steps_that_must_not_be_forgotten() -> None:
    text = (RELEASE / "release-runbook.md").read_text(encoding="utf-8")
    for needle in (
        "make check-release PROFILE=production",
        "REVIEWER_LOGIN_ENABLED=false",
        "rotate",
        "MOBILE_MIN_VERSION_ANDROID",
        "check_api_contract.py --release",
        "14 days",
        "make restore-drill",
        "Rollback",
    ):
        assert needle in text, needle
