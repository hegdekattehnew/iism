"""The design tokens hold together (Sprint 77, ADR-086, BL-19.4 to BL-19.6).

`globals.css` is the one place a colour, a type size, a corner or a duration is chosen, and the
phone's tables are generated from it. What this pins is what a visual refresh can quietly break:
a semantic token drifting off the ramp step it names, a pairing that stops being readable in one
theme, a size under the 12 px floor, a Hindi line shorter than the English one, a copy of a colour
(the address bar, the installed app's splash, the offline page) left behind when the page moved.
Contrast is computed here, from the file, because jsdom has no layout and cannot.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "web" / "src" / "app" / "globals.css").read_text(encoding="utf-8")
DECL = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")


def _block(text: str, opener: str) -> str:
    """The text inside the braces of the first `opener` (an opener may end with its own brace)."""
    at = text.index(opener) + len(opener)
    start = at if opener.endswith("{") else text.index("{", at) + 1
    depth, i = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[start : i - 1]


ROOT_BLOCK = _block(CSS, ":root")
LIGHT = {k: v.strip() for k, v in DECL.findall(ROOT_BLOCK)}
DARK_ONLY = {
    k: v.strip()
    for k, v in DECL.findall(_block(_block(CSS, "@media (prefers-color-scheme: dark)"), ":root"))
}
DARK = {**LIGHT, **DARK_ONLY}


def _rgb(hex_: str) -> tuple[float, float, float]:
    h = hex_.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lum(hex_: str) -> float:
    def channel(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in _rgb(hex_))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


STEPS = ("50", "100", "200", "300", "400", "500", "600", "700", "800", "900")


class TestTheRamps:
    def test_they_exist_and_get_darker_step_by_step(self) -> None:
        for family in ("brand", "neutral"):
            values = [LIGHT[f"{family}-{s}"] for s in STEPS]
            assert len(values) == 10
            lums = [_lum(v) for v in values]
            assert lums == sorted(lums, reverse=True), f"{family} is not monotonic"

    def test_the_neutral_ramp_has_the_two_dark_only_steps(self) -> None:
        assert LIGHT["neutral-850"] and LIGHT["neutral-950"]
        assert _lum(LIGHT["neutral-950"]) < _lum(LIGHT["neutral-900"]) < _lum(LIGHT["neutral-850"])

    def test_700_is_the_colour_the_product_has_always_used(self) -> None:
        assert LIGHT["brand-700"].lower() == "#1f4e79"


class TestSemanticTokensNameAStepInEachTheme:
    LIGHT_MAP = {
        "background": "neutral-50",
        "surface-muted": "neutral-100",
        "border": "neutral-200",
        "muted": "neutral-600",
        "input-border": "neutral-500",
        "foreground": "neutral-900",
        "brand": "brand-700",
        "brand-strong": "brand-800",
        "accent-soft": "brand-50",
        "accent-tint": "brand-100",
        "accent-text": "brand-800",
    }
    DARK_MAP = {
        "background": "neutral-950",
        "surface": "neutral-900",
        "surface-muted": "neutral-850",
        "surface-raised": "neutral-800",
        "border": "neutral-800",
        "muted": "neutral-400",
        "input-border": "neutral-500",
        "foreground": "neutral-100",
        "brand": "brand-400",
        "brand-strong": "brand-300",
        "brand-contrast": "brand-900",
        "accent-soft": "brand-900",
        "accent-tint": "brand-800",
        "accent-text": "brand-200",
    }

    @pytest.mark.parametrize(("token", "step"), LIGHT_MAP.items())
    def test_light(self, token: str, step: str) -> None:
        assert LIGHT[token].lower() == LIGHT[step].lower(), f"--{token} is not --{step}"

    @pytest.mark.parametrize(("token", "step"), DARK_MAP.items())
    def test_dark(self, token: str, step: str) -> None:
        assert DARK[token].lower() == DARK[step].lower(), f"--{token} is not --{step} in dark"

    def test_a_card_is_white_on_a_grey_page_in_light_and_lighter_than_the_page_in_dark(
        self,
    ) -> None:
        assert LIGHT["surface"].lower() == "#ffffff"
        assert _lum(LIGHT["surface"]) > _lum(LIGHT["background"])
        assert _lum(DARK["surface"]) > _lum(DARK["background"])


TEXT_PAIRS = [
    ("foreground", "background", 7.0),
    ("foreground", "surface", 7.0),
    ("foreground", "surface-muted", 7.0),
    ("foreground", "accent-soft", 7.0),
    ("muted", "background", 4.5),
    ("muted", "surface", 4.5),
    ("muted", "surface-muted", 4.5),
    ("muted", "accent-soft", 4.5),
    ("muted", "accent-tint", 4.5),
    ("brand", "background", 4.5),
    ("brand", "surface", 4.5),
    ("brand", "accent-soft", 4.5),
    ("brand-contrast", "brand", 4.5),
    ("brand-contrast", "brand-strong", 4.5),
    ("accent-text", "accent-soft", 4.5),
    ("accent-text", "accent-tint", 4.5),
    ("success-text", "success-surface", 4.5),
    ("warning-text", "warning-surface", 4.5),
    ("danger-text", "danger-surface", 4.5),
    ("info-text", "info-surface", 4.5),
]


class TestEveryPairingIsReadable:
    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize(("fg", "bg", "minimum"), TEXT_PAIRS)
    def test_text(self, theme: str, fg: str, bg: str, minimum: float) -> None:
        tokens = LIGHT if theme == "light" else DARK
        ratio = contrast(tokens[fg], tokens[bg])
        assert ratio >= minimum, f"{theme}: --{fg} on --{bg} is {ratio:.2f}:1, needs {minimum}"

    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize("surface", ["background", "surface", "surface-muted"])
    def test_a_control_edge_is_findable(self, theme: str, surface: str) -> None:
        """WCAG 1.4.11: the edge of an input you have to find to type in is 3:1 against its page."""
        tokens = LIGHT if theme == "light" else DARK
        assert contrast(tokens["input-border"], tokens[surface]) >= 3.0

    def test_the_checker_can_fail(self) -> None:
        assert contrast("#777777", "#888888") < 1.5
        assert contrast("#000000", "#ffffff") == pytest.approx(21.0)


class TestTheCopiesOfAColour:
    """The address bar, the installed app and the offline page cannot read the stylesheet."""

    def test_the_address_bar_follows_the_page(self) -> None:
        """The layout names the colours through `THEME_COLOURS` (Sprint 78), their one home."""
        layout = (ROOT / "web" / "src" / "app" / "[locale]" / "layout.tsx").read_text("utf-8")
        assert re.search(r'prefers-color-scheme: light\)", color: THEME_COLOURS\.light', layout)
        assert re.search(r'prefers-color-scheme: dark\)", color: THEME_COLOURS\.dark', layout)
        theme = (ROOT / "web" / "src" / "lib" / "theme.ts").read_text("utf-8")
        light = re.search(r'light: "(#[0-9a-f]{6})"', theme)
        dark = re.search(r'dark: "(#[0-9a-f]{6})"', theme)
        assert light and dark
        assert light[1] == LIGHT["background"]
        assert dark[1] == DARK["background"]

    def test_the_installed_app_opens_on_the_page_colour(self) -> None:
        manifest = json.loads((ROOT / "web" / "public" / "manifest.webmanifest").read_text("utf-8"))
        assert manifest["background_color"] == LIGHT["background"]
        assert manifest["theme_color"].lower() == LIGHT["brand"].lower()

    def test_the_offline_page_is_the_dark_page(self) -> None:
        html = (ROOT / "web" / "public" / "offline.html").read_text("utf-8")
        assert f"background: {DARK['background']}; color: {DARK['foreground']}" in html


class TestTheTypeScale:
    NAMES = ("caption", "small", "body", "lead", "title", "display")

    @staticmethod
    def _rem(value: str) -> float:
        match = re.fullmatch(r"([\d.]+)rem", value)
        assert match, value
        return float(match[1])

    def test_it_has_six_steps_that_grow_and_never_go_under_the_floor(self) -> None:
        sizes = [self._rem(LIGHT[f"type-{n}"]) * 16 for n in self.NAMES]
        assert sizes == sorted(sizes) and len(set(sizes)) == len(sizes)
        assert min(sizes) >= 12, "the 12 px floor (UI-07)"
        assert dict(zip(self.NAMES, sizes, strict=True))["small"] == 15  # the signed-off direction
        assert dict(zip(self.NAMES, sizes, strict=True))["body"] == 16

    def test_a_line_is_taller_than_its_text(self) -> None:
        for n in self.NAMES:
            assert self._rem(LIGHT[f"type-{n}-lh"]) >= self._rem(LIGHT[f"type-{n}"]) * 1.15

    def test_devanagari_gets_a_taller_line_at_every_step(self) -> None:
        hindi = {k: v.strip() for k, v in DECL.findall(_block(CSS, 'html[lang="hi"] {'))}
        for n in self.NAMES:
            en, hi = self._rem(LIGHT[f"type-{n}-lh"]), self._rem(hindi[f"type-{n}-lh"])
            assert hi > en, f"{n}: Hindi {hi} is not taller than English {en}"
            assert hi >= self._rem(LIGHT[f"type-{n}"]) * 1.3

    def test_tailwinds_own_steps_and_the_named_steps_both_point_at_the_scale(self) -> None:
        theme = _block(CSS, "@theme {")
        for tw, name in (
            ("xs", "caption"),
            ("sm", "small"),
            ("base", "body"),
            ("lg", "lead"),
            ("2xl", "title"),
            ("3xl", "display"),
        ):
            assert f"--text-{tw}: var(--type-{name});" in theme
            assert f"--text-{tw}--line-height: var(--type-{name}-lh);" in theme
        for name in self.NAMES:
            assert f"--text-{name}: var(--type-{name});" in theme


class TestCornersMotionAndTheRest:
    def test_three_corners_that_grow(self) -> None:
        sizes = [
            float(re.fullmatch(r"([\d.]+)rem", LIGHT[f"r-{k}"])[1]) * 16 for k in ("sm", "md", "lg")
        ]  # type: ignore[index]
        assert sizes == [6, 10, 16]

    def test_tailwinds_corners_point_at_ours(self) -> None:
        assert "--radius-md: var(--r-sm);" in CSS
        assert "--radius-lg: var(--r-md);" in CSS
        assert "--radius-xl: var(--r-lg);" in CSS

    def test_a_person_who_asked_for_less_movement_gets_none(self) -> None:
        rule = _block(CSS, "@media (prefers-reduced-motion: reduce)")
        assert "animation-duration: 0.01ms !important" in rule
        assert "transition-duration: 0.01ms !important" in rule

    def test_there_are_two_durations_and_one_ease(self) -> None:
        assert LIGHT["duration-fast"] == "120ms" and LIGHT["duration-base"] == "200ms"
        assert LIGHT["ease-standard"].startswith("cubic-bezier(")

    def test_every_theme_colour_a_class_can_use_is_mapped_in_the_theme_block(self) -> None:
        for token in ("surface-raised", "accent-tint", "accent-text", "shadow-card"):
            assert f"var(--{token})" in _block(CSS, "@theme inline"), token

    def test_no_ramp_step_is_offered_to_a_class(self) -> None:
        """A step used directly cannot flip in dark mode: only the semantic tokens are utilities."""
        theme = _block(CSS, "@theme inline")
        assert not re.search(r"--color-(brand|neutral)-\d", theme)


class TestThePhonesTables:
    TOKENS = (ROOT / "mobile" / "src" / "theme" / "tokens.ts").read_text(encoding="utf-8")

    def test_non_colours_are_never_emitted_as_colours(self) -> None:
        light = re.search(r"export const light = \{(.*?)\n\} as const", self.TOKENS, re.S)
        assert light
        for key in ("rSm", "typeBody", "durationFast", "easeStandard", "typeSmallLh"):
            assert f"  {key}:" not in light[1], key
        for line in light[1].splitlines():
            if line.strip():
                assert re.search(r'"(#[0-9a-fA-F]{3,8}|rgba\([^"]+\))",$', line), line

    def test_the_radius_and_the_type_scale_are_the_webs(self) -> None:
        radius = dict(re.findall(r"  (sm|md|lg): (\d+),", self.TOKENS))
        assert radius == {"sm": "6", "md": "10", "lg": "16"}
        for name in TestTheTypeScale.NAMES:
            size = TestTheTypeScale._rem(LIGHT[f"type-{name}"]) * 16
            line = TestTheTypeScale._rem(LIGHT[f"type-{name}-lh"]) * 16
            assert f"{name}: {{ size: {size:g}, lineHeight: {line:g} }}" in self.TOKENS

    def test_the_phones_text_sizes_come_from_the_scale(self) -> None:
        theme = (ROOT / "mobile" / "src" / "theme" / "index.tsx").read_text(encoding="utf-8")
        for member in ("caption", "small", "body", "lead", "title", "display"):
            assert f"typeTokens.{member}.size" in theme
        assert "radius = radiusTokens" in theme

    def test_spacing_is_multiples_of_the_webs_unit(self) -> None:
        theme = (ROOT / "mobile" / "src" / "theme" / "index.tsx").read_text(encoding="utf-8")
        values = [
            int(v)
            for v in re.findall(
                r"\w+: (\d+)", re.search(r"export const space = \{(.*?)\}", theme, re.S)[1]
            )
        ]  # type: ignore[index]
        assert values and all(v % 4 == 0 for v in values)


class TestTheThemeControl:
    """Light, dark or follow the device (Sprint 78, BL-19.8, ADR-087)."""

    THEME_TS = (ROOT / "web" / "src" / "lib" / "theme.ts").read_text(encoding="utf-8")
    LAYOUT = (ROOT / "web" / "src" / "app" / "[locale]" / "layout.tsx").read_text(encoding="utf-8")

    def test_the_media_query_yields_to_a_person_who_chose_light(self) -> None:
        media = _block(CSS, "@media (prefers-color-scheme: dark)")
        assert ':root:not([data-theme="light"])' in media, (
            "a chosen light theme would still turn dark with the device"
        )

    def test_the_two_copies_of_the_dark_tokens_are_the_same(self) -> None:
        by_media = _block(
            _block(CSS, "@media (prefers-color-scheme: dark)"), ':root:not([data-theme="light"])'
        )
        by_choice = _block(CSS, ':root[data-theme="dark"]')
        read = lambda text: {k: v.strip() for k, v in re.findall(r"([a-z-]+)\s*:\s*([^;]+);", text)}  # noqa: E731
        assert read(by_media), "found no dark tokens"
        assert read(by_media) == read(by_choice), (
            "the dark theme differs between the device's and the person's choice"
        )
        assert "color-scheme" in read(by_media), (
            "native controls and scrollbars must follow the theme too"
        )

    def test_light_is_a_pin_not_a_second_copy(self) -> None:
        assert _block(CSS, ':root[data-theme="light"]').strip() == "color-scheme: light;"

    def test_the_address_bar_colours_are_the_page_background_in_each_theme(self) -> None:
        colours = dict(
            re.findall(
                r'(light|dark): "(#[0-9a-fA-F]{6})"', self.THEME_TS.split("THEME_COLOURS")[1]
            )
        )
        assert colours["light"].lower() == LIGHT["background"].lower()
        assert colours["dark"].lower() == DARK["background"].lower()

    def test_the_layout_sets_the_theme_before_the_first_paint_and_tolerates_the_attribute(
        self,
    ) -> None:
        assert "themeScript" in self.LAYOUT and "dangerouslySetInnerHTML" in self.LAYOUT
        assert "suppressHydrationWarning" in self.LAYOUT, (
            "the head script changes <html> before React hydrates it"
        )
        assert self.LAYOUT.index("themeScript") < self.LAYOUT.index("<body"), (
            "the script must come before the body"
        )
