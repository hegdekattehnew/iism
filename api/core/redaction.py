"""The explicit redaction filter ADR-023 requires.

ADR-023's own words: these fields are "excluded from logs, traces, error
payloads and analytics events by an **explicit redaction filter** -- plaintext
must never reach a log sink". Until this module the filter was a call-site
convention: `mask_phone` and `mask_email`, applied by whoever remembered. A
convention is not a filter. There were four log lines in the whole codebase,
two of them were written carefully, and `mask_email` had no test at all.

This is the filter. It runs on every record from every logger in the process,
structlog-native and stdlib alike, as the last step before rendering -- see
`api/core/logging.py`, where the single shared processor tail is what makes it
unbypassable.

**It masks. It never drops a key and it never raises.**

Dropping the key destroys the diagnostic *and* hides the leak: you delete the
evidence you need to find the offending call site. Raising fires inside
`Handler.emit`, where `logging.raiseExceptions` prints to stderr and swallows
it -- inventing a fourth sink whose only content is "the redactor is unhappy",
visible nowhere the JSON goes. Masking satisfies the ADR literally, keeps the
correlation value `mask_phone` was designed for (`+9198*****999` still joins a
support ticket to a request), and leaves the call site greppable.

Every touched record is marked `redacted=True`, so one CloudWatch Insights
query -- `filter redacted = 1` -- enumerates every leaking call site in the
system. That feedback loop is what dropping and raising both fail to give.

Lives in `core/` rather than inside `logging.py` because `logging.py` would
otherwise import `mask_phone` from `api/adapters/notifications/console.py` --
core importing an adapter, inverting the layering that `adapters/` exists to
establish (ADR-017).
"""

import re
from collections.abc import Callable
from typing import Any

from structlog.typing import EventDict, WrappedLogger

REDACTED = "[redacted]"

# Depth cap on the recursive walk. A log payload nested deeper than this is
# already a bug; the cap is here so a cyclic or pathological structure cannot
# hang the logging path, which must never be the reason a request fails.
_MAX_DEPTH = 6


def mask_phone(phone: str) -> str:
    """+919812349999 -> +9198*****999.

    Enough to correlate a support report, not enough to identify or dial.
    """
    if len(phone) < 8:
        return "*" * len(phone)
    return f"{phone[:5]}{'*' * (len(phone) - 8)}{phone[-3:]}"


def mask_email(address: str) -> str:
    """`priya.sharma@example.com` -> `pr****@example.com`.

    The domain survives because it is what a support conversation needs; the
    local part does not, because that is the half that identifies a person.
    """
    local, _, domain = address.partition("@")
    if not domain:
        return "*" * len(address)
    keep = local[:2] if len(local) > 3 else ""
    return f"{keep}{'*' * max(len(local) - len(keep), 1)}@{domain}"


def mask_aadhaar(value: str) -> str:
    """`1234 5678 9012` -> `XXXX XXXX 9012`, the form UIDAI itself publishes.

    Anything that is not twelve digits is replaced outright rather than
    partially masked: if the shape is unrecognised, so is the risk.
    """
    digits = re.sub(r"\D", "", value)
    return f"XXXX XXXX {digits[-4:]}" if len(digits) == 12 else REDACTED


# A key whose *name* says the value is sensitive has its value replaced
# wholesale, never partially. A partial mask of a six-digit OTP is a two-digit
# OTP -- it narrows a brute force from a million to a hundred.
#
# This is the half that catches values with no recognisable shape: a resume
# blob, an embedding, an assessment result. No pattern can find those.
_DENY_KEYS: frozenset[str] = frozenset(
    {
        # Live credentials.
        "code",
        "otp",
        "otp_code",
        "debug_code",
        "verification_code",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "jwt",
        "jwt_secret_key",
        "authorization",
        "api_key",
        "credentials",
        # Personal identifiers (ADR-023, DPDP).
        "phone",
        "mobile",
        "msisdn",
        "email",
        "email_address",
        "aadhaar",
        "aadhaar_number",
        # Not collected yet -- listed so the filter is already correct on the
        # day the first feature that stores them lands, rather than being
        # retrofitted after it.
        "resume",
        "resume_text",
        "extracted_text",
        "document",
        "assessment",
        "assessment_result",
        "embedding",
        "vector",
    }
)

# Reached where a key denylist structurally cannot, and every one of these has
# a live example in this codebase:
#
#   * `health.py` builds `detail=str(exc)[:200]` from an asyncpg error, which
#     routinely carries the DSN -- password included;
#   * the notification adapters emit one pre-interpolated string with no keys;
#   * `ExtraAdder` lifts arq's `extra={...}` verbatim, with key names nobody
#     on this team chose;
#   * the rendered exception message is text you did not write.
_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str]], ...] = (
    # DSN credentials: postgresql+asyncpg://iism:secret@host/db
    (re.compile(r"(?<=://)[^:@/\s]+:[^@/\s]+(?=@)"), lambda m: "***:***"),
    # A JWT, by its three base64url segments after the `eyJ` header prefix.
    (re.compile(r"\beyJ[\w-]{6,}\.[\w-]{6,}\.[\w-]{6,}"), lambda _m: REDACTED),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}"), lambda m: mask_email(m.group())),
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), lambda m: mask_aadhaar(m.group())),
    # Phones, last, so a digit run inside an Aadhaar or a JWT has already been
    # consumed by the time these run.
    #
    # Two narrow patterns rather than one loose one. The obvious
    # `\+?\d[\d\- ]{8,14}\d` also matches **`2026-09-10`** and rewrites it to
    # `20260910` -- and `timestamp` is on every single log line, so the loose
    # form would corrupt the whole stream and mark every record `redacted`.
    # A test asserts an ISO timestamp survives intact.
    #
    # An international form must carry a literal `+`, which no date has;
    # separators are allowed after it because `+91 98123 49999` is how a person
    # types one.
    (
        re.compile(r"\+\d[\d\- ]{8,14}\d"),
        lambda m: mask_phone(re.sub(r"[ \-]", "", m.group())),
    ),
    # A bare Indian mobile: ten consecutive digits opening 6-9, with no
    # separators, so no date or timestamp fragment can reach it. `phone` is
    # normalised to `+91XXXXXXXXXX` before storage, so this is for free text.
    (re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"), lambda m: mask_phone(m.group())),
)


def _scrub_text(value: str) -> tuple[str, bool]:
    """Apply every pattern. Returns the text and whether anything matched."""
    touched = False
    for pattern, replace in _PATTERNS:
        value, count = pattern.subn(replace, value)
        touched = touched or bool(count)
    return value, touched


class RedactingProcessor:
    """A structlog processor. Stateless; one instance is shared per process."""

    def __call__(self, _logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
        scrubbed, touched = self._walk(dict(event_dict), depth=0)
        if touched:
            scrubbed["redacted"] = True
        return scrubbed

    def _walk(self, node: Any, *, depth: int, key: str | None = None) -> tuple[Any, bool]:
        if depth > _MAX_DEPTH:
            return REDACTED, True

        if key is not None and key.lower() in _DENY_KEYS:
            # Wholesale, whatever the value's type. `phone=None` stays None,
            # because a null is not a leak and replacing it would be a lie.
            return (node, False) if node is None else (REDACTED, True)

        if isinstance(node, str):
            return _scrub_text(node)

        if isinstance(node, dict):
            touched = False
            out: dict[Any, Any] = {}
            for k, v in node.items():
                out[k], hit = self._walk(v, depth=depth + 1, key=k if isinstance(k, str) else None)
                touched = touched or hit
            return out, touched

        if isinstance(node, (list, tuple)):
            touched = False
            items = []
            for v in node:
                scrubbed, hit = self._walk(v, depth=depth + 1)
                items.append(scrubbed)
                touched = touched or hit
            return (type(node)(items) if isinstance(node, tuple) else items), touched

        # int, float, bool, None, UUID, datetime -- nothing a pattern can match
        # and nothing worth stringifying just to look.
        return node, False
