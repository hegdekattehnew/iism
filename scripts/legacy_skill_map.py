"""The 52 hand-curated Sprint 2 skills, mapped to real National Occupational Standards.

Hand-authored, because this cannot be automated. Full-text search gets
`Blood sample collection` -> `HSS/N0513` exactly right and `Customer service` ->
a hair-and-beauty NOS quite wrong, and there is no signal in the data that tells
the two cases apart.

**The map is many-to-one, and that is the finding, not a compromise.** The
curated vocabulary was authored at capability level -- "hand hygiene", "bed
making", "catheter care" -- while an NOS is a job task: "Follow infection
control policies & procedures", "Provide ancillary services for supporting
patient care". Several curated skills therefore land on one standard. A job that
listed six curated skills may end up requiring three standards, and that is a
more honest statement of what it needs, not a loss of detail.

Where the choice was genuinely uncertain it is marked. Nothing here is asserted
more confidently than the evidence supports.
"""

# curated slug -> NOS code. Every one of the 52 is present; a missing entry is a
# hard failure in the seed, because a job silently losing a skill is invisible
# until matching returns nothing for it.
LEGACY_SKILL_MAP: dict[str, str] = {
    # --- patient handling and mobility ---------------------------------
    "ambulation-assistance": "HSS/N6012",  # Contribute to moving and positioning individuals
    "patient-mobility-support": "HSS/N6012",
    "patient-positioning": "HSS/N6012",
    "patient-transfer-techniques": "HSS/N5134",  # Transferring patient and their samples
    "bed-making": "THC/N0214",  # Replace linen and make beds
    "patient-bathing-assistance": "HSS/N5133",  # Assist patient in bathing, dressing, grooming
    "elderly-care": "HSS/N6006",  # Provide geriatric care to meet diverse needs
    "nutrition-and-feeding-support": "HSS/N6003",  # Support geriatrics in daily living activities
    # --- clinical observation and procedures ----------------------------
    # NSQF has no standard for a single vital sign; one unit covers the set.
    "vital-signs-measurement": "HSS/N6002",  # Assist in routine checkup and vital parameters
    "blood-pressure-measurement": "HSS/N6002",
    "temperature-monitoring": "HSS/N6002",
    "blood-sample-collection": "HSS/N0513",  # Sample collection: blood, sputum, urine, stool
    "urine-sample-analysis": "HSS/N0511",  # Procedural activities of sample collection
    "specimen-labelling": "HSS/N0512",  # Post-procedural activities of sample collection
    "wound-dressing": "HSS/N3015",  # Assist in management of wound and tissue
    # Uncertain: no NOS covers cannulation or injection for this role level.
    # Both are performed inside "prepare procedure area and patient", which is
    # the closest true statement rather than the closest words.
    "injection-administration": "HSS/N5139",
    "iv-cannulation": "HSS/N5139",
    # Uncertain: these are ancillary tasks a GDA performs under supervision, and
    # the NOS is written at that level rather than per task.
    "catheter-care": "HSS/N5127",  # Provide ancillary services for supporting patient care
    "medication-administration": "HSS/N5127",
    "oxygen-therapy-support": "HSS/N5127",
    # Uncertain: the only ECG standard outside a single-qualification course
    # module does not exist, so a course module it is.
    "ecg-recording": "MSU/HSS/CRS0056-004",  # Lead Placement & ECG Recording Techniques
    # --- emergency ------------------------------------------------------
    "cpr": "HYC/N3614",  # Perform CPR and first aid for trauma and medical emergency
    "basic-life-support": "HYC/N3614",
    "first-aid": "HSS/N3016",  # Provide first aid as per the emergency
    "emergency-response-coordination": "SSD/VSQ/N0104",  # Plan, organize and emergency protocols
    # --- infection control and equipment --------------------------------
    "infection-control": "HSS/N9618",  # Follow infection control policies & procedures
    "hand-hygiene": "HSS/N9618",
    "biomedical-waste-handling": "HSS/N9620",  # Comply with infection control and BMW disposal
    "sterilisation-of-instruments": "HSS/N5647",  # Routine care of sterilizing apparatus
    "medical-equipment-handling": "HSS/N5647",
    # --- laboratory -----------------------------------------------------
    "laboratory-safety": "LFS/N0533",  # Store & handle laboratory chemicals, maintain records
    "microscope-operation": "LFS/N1306",  # Perform laboratory investigations and analysis
    # --- records and administration -------------------------------------
    "medical-record-keeping": "HSS/N5508",  # Maintain medical records for compliance
    "documentation-and-reporting": "HYC/N9605",  # Report, record and prepare documentations
    "hospital-front-desk-operations": "THC/N0129",  # Assist in performing front office activities
    "patient-counselling": "MEP/N0721",  # Guidance and Counseling
    # --- retail ---------------------------------------------------------
    # One standard covers taking payment however it is tendered; the curated
    # vocabulary split it three ways.
    "cash-handling": "RAS/N0115",  # To process payments
    "pos-operation": "RAS/N0115",
    "digital-payments-handling": "RAS/N0115",
    "billing-and-invoicing": "RAS/N0115",
    "inventory-management": "RAS/N0101",  # Receive and store goods in retail operations
    "stock-replenishment": "RAS/N0104",  # Monitor and replenish stock on display
    "visual-merchandising": "RAS/N0107",  # Dress visual merchandising displays
    "product-demonstration": "RAS/N0125",  # To demonstrate products to customers
    "upselling-and-cross-selling": "BWS/N9006",  # Promote and sell services and products
    # --- cross-sector ---------------------------------------------------
    # These are the widely-required generic units, and the qualification counts
    # show it: workplace safety is required by 133 qualifications, teamwork 62,
    # communication 32.
    "workplace-safety": "MES/N0104",  # Maintain workplace health & safety
    "teamwork": "HYC/N9301",  # Working effectively in a team
    "customer-service": "THC/N9901",  # Communicate effectively and maintain service standards
    "workplace-communication": "THC/N9901",
    "time-management": "SSC/N9001",  # Manage your work to meet requirements
    "basic-computer-operation": "CPC/CAP/N0402",  # Basics of computer and data entry
    "spoken-english": "ASC/N9839",  # English language skills
}
