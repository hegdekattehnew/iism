"""Regression tests for the findings of the Sprint 5 self-review.

Each of these locks in a fix for something that was actually exploitable or
leaking, not a hypothetical.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from api.adapters.notifications import ConsoleNotificationProvider
from api.adapters.notifications.base import NotificationError
from api.adapters.notifications.console import mask_phone
from api.core.config import Settings

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------- demo task endpoints are local-only


def _paths(environment: str) -> set[str]:
    """Read a fresh app's OpenAPI paths for a given environment.

    Runs in a subprocess deliberately. Rebuilding the app in-process means
    purging api.* from sys.modules, which leaves every other test in this file
    holding a different get_settings object with its own lru_cache -- a
    contamination that is invisible until an unrelated test fails.

    Routes mounted via include_router are wrapped and expose no `.path`, so the
    OpenAPI schema is the only reliable source.
    """
    env = {**os.environ, "ENVIRONMENT": environment}
    if environment == "production":
        env["JWT_SECRET_KEY"] = "x" * 40
        env["OTP_EXPOSE_IN_RESPONSE"] = "false"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json;from api.main import app;print(json.dumps(list(app.openapi()['paths'])))",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        check=True,
    )
    return set(json.loads(result.stdout.strip().splitlines()[-1]))


def test_demo_task_endpoints_are_absent_in_production() -> None:
    """They are unauthenticated and enqueue work: an open queue-flooding
    vector if ever exposed."""
    assert "/tasks/ping" not in _paths("production")


def test_demo_task_endpoints_exist_in_development() -> None:
    """The homepage dev panel needs them locally."""
    assert "/tasks/ping" in _paths("development")


def test_employer_console_is_absent_in_production() -> None:
    """It is unauthenticated and it reads the candidate pool. Acceptable as a
    labelled demonstration; not acceptable anywhere a real candidate's profile
    exists. The guard is in the app assembly, so this boots the app to check it
    rather than calling the mount function directly."""
    assert "/employer/employers" not in _paths("production")


def test_employer_console_exists_in_development() -> None:
    assert "/employer/employers" in _paths("development")


# ------------------------------------------------ OTP never reaches a log sink


async def test_console_provider_logs_neither_the_code_nor_the_full_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An OTP is a live credential and a phone number is personal data;
    ADR-023 forbids either reaching a log sink.

    Asserts on the fully rendered log record rather than on handler output.
    pytest's logging plugin intercepts this logger's handlers, so a
    StreamHandler capture comes back empty and every assertion below would
    pass vacuously -- which is worse than no test.
    """
    import api.adapters.notifications.console as console

    records: list[str] = []
    monkeypatch.setattr(
        console.logger,
        "warning",
        lambda msg, *args: records.append(msg % args if args else msg),
    )

    phone, code = "+919812349999", "482913"
    await ConsoleNotificationProvider().send_sms(
        phone, f"Your IISM verification code is {code}. It expires in 5 minutes."
    )

    assert records, "nothing was logged -- the assertions below would be vacuous"
    logged = " ".join(records)
    assert code not in logged
    assert phone not in logged
    assert "verification code" not in logged
    assert "dispatched" in logged


def test_masked_phone_keeps_enough_to_correlate_but_not_to_dial() -> None:
    masked = mask_phone("+919812349999")
    assert masked.startswith("+9198")
    assert masked.endswith("999")
    assert "9812349" not in masked


def test_short_input_is_fully_masked() -> None:
    assert set(mask_phone("12345")) == {"*"}


async def test_console_provider_refuses_to_run_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A silent no-op provider would look exactly like working authentication
    that nobody can complete."""
    import api.adapters.notifications.console as console

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
    with pytest.raises(NotificationError):
        await ConsoleNotificationProvider().send_sms("+919812349999", "hello")


# ------------------------------------------------------ production config guard


def test_production_rejects_the_default_secret() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production")


def test_production_rejects_exposing_the_otp() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="x" * 40,
            otp_expose_in_response=True,
        )
