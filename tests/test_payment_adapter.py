"""The payment port (ADR-043) -- an adapter with no caller yet.

Unlike `ConsoleNotificationProvider`/`ConsoleEmailProvider`, `ConsolePaymentProvider`
has no legitimate success path in any environment: there is no course-checkout
feature calling it, so it must refuse unconditionally, not only in production.
"""

import pytest

from api.adapters.payments import ConsolePaymentProvider, get_payment_provider
from api.adapters.payments.base import PaymentError, PaymentProvider
from api.core.config import Settings


async def test_console_provider_refuses_in_development() -> None:
    """No feature exists to succeed for -- returning a transaction id here
    would fabricate a payment for a flow that is not built."""
    with pytest.raises(PaymentError):
        await ConsolePaymentProvider().create_payment(
            amount_paise=150000, currency="INR", reference="course-fake-checkout"
        )


async def test_console_provider_refuses_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.adapters.payments.console as console

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
    with pytest.raises(PaymentError):
        await ConsolePaymentProvider().create_payment(
            amount_paise=150000, currency="INR", reference="course-fake-checkout"
        )


async def test_production_refusal_fires_before_any_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """The production guard must be the first thing checked -- a provider
    that logged a reference before refusing in production would still be
    doing *something* in the environment it must do nothing in."""
    import api.adapters.payments.console as console

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

    with pytest.raises(PaymentError):
        await ConsolePaymentProvider().create_payment(
            amount_paise=150000, currency="INR", reference="course-fake-checkout"
        )
    assert not logged


def test_factory_returns_the_console_provider() -> None:
    get_payment_provider.cache_clear()
    provider = get_payment_provider()
    assert isinstance(provider, ConsolePaymentProvider)
    assert isinstance(provider, PaymentProvider)


def test_no_route_or_service_calls_the_payment_port_yet() -> None:
    """The ADR's whole premise: this port predates its first caller. If this
    ever fails, ADR-043 needs revisiting as course checkout, not as a port."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    hits: list[str] = []
    for path in (root / "api" / "modules").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and "adapters.payments" in node.module
            ):
                hits.append(str(path))
    assert hits == []
