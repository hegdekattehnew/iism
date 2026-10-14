"""The 426 an installed mobile app gets when it is older than the API supports (Sprint 62, BL-15.7,
ADR-072).

A web page ships with the API and an installed app does not, so the one safe way to retire a
breaking change is to tell an old build to update. The gate must be strict about what it reads and
**lenient about what it cannot read**: a garbled header must never lock anybody out.
"""

import pytest
from httpx import AsyncClient

from api.core.config import get_settings
from api.core.middleware import parse_app_version


class TestParsing:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("1.4.0", (1, 4, 0)), (" 0.0.1 ", (0, 0, 1)), ("10.20.30", (10, 20, 30))],
    )
    def test_three_whole_numbers(self, value: str, expected: tuple[int, int, int]) -> None:
        assert parse_app_version(value) == expected

    @pytest.mark.parametrize(
        "value", ["", "1", "1.2", "1.2.3.4", "1.2.x", "v1.2.3", "1.2.3-beta", "-1.2.3", "１.2.3"]
    )
    def test_anything_else_is_nothing(self, value: str) -> None:
        assert parse_app_version(value) is None

    def test_a_version_is_compared_as_numbers_not_text(self) -> None:
        """As text `1.10.0` sorts below `1.9.0`, which would lock out the newer build."""
        assert parse_app_version("1.10.0") > parse_app_version("1.9.0")  # type: ignore[operator]


@pytest.fixture
def minimums(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "mobile_min_version_android", "2.0.0")
    monkeypatch.setattr(settings, "mobile_min_version_ios", "3.1.0")


def _app(version: str | None, platform: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if version is not None:
        headers["x-app-version"] = version
    if platform is not None:
        headers["x-app-platform"] = platform
    return headers


class TestTheGate:
    async def test_an_old_android_build_is_told_to_update(
        self, client: AsyncClient, minimums: None
    ) -> None:
        response = await client.get("/jobs", headers=_app("1.9.9", "android"))
        assert response.status_code == 426
        assert response.headers["x-min-app-version"] == "2.0.0"
        assert "Update" in response.json()["detail"]

    async def test_each_platform_has_its_own_minimum(
        self, client: AsyncClient, minimums: None
    ) -> None:
        """2.5.0 is fine on Android (minimum 2.0.0) and too old on iOS (minimum 3.1.0)."""
        assert (await client.get("/jobs", headers=_app("2.5.0", "android"))).status_code == 200
        ios = await client.get("/jobs", headers=_app("2.5.0", "ios"))
        assert ios.status_code == 426
        assert ios.headers["x-min-app-version"] == "3.1.0"

    async def test_the_minimum_itself_and_anything_newer_is_served(
        self, client: AsyncClient, minimums: None
    ) -> None:
        for version in ("2.0.0", "2.0.1", "10.0.0"):
            response = await client.get("/jobs", headers=_app(version, "android"))
            assert response.status_code == 200, version

    async def test_a_tenth_minor_is_not_below_a_ninth(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(get_settings(), "mobile_min_version_android", "1.9.0")
        assert (await client.get("/jobs", headers=_app("1.10.0", "android"))).status_code == 200

    async def test_it_gates_every_route_not_only_a_public_one(
        self, client: AsyncClient, minimums: None
    ) -> None:
        for method, path in (("GET", "/auth/me"), ("POST", "/auth/otp/request")):
            response = await client.request(method, path, headers=_app("1.0.0", "android"))
            assert response.status_code == 426, path

    async def test_health_is_never_gated(self, client: AsyncClient, minimums: None) -> None:
        response = await client.get("/health", headers=_app("0.0.1", "android"))
        assert response.status_code != 426


class TestItFailsOpen:
    async def test_the_web_app_sends_no_header_and_is_never_gated(
        self, client: AsyncClient, minimums: None
    ) -> None:
        assert (await client.get("/jobs")).status_code == 200

    @pytest.mark.parametrize("version", ["", "1.2", "nonsense", "1.2.3.4", "v1.0.0"])
    async def test_an_unreadable_version_is_served_not_locked_out(
        self, client: AsyncClient, minimums: None, version: str
    ) -> None:
        assert (await client.get("/jobs", headers=_app(version, "android"))).status_code == 200

    @pytest.mark.parametrize("platform", [None, "", "windows", "web"])
    async def test_a_missing_or_unknown_platform_is_served(
        self, client: AsyncClient, minimums: None, platform: str | None
    ) -> None:
        assert (await client.get("/jobs", headers=_app("0.0.1", platform))).status_code == 200

    async def test_the_default_retires_nothing(self, client: AsyncClient) -> None:
        for platform in ("android", "ios"):
            assert (await client.get("/jobs", headers=_app("0.0.1", platform))).status_code == 200
