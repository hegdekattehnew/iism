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


# Generic, sector-agnostic word-level abbreviations -- never role-specific
# content, which is `api/modules/skills/role_aliases.py`'s job. "tech" was
# deliberately left out of that file's `ROLE_ALIASES`: it is a literal
# substring of "Technician", so a role-specific alias pointing it at one IT
# qualification would still leave the marketplace's own `/jobs`/`/search`
# full-text path unable to find "Information Technology Sector"/"IT-ITeS"
# listings, none of whose titles or descriptions happen to contain that word.
# This list stays small and sector-agnostic on purpose: unlike role aliases,
# it never needs per-sector curation, so it can genuinely reach every sector
# rather than the ones someone has thought to hand-author.
WORD_SYNONYMS: dict[str, list[str]] = {
    "tech": ["technology"],
    "dev": ["developer", "development"],
    "eng": ["engineer", "engineering"],
    "it": ["information technology"],
    "mfg": ["manufacturing"],
    "mgmt": ["management"],
    "admin": ["administration"],
    "bio": ["biotechnology"],
    "agri": ["agriculture"],
    "auto": ["automotive"],
    "telecom": ["telecommunications"],
    "logistics": ["supply chain"],
    "hr": ["human resources"],
    "healthcare": ["health care"],
}


def expand_query_terms(query: str) -> list[str]:
    """The query, plus one variant per whole-word synonym it contains.

    Whole-word only, so `WORD_SYNONYMS["it"]` cannot fire inside "credit" or
    "unit" -- a search is words, not a substring `LIKE`. Returns the original
    query first, then each expansion; a caller that only wants the count
    keeps its own de-duplication, this makes no claim about ranking.
    """
    words = query.lower().split()
    seen = {query}
    variants = [query]
    for index, word in enumerate(words):
        for synonym in WORD_SYNONYMS.get(word, []):
            expanded = " ".join([*words[:index], synonym, *words[index + 1 :]])
            if expanded not in seen:
                seen.add(expanded)
                variants.append(expanded)
    return variants
