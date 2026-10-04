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

**This dict only seeds** (Sprint 47, ADR-054). At runtime `_ROLE_SEARCH_SQL`
(`api/modules/skills/service.py`) queries the `role_aliases` table, which is the source
of truth: `scripts/seed_skills.py` inserts what is missing, keeps its own
(`source='seed'`) rows current and never touches a row an operator owns. An operator adds
and retires aliases on `/admin` (`skills/alias_admin.py`), with the checks below applied
by the screen as well as by `make check-role-aliases`. The dict is still the right home for
the starter list, reviewable in a diff; it is no longer the only way in, and a key removed
from it is removed from the table only if no operator has taken ownership of that row.

Rules for editing it:

* **Keys** are lower case, trimmed, and what a person would type -- English,
  romanised Hindi or Devanagari. No brand names.
* **Values** are the exact `job_role` of a current qualification with at least
  one standard, matched case-insensitively. A value that names nothing in the
  corpus matches nothing, silently; `unresolved_aliases()` in the service lists
  them, and the verification step of any change to this file runs it.
* **Point at the general qualification**, never a sector-specific or
  disability-track variant, even when the name fits better. Every
  disability-track pack carries a `PWD/` code, whether or not its name says
  "Divyangjan", and `alias_problems()` fails on an alias whose representative
  pack has one (Sprint 43, ADR-050; fourteen keys had been pointing at three). A candidate who
  types "waiter" and is offered *Food & Beverage Service Associate (Divyangjan)*
  has been told something untrue about the route open to them.
* **Leave a term out rather than guess.** Deliberately absent: "waiter" (only
  disability-track or manager-level packs exist) and "mason" (no general
  masonry pack). Unmapped terms fall through to fuzzy search and then to the
  free-text standard search.
* **Partial words count** (`MIN_ALIAS_PREFIX`), because this is a typeahead. So
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
    # No entry for salesman, saleswoman, sales boy, sales girl, shop assistant,
    # counter salesman or सेल्समैन (Sprint 43, ADR-050). They all pointed at
    # "Retail Sales Associate", which exists only as a disability-track pack
    # (PWD/RAS/Q0104) -- the very thing the rule above forbids, and invisible to
    # the checker until it learned to look at the code. The nearest general role,
    # "Retail Sales Executive", is a different qualification at NSQF 4, not the
    # same entry-level work at 3. A labour-market reviewer should decide whether it
    # stands in; until then these fall through to literal search.
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
    # "Assistant Chef" is the disability-track issue of THC/Q2702 (PWD/THC/Q2702);
    # the same qualification is issued generally as "Kitchen Trainee". "cook" has no
    # entry: the corpus has a role literally named "Cook (Multi-Cuisine)", which
    # search already reaches, and an alias would put a trainee qualification above it.
    "khansama": "Kitchen Trainee",
    "रसोइया": "Kitchen Trainee",
    "housekeeping": "Housekeeping Assistant",
    "cleaner": "Housekeeping Assistant",
    "sweeper": "Housekeeping Assistant",
    "room boy": "Housekeeping Assistant",
    "computer operator": "Certificate in Data Entry Operations - Domestic",
    "data entry": "Certificate in Data Entry Operations - Domestic",
    "कंप्यूटर ऑपरेटर": "Certificate in Data Entry Operations - Domestic",
    # "Customer Care Executive(Call Center)" is the disability-track issue of
    # TEL/Q0100 (PWD/TEL/Q0100); the general issue is "Call Center Executive".
    "telecaller": "Call Center Executive",
    "call centre": "Call Center Executive",
    "call center": "Call Center Executive",
    "bpo": "Call Center Executive",
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
    # ------------------------------------------------- information technology
    # Without these, "tech" reaches nothing here -- it is a literal substring
    # of "Technician", so the plain contains-tier surfaces AC/dialysis/solar
    # technicians from unrelated sectors before it ever reaches the real
    # IT-ITeS corpus, none of whose job roles happen to contain that word.
    "software developer": "Certificate Course in Coding Skills",
    # Genuinely a different, more senior target than "developer"/"coder" --
    # "Software Development" (NSQF 6: architecture & design patterns, DSA,
    # testing & QA, DevOps) over the NSQF-5 entry-level coding certificate,
    # checked against the live corpus rather than assumed the two words are
    # interchangeable.
    "software engineer": "Software Development",
    "programmer": "Certificate Course in Coding Skills",
    "coder": "Certificate Course in Coding Skills",
    "coding": "Certificate Course in Coding Skills",
    # No entry for "web developer": it is the exact title of SSC/Q0503, so the
    # literal match already reaches it, and an alias to the multimedia certificate
    # sent somebody who typed the title in full elsewhere (ADR-050).
    "website developer": "Certificate Course in Web Designing and Multimedia",
    "web designer": "Certificate Course in Web Designing and Multimedia",
    "web design": "Certificate Course in Web Designing and Multimedia",
    "app developer": "Application Development - Android",
    "android developer": "Application Development - Android",
    "mobile app developer": "Application Development - Android",
    "it support": "Certificate in Computer Hardware & Networking",
    "computer technician": "Certificate in Computer Hardware & Networking",
    "hardware technician": "Certificate in Computer Hardware & Networking",
    "computer hardware": "Certificate in Computer Hardware & Networking",
    "networking": "Certificate in Computer Hardware & Networking",
    "basic computer": "Certificate in Basic Computer Concepts",
    "computer course": "Certificate in Basic Computer Concepts",
    "data analyst": "Certificate in Data Analytics",
    "machine learning": "AI - Machine learning Developer",
    "ml engineer": "AI - Machine learning Developer",
    "ai developer": "AI - Machine learning Developer",
    "ethical hacking": "Certificate in Cyber Security & Ethical Hacking",
    # No entry for "security analyst" either: SSC/Q0901 is titled exactly that.
}

# How short a partial alias may be and still count. "wa" should not claim
# "ward boy"; "ward" may. Bound into `_ROLE_SEARCH_SQL`'s own `aliased` CTE
# (`api/modules/skills/service.py`) as `:min_alias_prefix`.
MIN_ALIAS_PREFIX = 3
