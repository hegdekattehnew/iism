"""The release-configuration check (Sprint 66, ADR-077).

It must hold two things at once: the repository as it is today reports its open owner items and no
defects, and a configuration that is *almost* ready fails for exactly the reason it
should. Each test asserts it found the files it is checking before it asserts about them,
because a checker that reads nothing reports a clean bill of health.
"""

import json
import shutil
import struct
import zlib
from pathlib import Path

import pytest

from scripts.check_release_config import (
    MOBILE,
    TEMPLATE_ASSETS,
    Finding,
    check,
    exit_code,
)

LEGAL_APPOINTED = "export const GRIEVANCE_OFFICER = { name: 'A Person', email: null };"


def _png(path: Path, size: int, seed: int) -> None:
    """A valid square PNG that is not any template file (the seed changes the bytes)."""
    row = b"\x00" + bytes([seed % 256]) * (size * 3)
    raw = zlib.compress(row * size)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    )


@pytest.fixture
def ready(tmp_path: Path) -> Path:
    """A mobile directory with every owner decision made: the one `check` should accept."""
    shutil.copy(MOBILE / "app.json", tmp_path / "app.json")
    shutil.copy(MOBILE / "eas.json", tmp_path / "eas.json")
    assets = tmp_path / "assets"
    assets.mkdir()
    for index, (name, size) in enumerate(
        [
            ("icon.png", 1024),
            ("android-icon-foreground.png", 512),
            ("android-icon-background.png", 512),
            ("android-icon-monochrome.png", 432),
            ("splash-icon.png", 512),
        ]
    ):
        _png(assets / name, size, index + 7)
    app = json.loads((tmp_path / "app.json").read_text())
    app["expo"]["ios"]["bundleIdentifier"] = "org.realco.skills"
    app["expo"]["android"]["package"] = "org.realco.skills"
    app["expo"]["extra"] = {"eas": {"projectId": "00000000-0000-0000-0000-000000000000"}}
    (tmp_path / "app.json").write_text(json.dumps(app))
    eas = json.loads((tmp_path / "eas.json").read_text())
    for name in ("preview", "production"):
        env = eas["build"][name]["env"]
        env["EXPO_PUBLIC_API_BASE_URL"] = "https://api.realco.org"
        env["EXPO_PUBLIC_WEB_BASE_URL"] = "https://www.realco.org"
    eas["build"]["production"]["env"]["EXPO_PUBLIC_STORE_URL_ANDROID"] = (
        "market://details?id=org.realco.skills"
    )
    eas["build"]["production"]["env"]["EXPO_PUBLIC_STORE_URL_IOS"] = (
        "https://apps.apple.com/app/id1234567890"
    )
    eas["submit"]["production"]["ios"]["ascAppId"] = "1234567890"
    (tmp_path / "eas.json").write_text(json.dumps(eas))
    return tmp_path


@pytest.fixture
def legal(tmp_path: Path) -> Path:
    path = tmp_path / "legal.ts"
    path.write_text(LEGAL_APPOINTED)
    return path


def _edit(directory: Path, name: str, change) -> None:
    path = directory / name
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def _messages(findings: list[Finding], kind: str) -> list[str]:
    return [f.message for f in findings if f.kind == kind]


def test_the_fixture_is_ready_and_the_checker_reads_it(ready: Path, legal: Path) -> None:
    assert (ready / "app.json").is_file() and (ready / "eas.json").is_file()
    assert len(list((ready / "assets").glob("*.png"))) == 5
    assert check(ready, "production", legal) == []
    assert check(ready, "preview", legal) == []


def test_the_repository_today_has_no_defects_only_open_owner_items() -> None:
    for profile in ("preview", "production"):
        findings = check(MOBILE, profile)
        assert findings, "the placeholders are real and must be reported"
        assert _messages(findings, "error") == [], findings
        assert exit_code(findings, "preview") == 0
    # The gate: a production build is refused while any owner decision is open.
    assert exit_code(check(MOBILE, "production"), "production") == 1


def test_the_repository_reports_the_owner_decisions_by_name() -> None:
    text = " ".join(_messages(check(MOBILE, "production"), "open"))
    for expected in ("bundle id", "EAS project id", "grievance officer", "placeholder", "template"):
        assert expected in text


def test_the_template_hashes_still_match_nothing_but_the_template() -> None:
    assert len(TEMPLATE_ASSETS) == 5
    assert all(len(digest) == 64 for digest in TEMPLATE_ASSETS)


@pytest.mark.parametrize(
    "origin", ["http://api.realco.org", "https://localhost:8000", "https://10.0.2.2:8000"]
)
def test_a_cleartext_or_local_origin_is_a_defect_in_every_profile(
    ready: Path, legal: Path, origin: str
) -> None:
    for profile in ("preview", "production"):
        _edit(
            ready,
            "eas.json",
            lambda d, p=profile: d["build"][p]["env"].update(EXPO_PUBLIC_API_BASE_URL=origin),
        )
        findings = check(ready, profile, legal)
        assert any("EXPO_PUBLIC_API_BASE_URL" in m for m in _messages(findings, "error")), findings
        assert exit_code(findings, "preview") == 1


def test_a_profile_that_sets_no_origin_is_a_defect(ready: Path, legal: Path) -> None:
    _edit(
        ready, "eas.json", lambda d: d["build"]["production"]["env"].pop("EXPO_PUBLIC_WEB_BASE_URL")
    )
    assert any(
        "EXPO_PUBLIC_WEB_BASE_URL" in m
        for m in _messages(check(ready, "production", legal), "error")
    )


def test_a_production_build_needs_both_store_links(ready: Path, legal: Path) -> None:
    _edit(
        ready,
        "eas.json",
        lambda d: d["build"]["production"]["env"].pop("EXPO_PUBLIC_STORE_URL_IOS"),
    )
    assert any("STORE_URL_IOS" in m for m in _messages(check(ready, "production", legal), "error"))


def test_a_placeholder_in_production_is_open_and_blocks_only_production(
    ready: Path, legal: Path
) -> None:
    _edit(ready, "app.json", lambda d: d["expo"]["ios"].update(bundleIdentifier="in.iism.app"))
    findings = check(ready, "production", legal)
    assert any("placeholder 'in.iism.app'" in m for m in _messages(findings, "open"))
    assert exit_code(findings, "production") == 1
    assert exit_code(check(ready, "preview", legal), "preview") == 0


def test_a_missing_eas_project_id_is_open(ready: Path, legal: Path) -> None:
    _edit(ready, "app.json", lambda d: d["expo"].pop("extra"))
    assert any("EAS project id" in m for m in _messages(check(ready, "production", legal), "open"))


def test_encryption_must_be_declared(ready: Path, legal: Path) -> None:
    _edit(ready, "app.json", lambda d: d["expo"]["ios"].pop("config"))
    assert any(
        "usesNonExemptEncryption" in m
        for m in _messages(check(ready, "production", legal), "error")
    )


@pytest.mark.parametrize(
    "extra", ["android.permission.CAMERA", "android.permission.ACCESS_FINE_LOCATION"]
)
def test_a_permission_the_app_does_not_use_is_a_defect(
    ready: Path, legal: Path, extra: str
) -> None:
    _edit(ready, "app.json", lambda d: d["expo"]["android"]["permissions"].append(extra))
    assert any(extra in m for m in _messages(check(ready, "production", legal), "error"))


def test_the_template_artwork_is_open_and_a_missing_or_wrong_icon_is_a_defect(
    ready: Path, legal: Path
) -> None:
    template = next(MOBILE.glob("assets/icon.png"))
    shutil.copy(template, ready / "assets" / "icon.png")
    assert any("Expo template" in m for m in _messages(check(ready, "production", legal), "open"))

    _png(ready / "assets" / "icon.png", 256, 99)
    assert any("1024" in m for m in _messages(check(ready, "production", legal), "error"))

    (ready / "assets" / "icon.png").unlink()
    assert any("not there" in m for m in _messages(check(ready, "production", legal), "error"))


def test_the_splash_must_be_configured(ready: Path, legal: Path) -> None:
    _edit(
        ready,
        "app.json",
        lambda d: d["expo"].update(
            plugins=[p for p in d["expo"]["plugins"] if "splash" not in str(p)]
        ),
    )
    assert any("splash" in m for m in _messages(check(ready, "production", legal), "error"))


def test_an_unappointed_grievance_officer_is_open(ready: Path, tmp_path: Path) -> None:
    unappointed = tmp_path / "legal2.ts"
    unappointed.write_text(
        "export const GRIEVANCE_OFFICER = { name: null, email: null, phone: null, address: null };"
    )
    assert any(
        "grievance officer" in m for m in _messages(check(ready, "production", unappointed), "open")
    )


def test_unreadable_configuration_is_a_defect_not_a_pass(tmp_path: Path, legal: Path) -> None:
    findings = check(tmp_path, "production", legal)
    assert _messages(findings, "error"), findings
    assert exit_code(findings, "preview") == 1


def test_an_unknown_profile_is_a_defect(ready: Path, legal: Path) -> None:
    _edit(ready, "eas.json", lambda d: d["build"].pop("production"))
    assert any(
        "no build profile" in m for m in _messages(check(ready, "production", legal), "error")
    )


def test_a_placeholder_origin_or_store_link_in_production_is_open(ready: Path, legal: Path) -> None:
    """The origin and the store links are checked for placeholders like the bundle id is."""
    _edit(
        ready,
        "eas.json",
        lambda d: d["build"]["production"]["env"].update(
            EXPO_PUBLIC_API_BASE_URL="https://REPLACE-WITH-PRODUCTION-API.invalid",
            EXPO_PUBLIC_STORE_URL_ANDROID="market://details?id=REPLACE_WITH_PACKAGE",
        ),
    )
    findings = check(ready, "production", legal)
    messages = _messages(findings, "open")
    assert any("EXPO_PUBLIC_API_BASE_URL" in m and "placeholder" in m for m in messages), messages
    assert any("STORE_URL_ANDROID" in m and "placeholder" in m for m in messages), messages
    assert _messages(findings, "error") == []
    assert exit_code(findings, "production") == 1


def test_a_placeholder_submit_value_is_open(ready: Path, legal: Path) -> None:
    _edit(
        ready,
        "eas.json",
        lambda d: d["submit"]["production"]["ios"].update(
            ascAppId="REPLACE_WITH_APP_STORE_CONNECT_APP_ID"
        ),
    )
    assert any(
        "submit.production.ios.ascAppId" in m
        for m in _messages(check(ready, "production", legal), "open")
    )
