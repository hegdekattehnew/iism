"""What people call their job, mapped to what the national corpus calls it.

Role search matches a candidate's words against `qualification_packs.job_role`,
fuzzily. That finds "delivery boy" -> *E-commerce Delivery Associate*, because
the strings share a word. It cannot find **"ward boy"** -> *General Duty
Assistant*, because they share nothing -- and "ward boy" is what the person this
product is built for actually says. No amount of trigram cleverness bridges two
strings with no letters in common. A list does.

Same move as `DISTRICT_ALIASES` in the geography service ("Bengaluru" is what an
employer writes; the corpus says BENGALURU URBAN) and `scripts/legacy_skill_map.py`:
one auditable file, rather than vocabulary scattered through SQL.

Rules for editing it:

* **Keys** are lower case, trimmed, and what a person would type -- English,
  romanised Hindi or Devanagari. No brand names.
* **Values** are the exact `job_role` of a current qualification with at least
  one standard, matched case-insensitively. A value that names nothing in the
  corpus matches nothing, silently; `unresolved_aliases()` in the service lists
  them, and the verification step of any change to this file runs it.
* **Point at the general qualification**, never a sector-specific or
  disability-track variant, even when the name fits better. A candidate who
  types "waiter" and is offered *Food & Beverage Service Associate (Divyangjan)*
  has been told something untrue about the route open to them.
* **Leave a term out rather than guess.** Deliberately absent: "waiter" (only
  disability-track or manager-level packs exist) and "mason" (no general
  masonry pack). Unmapped terms fall through to fuzzy search and then to the
  free-text standard search.
* **Partial words count** (`alias_scores`), because this is a typeahead. So
  "nurse" has no entry of its own -- a registered nurse is a GNM/B.Sc. route,
  not an NSQF pack -- yet still reaches the nursing-assistant certificate as a
  prefix of "nurse aide". That is the nearest route the corpus offers, and far
  better than what fuzzy search finds for "nurse" alone: *Plant Nursery
  Assistant*. Check the prefixes of any key you add, not only the key.

This is a starter list, authored in Sprint 23 and **awaiting review by someone
who knows the labour market** -- it is a claim about how people describe their
work, and that claim should be checked by a person, not only by a test.
"""

ROLE_ALIASES: dict[str, str] = {
    # ------------------------------------------------------------- healthcare
    "ward boy": "General Duty Assistant",
    "ward girl": "General Duty Assistant",
    "ward attendant": "General Duty Assistant",
    "hospital attendant": "General Duty Assistant",
    "patient attendant": "General Duty Assistant",
    "aaya": "General Duty Assistant",
    "ayah": "General Duty Assistant",
    "वार्ड बॉय": "General Duty Assistant",
    "वार्ड अटेंडेंट": "General Duty Assistant",
    "caretaker": "Geriatric Caregiver (Institutional & Home Care)",
    "caregiver": "Geriatric Caregiver (Institutional & Home Care)",
    "elderly care": "Geriatric Caregiver (Institutional & Home Care)",
    "old age care": "Geriatric Caregiver (Institutional & Home Care)",
    "home nurse": "Home Health Aide",
    "home care attendant": "Home Health Aide",
    "home attendant": "Home Health Aide",
    # Without these, fuzzy search answers "care worker" with *Aquaculture
    # Worker* -- it matches the second word and nothing else.
    "care worker": "Home Health Aide",
    "care assistant": "Home Health Aide",
    "blood collector": "Phlebotomist",
    "sample collector": "Phlebotomist",
    "blood sample collector": "Phlebotomist",
    "compounder": "Certificate in Pharmacy Assistance",
    "pharmacy helper": "Certificate in Pharmacy Assistance",
    "chemist helper": "Certificate in Pharmacy Assistance",
    "nursing assistant": "Certificate in Nursing Assistant",
    "nurse aide": "Certificate in Nursing Assistant",
    "ambulance attendant": "Emergency Medical Technician-Basic",
    "emt": "Emergency Medical Technician-Basic",
    "ot technician": "Certificate in Operation Theatre Technology",
    "ot assistant": "Certificate in Operation Theatre Technology",
    "x-ray technician": "Certificate in X-Ray Technology",
    "xray technician": "Certificate in X-Ray Technology",
    "dialysis technician": "Certificate in Dialysis Technology",
    # ----------------------------------------------------------------- retail
    "salesman": "Retail Sales Associate",
    "saleswoman": "Retail Sales Associate",
    "sales boy": "Retail Sales Associate",
    "sales girl": "Retail Sales Associate",
    "shop assistant": "Retail Sales Associate",
    "counter salesman": "Retail Sales Associate",
    "सेल्समैन": "Retail Sales Associate",
    "cashier": "Retail Cashier",
    "billing clerk": "Retail Cashier",
    "billing staff": "Retail Cashier",
    "कैशियर": "Retail Cashier",
    # -------------------------------------------------------------- logistics
    "delivery boy": "E-commerce Delivery Associate",
    "courier boy": "E-commerce Delivery Associate",
    "delivery executive": "E-commerce Delivery Associate",
    "डिलीवरी बॉय": "E-commerce Delivery Associate",
    "food delivery boy": "Food Delivery Associate",
    "godown helper": "Warehouse Associate",
    "godown boy": "Warehouse Associate",
    "warehouse helper": "Warehouse Associate",
    "forklift driver": "Forklift Operator/Driver",
    # --------------------------------------------------------------- services
    "watchman": "Security Guard",
    "chowkidar": "Security Guard",
    "guard": "Security Guard",
    "चौकीदार": "Security Guard",
    "गार्ड": "Security Guard",
    "peon": "Office Assistant",
    "office boy": "Office Assistant",
    "office helper": "Office Assistant",
    "चपरासी": "Office Assistant",
    "driver": "Light Motor Vehicle Driver",
    "car driver": "Light Motor Vehicle Driver",
    "ड्राइवर": "Light Motor Vehicle Driver",
    "truck driver": "Commercial Vehicle Driver",
    "lorry driver": "Commercial Vehicle Driver",
    "cook": "Assistant Chef",
    "khansama": "Assistant Chef",
    "रसोइया": "Assistant Chef",
    "housekeeping": "Housekeeping Assistant",
    "cleaner": "Housekeeping Assistant",
    "sweeper": "Housekeeping Assistant",
    "room boy": "Housekeeping Assistant",
    "computer operator": "Certificate in Data Entry Operations - Domestic",
    "data entry": "Certificate in Data Entry Operations - Domestic",
    "कंप्यूटर ऑपरेटर": "Certificate in Data Entry Operations - Domestic",
    "telecaller": "Customer Care Executive(Call Center)",
    "call centre": "Customer Care Executive(Call Center)",
    "call center": "Customer Care Executive(Call Center)",
    "bpo": "Customer Care Executive(Call Center)",
    # ---------------------------------------------------------------- trades
    "electrician": "Assistant Electrician",
    "बिजली मिस्त्री": "Assistant Electrician",
    "plumber": "Plumber - General",
    "प्लंबर": "Plumber - General",
    "tailor": "Self Employed Tailor",
    "darzi": "Self Employed Tailor",
    "दर्जी": "Self Employed Tailor",
    "silai": "Sewing Machine Operator",
    "beauty parlour": "Beautician",
    "parlour": "Beautician",
    "badhai": "Carpenter",
    "बढ़ई": "Carpenter",
    "welder": "Welder (Manual Metal Arc Welding and Gas Cutting)",
    "ac mechanic": "Field Technician - Air Conditioner",
    "ac technician": "Field Technician - Air Conditioner",
    "ac repair": "Field Technician - Air Conditioner",
    "mobile repair": "Mobile Phone Hardware Repair Technician",
    "mobile mechanic": "Mobile Phone Hardware Repair Technician",
}

# How short a partial alias may be and still count. "wa" should not claim
# "ward boy"; "ward" may.
MIN_ALIAS_PREFIX = 3


def alias_scores(query: str) -> dict[str, tuple[float, str]]:
    """Roles the query reaches through an alias: `{role_key: (score, alias)}`.

    Scored on the same tiers as the literal search -- a whole alias as an exact
    match, a partial one as a prefix -- so an alias never outranks a role the
    candidate actually named, and a half-typed word still finds its target.
    """
    norm = " ".join(query.lower().split())
    found: dict[str, tuple[float, str]] = {}
    for alias, role in ROLE_ALIASES.items():
        if alias == norm:
            score = 4.0
        elif len(norm) >= MIN_ALIAS_PREFIX and alias.startswith(norm):
            score = 3.0
        else:
            continue
        key = role.lower().strip()
        if key not in found or score > found[key][0]:
            found[key] = (score, alias)
    return found
