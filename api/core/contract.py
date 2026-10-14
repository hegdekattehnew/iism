"""What a released mobile app depends on, and what would break it (Sprint 62, BL-15.7, ADR-072).

A web page ships with the API; an installed app does not, and cannot be updated on demand. So the
API is **additive-only for the operations the released app calls**, and this module is how that is
held: a snapshot of those operations (their parameters, request body and responses, with every
`$ref` inlined) is committed at each store release, and `breaking_changes` says what the current API
would break against it.

**Only the mobile surface is checked.** `mobile/contract/surface.txt` names the operations the app
calls; the rest of the API may change freely, as it always has, because the web app deploys with it.

**What counts as breaking**, from the app's side of each exchange:

* a surface operation removed, or a success response (2xx) removed;
* a response property removed, changed to a type the app did not expect (including `null`, which
  an app reads unguarded), or no longer always present;
* a request that now needs something the app does not send (a new required parameter or property,
  a stricter type, a smaller maximum length, a narrower enum, a changed pattern).

A widened *response* enum is **reported but does not fail**: whether it breaks depends on whether
the app's code is exhaustive over it, which a schema cannot say.

Pure functions over plain dictionaries: no I/O, so each rule has a test that fails without it.
"""

from collections.abc import Iterable
from typing import Any

_METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


class ContractError(Exception):
    """The surface names an operation the API does not have."""


# --------------------------------------------------------------------------- snapshotting


def surface_operations(text: str) -> list[str]:
    """`"POST /auth/refresh"` per line; blank lines and `#` comments are ignored."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            method, _, path = line.partition(" ")
            out.append(f"{method.upper()} {path.strip()}")
    return out


def _inline(node: Any, components: dict[str, Any], stack: tuple[str, ...] = ()) -> Any:
    """Resolve every `$ref`. A schema that contains itself is cut at the second visit, marked."""
    if isinstance(node, list):
        return [_inline(item, components, stack) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[1]
        if name in stack:
            return {"$cycle": name}
        return _inline(components.get(name, {}), components, (*stack, name))
    return {
        key: _inline(value, components, stack)
        for key, value in node.items()
        if key not in ("title", "description", "examples", "example", "default")
    }


def snapshot(openapi: dict[str, Any], surface: Iterable[str]) -> dict[str, Any]:
    """The named operations, fully inlined. Raises `ContractError` for one that does not exist."""
    components = openapi.get("components", {}).get("schemas", {})
    out: dict[str, Any] = {}
    for key in surface:
        method, _, path = key.partition(" ")
        operation = openapi.get("paths", {}).get(path, {}).get(method.lower())
        if operation is None:
            raise ContractError(f"{key} is on the mobile surface but is not an API operation")
        out[key] = _inline(
            {
                "parameters": operation.get("parameters", []),
                "requestBody": operation.get("requestBody"),
                "responses": operation.get("responses", {}),
            },
            components,
        )
    return dict(sorted(out.items()))


# ------------------------------------------------------------------------------ comparing


def _unwrap(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """`anyOf: [X, null]` -> `(X, True)`: the nullable wrapper pydantic writes for `X | None`."""
    for key in ("anyOf", "oneOf"):
        members = schema.get(key)
        if isinstance(members, list):
            kept = [m for m in members if m.get("type") != "null"]
            if len(kept) == 1 and len(members) == 2:
                return kept[0], True
    return schema, schema.get("type") == "null"


def _types(schema: dict[str, Any]) -> set[str]:
    kind = schema.get("type")
    if isinstance(kind, list):
        return {str(k) for k in kind}
    if isinstance(kind, str):
        return {kind}
    members = schema.get("anyOf") or schema.get("oneOf")
    if isinstance(members, list):
        merged: set[str] = set()
        for member in members:
            merged |= _types(member)
        return merged
    return set()


def _widen(types: set[str]) -> set[str]:
    return types | {"number"} if "integer" in types else types


def _response(old: dict[str, Any], new: dict[str, Any], where: str, out: list[str]) -> None:
    if "$cycle" in old or "$cycle" in new:
        return
    old, old_null = _unwrap(old)
    new, new_null = _unwrap(new)
    if new_null and not old_null:
        out.append(f"{where}: can now be null")
    old_types, new_types = _widen(_types(old)), _widen(_types(new))
    if old_types and new_types and (new_types - {"null"}) - old_types:
        out.append(f"{where}: type changed from {sorted(old_types)} to {sorted(new_types)}")
        return
    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    for name, schema in old_props.items():
        if name not in new_props:
            out.append(f"{where}.{name}: removed")
            continue
        if name in old.get("required", []) and name not in new.get("required", []):
            out.append(f"{where}.{name}: no longer always present")
        _response(schema, new_props[name], f"{where}.{name}", out)
    if "items" in old and "items" in new:
        _response(old["items"], new["items"], f"{where}[]", out)


def _request(old: dict[str, Any], new: dict[str, Any], where: str, out: list[str]) -> None:
    if "$cycle" in old or "$cycle" in new:
        return
    old, _ = _unwrap(old)
    new, _ = _unwrap(new)
    old_types, new_types = _widen(_types(old)), _widen(_types(new))
    if old_types and new_types and old_types - new_types:
        out.append(f"{where}: no longer accepts {sorted(old_types - new_types)}")
    if "enum" in old and "enum" in new:
        gone = [v for v in old["enum"] if v not in new["enum"]]
        if gone:
            out.append(f"{where}: no longer accepts {gone}")
    for bound, tighter in (
        ("maxLength", lambda a, b: b < a),
        ("minLength", lambda a, b: b > a),
        ("maximum", lambda a, b: b < a),
        ("minimum", lambda a, b: b > a),
    ):
        if bound in new and (bound not in old or tighter(old[bound], new[bound])):
            out.append(f"{where}: {bound} is now {new[bound]}")
    if new.get("pattern") != old.get("pattern") and "pattern" in new:
        out.append(f"{where}: pattern changed")
    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    for name in new.get("required", []):
        if name not in old.get("required", []):
            out.append(f"{where}.{name}: now required")
    for name, schema in old_props.items():
        if name in new_props:
            _request(schema, new_props[name], f"{where}.{name}", out)
    if "items" in old and "items" in new:
        _request(old["items"], new["items"], f"{where}[]", out)


def _json(content: dict[str, Any] | None) -> dict[str, Any] | None:
    return (content or {}).get("application/json", {}).get("schema")


def _parameters(
    old: list[dict[str, Any]], new: list[dict[str, Any]], key: str, out: list[str]
) -> None:
    """A new required parameter, or an optional one made required, breaks an app that omits it."""
    before = {(p["in"], p["name"]): p for p in old}
    for ident, parameter in {(p["in"], p["name"]): p for p in new}.items():
        where = f"{key} {ident[0]} parameter '{ident[1]}'"
        earlier = before.get(ident)
        if parameter.get("required") and not (earlier and earlier.get("required")):
            out.append(f"{where}: now required")
        if earlier:
            _request(earlier.get("schema", {}), parameter.get("schema", {}), where, out)


def breaking_changes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """What `new` would break for an app built against `old`. Both are `snapshot()` results."""
    out: list[str] = []
    for key, before in old.items():
        after = new.get(key)
        if after is None:
            out.append(f"{key}: removed")
            continue
        _parameters(before.get("parameters", []), after.get("parameters", []), key, out)

        if (before.get("requestBody") or {}) or (after.get("requestBody") or {}):
            old_body = _json((before.get("requestBody") or {}).get("content"))
            new_body = _json((after.get("requestBody") or {}).get("content"))
            if (after.get("requestBody") or {}).get("required") and not (
                before.get("requestBody") or {}
            ).get("required"):
                out.append(f"{key} request body: now required")
            if old_body is not None and new_body is not None:
                _request(old_body, new_body, f"{key} request", out)
            elif old_body is not None:
                out.append(f"{key} request body: no longer accepts JSON")

        for status, response in before.get("responses", {}).items():
            replacement = after.get("responses", {}).get(status)
            if replacement is None:
                if status.startswith("2"):
                    out.append(f"{key} -> {status}: success response removed")
                continue
            old_json, new_json = _json(response.get("content")), _json(replacement.get("content"))
            if old_json is not None and new_json is None:
                out.append(f"{key} -> {status}: no longer returns JSON")
            elif old_json is not None and new_json is not None:
                _response(old_json, new_json, f"{key} -> {status}", out)
    return out


def widened_enums(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Response enums that gained a value: reported, never failing (see the module docstring)."""
    out: list[str] = []

    def walk(a: Any, b: Any, where: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            if "enum" in a and "enum" in b:
                added = [v for v in b["enum"] if v not in a["enum"]]
                if added:
                    out.append(f"{where}: gained {added}")
            for name in a:
                if name in b:
                    walk(a[name], b[name], f"{where}.{name}" if name != "properties" else where)
        elif isinstance(a, list) and isinstance(b, list):
            for index, (x, y) in enumerate(zip(a, b, strict=False)):
                walk(x, y, f"{where}[{index}]")

    for key, before in old.items():
        if key in new:
            walk(before.get("responses", {}), new[key].get("responses", {}), key)
    return out
