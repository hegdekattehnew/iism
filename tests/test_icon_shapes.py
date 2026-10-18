"""The icon set is drawn once, on the web, and the phone's copy is generated (Sprint 78, ADR-087).

`web/src/components/ui/icons.tsx` holds one `makeIcon("Name", [paths])` per icon, each marked
`/*#__PURE__*/` so an unused one is dropped from a route's first load (a table looked up by name
would put all of them on every route; `/profile` has only a few KB of headroom). These tests
hold the parts a person cannot see: that the phone's copy is the web's, that every icon is reachable
by the sync script, and that a shape is something an SVG will draw.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "src" / "components" / "ui" / "icons.tsx"
PHONE = ROOT / "mobile" / "src" / "ui" / "icon-shapes.ts"

_MAKE = re.compile(r'makeIcon\("([A-Za-z]+)",\s*\[(.*?)\]\)', re.S)
_PURE = re.compile(r'/\*#__PURE__\*/ makeIcon\("([A-Za-z]+)"')
_EXPORT = re.compile(r"^export const ([A-Za-z]+)Icon = ", re.M)
_PATH_CHARS = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9eE.,\- ]+$")


def _web() -> dict[str, list[str]]:
    text = WEB.read_text(encoding="utf-8")
    # The first match is the factory's own signature in the doc comment, which has no PURE marker.
    return {
        name: re.findall(r'"([^"]*)"', body)
        for name, body in _MAKE.findall(text)
        if f'/*#__PURE__*/ makeIcon("{name}"' in text
    }


def test_the_phones_icon_shapes_are_generated_from_the_webs() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_mobile_tokens.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_there_are_about_thirty_icons_and_the_check_found_them() -> None:
    icons = _web()
    assert 30 <= len(icons) <= 60, (
        "the set is about thirty: a number outside this is a different decision"
    )
    phone = PHONE.read_text(encoding="utf-8")
    for name in icons:
        assert f"  {name}: [" in phone, f"{name} is on the web and not on the phone"


def test_every_icon_is_its_own_pure_export_so_a_route_pays_only_for_what_it_imports() -> None:
    text = WEB.read_text(encoding="utf-8")
    exports = _EXPORT.findall(text)
    pure = _PURE.findall(text)
    assert exports, "found no icon exports"
    assert sorted(exports) == sorted(pure), (
        "an icon export without the pure marker stays in a bundle that does not use it"
    )
    assert len(set(exports)) == len(exports), "two icons share a name"


def test_every_shape_is_a_path_an_svg_draws() -> None:
    for name, paths in _web().items():
        assert paths, f"{name} has no shape"
        for d in paths:
            assert d.startswith(("M", "m")), f"{name}: a path must start with a move: {d!r}"
            assert _PATH_CHARS.fullmatch(d), f"{name}: {d!r} holds a character an SVG path does not"


def test_the_alerts_own_shapes_are_the_icon_sets() -> None:
    """`Alert` draws four of the set's icons inline, to stay off the icon factory (Sprint 80)."""
    alert = (ROOT / "web" / "src" / "components" / "ui" / "alert.tsx").read_text(encoding="utf-8")
    block = alert.split("const SHAPES = {", 1)[1].split("} as const;", 1)[0]
    icons = _web()
    for tone, name in (
        ("danger", "XCircle"),
        ("warning", "AlertTriangle"),
        ("success", "CheckCircle"),
        ("info", "Info"),
    ):
        drawn = re.search(rf"{tone}: \[(.*?)\]", block, re.S)
        assert drawn, f"no shape for {tone}"
        assert re.findall(r'"([^"]*)"', drawn.group(1)) == icons[name], (
            f"{tone} drifted from {name}"
        )
