"""The title set role search is scored against, and the rule that scores it (Sprint 71, BL-12.12).

`make evaluate-roles` needs the real corpus, so it cannot run in CI (the fixture corpus has nine
invented codes, the reason `make evaluate` is a script too). What *can* run is everything true of
set regardless of the corpus, and it is not a consolation prize: the mistakes a set like this makes
are mostly in its shape. A label the evaluator does not handle, a duplicate query, an empty answer
list, a hold-out title that is also an alias key (so it was tuned against), a pattern that does not
compile: each of those makes the headline number say something untrue.
"""

import json
import re
from pathlib import Path

from api.modules.skills.role_aliases import ROLE_ALIASES
from scripts.evaluate_role_search import FIXTURE, accepted_roles, judge, summarise

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def test_the_fixture_is_where_the_evaluator_reads_it_and_is_not_empty() -> None:
    assert (Path(__file__).parent / "fixtures" / "role_titles.json") == FIXTURE
    assert len(CASES) >= 120  # found them before judging any


def test_every_query_is_unique_and_written_as_a_person_would_type_it() -> None:
    queries = [c["query"] for c in CASES]
    assert len(queries) == len({q.lower().strip() for q in queries}), "a query appears twice"
    for q in queries:
        assert q == q.lower().strip() and q, q


def test_every_title_has_an_answer_or_says_there_is_none() -> None:
    for c in CASES:
        has_answer = bool(c.get("accept")) or bool(c.get("accept_like"))
        assert has_answer != bool(c.get("none_ok")), c["query"]
        if c.get("none_ok"):
            assert "accept" not in c and "accept_like" not in c, c["query"]
        for name in c.get("accept", []):
            assert name and name == name.strip(), c["query"]
        assert not (
            {n.lower() for n in c.get("accept", [])} & {n.lower() for n in c.get("reject", [])}
        )


def test_patterns_compile_and_are_not_empty() -> None:
    for c in CASES:
        for pattern in c.get("accept_like", []):
            assert pattern.strip(), c["query"]
            re.compile(pattern, re.IGNORECASE)


def test_the_wordings_are_what_they_say_they_are() -> None:
    kinds = {c["kind"] for c in CASES}
    assert kinds == {"english", "hinglish", "devanagari"}
    for c in CASES:
        written_in_devanagari = bool(DEVANAGARI.search(c["query"]))
        assert written_in_devanagari == (c["kind"] == "devanagari"), c["query"]


def test_the_hold_out_is_a_real_share_and_was_never_tuned_against() -> None:
    hold = [c for c in CASES if c["split"] == "hold"]
    tune = [c for c in CASES if c["split"] == "tune"]
    assert {c["split"] for c in CASES} == {"hold", "tune"}
    assert 0.2 <= len(hold) / len(CASES) <= 0.4, "the hold-out should be about a quarter to a third"
    assert len(tune) > len(hold)
    # A hold-out title that is an alias key was tuned against: the alias answers it by construction.
    keys = {k.lower().strip() for k in ROLE_ALIASES}
    tuned = sorted(c["query"] for c in hold if c["query"].lower() in keys)
    assert tuned == [], f"hold-out titles that are alias keys: {tuned}"


def test_the_set_covers_each_wording_in_both_splits_and_a_job_with_no_role() -> None:
    for kind in ("english", "hinglish", "devanagari"):
        assert any(c["kind"] == kind and c["split"] == "tune" for c in CASES), kind
    assert any(c["kind"] == "devanagari" and c["split"] == "hold" for c in CASES)
    assert sum(1 for c in CASES if c.get("none_ok")) >= 3


# ---------------------------------------------------------------- the scoring rule, which is pure

CASE = {"query": "mason", "kind": "english", "split": "tune", "accept": ["Brick Mason"]}


def hit(role: str, code: str = "BWS/Q1") -> tuple[str, str]:
    return role, code


class TestJudge:
    def test_a_right_answer_first_is_rank_one(self) -> None:
        out = judge(CASE, [hit("Brick Mason"), hit("Warper")])
        assert out.passed and out.rank == 1

    def test_a_right_answer_third_still_passes_and_fourth_does_not(self) -> None:
        third = judge(CASE, [hit("A"), hit("B"), hit("brick  mason")])
        assert third.passed and third.rank == 3  # case and spacing are not a miss
        fourth = judge(CASE, [hit("A"), hit("B"), hit("C"), hit("Brick Mason")])
        assert not fourth.passed and fourth.rank == 4  # found, but not where a person looks

    def test_no_right_answer_is_a_miss_and_is_not_a_crash(self) -> None:
        assert not judge(CASE, [hit("A"), hit("B")]).passed
        out = judge(CASE, [])
        assert not out.passed and out.rank is None and out.top1 is None

    def test_a_title_with_no_honest_role_passes_on_nothing_or_on_something_unrelated(self) -> None:
        none = {"query": "waiter", "kind": "english", "split": "tune", "none_ok": True}
        assert judge(none, []).passed
        assert judge(none, [hit("Metro Rail Maintainer")]).passed

    def test_it_fails_when_a_rejected_role_leads(self) -> None:
        none = {**CASE, "accept": None, "none_ok": True, "reject": ["Bad Diploma"]}
        none.pop("accept")
        assert not judge(none, [hit("Bad Diploma")]).passed
        assert judge(none, [hit("Fine"), hit("Bad Diploma")]).passed  # only the first counts

    def test_it_fails_when_a_disability_track_pack_leads_a_title_with_no_honest_role(self) -> None:
        none = {"query": "waiter", "kind": "english", "split": "tune", "none_ok": True}
        assert not judge(none, [hit("Food Service Associate", "PWD/HSS/Q1")]).passed

    def test_patterns_widen_what_counts_and_exact_names_still_count(self) -> None:
        corpus = ["Brick Mason", "Plaster Mason - Basic", "Scaffolder", "Mason Tiling"]
        case = {"query": "mason", "kind": "english", "split": "tune",
                "accept": ["Scaffolder"], "accept_like": ["mason"]}  # fmt: skip
        accepted = accepted_roles(case, corpus)
        assert accepted == {"brick mason", "plaster mason - basic", "mason tiling", "scaffolder"}
        assert judge(case, [hit("Plaster Mason - Basic")], accepted).rank == 1
        # Without the expansion only the exact name counts: the second argument matters.
        assert judge(case, [hit("Plaster Mason - Basic")]).rank is None


class TestSummary:
    def test_rates_are_over_titles_with_an_answer_by_split_and_wording(self) -> None:
        def case(q: str, kind: str, split: str) -> dict:
            return {"query": q, "kind": kind, "split": split, "accept": ["X"]}

        outcomes = [
            judge(case("a", "english", "tune"), [hit("X")]),
            judge(case("b", "english", "tune"), [hit("Y"), hit("X")]),
            judge(case("c", "hinglish", "hold"), [hit("Y")]),
            judge({"query": "w", "kind": "english", "split": "tune", "none_ok": True}, []),
        ]
        rows = summarise(outcomes)
        assert rows["all"]["titles"] == 3  # the title with no honest role is not in the rate
        assert rows["all"]["top1"] == 1 / 3 and rows["all"]["top3"] == 2 / 3
        assert rows["split:hold"]["top3"] == 0
        assert rows["kind:english"]["top1"] == 0.5
