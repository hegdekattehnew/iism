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

This dict is the *authored* source of truth, reviewable in a diff; at runtime
`_ROLE_SEARCH_SQL` (`api/modules/skills/service.py`) queries the `role_aliases`
table instead, which `scripts/seed_skills.py` replaces wholesale from this dict
on every run -- the same relationship `SKILLS` in that script has to
`skill_aliases`.

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
    "web developer": "Certificate Course in Web Designing and Multimedia",
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
    "security analyst": "Certificate in Cyber Security",
}

# How short a partial alias may be and still count. "wa" should not claim
# "ward boy"; "ward" may. Bound into `_ROLE_SEARCH_SQL`'s own `aliased` CTE
# (`api/modules/skills/service.py`) as `:min_alias_prefix`.
MIN_ALIAS_PREFIX = 3
