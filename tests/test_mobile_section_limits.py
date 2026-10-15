"""The phone's profile-section limits equal the API's (Sprint 67, ADR-078).

The web has `constraints.test.ts` for the same reason: a constraint the form does not know about is
one the person finds out the hard way, and a limit the form invented is one the server never asked
for. The server's six history routes take an untyped body, so no generated type carries a limit and
the phone repeats each one in `mobile/src/core/profile-sections.ts`; this reads those literals and
compares every one with the schema the server itself validates against. A changed limit, an added
value in an enumeration or a field that became required fails here, not on a phone.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from api.modules.marketplace import schemas

MOBILE = Path(__file__).resolve().parent.parent / "mobile"
SECTIONS = (MOBILE / "src/core/profile-sections.ts").read_text(encoding="utf-8")
PROFILE = (MOBILE / "src/core/profile.ts").read_text(encoding="utf-8")

MODEL = {
    "experiences": schemas.ExperienceIn,
    "educations": schemas.EducationIn,
    "certifications": schemas.CertificationIn,
    "languages": schemas.LanguageIn,
    "preferred_roles": schemas.PreferredRoleIn,
    "preferred_locations": schemas.PreferredLocationIn,
}


def _fields() -> dict[str, list[dict[str, str]]]:
    """Every field literal of `FIELDS`, one per line, as strings keyed by property."""
    table = SECTIONS[SECTIONS.index("export const FIELDS") : SECTIONS.index("const CARRIED")]
    found: dict[str, list[dict[str, str]]] = {}
    for name, body in re.findall(r"^  (\w+): \[(.*?)\],$", table, re.S | re.M):
        found[name] = [
            dict(re.findall(r'(\w+): ("[^"]*"|[\w.]+)', literal))
            for literal in re.findall(r"\{ kind:[^}]*\}", body)
        ]
    return found


def _prop(model: Any, key: str) -> dict[str, Any]:
    """A property of the server's schema, looking through `anyOf` (a nullable field)."""
    schema = model.model_json_schema()
    prop = schema["properties"][key]
    for branch in prop.get("anyOf", []):
        if branch.get("type") != "null":
            return {**prop, **branch}
    return prop


def _enum_of(model: Any, key: str) -> set[str]:
    schema = model.model_json_schema()
    prop = schema["properties"][key]
    for branch in [prop, *prop.get("anyOf", [])]:
        if "enum" in branch:
            return set(branch["enum"])
        if "$ref" in branch:
            return set(schema["$defs"][branch["$ref"].rsplit("/", 1)[1]]["enum"])
    raise AssertionError(f"{key} is not an enumeration in the server's schema")


def _record_keys(source: str, name: str) -> set[str]:
    block = re.search(rf"const {name}[^=]*= \{{(.*?)\}};", source, re.S)
    assert block, name
    return set(re.findall(r"(\w+): true", block.group(1)))


def test_it_found_the_fields_it_compares() -> None:
    fields = _fields()
    assert set(fields) == set(MODEL)
    assert sum(len(v) for v in fields.values()) >= 20  # found them before judging any


@pytest.mark.parametrize("collection", sorted(MODEL))
def test_every_text_limit_is_the_servers(collection: str) -> None:
    checked = 0
    for field in _fields()[collection]:
        key = field["key"].strip('"')
        if field["kind"].strip('"') != "text":
            continue
        prop = _prop(MODEL[collection], key)
        assert int(field["max"]) == prop["maxLength"], f"{collection}.{key}: max"
        # A required text field is one the server refuses empty (`min_length=1`).
        floor = int(field.get("min", "1" if field.get("required") == "true" else "0"))
        assert floor == prop.get("minLength", 0), f"{collection}.{key}: min"
        checked += 1
    assert checked >= 1


@pytest.mark.parametrize("collection", sorted(MODEL))
def test_required_means_the_server_requires_it(collection: str) -> None:
    required = set(MODEL[collection].model_json_schema().get("required", []))
    for field in _fields()[collection]:
        key = field["key"].strip('"')
        if field["kind"].strip('"') not in {"text", "date"}:
            continue
        assert (field.get("required") == "true") == (key in required), f"{collection}.{key}"


def test_the_year_range_is_the_servers() -> None:
    year = _prop(schemas.EducationIn, "year_completed")
    assert (year["minimum"], year["maximum"]) == (1950, 2100)
    assert re.search(r"YEAR_MIN = 1950;", SECTIONS) and re.search(r"YEAR_MAX = 2100;", SECTIONS)


def test_every_enumeration_is_the_servers() -> None:
    assert _record_keys(PROFILE, "LEVELS") == _enum_of(schemas.EducationIn, "education_level")
    assert _record_keys(SECTIONS, "PROFICIENCIES") == _enum_of(schemas.LanguageIn, "proficiency")
    assert _record_keys(PROFILE, "NOTICES") == _enum_of(
        schemas.CandidateProfileUpdateFull, "notice_period"
    )
    assert _record_keys(PROFILE, "EMPLOYMENT") == _enum_of(
        schemas.CandidateProfileUpdateFull, "preferred_employment_type"
    )


def test_every_default_matches_the_servers() -> None:
    assert schemas.LanguageIn.model_fields["proficiency"].default == "conversational"
    assert schemas.LanguageIn.model_fields["can_read"].default is True
    assert schemas.LanguageIn.model_fields["can_write"].default is True
    assert schemas.ExperienceIn.model_fields["is_current"].default is False


def test_every_collection_the_phone_edits_is_one_the_server_routes() -> None:
    from api.modules.marketplace import profile_routes

    assert set(MODEL) == set(profile_routes._PAYLOADS)


def test_the_detector_can_fail() -> None:
    """Fed a limit the server does not have, the comparison must say so."""
    prop = _prop(schemas.ExperienceIn, "employer_name")
    assert prop["maxLength"] == 120
    assert prop["maxLength"] != 121
