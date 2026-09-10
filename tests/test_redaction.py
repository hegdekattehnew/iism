"""The ADR-023 filter, on its own — before any logging config depends on it.

ADR-023 says the sensitive fields are "excluded from logs, traces, error
payloads and analytics events by an explicit redaction filter — plaintext must
never reach a log sink". These are the assertions that make that sentence true
rather than aspirational.

Two halves, and they catch different things. The **key denylist** is the only
mechanism that can reach a value with no recognisable shape: a resume, an
embedding, an assessment result. The **patterns** are the only mechanism that
can reach a value with no key at all — an interpolated stdlib message, a DSN
inside `str(exc)`, a third-party `extra`.
"""

import pytest

from api.core.redaction import (
    REDACTED,
    RedactingProcessor,
    mask_aadhaar,
    mask_email,
    mask_phone,
)

scrub = RedactingProcessor()


def run(**event: object) -> dict:
    """Push an event dict through the processor as structlog would."""
    return dict(scrub(None, "info", dict(event)))


class TestTheKeyDenylist:
    """A key whose *name* says the value is sensitive."""

    @pytest.mark.parametrize(
        "key",
        ["code", "otp", "debug_code", "password", "access_token", "phone", "email"],
    )
    def test_the_value_is_replaced_wholesale(self, key: str) -> None:
        """Wholesale, never partially. A partial mask of a six-digit OTP is a
        two-digit OTP — it narrows a brute force from a million to a hundred."""
        out = run(event="auth.otp_sent", **{key: "482913"})
        assert out[key] == REDACTED
        assert out["redacted"] is True

    def test_it_reaches_a_value_no_pattern_could_match(self) -> None:
        """The whole reason a denylist exists beside the patterns: a resume or
        an embedding has no shape to match on."""
        out = run(event="profile.parsed", resume_text="Ten years of ward nursing.")
        assert out["resume_text"] == REDACTED

    def test_it_is_case_insensitive(self) -> None:
        assert run(event="e", PHONE="+919812349999")["PHONE"] == REDACTED

    def test_a_null_is_left_alone(self) -> None:
        """`phone=None` is not a leak, and replacing it would be a lie about
        what the record contained."""
        out = run(event="e", phone=None)
        assert out["phone"] is None
        assert "redacted" not in out

    def test_nested_and_listed_values_are_reached(self) -> None:
        out = run(event="e", payload={"user": {"phone": "+919812349999"}})
        assert out["payload"]["user"]["phone"] == REDACTED
        assert run(event="e", batch=[{"otp": "111111"}])["batch"][0]["otp"] == REDACTED


class TestThePatterns:
    """A sensitive value with no key of its own to give it away."""

    def test_a_dsn_password_cannot_survive(self) -> None:
        """`health.py` puts `str(exc)[:200]` into a log line, and an asyncpg
        connection error routinely carries the DSN with the password in it."""
        out = run(
            event="health.check_failed",
            detail="could not connect: postgresql+asyncpg://iism:s3cret@db:5432/iism",
        )
        assert "s3cret" not in out["detail"]
        assert "***:***" in out["detail"]
        assert out["redacted"] is True

    def test_a_jwt_cannot_survive(self) -> None:
        token = "eyJhbGciOi.eyJzdWIiOiJhYmMi.9tvKQ2Vz0dQs"
        assert token not in run(event="e", detail=f"bad token {token}")["detail"]

    def test_an_interpolated_message_is_still_reached(self) -> None:
        """The notification adapters emit one pre-interpolated string with no
        keys at all. If someone later drops the mask, this is the backstop."""
        out = run(event="notification dispatched to +919812349999")
        assert "+919812349999" not in out["event"]

    def test_an_email_in_free_text_is_masked_not_dropped(self) -> None:
        out = run(event="e", detail="rejected priya.sharma@example.com")
        assert "priya.sharma" not in out["detail"]
        assert "@example.com" in out["detail"]

    def test_an_aadhaar_in_free_text_keeps_only_its_last_four(self) -> None:
        out = run(event="e", detail="id 1234 5678 9012 on file")
        assert "1234 5678" not in out["detail"]
        assert "XXXX XXXX 9012" in out["detail"]


class TestItNeverMakesThingsWorse:
    def test_a_clean_record_is_untouched_and_unmarked(self) -> None:
        """`redacted` is a signal. If it appeared on clean records the
        CloudWatch query that finds leaking call sites would return everything."""
        out = run(event="http.request", route="/org/{org_slug}/jobs", status=200)
        assert out == {"event": "http.request", "route": "/org/{org_slug}/jobs", "status": 200}

    def test_non_strings_pass_through_unchanged(self) -> None:
        out = run(event="e", status=200, ok=True, ratio=1.5, nothing=None)
        assert (out["status"], out["ok"], out["ratio"], out["nothing"]) == (200, True, 1.5, None)

    def test_a_uuid_is_not_mistaken_for_a_phone_number(self) -> None:
        """`user_id` and `tenant_id` are bound on every authenticated request.
        If the loose phone pattern ate them, every log line would be redacted
        and the whole context layer would be worthless."""
        out = run(event="e", user_id="4a9f3fe6-55f1-4ac4-ad30-52e02d9b438d")
        assert out["user_id"] == "4a9f3fe6-55f1-4ac4-ad30-52e02d9b438d"
        assert "redacted" not in out

    def test_a_timestamp_is_not_mistaken_for_a_phone_number(self) -> None:
        """Writing this found a real one. The obvious phone pattern
        `\\+?\\d[\\d\\- ]{8,14}\\d` matches `2026-09-10` and rewrote it to
        `20260910` -- and `timestamp` is on *every* log line, so the loose form
        corrupted the whole stream and marked every record `redacted`."""
        out = run(event="e", timestamp="2026-09-10T06:12:33.421Z")
        assert out["timestamp"] == "2026-09-10T06:12:33.421Z"
        assert "redacted" not in out

    def test_a_date_range_is_not_mistaken_for_a_phone_number(self) -> None:
        out = run(event="e", detail="valid 2026-09-10 to 2027-01-31")
        assert out["detail"] == "valid 2026-09-10 to 2027-01-31"

    def test_a_bare_indian_mobile_in_free_text_is_still_caught(self) -> None:
        """Narrowing the pattern must not have narrowed it past usefulness."""
        out = run(event="e", detail="called 9812349999 twice")
        assert "9812349999" not in out["detail"]
        assert out["redacted"] is True

    def test_deep_nesting_terminates(self) -> None:
        """Logging must never be the reason a request fails, so the walk is
        depth-capped rather than trusting the shape of what it is handed."""
        node: dict = {"v": "leaf"}
        for _ in range(40):
            node = {"v": node}
        assert run(event="e", payload=node)["redacted"] is True


class TestTheMasks:
    """`mask_email` shipped in Sprint 12 with no test at all."""

    def test_phone_keeps_enough_to_correlate_but_not_to_dial(self) -> None:
        masked = mask_phone("+919812349999")
        assert masked.startswith("+9198")
        assert masked.endswith("999")
        assert "9812349" not in masked

    def test_short_phone_input_is_fully_masked(self) -> None:
        assert set(mask_phone("12345")) == {"*"}

    def test_email_keeps_the_domain_and_loses_the_person(self) -> None:
        """The domain is what a support conversation needs; the local part is
        the half that identifies someone."""
        masked = mask_email("priya.sharma@example.com")
        assert masked.endswith("@example.com")
        assert "sharma" not in masked
        assert masked.startswith("pr")

    def test_a_short_local_part_keeps_nothing(self) -> None:
        assert mask_email("ab@example.com").startswith("*")

    def test_an_address_with_no_domain_is_fully_masked(self) -> None:
        assert set(mask_email("not-an-address")) == {"*"}

    def test_aadhaar_keeps_only_the_last_four(self) -> None:
        assert mask_aadhaar("1234 5678 9012") == "XXXX XXXX 9012"

    def test_a_wrong_length_aadhaar_is_replaced_outright(self) -> None:
        """If the shape is unrecognised, so is the risk."""
        assert mask_aadhaar("12345") == REDACTED
