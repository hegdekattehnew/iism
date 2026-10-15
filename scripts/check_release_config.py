"""Check that the mobile app's release configuration is fit to ship (Sprint 66, ADR-077).

    .venv/bin/python scripts/check_release_config.py                       # preview: defects fail
    .venv/bin/python scripts/check_release_config.py --profile production  # the gate

Two kinds of finding, kept apart on purpose:

* **error** is a defect in what is written down (a missing icon, an `http://` origin, a permission
  the app does not use, encryption not declared). It fails every profile.
* **open** is a decision only the owner can make and that is still a placeholder (the bundle id, a
  hostname, a store id, the app's own artwork, an EAS project id, the grievance officer). It is
  reported for every profile and **fails `production` only**, so the build stays green while the
  accounts do not exist and a production build cannot be cut by accident.

The check reads files; it builds nothing and contacts nothing. No Expo or EAS install is needed.
"""

import argparse
import hashlib
import json
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
MOBILE = ROOT / "mobile"
LEGAL = ROOT / "web" / "src" / "lib" / "legal.ts"

PLACEHOLDER_BUNDLE_ID = "in.iism.app"
# The permissions the app uses: it reaches the network and shows notifications. Nothing else.
ALLOWED_ANDROID_PERMISSIONS = {"android.permission.POST_NOTIFICATIONS"}
LOCAL_HOSTS = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|10\.0\.2\.2|0\.0\.0\.0|\[::1\]|[^.]+\.localhost)$", re.I
)
PLACEHOLDER_MARK = re.compile(r"REPLACE|\.invalid\b|example\.(com|org|net)\b", re.I)
# What the app must be told at build time, per profile (config.ts reads exactly these).
REQUIRED_ENV = {
    "preview": ["EXPO_PUBLIC_API_BASE_URL", "EXPO_PUBLIC_WEB_BASE_URL"],
    "production": [
        "EXPO_PUBLIC_API_BASE_URL",
        "EXPO_PUBLIC_WEB_BASE_URL",
        "EXPO_PUBLIC_STORE_URL_ANDROID",
        "EXPO_PUBLIC_STORE_URL_IOS",
    ],
}
# SHA-256 of the files `create-expo-app` ships. Shipping them puts Expo's artwork on an IISM
# listing, which stores reject and which says nothing about this product.
TEMPLATE_ASSETS = {
    "fb139c2dee362ebf2070e23b96da6fc0d43f8492de38b8af1fd7223e19b5861d": "android-icon-background",
    "9e3d0315a33c6799de601dd34cd8bf8cc3a8d16f3bf75592baec2ceb7240b391": "android-icon-foreground",
    "6371fc2c12e33ad2215a86c281db3d682a81bebe7c957a842c13b8bf00cceb83": "android-icon-monochrome",
    "119462bb78eb240a65c869fc067ee599639b3cb5a41953f25c07b17d2a8c7e0f": "icon.png",
    "5f4c0a732b6325bf4071d9124d2ae67e037cb24fcc9c482ef82bea742109a3b8": "splash-icon.png",
}


@dataclass(frozen=True)
class Finding:
    kind: str  # "error" | "open"
    message: str


def _png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _origin_findings(label: str, name: str, value: str) -> list[Finding]:
    found: list[Finding] = []
    parsed = urlparse(value)
    if name.endswith("BASE_URL"):
        if parsed.scheme != "https":
            found.append(Finding("error", f"{label}: {name} is not an https:// origin ({value!r})"))
        elif parsed.hostname and LOCAL_HOSTS.match(parsed.hostname):
            found.append(Finding("error", f"{label}: {name} is a local address ({value!r})"))
    if PLACEHOLDER_MARK.search(value):
        found.append(Finding("open", f"{label}: {name} is still a placeholder ({value!r})"))
    return found


def _icon_findings(mobile: Path, expo: dict[str, object]) -> list[Finding]:
    found: list[Finding] = []
    android = expo.get("android")
    adaptive = android.get("adaptiveIcon", {}) if isinstance(android, dict) else {}
    wanted: dict[str, tuple[str, int]] = {"icon": (str(expo.get("icon", "")), 1024)}
    for key in ("foregroundImage", "backgroundImage", "monochromeImage"):
        wanted[f"android.adaptiveIcon.{key}"] = (str(adaptive.get(key, "")), 432)
    plugins = expo.get("plugins", [])
    splash = next(
        (
            p[1]
            for p in plugins
            if isinstance(p, list) and len(p) > 1 and p[0] == "expo-splash-screen"
        ),
        None,
    )
    if isinstance(splash, dict):
        wanted["splash.image"] = (str(splash.get("image", "")), 200)
        dark = splash.get("dark")
        if isinstance(dark, dict):
            wanted["splash.dark.image"] = (str(dark.get("image", "")), 200)
    else:
        found.append(Finding("error", "app.json: the expo-splash-screen plugin is not configured"))
    for label, (relative, minimum) in wanted.items():
        path = mobile / relative
        if not relative or not path.is_file():
            found.append(
                Finding(
                    "error", f"app.json: {label} points at a file that is not there ({relative!r})"
                )
            )
            continue
        size = _png_size(path)
        if size is None:
            found.append(Finding("error", f"{relative}: not a PNG"))
        elif size[0] != size[1] or size[0] < minimum:
            found.append(
                Finding("error", f"{relative}: {size[0]}x{size[1]} (square, at least {minimum} px)")
            )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in TEMPLATE_ASSETS:
            found.append(
                Finding(
                    "open",
                    f"{relative} is the Expo template's {TEMPLATE_ASSETS[digest]}, not ours",
                )
            )
    return found


def _grievance_findings(legal: Path) -> list[Finding]:
    if not legal.is_file():
        return [
            Finding("error", f"{legal.name}: not found, so the grievance officer cannot be checked")
        ]
    text = legal.read_text(encoding="utf-8")
    block = re.search(r"GRIEVANCE_OFFICER[^=]*=\s*\{(.*?)\}", text, re.S)
    if not block:
        return [Finding("error", "legal.ts: GRIEVANCE_OFFICER not found")]
    if re.search(r"name:\s*null", block.group(1)):
        return [Finding("open", "the grievance officer is not appointed (web/src/lib/legal.ts)")]
    return []


def check(mobile: Path, profile: str, legal: Path = LEGAL) -> list[Finding]:
    """Everything wrong or still open for `profile` in the app under `mobile`."""
    found: list[Finding] = []
    try:
        expo = json.loads((mobile / "app.json").read_text(encoding="utf-8"))["expo"]
        eas = json.loads((mobile / "eas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as error:
        return [Finding("error", f"cannot read app.json / eas.json: {error!r}")]

    builds = eas.get("build", {})
    build = builds.get(profile)
    if not isinstance(build, dict):
        return [Finding("error", f"eas.json: no build profile named {profile!r}")]

    for name in REQUIRED_ENV[profile]:
        value = build.get("env", {}).get(name)
        if not isinstance(value, str) or not value:
            found.append(
                Finding(
                    "error",
                    f"eas.json: {profile} sets no {name} (it would use a dev default)",
                )
            )
        else:
            found.extend(_origin_findings(f"eas.json {profile}", name, value))

    if expo.get("ios", {}).get("config", {}).get("usesNonExemptEncryption") is not False:
        found.append(
            Finding(
                "error", "app.json: ios.config.usesNonExemptEncryption must be false (HTTPS only)"
            )
        )
    permissions = set(expo.get("android", {}).get("permissions", []))
    if not permissions or not permissions <= ALLOWED_ANDROID_PERMISSIONS:
        extra = sorted(permissions - ALLOWED_ANDROID_PERMISSIONS)
        found.append(
            Finding(
                "error",
                f"app.json: android.permissions must be exactly the app's own (extra: {extra})",
            )
        )
    if expo.get("scheme") != "iism":
        found.append(
            Finding(
                "error", "app.json: the link scheme is not 'iism' (core/links.ts depends on it)"
            )
        )
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(expo.get("version", ""))):
        found.append(
            Finding("error", f"app.json: version {expo.get('version')!r} is not major.minor.patch")
        )
    if eas.get("cli", {}).get("appVersionSource") != "remote":
        found.append(
            Finding(
                "error",
                "eas.json: cli.appVersionSource must be 'remote' so build numbers cannot repeat",
            )
        )
    if profile == "production":
        if build.get("android", {}).get("buildType") != "app-bundle":
            found.append(
                Finding("error", "eas.json: production must build an app bundle for Google Play")
            )
        if not build.get("android", {}).get("autoIncrement") or not build.get("ios", {}).get(
            "autoIncrement"
        ):
            found.append(
                Finding("error", "eas.json: production must auto-increment both build numbers")
            )

    found.extend(_icon_findings(mobile, expo))

    ids = {expo.get("ios", {}).get("bundleIdentifier"), expo.get("android", {}).get("package")}
    if None in ids or "" in ids:
        found.append(
            Finding("error", "app.json: the iOS bundle id and the Android package must both be set")
        )
    if PLACEHOLDER_BUNDLE_ID in ids:
        found.append(
            Finding("open", f"the bundle id / package is the placeholder {PLACEHOLDER_BUNDLE_ID!r}")
        )
    if not expo.get("extra", {}).get("eas", {}).get("projectId"):
        found.append(
            Finding(
                "open",
                "no EAS project id (app.json extra.eas.projectId): there is no EAS account yet",
            )
        )

    submit = eas.get("submit", {}).get("production", {})
    flat = {
        **{f"android.{k}": v for k, v in submit.get("android", {}).items()},
        **{f"ios.{k}": v for k, v in submit.get("ios", {}).items()},
    }
    if not flat:
        found.append(Finding("error", "eas.json: no submit.production section"))
    for key, value in flat.items():
        if isinstance(value, str) and PLACEHOLDER_MARK.search(value):
            found.append(
                Finding("open", f"eas.json submit.production.{key} is still a placeholder")
            )

    found.extend(_grievance_findings(legal))
    return list(
        dict.fromkeys(found)
    )  # the same file named twice (splash light and dark) reads once


def exit_code(findings: list[Finding], profile: str) -> int:
    if any(f.kind == "error" for f in findings):
        return 1
    return 1 if profile == "production" and findings else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(REQUIRED_ENV), default="preview")
    args = parser.parse_args()
    findings = check(MOBILE, args.profile)
    for finding in findings:
        print(f"{finding.kind.upper():5} {finding.message}")
    errors = sum(f.kind == "error" for f in findings)
    open_items = len(findings) - errors
    print(f"release config ({args.profile}): {errors} defect(s), {open_items} owner item(s) open")
    return exit_code(findings, args.profile)


if __name__ == "__main__":
    sys.exit(main())
