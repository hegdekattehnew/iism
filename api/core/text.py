"""Text helpers shared across modules.

`slugify` lived in `api/adapters/nsqf/normalise.py` while the NSQF importer was
its only caller. Identity now needs it too, to name an organisation's tenant,
and a module reaching into an adapter for a pure string function is the wrong
direction of dependency (ADR-014, ADR-017). The importer imports it from here
instead; its behaviour is unchanged, and the NSQF slug tests still cover it.
"""

import re
import unicodedata

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """ASCII, lowercase, hyphen-separated. Devanagari transliterates to nothing.

    That last part is deliberate rather than unfortunate: a slug is a URL, and
    a Hindi name yielding an empty slug is a case the caller must handle with a
    fallback it chooses, not one this function should guess at.
    """
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return _SLUG_STRIP.sub("-", ascii_text.lower()).strip("-")
