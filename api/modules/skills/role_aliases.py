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
* **Leave a term out rather than guess.** Deliberately absent (Sprint 71): words that name
  no single role ("helper", "mechanic", "machine operator", "nurse", "loader", "packer") and
  jobs the national list has no role for ("housemaid", "maid", "accountant", "turner",
  "lathe operator"). Earlier versions of this note said "waiter" and "mason" had no general
  pack; both do (*Food and Beverage Service Assistant*, *Brick Mason*), which was found by
  reading the corpus for the Sprint 71 title set, and both are keys now. Unmapped terms fall
  through to fuzzy search and then to the free-text standard search.
* **Partial words count** (`MIN_ALIAS_PREFIX`), because this is a typeahead. So
  "nurse" has no entry of its own -- a registered nurse is a GNM/B.Sc. route,
  not an NSQF pack -- yet still reaches the nursing-assistant certificate as a
  prefix of "nurse aide". That is the nearest route the corpus offers, and far
  better than what fuzzy search finds for "nurse" alone: *Plant Nursery
  Assistant*. Check the prefixes of any key you add, not only the key.

This is a starter list, authored in Sprint 23 and extended in Sprint 71, and **awaiting
review by someone who knows the labour market** -- it is a claim about how people
describe their work, and that claim should be checked by a person, not only by a test.
`docs/IISM-Role-Aliases-for-Review.xlsx` (built by `scripts/build_role_alias_review.py`) is
that person's copy, and `make evaluate-roles` measures it against titles written before it.
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
    # Salesman, saleswoman, sales boy, shop assistant and counter salesman had no entry from
    # Sprint 43 (ADR-050): they all pointed at "Retail Sales Associate", which exists only as a
    # disability-track pack (PWD/RAS/Q0104). Sprint 71 found a general pack that fits the same
    # work, "Retail Sales Assistant", and they are keys again (see the Sprint 71 batch below);
    # "sales girl" and सेल्समैन are held out of the keys on purpose, to measure whether the
    # others generalise. A labour-market reviewer should still confirm the target.
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
    # =====================================================================================
    # Sprint 71 batch (BL-12.12): coverage. Drafted by engineering from public knowledge of
    # how entry-level work is named in India, **not reviewed by anyone who works in these
    # labour markets**. Every row is `source='seed'`, so an admin-tier operator can retire or
    # change it on /admin, and `docs/IISM-Role-Aliases-for-Review.xlsx` lists them for a
    # reviewer. It is scored by `make evaluate-roles` against `tests/fixtures/role_titles.json`
    # (written first; its hold-out titles are deliberately *not* keys here).
    # Left out on purpose, because there is no honest single target or a wrong one would be
    # worse than none: helper, mechanic, machine operator, accountant, turner, lathe operator,
    # housemaid, maid, nurse (a registered nurse is not an NSQF pack), anganwadi worker,
    # bouncer, loader, packer.
    # =====================================================================================
    # ------------------------------------------------------------ healthcare (batch)
    "hospital helper": "General Duty Assistant",
    "patient care assistant": "General Duty Assistant",
    "patient care": "General Duty Assistant",
    "nursing orderly": "General Duty Assistant",
    "gda": "General Duty Assistant",
    "आया": "General Duty Assistant",
    "वार्ड गर्ल": "General Duty Assistant",
    "अस्पताल सहायक": "General Duty Assistant",
    "nanny": "Baby Caregiver (Nanny)",
    "child care": "Baby Caregiver (Nanny)",
    "child minder": "Baby Caregiver (Nanny)",
    "creche attendant": "Baby Caregiver (Nanny)",
    "baby caretaker": "Baby Caregiver (Nanny)",
    "nurse assistant": "Certificate in Nursing Assistant",
    "nursing attendant": "Certificate in Nursing Assistant",
    "नर्सिंग असिस्टेंट": "Certificate in Nursing Assistant",
    "pharmacy assistant": "Certificate in Pharmacy Assistance",
    "medical store assistant": "Certificate in Pharmacy Assistance",
    "medical shop helper": "Certificate in Pharmacy Assistance",
    "कंपाउंडर": "Certificate in Pharmacy Assistance",
    "dialysis assistant": "Certificate in Dialysis Technology",
    "physiotherapy assistant": "Certificate in Physiotherapy Assistance",
    "physio assistant": "Certificate in Physiotherapy Assistance",
    "physiotherapy helper": "Certificate in Physiotherapy Assistance",
    "dentist assistant": "Certificate in Dental Assisting",
    "dental helper": "Certificate in Dental Assisting",
    "emergency medical technician": "Emergency Medical Technician-Basic",
    "asha worker": "Certificate in Community Health (CCH)",
    "community health worker": "Certificate in Community Health (CCH)",
    "आशा कार्यकर्ता": "Certificate in Community Health (CCH)",
    "elder care": "Geriatric Caregiver (Institutional & Home Care)",
    "senior citizen care": "Geriatric Caregiver (Institutional & Home Care)",
    # ------------------------------------------------------------ security (batch)
    "सिक्योरिटी गार्ड": "Security Guard",
    "सुरक्षा गार्ड": "Security Guard",
    "सुरक्षाकर्मी": "Security Guard",
    "darban": "Security Guard",
    "gate keeper": "Security Guard",
    "gatekeeper": "Security Guard",
    "night watchman": "Security Guard",
    "night guard": "Security Guard",
    "gunman": "Armed Security Guard",
    "cctv installer": "CCTV Installation Technician",
    "cctv technician": "CCTV Installation Technician",
    "cctv camera installer": "CCTV Installation Technician",
    # ------------------------------------------------- driving and machines (batch)
    "private driver": "Light Motor Vehicle Driver",
    "personal driver": "Light Motor Vehicle Driver",
    "कार ड्राइवर": "Light Motor Vehicle Driver",
    "cab driver": "Taxi Driver",
    "ट्रक ड्राइवर": "Commercial Vehicle Driver",
    "heavy vehicle driver": "Commercial Vehicle Driver",
    "hmv driver": "Commercial Vehicle Driver",
    "tanker driver": "Tank Lorry Driver-Petroleum Products",
    "e rickshaw": "E-Rickshaw Driver",
    "e-rickshaw": "E-Rickshaw Driver",
    "battery rickshaw": "E-Rickshaw Driver",
    "auto driver": "Auto Rickshaw Driver",
    "jcb operator": "Backhoe Loader Operator",
    "jcb driver": "Backhoe Loader Operator",
    "backhoe operator": "Backhoe Loader Operator",
    "excavator driver": "Excavator Operator",
    "forklift operator": "Forklift Operator/Driver",
    # ------------------------------------------------------------------ trades (batch)
    "wireman": "Assistant House Wireman and Motor Winder",
    "house wireman": "Assistant House Wireman and Motor Winder",
    "bijli mistri": "Bijli Mistry",
    "bijli mistry": "Bijli Mistry",
    "इलेक्ट्रीशियन": "Assistant Electrician",
    "woodworker": "Carpenter",
    "wood worker": "Carpenter",
    "mason": "Brick Mason",
    "rajmistri": "Brick Mason",
    "raj mistri": "Brick Mason",
    "राजमिस्त्री": "Brick Mason",
    "bricklayer": "Brick Mason",
    "brick layer": "Brick Mason",
    "plasterer": "Plaster Mason - Basic",
    "mason helper": "Assistant Mason",
    "painter": "Construction Painter & Decorator",
    "wall painter": "Construction Painter & Decorator",
    "paint mistri": "Construction Painter & Decorator",
    "पेंटर": "Construction Painter & Decorator",
    "वेल्डर": "Welder (Manual Metal Arc Welding and Gas Cutting)",
    "tig welder": "Welder - (GTAW)",
    # ------------------------------------------------------ repair and install (batch)
    "refrigerator mechanic": "Certificate in Refrigeration & Air Conditioning Systems",
    "refrigerator repair": "Certificate in Refrigeration & Air Conditioning Systems",
    "ac fitter": "Field Technician - Air Conditioner",
    "ac installer": "Field Technician - Air Conditioner",
    "air conditioner technician": "Field Technician - Air Conditioner",
    "washing machine mechanic": "Service Technician - Home Appliances",
    "washing machine repair": "Service Technician - Home Appliances",
    "home appliance repair": "Service Technician - Home Appliances",
    "home appliances technician": "Service Technician - Home Appliances",
    "phone repair": "Mobile Phone Hardware Repair Technician",
    "mobile phone repair": "Mobile Phone Hardware Repair Technician",
    "car mechanic": "Four Wheeler Service Technician",
    "auto mechanic": "Four Wheeler Service Technician",
    "motor mechanic": "Four Wheeler Service Technician",
    "garage mechanic": "Four Wheeler Service Technician",
    "bike mechanic": "Two Wheeler Service Technician",
    "scooter mechanic": "Two Wheeler Service Technician",
    "motorcycle mechanic": "Two Wheeler Service Technician",
    "bike repair": "Two Wheeler Service Technician",
    "solar installer": "Rooftop Solar PV (Installation & Maintenance)",
    "solar technician": "Rooftop Solar PV (Installation & Maintenance)",
    "solar panel installer": "Rooftop Solar PV (Installation & Maintenance)",
    "suryamitra": "Solar PV Installer (Suryamitra)",
    "computer repair": "Certificate in Computer Hardware & Networking",
    "laptop repair": "Certificate in Computer Hardware & Networking",
    "puncture repair": "Tyre Fitter-Servicing and Maintenance",
    "laptop technician": "Certificate in Computer Hardware & Networking",
    "pc technician": "Certificate in Computer Hardware & Networking",
    "computer mechanic": "Certificate in Computer Hardware & Networking",
    "lan technician": "Broadband Network Technician",
    "internet technician": "Broadband Network Technician",
    "set top box installer": "DTH Set Top Box Installation & Service Technician",
    # ---------------------------------------------------- retail and logistics (batch)
    "salesman": "Retail Sales Assistant",
    "saleswoman": "Retail Sales Assistant",
    "sales boy": "Retail Sales Assistant",
    "shop assistant": "Retail Sales Assistant",
    "shop helper": "Retail Sales Assistant",
    "shop boy": "Retail Sales Assistant",
    "counter salesman": "Retail Sales Assistant",
    "counter sales": "Retail Sales Assistant",
    "retail assistant": "Retail Sales Assistant",
    "शॉप असिस्टेंट": "Retail Sales Assistant",
    "store keeper": "Warehouse Associate",
    "storekeeper": "Warehouse Associate",
    "store boy": "Warehouse Associate",
    "stock keeper": "Warehouse Associate",
    "warehouse worker": "Warehouse Associate",
    "warehouse staff": "Warehouse Associate",
    "warehouse boy": "Warehouse Associate",
    "godown keeper": "Warehouse Associate",
    "delivery person": "E-commerce Delivery Associate",
    "delivery partner": "E-commerce Delivery Associate",
    "delivery agent": "E-commerce Delivery Associate",
    "courier": "Courier Associate - Operations",
    "parcel delivery": "Courier Associate - Operations",
    # ------------------------------------------------------ hospitality, office (batch)
    "कुक": "Cook (Multi-Cuisine)",
    "cook helper": "Kitchen Helper",
    "kitchen assistant": "Kitchen Steward",
    "dishwasher": "Kitchen Steward",
    "dish washer": "Kitchen Steward",
    "utensil washer": "Kitchen Steward",
    "waiter": "Food and Beverage Service Assistant",
    "waitress": "Food and Beverage Service Assistant",
    "restaurant waiter": "Food and Beverage Service Assistant",
    "वेटर": "Food and Beverage Service Assistant",
    "housekeeping boy": "Housekeeping Assistant",
    "house keeping": "Housekeeping Assistant",
    "safai karmachari": "Housekeeping Assistant",
    "सफाई कर्मचारी": "Housekeeping Assistant",
    "room attendant": "Housekeeping Assistant",
    "hotel housekeeping": "Housekeeping Assistant",
    "front office": "Front Office Assistant",
    "front desk": "Front Office Assistant",
    "hotel receptionist": "Front Office Assistant",
    "रिसेप्शनिस्ट": "Front Office Assistant",
    "डेटा एंट्री": "Certificate in Data Entry Operations - Domestic",
    "tally": "Certificate in Tally Prime",
    "tally operator": "Certificate in Tally Prime",
    "tally clerk": "Accounts Assistant",
    "accounts clerk": "Accounts Assistant",
    "call centre agent": "Call Center Executive",
    "call center agent": "Call Center Executive",
    "call centre executive": "Call Center Executive",
    "customer care": "Customer Care Executive-Domestic- Non- Voice",
    "customer service executive": "Customer Care Executive-Domestic- Non- Voice",
    "customer support": "Customer Care Executive-Domestic- Non- Voice",
    "कस्टमर केयर": "Customer Care Executive-Domestic- Non- Voice",
    # ------------------------------------------------- textiles, beauty, crafts (batch)
    "tailor master": "Self Employed Tailor",
    "ladies tailor": "Self Employed Tailor",
    "सिलाई": "Sewing Machine Operator",
    "garment stitcher": "Sewing Machine Operator",
    "stitcher": "Sewing Machine Operator",
    "ब्यूटीशियन": "Beautician",
    "parlour girl": "Beautician",
    "नाई": "Assistant Barber-Salon Services",
    "hair cutter": "Assistant Barber-Salon Services",
    "makeup artist": "Make-Up Artist",
    "make up artist": "Make-Up Artist",
    "bridal makeup": "Bridal, Fashion and Portfolio Makeup Artist",
    "manicurist": "Nail Technician",
    "pedicurist": "Nail Technician",
    # ---------------------------------------------- agriculture, education, other (batch)
    "माली": "Assistant Gardener",
    "poultry worker": "Poultry Farm Worker",
    "poultry farm helper": "Poultry Farm Worker",
    "fish farm worker": "Aquaculture Worker",
    "pre school teacher": "Certificate in Early Childhood Care and Education",
    "preschool teacher": "Certificate in Early Childhood Care and Education",
    "nursery teacher": "Certificate in Early Childhood Care and Education",
    "play school teacher": "Certificate in Early Childhood Care and Education",
    "kindergarten teacher": "Certificate in Early Childhood Care and Education",
    "yoga teacher": "Certificate in Yoga Teacher Training",
}

# How short a partial alias may be and still count. "wa" should not claim
# "ward boy"; "ward" may. Bound into `_ROLE_SEARCH_SQL`'s own `aliased` CTE
# (`api/modules/skills/service.py`) as `:min_alias_prefix`.
MIN_ALIAS_PREFIX = 3
