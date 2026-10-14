"""The contract a released mobile app depends on (Sprint 62, BL-15.7, ADR-072).

Each rule has a test that fails without it, and the real API is held against the committed
snapshot, so a change that would break an installed app fails the suite before it ships.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from api.core.contract import (
    ContractError,
    breaking_changes,
    snapshot,
    surface_operations,
    widened_enums,
)

ROOT = Path(__file__).resolve().parent.parent
SURFACE = ROOT / "mobile" / "contract" / "surface.txt"
SNAPSHOT = ROOT / "mobile" / "contract" / "openapi.snapshot.json"


def _api(
    *,
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    parameters: list[dict[str, Any]] | None = None,
    status: str = "200",
) -> dict[str, Any]:
    """A one-operation OpenAPI document, `POST /thing`, with the schemas under test."""
    operation: dict[str, Any] = {
        "parameters": parameters or [],
        "responses": {
            status: {"content": {"application/json": {"schema": response or {"type": "object"}}}}
        },
    }
    if request is not None:
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": request}},
        }
    return {"paths": {"/thing": {"post": operation}}, "components": {"schemas": {}}}


def _compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return breaking_changes(snapshot(before, ["POST /thing"]), snapshot(after, ["POST /thing"]))


USER = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
}


class TestWhatBreaksAnInstalledApp:
    def test_an_identical_api_breaks_nothing(self) -> None:
        assert _compare(_api(response=USER), _api(response=USER)) == []

    def test_a_removed_operation(self) -> None:
        old = snapshot(_api(), ["POST /thing"])
        assert breaking_changes(old, {}) == ["POST /thing: removed"]

    def test_a_removed_success_response(self) -> None:
        assert any("success response removed" in m for m in _compare(_api(), _api(status="201")))

    def test_a_removed_response_property(self) -> None:
        trimmed = copy.deepcopy(USER)
        del trimmed["properties"]["age"]
        assert any(
            ".age: removed" in m for m in _compare(_api(response=USER), _api(response=trimmed))
        )

    def test_a_response_property_that_is_no_longer_always_there(self) -> None:
        looser = {**USER, "required": ["id"]}
        assert any(
            "no longer always present" in m
            for m in _compare(_api(response=USER), _api(response=looser))
        )

    def test_a_response_type_change(self) -> None:
        changed = copy.deepcopy(USER)
        changed["properties"]["id"] = {"type": "integer"}
        assert any(
            ".id: type changed" in m for m in _compare(_api(response=USER), _api(response=changed))
        )

    def test_a_response_that_can_now_be_null(self) -> None:
        nullable = copy.deepcopy(USER)
        nullable["properties"]["name"] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        assert any(
            ".name: can now be null" in m
            for m in _compare(_api(response=USER), _api(response=nullable))
        )

    def test_a_removed_property_inside_a_list(self) -> None:
        listed = {"type": "array", "items": USER}
        trimmed = copy.deepcopy(listed)
        del trimmed["items"]["properties"]["name"]
        assert any(
            "[].name: removed" in m for m in _compare(_api(response=listed), _api(response=trimmed))
        )

    def test_a_new_required_request_property(self) -> None:
        old = {"type": "object", "required": ["phone"], "properties": {"phone": {"type": "string"}}}
        new = {
            "type": "object",
            "required": ["phone", "consent"],
            "properties": {"phone": {"type": "string"}, "consent": {"type": "string"}},
        }
        assert any(
            ".consent: now required" in m for m in _compare(_api(request=old), _api(request=new))
        )

    def test_a_request_limit_that_got_tighter(self) -> None:
        old = {"type": "object", "properties": {"code": {"type": "string", "maxLength": 8}}}
        new = {"type": "object", "properties": {"code": {"type": "string", "maxLength": 6}}}
        assert any(
            "maxLength is now 6" in m for m in _compare(_api(request=old), _api(request=new))
        )

    def test_a_request_enum_that_lost_a_value(self) -> None:
        old = {"type": "object", "properties": {"kind": {"enum": ["a", "b"]}}}
        new = {"type": "object", "properties": {"kind": {"enum": ["a"]}}}
        assert any(
            "no longer accepts ['b']" in m for m in _compare(_api(request=old), _api(request=new))
        )

    def test_a_new_required_parameter(self) -> None:
        parameter = {
            "in": "query",
            "name": "limit",
            "required": True,
            "schema": {"type": "integer"},
        }
        assert any("now required" in m for m in _compare(_api(), _api(parameters=[parameter])))

    def test_an_optional_parameter_made_required(self) -> None:
        optional = {
            "in": "query",
            "name": "limit",
            "required": False,
            "schema": {"type": "integer"},
        }
        required = {**optional, "required": True}
        assert any(
            "now required" in m
            for m in _compare(_api(parameters=[optional]), _api(parameters=[required]))
        )

    def test_a_request_body_that_became_required(self) -> None:
        body = {"type": "object"}
        old, new = _api(request=body), _api(request=body)
        old["paths"]["/thing"]["post"]["requestBody"]["required"] = False
        assert any("request body: now required" in m for m in _compare(old, new))


class TestWhatDoesNotBreakIt:
    def test_a_new_response_property(self) -> None:
        wider = copy.deepcopy(USER)
        wider["properties"]["email"] = {"type": "string"}
        assert _compare(_api(response=USER), _api(response=wider)) == []

    def test_a_new_optional_request_property_and_parameter(self) -> None:
        old = {"type": "object", "properties": {"phone": {"type": "string"}}}
        new = {
            "type": "object",
            "properties": {"phone": {"type": "string"}, "note": {"type": "string"}},
        }
        parameter = {"in": "query", "name": "x", "required": False, "schema": {"type": "string"}}
        assert _compare(_api(request=old), _api(request=new, parameters=[parameter])) == []

    def test_a_request_that_became_more_lenient(self) -> None:
        old = {"type": "object", "properties": {"code": {"type": "string", "maxLength": 6}}}
        new = {"type": "object", "properties": {"code": {"type": "string", "maxLength": 8}}}
        assert _compare(_api(request=old), _api(request=new)) == []

    def test_a_response_property_that_became_always_present(self) -> None:
        stricter = {**USER, "required": ["id", "name", "age"]}
        assert _compare(_api(response=USER), _api(response=stricter)) == []

    def test_an_error_response_may_change(self) -> None:
        old = _api()
        old["paths"]["/thing"]["post"]["responses"]["422"] = {}
        assert _compare(old, _api()) == []

    def test_a_widened_response_enum_is_reported_not_failed(self) -> None:
        old = {"type": "object", "properties": {"status": {"enum": ["a"]}}}
        new = {"type": "object", "properties": {"status": {"enum": ["a", "b"]}}}
        before = snapshot(_api(response=old), ["POST /thing"])
        after = snapshot(_api(response=new), ["POST /thing"])
        assert breaking_changes(before, after) == []
        assert any("gained ['b']" in m for m in widened_enums(before, after))


class TestSnapshotting:
    def test_refs_are_inlined_so_a_shared_schema_change_is_seen(self) -> None:
        document = {
            "paths": {
                "/thing": {
                    "post": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {"schemas": {"User": USER}},
        }
        shown = snapshot(document, ["POST /thing"])["POST /thing"]
        schema = shown["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema["properties"]["id"] == {"type": "string"}

    def test_a_schema_that_contains_itself_does_not_loop(self) -> None:
        node = {"type": "object", "properties": {"child": {"$ref": "#/components/schemas/Node"}}}
        document = {
            "paths": {
                "/thing": {
                    "post": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Node"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {"schemas": {"Node": node}},
        }
        shown = json.dumps(snapshot(document, ["POST /thing"]))
        assert '"$cycle": "Node"' in shown

    def test_an_operation_that_does_not_exist_is_an_error(self) -> None:
        with pytest.raises(ContractError, match="not an API operation"):
            snapshot(_api(), ["GET /nowhere"])

    def test_the_surface_file_is_read_with_comments_and_blank_lines(self) -> None:
        assert surface_operations("# a\n\nget /health  # probe\nPOST /auth/refresh\n") == [
            "GET /health",
            "POST /auth/refresh",
        ]


class TestTheRealApi:
    """The thing that matters: the API as it is, against the snapshot a store release recorded."""

    def test_the_snapshot_and_the_surface_were_found_and_are_not_empty(self) -> None:
        """Asserts it **found** them before asserting anything about them: a check that compares
        nothing to nothing reports a clean contract for ever."""
        recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        assert len(recorded) >= 6
        assert set(recorded) == set(surface_operations(SURFACE.read_text(encoding="utf-8")))

    def test_the_current_api_breaks_nothing_the_released_app_depends_on(self) -> None:
        from api.main import app

        recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        current = snapshot(app.openapi(), surface_operations(SURFACE.read_text(encoding="utf-8")))
        assert breaking_changes(recorded, current) == [], (
            "This change would break the released mobile app. Keep the old shape and add the new "
            "one beside it, or raise MOBILE_MIN_VERSION_* and run "
            "`scripts/check_api_contract.py --release` (ADR-072)."
        )
        assert set(current) == set(recorded), "run `make snapshot-contract`"

    def test_the_check_can_fail(self) -> None:
        """The same comparison, fed a removed field, must report it."""
        recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        broken = copy.deepcopy(recorded)
        me = broken["GET /auth/me"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert me["properties"], "the fixture must have properties to remove"
        del me["properties"][next(iter(me["properties"]))]
        assert breaking_changes(recorded, broken)
