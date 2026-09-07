"""The manifest, and the files it promises exist.

Installability fails silently: Chrome simply stops offering "Install", and the
only symptom is an absent button nobody thinks to look for. A renamed or
deleted icon is the most likely cause, so it is worth a test that runs in CI
rather than a check somebody remembers to do on a phone.
"""

import json
from pathlib import Path

PUBLIC = Path(__file__).resolve().parents[1] / "web" / "public"
MANIFEST = json.loads((PUBLIC / "manifest.webmanifest").read_text())


def test_every_icon_the_manifest_promises_exists() -> None:
    for icon in MANIFEST["icons"]:
        assert (PUBLIC / icon["src"].lstrip("/")).is_file(), icon["src"]


def test_a_maskable_icon_is_declared() -> None:
    """Without one, Android crops the square icon inside its own mask and the
    result is a shrunken logo in a white box."""
    assert any("maskable" in i.get("purpose", "") for i in MANIFEST["icons"])


def test_png_icons_exist_because_ios_ignores_svg() -> None:
    sizes = {i["sizes"] for i in MANIFEST["icons"] if i.get("type") == "image/png"}
    assert {"192x192", "512x512"} <= sizes
    assert (PUBLIC / "apple-touch-icon.png").is_file()


def test_the_service_worker_has_a_fetch_handler() -> None:
    """Chrome will not offer to install without one, so its absence is not a
    missing optimisation -- it is the feature not existing."""
    assert 'addEventListener("fetch"' in (PUBLIC / "sw.js").read_text()


def test_personal_and_computed_routes_are_never_cached() -> None:
    """A stale match would show a candidate a gap they have already closed, and
    cached profile data on a shared phone is an ADR-023 problem. This is a
    security boundary, so it is asserted rather than trusted to a code review."""
    sw = (PUBLIC / "sw.js").read_text()
    deny = sw[sw.index("const DENY") : sw.index("// Public taxonomy")]
    for route in ("/me/", "/auth/", "/employer/", "/matches", "/profile", "/signin"):
        assert f'"{route}"' in deny, route
    assert 'request.headers.has("authorization")' in sw
