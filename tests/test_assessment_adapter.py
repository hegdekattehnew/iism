"""The assessment-provider port (ADR-017, Sprint 35, BL-3.1)."""

import pytest

from api.adapters.assessment import ConsoleAssessmentProvider, get_assessment_provider
from api.adapters.assessment.base import AssessmentError, AssessmentProvider, AssessmentResult
from api.core.config import Settings


def test_console_provider_parses_a_pass() -> None:
    result = ConsoleAssessmentProvider().parse_result(
        {"phone": "+919812349999", "standard_code": "HSS/N1001", "outcome": "pass"}
    )
    assert result == AssessmentResult(phone="+919812349999", standard_code="HSS/N1001", passed=True)


def test_console_provider_parses_a_fail() -> None:
    result = ConsoleAssessmentProvider().parse_result(
        {"phone": "+919812349999", "standard_code": "HSS/N1001", "outcome": "fail"}
    )
    assert result.passed is False


def test_a_missing_field_is_refused_by_name() -> None:
    with pytest.raises(AssessmentError, match="phone"):
        ConsoleAssessmentProvider().parse_result({"standard_code": "HSS/N1001", "outcome": "pass"})


def test_an_unknown_outcome_is_refused() -> None:
    with pytest.raises(AssessmentError, match="unknown outcome"):
        ConsoleAssessmentProvider().parse_result(
            {"phone": "+919812349999", "standard_code": "HSS/N1001", "outcome": "maybe"}
        )


def test_console_provider_refuses_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.adapters.assessment.console as console

    monkeypatch.setattr(
        console,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="x" * 40,
            otp_expose_in_response=False,
        ),
    )
    with pytest.raises(AssessmentError):
        ConsoleAssessmentProvider().parse_result(
            {"phone": "+919812349999", "standard_code": "HSS/N1001", "outcome": "pass"}
        )


def test_production_refusal_never_logs_the_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.adapters.assessment.console as console

    monkeypatch.setattr(
        console,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="x" * 40,
            otp_expose_in_response=False,
        ),
    )
    logged: list[str] = []
    monkeypatch.setattr(console.logger, "warning", lambda *a, **k: logged.append("called"))
    with pytest.raises(AssessmentError):
        ConsoleAssessmentProvider().parse_result(
            {"phone": "+919812349999", "standard_code": "HSS/N1001", "outcome": "pass"}
        )
    assert not logged


def test_factory_returns_the_console_provider() -> None:
    get_assessment_provider.cache_clear()
    provider = get_assessment_provider()
    assert isinstance(provider, ConsoleAssessmentProvider)
    assert isinstance(provider, AssessmentProvider)
