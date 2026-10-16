"""The notice says 18 and over, and now something checks it (Sprint 72, ADR-082).

The rule is on the way in: a date of birth that would make the person younger than 18 today is
refused with a sentence the form can show, whatever else is in the payload. Stored dates are not
rewritten. Whether and how a minor may ever use the product is the owner's decision.
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from api.core.clock import today_ist
from api.modules.marketplace.schemas import (
    MINIMUM_AGE,
    CandidateProfileUpdateFull,
    years_between,
)
from tests.test_operations import _candidate


def _born(years: int, extra_days: int = 0) -> date:
    today = today_ist()
    return today.replace(year=today.year - years) - timedelta(days=extra_days)


class TestYearsBetween:
    def test_the_birthday_has_to_have_passed(self) -> None:
        assert years_between(date(2008, 10, 17), date(2026, 10, 17)) == 18
        assert years_between(date(2008, 10, 18), date(2026, 10, 17)) == 17
        assert years_between(date(2008, 12, 31), date(2026, 1, 1)) == 17

    def test_a_leap_day_birthday_is_a_whole_year_by_the_first_of_march(self) -> None:
        assert years_between(date(2008, 2, 29), date(2026, 3, 1)) == 18
        assert years_between(date(2008, 2, 29), date(2026, 2, 28)) == 17


class TestTheRule:
    def test_exactly_eighteen_today_is_accepted(self) -> None:
        dob = _born(MINIMUM_AGE)
        assert CandidateProfileUpdateFull(date_of_birth=dob).date_of_birth == dob

    def test_a_day_short_of_eighteen_is_refused_in_words_a_form_can_show(self) -> None:
        with pytest.raises(ValidationError) as caught:
            CandidateProfileUpdateFull(date_of_birth=_born(MINIMUM_AGE) + timedelta(days=1))
        assert "You must be 18 or over" in str(caught.value)

    def test_a_date_in_the_future_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            CandidateProfileUpdateFull(date_of_birth=today_ist() + timedelta(days=30))

    def test_no_date_of_birth_is_fine_it_is_optional(self) -> None:
        assert CandidateProfileUpdateFull().date_of_birth is None
        assert CandidateProfileUpdateFull(date_of_birth=None).date_of_birth is None

    def test_an_adult_of_any_age_is_accepted(self) -> None:
        assert CandidateProfileUpdateFull(date_of_birth=date(1960, 1, 1)).date_of_birth


async def test_the_profile_route_refuses_a_minor_and_saves_nothing(client: AsyncClient) -> None:
    headers = await _candidate(client)
    refused = await client.put(
        "/me/profile",
        headers=headers,
        json={"date_of_birth": (_born(MINIMUM_AGE) + timedelta(days=1)).isoformat()},
    )
    assert refused.status_code == 422
    assert "You must be 18 or over" in str(refused.json())
    assert (await client.get("/me/profile", headers=headers)).json()["date_of_birth"] is None


async def test_the_profile_route_accepts_an_adult(client: AsyncClient) -> None:
    headers = await _candidate(client)
    dob = _born(30).isoformat()
    saved = await client.put("/me/profile", headers=headers, json={"date_of_birth": dob})
    assert saved.status_code == 200 and saved.json()["date_of_birth"] == dob
