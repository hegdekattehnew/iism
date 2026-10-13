"""The golden set's own coherence, checked without scoring anything.

`make evaluate` cannot run in CI and will not until the corpus can: it needs
the 21,303-standard NSQF projection, which lives in MongoDB on a developer's
machine and is not in this repository. `tests/fixtures/nsqf_sample.json` holds
nine invented standards (`HC/N0001` and friends) and **none** of the thirty-five
real codes the seed maps onto, so a scheduled workflow would be red every
morning for a reason nobody could fix from here. A red build nobody can act on
teaches people to ignore red builds.

What *can* run in CI is everything about the set that is true regardless of the
scorer -- and it is not a consolation prize, because both mistakes Sprint 29's
expansion actually made are in here:

* **An expectation the evaluator does not handle.** `below_assessed_peer` sat
  in the set for nineteen sprints against a three-armed `if/elif` with no
  `else`. It asserted nothing while the summary line counted it as holding.
* **A label against a vacancy the seed closes.** `inventory-clerk-nagpur` is
  closed as filled on every seed, and `match_job_by_slug` uses `open_job()`, so
  four labels naming it could never be evaluated at all.

Both are properties of the *data*, visible without a database.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from seed_candidates import (  # noqa: E402
    CANDIDATES,
    COURSE_INTERESTS,  # noqa: E402
    GOLDEN_COURSE_PAIRS,
    GOLDEN_ORDERINGS,
    GOLDEN_PAIRS,
)
from seed_marketplace import CLOSED_VACANCY_SLUG, COURSES, JOBS, course_intake  # noqa: E402

PHONES = {c[0] for c in CANDIDATES}
JOB_SLUGS = {j[0] for j in JOBS}
COURSE_SLUGS = {c[0] for c in COURSES}

# Kept in step with `evaluate_matching.py`'s branches by the first two tests
# below, which read that file rather than trusting this list.
JOB_EXPECTATIONS = {
    "top",
    "ranked",
    "capped_missing_mandatory",
    "missing_mandatory",
    "not_ranked",
}
COURSE_EXPECTATIONS = {"closes_mandatory", "no_suggestions", "attendable_first"}
ATTEND_PREFIXES = ("attendable:", "not_attendable:", "reach:")

EVALUATOR = (ROOT / "scripts" / "evaluate_matching.py").read_text()


class TestEveryExpectationIsHandled:
    """The `below_assessed_peer` class of bug, caught statically."""

    @pytest.mark.parametrize("expectation", sorted(JOB_EXPECTATIONS))
    def test_the_evaluator_has_a_branch_for_each_job_expectation(self, expectation: str) -> None:
        assert f'expectation == "{expectation}"' in EVALUATOR, expectation

    @pytest.mark.parametrize("expectation", sorted(COURSE_EXPECTATIONS))
    def test_the_evaluator_has_a_branch_for_each_course_expectation(self, expectation: str) -> None:
        assert f'expectation == "{expectation}"' in EVALUATOR, expectation

    def test_an_unknown_expectation_fails_rather_than_passing_silently(self) -> None:
        """The `else` that was missing. Without it a typo asserts nothing and
        the summary counts it as holding."""
        assert "unknown expectation" in EVALUATOR
        assert "unknown course expectation" in EVALUATOR

    def test_no_pair_uses_an_expectation_nobody_handles(self) -> None:
        used = {e for _, _, e in GOLDEN_PAIRS}
        assert used <= JOB_EXPECTATIONS, used - JOB_EXPECTATIONS

    def test_no_course_pair_uses_an_expectation_nobody_handles(self) -> None:
        used = {
            e.split(":", 1)[0] + ":" if e.startswith(("suggests:", *ATTEND_PREFIXES)) else e
            for _, _, e in GOLDEN_COURSE_PAIRS
        }
        assert used <= COURSE_EXPECTATIONS | {"suggests:", *ATTEND_PREFIXES}, used

    @pytest.mark.parametrize("prefix", ATTEND_PREFIXES)
    def test_the_evaluator_has_a_branch_for_each_attendability_expectation(
        self, prefix: str
    ) -> None:
        assert f'"{prefix}"' in EVALUATOR, prefix


class TestEveryLabelNamesSomethingThatExists:
    def test_every_phone_is_a_seeded_candidate(self) -> None:
        named = (
            {p for p, _, _ in GOLDEN_PAIRS}
            | {p for p, _, _ in GOLDEN_COURSE_PAIRS}
            | {p for p, _, _, _ in GOLDEN_ORDERINGS}
            | {p for _, p, _, _ in GOLDEN_ORDERINGS}
        )
        assert named, "no labels at all -- the assertions below would be vacuous"
        assert named <= PHONES, named - PHONES

    def test_every_job_is_a_seeded_vacancy(self) -> None:
        named = (
            {s for _, s, _ in GOLDEN_PAIRS}
            | {s for _, s, _ in GOLDEN_COURSE_PAIRS}
            | {s for _, _, s, _ in GOLDEN_ORDERINGS}
        )
        assert named <= JOB_SLUGS, named - JOB_SLUGS

    def test_every_named_course_is_a_seeded_course(self) -> None:
        named = {e.split(":", 1)[1] for _, _, e in GOLDEN_COURSE_PAIRS if e.startswith("suggests:")}
        assert named, "no named course expectations -- this assertion would be vacuous"
        assert named <= COURSE_SLUGS, named - COURSE_SLUGS


class TestNoLabelIsUnevaluable:
    def test_nothing_is_labelled_against_the_closed_vacancy(self) -> None:
        """The seed closes one vacancy as filled on every run so a fresh
        database shows the third state, and `match_job_by_slug` filters on
        `open_job()`. Four labels named it on the first run of the expanded
        set, and none of them could ever have been evaluated."""
        named = (
            {s for _, s, _ in GOLDEN_PAIRS}
            | {s for _, s, _ in GOLDEN_COURSE_PAIRS}
            | {s for _, _, s, _ in GOLDEN_ORDERINGS}
        )
        assert CLOSED_VACANCY_SLUG in JOB_SLUGS, "the seed's closed vacancy moved"
        assert CLOSED_VACANCY_SLUG not in named

    def test_no_ordering_compares_a_candidate_with_themselves(self) -> None:
        for better, worse, slug, _ in GOLDEN_ORDERINGS:
            assert better != worse, slug

    def test_no_pair_is_labelled_twice_with_different_expectations(self) -> None:
        seen: dict[tuple[str, str], str] = {}
        for phone, slug, expectation in GOLDEN_PAIRS:
            key = (phone, slug)
            assert seen.get(key, expectation) == expectation, f"{key}: {seen[key]} vs {expectation}"
            seen[key] = expectation


class TestTheSetIsWorthHaving:
    def test_it_is_no_longer_five_pairs(self) -> None:
        """Five caught a regression and could not defend a weighting. This is
        a floor, not a target -- delete it if the set is ever shrunk on
        purpose, rather than lowering it quietly."""
        assert len(GOLDEN_PAIRS) >= 30

    def test_it_covers_more_than_two_vacancies(self) -> None:
        """Three of twenty were labelled before Sprint 29."""
        assert len({s for _, s, _ in GOLDEN_PAIRS}) >= 10

    def test_course_recommendation_is_labelled_at_all(self) -> None:
        """ADR-025 names course recommendation as one of three metrics standing
        in for a revenue signal. It had no labelled data of any kind until
        Sprint 29, which is why Sprint 28 found the gate uncitable."""
        assert len(GOLDEN_COURSE_PAIRS) >= 10


class TestAttendabilityLabelsAreDerivedFromInputs:
    """Sprint 58's labels name no scorer output. Each is a fact about where a candidate lives and
    where, when and how many a course takes, computed here **independently** of
    `matching.attendance` -- from the seed's own tables, by name -- so a mislabel fails here and a
    broken ranking fails `make evaluate`, and neither can hide behind the other."""

    PLACE = {c[0]: (c[3], c[4]) for c in CANDIDATES}
    MODE = {c[0]: c[6] for c in COURSES}
    ENROLLED = {
        slug: sum(1 for _, s, status in COURSE_INTERESTS if s == slug and status == "enrolled")
        for slug in {s for _, s, _ in COURSE_INTERESTS}
    }

    def facts(self, phone: str, slug: str) -> dict[str, object]:
        state, district, offset, seats = course_intake(slug)
        mine = self.PLACE[phone]
        if self.MODE[slug] == "online":
            reach = "online"
        elif district == mine[1]:
            reach = "district"
        elif state == mine[0]:
            reach = "state"
        else:
            reach = "elsewhere"
        started = offset < 0
        full = self.ENROLLED.get(slug, 0) >= seats
        return {
            "reach": reach,
            "attendable": reach != "elsewhere" and not started and not full,
        }

    def labels(self) -> list[tuple[str, str, str]]:
        return [(p, j, e) for p, j, e in GOLDEN_COURSE_PAIRS if e.startswith(ATTEND_PREFIXES)]

    def test_there_are_attendability_labels_to_check(self) -> None:
        kinds = {e.split(":", 1)[0] for _, _, e in self.labels()}
        assert kinds == {"attendable", "not_attendable", "reach"}, kinds

    def test_every_label_matches_what_the_inputs_say(self) -> None:
        for phone, _job, expectation in self.labels():
            kind, _, rest = expectation.partition(":")
            if kind == "reach":
                slug, _, wanted = rest.rpartition(":")
                assert self.facts(phone, slug)["reach"] == wanted, expectation
            else:
                assert self.facts(phone, rest)["attendable"] is (kind == "attendable"), expectation

    def test_every_course_named_is_seeded_and_has_an_intake(self) -> None:
        for _, _, expectation in self.labels():
            slug = expectation.split(":")[1]
            assert slug in COURSE_SLUGS, expectation
            course_intake(slug)

    def test_the_set_covers_every_way_a_course_can_be_out_of_reach(self) -> None:
        named = {e.split(":")[1] for _, _, e in self.labels() if e.startswith("not_attendable")}
        reasons = set()
        for phone, _job, e in self.labels():
            if e.startswith("not_attendable"):
                f = self.facts(phone, e.split(":")[1])
                _state, _district, offset, seats = course_intake(e.split(":")[1])
                if f["reach"] == "elsewhere":
                    reasons.add("elsewhere")
                if offset < 0:
                    reasons.add("started")
                if self.ENROLLED.get(e.split(":")[1], 0) >= seats:
                    reasons.add("full")
        assert named and reasons == {"elsewhere", "started", "full"}, reasons
