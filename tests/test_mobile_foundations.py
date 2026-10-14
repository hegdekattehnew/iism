"""Guards on the mobile app that can run without its toolchain (Sprint 62, ADR-072).

The React Native layer needs Expo installed to compile; these tests hold everything about the
mobile app that is *derived from, or must agree with,* the rest of the repository, so a drift is a
red build here and not a surprise on a phone. Each asserts it **found** what it is guarding before
asserting anything about it.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from api.core.config import PRIVACY_NOTICE_VERSION
from api.core.contract import surface_operations

ROOT = Path(__file__).resolve().parent.parent
MOBILE = ROOT / "mobile"
WEB_MESSAGES = ROOT / "web" / "src" / "messages"
SOURCES = [*MOBILE.glob("app/**/*.ts*"), *MOBILE.glob("src/**/*.ts*")]
# Generated or data files: tokens.ts is where colours are allowed to be named.
_GENERATED = {"schema.d.ts", "tokens.ts"}


def _hand_written() -> list[Path]:
    return [p for p in SOURCES if p.name not in _GENERATED and "messages" not in p.parts]


def test_it_found_the_mobile_sources() -> None:
    names = {p.name for p in _hand_written()}
    assert {"api.ts", "token-store.ts", "sign-in.ts", "_layout.tsx"} <= names
    assert len(names) >= 15


def test_the_messages_are_the_webs_and_are_not_edited_here() -> None:
    """Edit `web/src/messages`, then `make sync-mobile-messages`."""
    checked = 0
    for source in sorted(WEB_MESSAGES.glob("*.json")):
        if source.name == "fatal.json":
            continue
        copy = MOBILE / "src" / "messages" / source.name
        assert copy.exists(), f"{copy} is missing: run `make sync-mobile-messages`"
        assert copy.read_text(encoding="utf-8") == source.read_text(encoding="utf-8"), (
            f"{copy.name} differs from the web's: run `make sync-mobile-messages`"
        )
        checked += 1
    assert checked >= 3


def test_the_phone_only_strings_exist_in_both_languages_with_the_same_keys() -> None:
    def keys(node: object, prefix: str = "") -> set[str]:
        if isinstance(node, dict):
            return {k for name, v in node.items() for k in keys(v, f"{prefix}{name}.")}
        return {prefix.rstrip(".")}

    english = json.loads((MOBILE / "src/messages/app.en.json").read_text(encoding="utf-8"))
    hindi = json.loads((MOBILE / "src/messages/app.hi.json").read_text(encoding="utf-8"))
    assert len(keys(english)) >= 15
    assert keys(english) == keys(hindi)


def test_every_message_the_screens_use_exists() -> None:
    """A missing key renders as the key itself; the web's `renderUi` throws on it, and this is the
    same guard for a layer that has no render test yet."""
    catalogue = json.loads((WEB_MESSAGES / "en.json").read_text(encoding="utf-8"))
    catalogue["mobile"] = json.loads(
        (MOBILE / "src/messages/app.en.json").read_text(encoding="utf-8")
    )
    used = 0
    for path in _hand_written():
        source = path.read_text(encoding="utf-8")
        for namespace_var, namespace in re.findall(
            r'(\w+) = useTranslations\("([\w.]+)"\)', source
        ):
            for key in re.findall(rf"\b{namespace_var}\(\s*\"([\w.]+)\"", source):
                node: object = catalogue
                for part in [*namespace.split("."), *key.split(".")]:
                    assert isinstance(node, dict) and part in node, (
                        f"{path.name}: {namespace}.{key} is not in the catalogue"
                    )
                    node = node[part]
                used += 1
    assert used >= 15, "the check found almost nothing to check"


def test_the_colour_tokens_are_generated_from_the_webs() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_mobile_tokens.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_token_exists_in_both_themes() -> None:
    tokens = (MOBILE / "src/theme/tokens.ts").read_text(encoding="utf-8")
    light = re.search(r"export const light = \{(.*?)\n\} as const", tokens, re.S)
    dark = re.search(r"export const dark = \{(.*?)\n\} as const", tokens, re.S)
    assert light and dark
    names = lambda block: set(re.findall(r"^\s+(\w+):", block, re.M))  # noqa: E731
    assert len(names(light.group(1))) >= 25
    assert names(light.group(1)) == names(dark.group(1))


def test_no_screen_names_a_colour() -> None:
    """The web's rule, kept: `tokens.ts` is the only file that may."""
    pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
    offenders = [
        f"{p.relative_to(MOBILE)}:{n}"
        for p in _hand_written()
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line) and not line.lstrip().startswith(("//", "*", "/*"))
    ]
    assert offenders == [], f"a colour is named outside tokens.ts: {offenders}"


def test_the_privacy_notice_version_is_the_apis() -> None:
    """A different version here would make every sign-up fail with 428 (as on the web)."""
    source = (MOBILE / "src/core/sign-in.ts").read_text(encoding="utf-8")
    found = re.search(r'PRIVACY_NOTICE_VERSION = "([^"]+)"', source)
    assert found and found.group(1) == PRIVACY_NOTICE_VERSION


def test_the_released_surface_is_exactly_what_the_app_calls() -> None:
    """An operation the app calls but the surface does not list is unprotected by the contract
    check; one it lists but never calls is a promise nobody needs. Both are drift."""
    surface = set(surface_operations((MOBILE / "contract/surface.txt").read_text(encoding="utf-8")))
    called: set[str] = set()
    for path in (p for p in _hand_written() if ".test." not in p.name):
        for method, route in re.findall(
            r'api\s*\.\s*(GET|POST|PUT|PATCH|DELETE)\(\s*"(/[^"]+)"',
            path.read_text(encoding="utf-8"),
        ):
            called.add(f"{method} {route}")
    assert {"POST /auth/otp/request", "POST /auth/otp/verify", "GET /auth/me"} <= called
    assert not (called - surface), f"called but not on the contract surface: {called - surface}"
    # The health probe and the other session endpoints are listed ahead of their screens in M1.
    allowed_unused = {"GET /health", "POST /auth/refresh", "POST /auth/logout-all"}
    assert not (surface - called - allowed_unused), (
        f"on the surface but never called: {surface - called - allowed_unused}"
    )


def test_the_app_is_a_candidate_app_with_placeholder_ids_marked() -> None:
    app = json.loads((MOBILE / "app.json").read_text(encoding="utf-8"))["expo"]
    assert app["ios"]["bundleIdentifier"] == app["android"]["package"] == "in.iism.app"
    readme = (MOBILE / "README.md").read_text(encoding="utf-8")
    assert "placeholder" in readme.lower()


def test_the_native_module_is_touched_in_one_file() -> None:
    users = [
        p.name
        for p in _hand_written()
        if 'from "expo-secure-store"' in p.read_text(encoding="utf-8")
    ]
    assert users == ["secure-backend.ts"]


def test_every_package_the_app_imports_is_declared_and_locked() -> None:
    """An import that only resolves because a dependency hoisted it is a break waiting for the next
    install. Every bare import in the app's own code must be in `package.json`, which must be
    locked, and the entry point must be Expo Router's."""
    manifest = json.loads((MOBILE / "package.json").read_text(encoding="utf-8"))
    declared = {*manifest["dependencies"], *manifest["devDependencies"]}
    assert manifest["main"] == "expo-router/entry"
    assert (MOBILE / "package-lock.json").exists()

    seen: set[str] = set()
    for path in _hand_written():
        for spec in re.findall(
            r'(?:from|jest\.mock\(|require\()\s*"([^."][^"]*)"', path.read_text(encoding="utf-8")
        ):
            package = "/".join(spec.split("/")[: 2 if spec.startswith("@") else 1])
            seen.add(package)
            assert package in declared, f"{path.name} imports {package}, which is not declared"
    assert {"react", "react-native", "use-intl", "expo-router", "openapi-fetch"} <= seen
