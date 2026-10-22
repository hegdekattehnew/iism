"""The demonstration seed no longer ships generated descriptions (Sprint 73, UI-26).

The Sprint 68 review read "boilerplate on every vacancy" off the demonstration and wrote that bulk
upload inherits it. It does not: nothing in the API generates a description. The sentences are
129 job and 129 course literals in `scripts/seed_sector_expansion.py`, each the title and the sector
poured into one of six templates, which led the vacancy and course pages. A row whose description
is one of those is now seeded with none (an empty description renders nothing). This holds the six
patterns against every tuple so a seventh template cannot slip back in unnoticed.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import seed_marketplace as healthcare_seed  # noqa: E402
import seed_sector_expansion as expansion  # noqa: E402

DESC = 4  # (slug, tenant, title, title_hi, desc_en, ...) in both data lists


def test_the_patterns_match_every_generated_description_in_the_expansion_data() -> None:
    assert len(expansion.JOBS) >= 100 and len(expansion.COURSES) >= 100  # found them first
    unmatched = [
        row[DESC]
        for row in (*expansion.JOBS, *expansion.COURSES)
        if not expansion.is_template_description(row[DESC])
    ]
    assert unmatched == [], f"a description that is not one of the six templates: {unmatched[:3]}"


def test_the_hand_written_demonstration_listings_are_not_mistaken_for_templates() -> None:
    assert len(healthcare_seed.JOBS) >= 10 and len(healthcare_seed.COURSES) >= 10
    flagged = [
        row[DESC]
        for row in (*healthcare_seed.JOBS, *healthcare_seed.COURSES)
        if expansion.is_template_description(row[DESC])
    ]
    assert flagged == []


@pytest.mark.parametrize(
    "text",
    [
        "In the Retail sector: Sales Associate, working to the standards a real National "
        "Occupational Standard for this role sets out.",
        "Day-to-day responsibilities of the Welder role, anchored to the qualification pack that "
        "defines it in the Construction sector.",
        "An entry point into the Telecom sector: Tower Technician, covering the core tasks this "
        "qualification defines.",
        "A training programme preparing learners for the Bank Teller qualification in the BFSI "
        "sector.",
        "Covers the standards behind Plumber, for a learner aiming to enter the Construction "
        "sector.",
        "A skilling course built directly on the qualification pack for Cook, Tourism sector.",
    ],
)
def test_each_of_the_six_templates_is_recognised(text: str) -> None:
    assert expansion.is_template_description(text)


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "Day shift at a 120-bed hospital, assisting nurses with patient transfers.",
        # Starts alike and is not one:
        "In the Retail sector we are hiring a cashier for our Pune store.",
        "A training programme preparing learners for the exam.",  # truncated: not a template
    ],
)
def test_a_real_description_is_never_dropped(text: str | None) -> None:
    assert not expansion.is_template_description(text)


def test_both_seed_loops_route_the_description_through_the_filter() -> None:
    """The patterns are only worth holding if the loops that write the rows use them."""
    source = (ROOT / "scripts" / "seed_sector_expansion.py").read_text(encoding="utf-8")
    assert source.count("generic = is_template_description(d_en)") == 2  # jobs and courses
    assert source.count("None if generic else d_en") == 2
    assert source.count("None if generic else d_hi") == 2  # the Hindi twin goes with it
    # ...and a stale Hindi one from an earlier run is dropped:
    assert source.count("await _forget_description_translation(db,") == 2


# --- Sprint 94, BL-22.9: a demonstration vacancy is called what the job is called ---------

from api.modules.marketplace.listings import title_reads_like_a_course  # noqa: E402

TITLE, TITLE_HI = 2, 3

# What the demonstration had before the suffix came off was 42 of 129 vacancies; 19 remain, each a
# qualification's whole name that only a person who knows the work can rename. A ratchet: it may go
# down (a rename, or a row removed), never up.
STILL_READ_LIKE_A_COURSE = 19


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("Mushroom Grower (Small Unit) — Trainee Programme", "Mushroom Grower (Small Unit)"),
        ("Diamond Assorter - Trainee Programme", "Diamond Assorter"),
        ("मशरूम उत्पादक (लघु इकाई) — प्रशिक्षु कार्यक्रम", "मशरूम उत्पादक (लघु इकाई)"),
        ("Cook", "Cook"),
        ("Trainee Programme", "Trainee Programme"),  # never leaves nothing
        ("Programme Manager", "Programme Manager"),
    ],
)
def test_the_programme_suffix_comes_off_a_vacancy_title_and_nothing_else(
    given: str, expected: str
) -> None:
    assert expansion.as_a_job_title(given) == expected


def test_no_demonstration_vacancy_is_called_a_trainee_programme() -> None:
    assert len(expansion.JOBS) >= 100  # found them first
    left = [
        row[TITLE]
        for row in expansion.JOBS
        if "Trainee Programme" in expansion.as_a_job_title(row[TITLE])
        or "प्रशिक्षु कार्यक्रम" in expansion.as_a_job_title(row[TITLE_HI])
    ]
    assert left == []


def test_the_vacancies_that_still_read_like_a_course_do_not_grow_in_number() -> None:
    like = [
        expansion.as_a_job_title(row[TITLE])
        for row in expansion.JOBS
        if title_reads_like_a_course(expansion.as_a_job_title(row[TITLE]))
    ]
    assert len(like) <= STILL_READ_LIKE_A_COURSE, like[:5]
