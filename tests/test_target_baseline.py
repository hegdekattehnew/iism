"""The touch-target ratchet (Sprint 78, BL-19.9): a page's small controls only ever go down.

The browser sweep compares each page with `web/e2e/support/target-baseline.json`; this file holds
the recording script and the file's shape. The sweep itself (a page that gets a new small
control fails) is mutation-checked in the browser, not here.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from merge_target_baseline import merge, normalise  # noqa: E402

BASELINE = ROOT / "web" / "e2e" / "support" / "target-baseline.json"


def _line(label: str, count: int) -> str:
    return json.dumps({"label": label, "count": count})


def test_a_new_page_is_recorded() -> None:
    assert merge({}, [_line("en/jobs", 2)]) == {"en/jobs": 2}


def test_a_known_page_only_ever_goes_down() -> None:
    before = {"en/jobs": 3}
    assert merge(before, [_line("en/jobs", 1)]) == {"en/jobs": 1}
    assert merge(before, [_line("en/jobs", 5)]) == {"en/jobs": 3}, (
        "recording after a regression raised a ceiling"
    )


def test_raising_a_page_is_a_named_act() -> None:
    assert merge({"en/jobs": 3}, [_line("en/jobs", 5)], {"en/jobs"}) == {"en/jobs": 5}
    assert (
        merge({"en/jobs": 3, "en/courses": 1}, [_line("en/courses", 4)], {"en/jobs"})["en/courses"]
        == 1
    )


def test_the_lowest_of_a_pages_repeats_wins() -> None:
    assert merge({}, [_line("a", 4), _line("a", 2), _line("a", 3)]) == {"a": 2}


def test_a_count_must_be_a_whole_number() -> None:
    for bad in (-1, 1.5, "2", None):
        with pytest.raises(ValueError):
            merge({}, [json.dumps({"label": "a", "count": bad})])


def test_a_page_made_for_the_run_is_recorded_by_page_not_by_run() -> None:
    assert normalise("employer en/jobs/sweep-vacancy-4a898c47-bengaluru/applications") == (
        "employer en/jobs/sweep-vacancy-<id>-bengaluru/applications"
    )
    assert normalise("seeker en/profile") == "seeker en/profile"


def test_the_recorded_baseline_covers_the_pages_that_matter_and_is_well_formed() -> None:
    recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert len(recorded) >= 100, (
        "the baseline is nearly empty: a ratchet over nothing holds nothing"
    )
    for page in (
        "en/jobs",
        "hi/jobs",
        "en/signin",
        "seeker en/profile",
        "seeker en/matches",
        "phone seeker en/profile",
    ):
        assert page in recorded, f"{page} has no recorded count"
    assert all(isinstance(n, int) and n >= 0 for n in recorded.values())
    assert list(recorded) == sorted(recorded), "keep the file sorted so a change reads as a diff"
    assert not any(re.search(r"\b[0-9a-f]{8}\b", k) for k in recorded), (
        "a run id leaked into a label"
    )
