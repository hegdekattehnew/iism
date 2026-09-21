"""Normalisation for the raw NSQF corpus.

Every function here exists because the real data violates an assumption the
schema would otherwise make. Each is small and separately tested, because a
silent coercion in an import of 30,000 records is invisible until matching
returns the wrong answer.
"""

import re
from decimal import Decimal, InvalidOperation

# Re-exported: `slugify` moved to `api/core/text.py` when identity needed it to
# name an organisation's tenant, and a module importing from an adapter for a
# pure string function is the wrong direction. Every existing caller and import
# of `normalise.slugify` keeps working.
from api.core.text import slugify

# "0126:00" -> 126 hours 0 minutes. Leading zeros are meaningful padding only.
_HHMM = re.compile(r"^\s*(\d{1,5}):([0-5]?\d)\s*$")

MAX_SLUG_TITLE = 80


class NormalisationError(ValueError):
    """A source value could not be interpreted. Never swallowed: the importer
    reports the record and its reason rather than skipping it silently."""


def clean_text(value: object) -> str | None:
    """Trim and collapse whitespace. 1,050 NOS titles have trailing spaces,
    which would otherwise leak into slugs and search vectors."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def parse_level(value: object) -> Decimal | None:
    """NSQF level as a Decimal.

    The corpus contains half-levels (2.5, 3.5, 4.5, 5.5) and duplicate forms of
    the same level ("4" and "4.0"), so this normalises to a single Decimal and
    the column is Numeric(3,1) rather than Integer.
    """
    if value is None or value == "":
        return None
    try:
        level = Decimal(str(value).strip())
    except (InvalidOperation, ArithmeticError) as exc:
        raise NormalisationError(f"unreadable NSQF level: {value!r}") from exc
    if not (Decimal(1) <= level <= Decimal(10)):
        raise NormalisationError(f"NSQF level out of range 1-10: {value!r}")
    return level.quantize(Decimal("0.1"))


def parse_hhmm_to_minutes(value: object) -> int | None:
    """'570:00' -> 34200 minutes.

    Minutes, not hours: the source expresses durations as HH:MM and integer
    minutes is the only lossless representation. '00:00' means zero, which is
    a real answer and must not become None.
    """
    if value is None or value == "":
        return None
    match = _HHMM.match(str(value))
    if match is None:
        raise NormalisationError(f"unreadable HH:MM duration: {value!r}")
    hours, minutes = int(match.group(1)), int(match.group(2))
    return hours * 60 + minutes


def parse_credits(value: object) -> Decimal | None:
    """Credits are frequently the literal string 'TBD'.

    Returns None for anything non-numeric rather than coercing to zero — zero
    credits and unknown credits are different facts.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"TBD", "NA", "N/A", "-"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ArithmeticError):
        return None


def parse_decimal(value: object) -> Decimal | None:
    """A plain numeric field, tolerant of what the feed puts in one.

    Returns None rather than zero for an absent value: a weightage of nothing
    and a weightage of zero would score differently.
    """
    if value is None:
        return None
    text = str(value).strip().rstrip("%").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ArithmeticError):
        return None


# An NCO-2015 occupation code: four digits, a dot, then three or four more.
_NCO_CODE = re.compile(r"\b(\d{4}\.\d{3,4})\b")


def parse_nco_codes(value: object) -> list[str]:
    """Pull every NCO occupation code out of one `alignedTo` string.

    The field is a mess and must be treated as one. Of 3,214 values, 1,914 are
    well formed, 507 carry a code in a variant format -- unicode hyphens,
    'NCO 2015- ' spacing, or several codes comma-separated -- and 793 are free
    text such as '(CNC Operator)', which is a job role and not a code at all.

    Returns the codes found, normalised and de-duplicated in order. An empty list
    means there was nothing usable, which the importer counts and reports rather
    than storing a job role as though it were a classification.
    """
    if value is None:
        return []
    text = str(value)
    # U+2010 HYPHEN and friends appear in place of ASCII '-'.
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014"):
        text = text.replace(dash, "-")
    text = text.replace("\u00a0", " ")
    seen: list[str] = []
    for match in _NCO_CODE.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def make_skill_slug(title: str, code: str) -> str:
    """`prepare-documentation-for-export-lsc-n2131`.

    Title alone is neither unique nor stable across versions; code alone is
    stable but opaque and costs the organic search ADR-029 depends on. The
    combination is unique because the code is.
    """
    title_part = slugify(title or "")[:MAX_SLUG_TITLE].strip("-")
    code_part = slugify(code)
    if not code_part:
        raise NormalisationError(f"cannot build a slug from code {code!r}")
    return f"{title_part}-{code_part}" if title_part else code_part


def make_qp_slug(name: str, code: str, version: str) -> str:
    """`general-duty-assistant-hss-q5101-1-0`.

    The identifying part is appended *after* truncation, never before it.
    Truncating `name-code` as one string silently removes the code, and several
    NSQF qualification names run past 120 characters with a common prefix --
    which collides on the unique index.
    """
    name_part = slugify(name or "")[:MAX_SLUG_TITLE].strip("-")
    tail = f"{slugify(code)}-{slugify(version)}".strip("-")
    if not tail:
        raise NormalisationError(f"cannot build a slug from code {code!r}")
    return f"{name_part}-{tail}" if name_part else tail


def version_sort_key(version: object) -> tuple[int, ...]:
    """Order versions numerically: '10.0' is newer than '9.0', which a string
    comparison gets backwards."""
    parts = re.findall(r"\d+", str(version or "0"))
    return tuple(int(p) for p in parts) or (0,)
