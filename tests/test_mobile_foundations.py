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
    same guard for the keys a screen names literally. Scoped per function, because `t` is a
    different namespace in each (a component may translate `errors` in one and `mobile.list` in
    another)."""
    catalogue = json.loads((WEB_MESSAGES / "en.json").read_text(encoding="utf-8"))
    catalogue["mobile"] = json.loads(
        (MOBILE / "src/messages/app.en.json").read_text(encoding="utf-8")
    )
    used = 0
    for path in _hand_written():
        source = path.read_text(encoding="utf-8")
        for block in re.split(r"(?m)^(?=(?:export )?(?:default )?(?:async )?function\b)", source):
            for var, namespace in re.findall(r'(\w+) = useTranslations\("([\w.]+)"\)', block):
                for key in re.findall(rf"\b{var}\(\s*\"([\w.]+)\"", block):
                    node: object = catalogue
                    for part in [*namespace.split("."), *key.split(".")]:
                        assert isinstance(node, dict) and part in node, (
                            f"{path.name}: {namespace}.{key} is not in the catalogue"
                        )
                        node = node[part]
                    used += 1
    assert used >= 40, "the check found almost nothing to check"


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


def test_each_native_module_is_touched_in_one_file() -> None:
    """The Keychain in one file and the plain store in another: a secret can never end up in the
    store that holds the language and the public cache because nothing else imports either."""
    owners = {
        "expo-secure-store": ["secure-backend.ts"],
        "@react-native-async-storage/async-storage": ["storage.ts"],
        # Push (ADR-075): the decisions are in `core/push.ts`, the operating system is touched here.
        "expo-notifications": ["push.ts"],
    }
    for module, expected in owners.items():
        users = sorted(
            p.name
            for p in _hand_written()
            if f'from "{module}"' in p.read_text(encoding="utf-8") and ".test." not in p.name
        )
        assert users == expected, f"{module} is imported by {users}"


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
            r'(?m)^(?:import\b.*?\bfrom\s+|\}\s*from\s+|import\s+)"([^."][^"]*)"',
            path.read_text(encoding="utf-8"),
        ):
            package = "/".join(spec.split("/")[: 2 if spec.startswith("@") else 1])
            seen.add(package)
            assert package in declared, f"{path.name} imports {package}, which is not declared"
    assert {"react", "react-native", "use-intl", "expo-router", "openapi-fetch"} <= seen


def test_the_apps_modules_do_not_import_each_other_in_a_circle() -> None:
    """A require cycle works until an import is used at module level, then it is an `undefined`
    nobody can explain (Metro warns, and the first browser run did: `ui/index` and `ui/list`)."""
    sources = {
        p.relative_to(MOBILE).with_suffix(""): p.read_text(encoding="utf-8")
        for p in _hand_written()
        if ".test." not in p.name
    }
    edges: dict[Path, set[Path]] = {}
    for module, source in sources.items():
        edges[module] = set()
        for spec in re.findall(r'(?m)(?:from\s+|import\s+)"(\.[^"]*)"', source):
            target = (MOBILE / module.parent / spec).resolve().relative_to(MOBILE.resolve())
            for candidate in (target, target / "index"):
                if candidate in sources:
                    edges[module].add(candidate)
    assert len(edges) >= 20 and sum(len(v) for v in edges.values()) >= 30

    def cycle_from(start: Path, path: tuple[Path, ...] = ()) -> tuple[Path, ...] | None:
        if start in path:
            return (*path[path.index(start) :], start)
        for nxt in edges.get(start, ()):
            found = cycle_from(nxt, (*path, start))
            if found:
                return found
        return None

    for module in edges:
        found = cycle_from(module)
        assert found is None, "import cycle: " + " -> ".join(str(p) for p in found or ())


def _mutation_hooks() -> list[str]:
    source = (MOBILE / "src/lib/me-queries.ts").read_text(encoding="utf-8")
    return re.findall(r"export function (use\w+)\(\)\s*\{[^}]*?useMutation\(", source, flags=re.S)


def test_every_write_can_report_its_own_failure() -> None:
    """The web's `mutation-errors.test.ts` (Sprint 41), for the phone (Sprint 64, ADR-074).

    openapi-fetch resolves on a non-2xx and TanStack swallows a rejection nobody reads, so a write
    whose screen never looks at its error does nothing, in silence, on a 500. `tsc` and `eslint`
    cannot see it. Every screen that calls a mutation hook must read `.isError` or `.error` of the
    variable it bound the result to.
    """
    hooks = _mutation_hooks()
    assert len(hooks) >= 8, hooks  # found them before judging anything
    screens = [p for p in _hand_written() if ".test." not in p.name and p.name != "me-queries.ts"]
    for hook in hooks:
        users = [p for p in screens if re.search(rf"\b{hook}\(", p.read_text(encoding="utf-8"))]
        assert users, f"{hook} is used by no screen"
        for path in users:
            text = path.read_text(encoding="utf-8")
            bound = re.findall(rf"const (\w+) = {hook}\(", text)
            assert bound, f"{path.name} calls {hook} without keeping the result"
            for name in bound:
                assert re.search(rf"\b{name}\.(isError|error)\b", text), (
                    f"{path.name} never reads {name}.isError or {name}.error: a failed "
                    f"{hook} would do nothing, in silence"
                )


def test_every_personal_query_key_starts_with_me() -> None:
    """Persisting keeps only `"public"` keys and sign-out removes everything (the cache is
    cleared whole), but a personal query keyed any other way would sit beside public data and be
    invisible to anyone reading the key to decide what it is."""
    source = (MOBILE / "src/lib/me-queries.ts").read_text(encoding="utf-8")
    keys = re.findall(r"useQuery\(\{\s*queryKey:\s*([^,\n]+)", source)
    assert len(keys) >= 8, keys
    for key in keys:
        assert key.strip().startswith("meKeys."), f"a personal query is not keyed by meKeys: {key}"
    for path in (p for p in _hand_written() if "app" in p.parts or "ui" in p.parts):
        assert "useQuery(" not in path.read_text(encoding="utf-8"), (
            f"{path.name} builds its own query: personal reads belong in lib/me-queries.ts"
        )
