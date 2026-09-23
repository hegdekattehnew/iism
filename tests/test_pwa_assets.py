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
    for route in ("/me/", "/auth/", "/employer/", "/matches", "/profile", "/signin", "/account"):
        assert f'"{route}"' in deny, route
    assert 'request.headers.has("authorization")' in sw


def test_the_live_counts_are_network_first_not_stale_while_revalidate() -> None:
    """The homepage says these numbers are "counted live from the platform
    database". Under stale-while-revalidate they were not: the cached figure
    was returned and the fresh one only arrived on the *next* visit, so an
    employer who had just published a vacancy saw the count from before it.

    The order matters as much as the list -- `/skills/count` starts with
    `/skills`, which is in `CACHEABLE_DATA`, so a branch placed after it would
    never be reached.
    """
    sw = (PUBLIC / "sw.js").read_text()

    live = sw[sw.index("const LIVE_DATA") : sw.index("const denied")]
    for route in ("/marketplace/counts", "/marketplace/stats", "/skills/count"):
        assert f'"{route}"' in live, route

    assert "async function networkFirst(" in sw
    assert sw.index("LIVE_DATA.some(") < sw.index("CACHEABLE_DATA.some(")
