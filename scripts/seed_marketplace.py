"""Seed marketplace inventory: tenants, jobs and courses.

Idempotent by slug, like scripts/seed_skills.py — skill associations are
replaced wholesale on each run so this file stays the source of truth.

Every skill reference is a slug from the taxonomy. A typo fails loudly rather
than silently creating a job with no skills, because a job with no skills is
invisible to matching and the failure would not surface until Sprint 5.

    make seed
"""

import asyncio
import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta

# Sibling import: `scripts/` is not an installed package, but Python puts a
# script's own directory on sys.path, so this resolves when run as
# `python scripts/seed_marketplace.py` -- which is how the Makefile runs it.
from legacy_skill_map import LEGACY_SKILL_MAP  # noqa: E402
from sqlalchemy import delete, select

from api.core import localisation
from api.core.config import PRIVACY_NOTICE_VERSION
from api.core.database import dispose_engine, get_sessionmaker
from api.core.security import hash_secret
from api.modules.geography import resolve_location
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace.models import Course, CourseSkill, Job, JobSkill
from api.modules.skills.models import Skill

# slug, name, type, city
# slug, name, type, city, owner address.
#
# **Every organisation has an owner account.** A seeded tenant with no
# membership is invisible to everything that reads one -- the employer console
# refuses it, the switcher never shows it, and its applicants cannot be seen by
# anybody. Sprint 12 found seeded *candidates* in exactly that state; the
# organisations stayed that way until the demo needed them. `.example` is the
# reserved documentation domain, so none of these can be a real mailbox.
TENANTS = [
    (
        "apollo-care-hospitals",
        "Apollo Care Hospitals",
        "employer",
        "Chennai",
        "hiring@apollo-care.example",
    ),
    (
        "sunrise-multispeciality",
        "Sunrise Multispeciality Hospital",
        "employer",
        "Pune",
        "hiring@sunrise-multispeciality.example",
    ),
    (
        "medlife-diagnostics",
        "MedLife Diagnostics",
        "employer",
        "Hyderabad",
        "hiring@medlife-diagnostics.example",
    ),
    (
        "greenmart-retail",
        "GreenMart Retail",
        "employer",
        "Bengaluru",
        "hiring@greenmart-retail.example",
    ),
    (
        "swift-logistics",
        "Swift Logistics India",
        "employer",
        "Nagpur",
        "hiring@swift-logistics.example",
    ),
    (
        "nsdc-healthcare-academy",
        "NSDC Healthcare Academy",
        "course_provider",
        "Delhi",
        "admin@nsdc-healthcare-academy.example",
    ),
    (
        "skillbridge-institute",
        "SkillBridge Institute",
        "course_provider",
        "Jaipur",
        "admin@skillbridge-institute.example",
    ),
    (
        "retail-skills-council-academy",
        "Retail Skills Academy",
        "course_provider",
        "Mumbai",
        "admin@retail-skills-academy.example",
    ),
    (
        "allied-health-skills-academy",
        "Allied Health Skills Academy",
        "course_provider",
        "Chennai",
        "admin@allied-health-academy.example",
    ),
    (
        "logistics-retail-institute",
        "Bharat Logistics and Retail Institute",
        "course_provider",
        "Nagpur",
        "admin@logistics-retail-institute.example",
    ),
]

# slug, tenant, title, title_hi, desc_en, desc_hi, state, district,
# employment_type, exp_min, exp_max, sal_min, sal_max, nsqf_min,
# [(skill_slug, importance 1-5, mandatory)]
JOBS = [
    (
        "general-duty-assistant-chennai",
        "apollo-care-hospitals",
        "General Duty Assistant",
        "जनरल ड्यूटी असिस्टेंट",
        "Ward support for inpatients: mobility, hygiene, vitals and comfort.",
        "भर्ती रोगियों के लिए वार्ड सहायता: गतिशीलता, स्वच्छता, महत्वपूर्ण संकेत और आराम।",
        "Tamil Nadu",
        "Chennai",
        "full_time",
        0,
        2,
        168000,
        216000,
        3,
        [
            ("patient-mobility-support", 5, True),
            ("vital-signs-measurement", 4, True),
            ("hand-hygiene", 4, True),
            ("bed-making", 3, False),
            ("patient-bathing-assistance", 3, False),
            ("elderly-care", 3, False),
        ],
    ),
    (
        "staff-nurse-pune",
        "sunrise-multispeciality",
        "Staff Nurse",
        "स्टाफ़ नर्स",
        "Bedside nursing on a 30-bed medical ward.",
        "30 बिस्तरों वाले मेडिकल वार्ड में रोगी के पास नर्सिंग।",
        "Maharashtra",
        "Pune",
        "full_time",
        2,
        6,
        300000,
        420000,
        5,
        [
            ("medication-administration", 5, True),
            ("injection-administration", 5, True),
            ("iv-cannulation", 4, True),
            ("wound-dressing", 4, False),
            ("medical-record-keeping", 3, False),
            ("patient-counselling", 3, False),
        ],
    ),
    (
        "phlebotomist-hyderabad",
        "medlife-diagnostics",
        "Phlebotomist",
        "फ़्लेबोटोमिस्ट",
        "Sample collection across two collection centres.",
        "दो संग्रह केंद्रों पर नमूना संग्रह।",
        "Telangana",
        "Hyderabad",
        "full_time",
        1,
        4,
        192000,
        264000,
        4,
        [
            ("blood-sample-collection", 5, True),
            ("specimen-labelling", 4, True),
            ("infection-control", 4, True),
            ("laboratory-safety", 3, False),
            ("documentation-and-reporting", 3, False),
        ],
    ),
    (
        "lab-technician-hyderabad",
        "medlife-diagnostics",
        "Laboratory Technician",
        "प्रयोगशाला तकनीशियन",
        "Routine pathology testing and reporting.",
        "नियमित पैथोलॉजी जाँच और रिपोर्टिंग।",
        "Telangana",
        "Hyderabad",
        "full_time",
        2,
        5,
        240000,
        336000,
        5,
        [
            ("microscope-operation", 5, True),
            ("urine-sample-analysis", 4, True),
            ("laboratory-safety", 5, True),
            ("specimen-labelling", 3, False),
            ("basic-computer-operation", 2, False),
        ],
    ),
    (
        "icu-attendant-pune",
        "sunrise-multispeciality",
        "ICU Attendant",
        "आईसीयू अटेंडेंट",
        "Critical care support under nursing supervision.",
        "नर्सिंग पर्यवेक्षण में गहन देखभाल सहायता।",
        "Maharashtra",
        "Pune",
        "full_time",
        1,
        4,
        216000,
        300000,
        4,
        [
            ("basic-life-support", 5, True),
            ("oxygen-therapy-support", 4, True),
            ("patient-positioning", 4, True),
            ("vital-signs-measurement", 4, True),
            ("cpr", 4, False),
            ("infection-control", 3, False),
        ],
    ),
    (
        "ward-boy-chennai",
        "apollo-care-hospitals",
        "Ward Attendant",
        "वार्ड अटेंडेंट",
        "Patient transfer, bed making and ward hygiene.",
        "रोगी स्थानांतरण, बिस्तर बनाना और वार्ड स्वच्छता।",
        "Tamil Nadu",
        "Chennai",
        "full_time",
        0,
        1,
        144000,
        180000,
        2,
        [
            ("patient-transfer-techniques", 5, True),
            ("bed-making", 4, True),
            ("hand-hygiene", 4, True),
            ("biomedical-waste-handling", 3, False),
            ("teamwork", 3, False),
        ],
    ),
    (
        "home-care-attendant-pune",
        "sunrise-multispeciality",
        "Home Care Attendant",
        "होम केयर अटेंडेंट",
        "In-home support for elderly and post-operative patients.",
        "वृद्ध और शल्यक्रिया-पश्चात रोगियों के लिए घर पर सहायता।",
        "Maharashtra",
        "Pune",
        "part_time",
        1,
        5,
        156000,
        216000,
        3,
        [
            ("elderly-care", 5, True),
            ("nutrition-and-feeding-support", 4, True),
            ("ambulation-assistance", 4, True),
            ("first-aid", 3, False),
            ("patient-counselling", 3, False),
        ],
    ),
    (
        "ecg-technician-chennai",
        "apollo-care-hospitals",
        "ECG Technician",
        "ईसीजी तकनीशियन",
        "Recording diagnostic ECGs in outpatient clinics.",
        "बाह्य रोगी क्लिनिक में निदान ईसीजी रिकॉर्ड करना।",
        "Tamil Nadu",
        "Chennai",
        "full_time",
        1,
        3,
        216000,
        288000,
        5,
        [
            ("ecg-recording", 5, True),
            ("medical-equipment-handling", 4, True),
            ("vital-signs-measurement", 3, False),
            ("patient-counselling", 2, False),
        ],
    ),
    (
        "hospital-receptionist-pune",
        "sunrise-multispeciality",
        "Hospital Receptionist",
        "अस्पताल रिसेप्शनिस्ट",
        "Front desk registration, appointments and enquiries.",
        "स्वागत कक्ष पंजीकरण, अपॉइंटमेंट और पूछताछ।",
        "Maharashtra",
        "Pune",
        "full_time",
        0,
        3,
        168000,
        228000,
        3,
        [
            ("hospital-front-desk-operations", 5, True),
            ("basic-computer-operation", 4, True),
            ("workplace-communication", 4, True),
            ("spoken-english", 3, False),
            ("customer-service", 3, False),
        ],
    ),
    (
        "cssd-technician-chennai",
        "apollo-care-hospitals",
        "CSSD Technician",
        "सीएसएसडी तकनीशियन",
        "Sterile processing of surgical instruments.",
        "शल्य उपकरणों की रोगाणुरहित प्रक्रिया।",
        "Tamil Nadu",
        "Chennai",
        "full_time",
        1,
        4,
        192000,
        252000,
        4,
        [
            ("sterilisation-of-instruments", 5, True),
            ("infection-control", 5, True),
            ("biomedical-waste-handling", 4, True),
            ("documentation-and-reporting", 2, False),
        ],
    ),
    (
        "emergency-room-assistant-pune",
        "sunrise-multispeciality",
        "Emergency Room Assistant",
        "आपातकालीन कक्ष सहायक",
        "Triage support and rapid response in a busy casualty.",
        "व्यस्त आपातकालीन विभाग में ट्राइएज सहायता और त्वरित प्रतिक्रिया।",
        "Maharashtra",
        "Pune",
        "full_time",
        2,
        5,
        240000,
        324000,
        5,
        [
            ("emergency-response-coordination", 5, True),
            ("basic-life-support", 5, True),
            ("cpr", 4, True),
            ("first-aid", 4, True),
            ("patient-transfer-techniques", 3, False),
        ],
    ),
    (
        "store-sales-associate-bengaluru",
        "greenmart-retail",
        "Store Sales Associate",
        "स्टोर सेल्स एसोसिएट",
        "Customer assistance and checkout in a supermarket.",
        "सुपरमार्केट में ग्राहक सहायता और चेकआउट।",
        "Karnataka",
        "Bengaluru",
        "full_time",
        0,
        2,
        156000,
        204000,
        3,
        [
            ("customer-service", 5, True),
            ("pos-operation", 4, True),
            ("cash-handling", 4, True),
            ("stock-replenishment", 3, False),
            ("upselling-and-cross-selling", 3, False),
        ],
    ),
    (
        "cashier-bengaluru",
        "greenmart-retail",
        "Cashier",
        "कैशियर",
        "Billing, cash handling and end-of-day reconciliation.",
        "बिलिंग, नकदी प्रबंधन और दिन के अंत का मिलान।",
        "Karnataka",
        "Bengaluru",
        "full_time",
        0,
        2,
        150000,
        192000,
        3,
        [
            ("cash-handling", 5, True),
            ("billing-and-invoicing", 5, True),
            ("pos-operation", 4, True),
            ("digital-payments-handling", 4, True),
            ("customer-service", 3, False),
        ],
    ),
    (
        "store-supervisor-bengaluru",
        "greenmart-retail",
        "Store Supervisor",
        "स्टोर सुपरवाइज़र",
        "Shift supervision, stock control and team scheduling.",
        "शिफ़्ट पर्यवेक्षण, स्टॉक नियंत्रण और टीम शेड्यूलिंग।",
        "Karnataka",
        "Bengaluru",
        "full_time",
        3,
        7,
        288000,
        396000,
        5,
        [
            ("inventory-management", 5, True),
            ("teamwork", 4, True),
            ("time-management", 4, True),
            ("customer-service", 4, False),
            ("visual-merchandising", 3, False),
            ("documentation-and-reporting", 3, False),
        ],
    ),
    (
        "visual-merchandiser-mumbai",
        "greenmart-retail",
        "Visual Merchandiser",
        "विज़ुअल मर्चेंडाइज़र",
        "Planning and building in-store displays.",
        "स्टोर के अंदर प्रदर्शन की योजना और निर्माण।",
        "Maharashtra",
        "Mumbai",
        "contract",
        2,
        5,
        240000,
        336000,
        4,
        [
            ("visual-merchandising", 5, True),
            ("product-demonstration", 3, False),
            ("teamwork", 3, False),
        ],
    ),
    (
        "warehouse-assistant-nagpur",
        "swift-logistics",
        "Warehouse Assistant",
        "गोदाम सहायक",
        "Inward, putaway and stock accuracy in a regional hub.",
        "क्षेत्रीय हब में आवक, भंडारण और स्टॉक सटीकता।",
        "Maharashtra",
        "Nagpur",
        "full_time",
        0,
        3,
        156000,
        216000,
        3,
        [
            ("inventory-management", 5, True),
            ("stock-replenishment", 4, True),
            ("workplace-safety", 4, True),
            ("documentation-and-reporting", 3, False),
        ],
    ),
    (
        "delivery-associate-nagpur",
        "swift-logistics",
        "Delivery Associate",
        "डिलीवरी एसोसिएट",
        "Last-mile delivery with digital proof of delivery.",
        "डिजिटल डिलीवरी प्रमाण के साथ अंतिम-मील डिलीवरी।",
        "Maharashtra",
        "Nagpur",
        "full_time",
        0,
        2,
        168000,
        240000,
        3,
        [
            ("digital-payments-handling", 4, True),
            ("customer-service", 4, True),
            ("time-management", 4, True),
            ("workplace-safety", 3, False),
        ],
    ),
    (
        "inventory-clerk-nagpur",
        "swift-logistics",
        "Inventory Clerk",
        "सूची लिपिक",
        "Cycle counts, reconciliation and system updates.",
        "चक्र गणना, मिलान और सिस्टम अपडेट।",
        "Maharashtra",
        "Nagpur",
        "full_time",
        1,
        4,
        180000,
        252000,
        4,
        [
            ("inventory-management", 5, True),
            ("basic-computer-operation", 4, True),
            ("documentation-and-reporting", 4, True),
            ("time-management", 3, False),
        ],
    ),
    (
        "telecaller-bengaluru",
        "greenmart-retail",
        "Customer Support Telecaller",
        "ग्राहक सहायता टेलीकॉलर",
        "Inbound customer queries and order follow-up.",
        "इनबाउंड ग्राहक प्रश्न और ऑर्डर फ़ॉलो-अप।",
        "Karnataka",
        "Bengaluru",
        "part_time",
        0,
        2,
        144000,
        192000,
        3,
        [
            ("customer-service", 5, True),
            ("workplace-communication", 4, True),
            ("spoken-english", 4, False),
            ("basic-computer-operation", 3, False),
        ],
    ),
    (
        "nursing-apprentice-chennai",
        "apollo-care-hospitals",
        "Nursing Apprentice",
        "नर्सिंग प्रशिक्षु",
        "Structured 12-month apprenticeship on medical wards.",
        "मेडिकल वार्ड में संरचित 12-माह की प्रशिक्षुता।",
        "Tamil Nadu",
        "Chennai",
        "apprenticeship",
        0,
        1,
        120000,
        144000,
        3,
        [
            ("hand-hygiene", 4, True),
            ("vital-signs-measurement", 4, True),
            ("first-aid", 3, False),
            ("teamwork", 3, False),
            ("workplace-safety", 3, False),
        ],
    ),
]

# slug, tenant, title, title_hi, desc_en, desc_hi, mode, language,
# hours, fee, nsqf_level, [(skill_slug, level_taught)]
COURSES = [
    (
        "general-duty-assistant-certificate",
        "nsdc-healthcare-academy",
        "General Duty Assistant Certificate",
        "जनरल ड्यूटी असिस्टेंट प्रमाणपत्र",
        "Entry-level ward support, aligned to the GDA qualification pack.",
        "प्रवेश-स्तर वार्ड सहायता, जीडीए क्वालिफ़िकेशन पैक से संरेखित।",
        "offline",
        "both",
        480,
        12000,
        3,
        [
            ("patient-mobility-support", 3),
            ("bed-making", 2),
            ("hand-hygiene", 2),
            ("patient-bathing-assistance", 3),
            ("vital-signs-measurement", 3),
            ("patient-transfer-techniques", 3),
        ],
    ),
    (
        "phlebotomy-technician-course",
        "nsdc-healthcare-academy",
        "Phlebotomy Technician",
        "फ़्लेबोटोमी तकनीशियन",
        "Venous sampling, labelling and specimen handling.",
        "शिरा नमूना, लेबलिंग और नमूना प्रबंधन।",
        "offline",
        "both",
        240,
        9000,
        4,
        [
            ("blood-sample-collection", 4),
            ("specimen-labelling", 3),
            ("infection-control", 3),
            ("laboratory-safety", 3),
        ],
    ),
    (
        "basic-life-support-certification",
        "nsdc-healthcare-academy",
        "Basic Life Support Certification",
        "बुनियादी जीवन रक्षा प्रमाणन",
        "BLS and CPR to national resuscitation standards.",
        "राष्ट्रीय पुनर्जीवन मानकों के अनुसार बीएलएस और सीपीआर।",
        "hybrid",
        "both",
        24,
        2500,
        4,
        [("basic-life-support", 4), ("cpr", 4), ("first-aid", 3)],
    ),
    (
        "infection-control-in-hospitals",
        "nsdc-healthcare-academy",
        "Infection Control in Hospitals",
        "अस्पतालों में संक्रमण नियंत्रण",
        "Standard precautions, waste segregation and sterile technique.",
        "मानक सावधानियाँ, अपशिष्ट पृथक्करण और रोगाणुरहित तकनीक।",
        "online",
        "both",
        40,
        1800,
        4,
        [
            ("infection-control", 4),
            ("hand-hygiene", 3),
            ("biomedical-waste-handling", 3),
            ("sterilisation-of-instruments", 3),
        ],
    ),
    (
        "medication-administration-for-nurses",
        "nsdc-healthcare-academy",
        "Medication Administration for Nurses",
        "नर्सों के लिए दवा प्रशासन",
        "Safe dosing, routes, and injection technique.",
        "सुरक्षित मात्रा, मार्ग और इंजेक्शन तकनीक।",
        "offline",
        "both",
        120,
        7500,
        5,
        [
            ("medication-administration", 5),
            ("injection-administration", 4),
            ("iv-cannulation", 4),
            ("medical-record-keeping", 3),
        ],
    ),
    (
        "wound-care-and-dressing",
        "nsdc-healthcare-academy",
        "Wound Care and Dressing",
        "घाव देखभाल एवं ड्रेसिंग",
        "Aseptic dressing technique for common wound types.",
        "सामान्य घावों के लिए रोगाणुरहित ड्रेसिंग तकनीक।",
        "offline",
        "hi",
        80,
        4500,
        4,
        [("wound-dressing", 4), ("infection-control", 3), ("hand-hygiene", 2)],
    ),
    (
        "ecg-technician-training",
        "skillbridge-institute",
        "ECG Technician Training",
        "ईसीजी तकनीशियन प्रशिक्षण",
        "Lead placement, recording and artefact recognition.",
        "लीड प्लेसमेंट, रिकॉर्डिंग और आर्टिफ़ैक्ट पहचान।",
        "offline",
        "both",
        160,
        11000,
        5,
        [("ecg-recording", 5), ("medical-equipment-handling", 4), ("vital-signs-measurement", 3)],
    ),
    (
        "medical-laboratory-technician",
        "skillbridge-institute",
        "Medical Laboratory Technician",
        "मेडिकल लैबोरेटरी तकनीशियन",
        "Routine pathology: microscopy, urinalysis and lab safety.",
        "नियमित पैथोलॉजी: सूक्ष्मदर्शी, मूत्र विश्लेषण और लैब सुरक्षा।",
        "offline",
        "both",
        600,
        22000,
        5,
        [
            ("microscope-operation", 5),
            ("urine-sample-analysis", 4),
            ("laboratory-safety", 4),
            ("specimen-labelling", 3),
            ("documentation-and-reporting", 3),
        ],
    ),
    (
        "elderly-and-home-care",
        "skillbridge-institute",
        "Elderly and Home Care",
        "वृद्ध एवं गृह देखभाल",
        "Home-based support for older and recovering patients.",
        "वृद्ध और स्वस्थ हो रहे रोगियों के लिए घर-आधारित सहायता।",
        "hybrid",
        "hi",
        200,
        8000,
        3,
        [
            ("elderly-care", 4),
            ("nutrition-and-feeding-support", 3),
            ("ambulation-assistance", 3),
            ("first-aid", 3),
            ("patient-counselling", 3),
        ],
    ),
    (
        "critical-care-support-skills",
        "nsdc-healthcare-academy",
        "Critical Care Support Skills",
        "गहन देखभाल सहायता कौशल",
        "Oxygen therapy, positioning and monitoring in the ICU.",
        "आईसीयू में ऑक्सीजन थेरेपी, स्थिति और निगरानी।",
        "offline",
        "en",
        160,
        14000,
        5,
        [
            ("oxygen-therapy-support", 4),
            ("patient-positioning", 4),
            ("basic-life-support", 4),
            ("catheter-care", 3),
        ],
    ),
    (
        "hospital-front-office-operations",
        "skillbridge-institute",
        "Hospital Front Office Operations",
        "अस्पताल फ्रंट ऑफिस संचालन",
        "Registration, scheduling and patient communication.",
        "पंजीकरण, समय-निर्धारण और रोगी संचार।",
        "online",
        "both",
        60,
        3200,
        3,
        [
            ("hospital-front-desk-operations", 3),
            ("basic-computer-operation", 3),
            ("workplace-communication", 3),
            ("customer-service", 3),
        ],
    ),
    (
        "sterile-processing-technician",
        "skillbridge-institute",
        "Sterile Processing Technician",
        "स्टेराइल प्रोसेसिंग तकनीशियन",
        "Decontamination, autoclaving and sterile storage.",
        "संदूषण-मुक्ति, ऑटोक्लेविंग और रोगाणुरहित भंडारण।",
        "offline",
        "both",
        180,
        9500,
        4,
        [
            ("sterilisation-of-instruments", 4),
            ("infection-control", 4),
            ("medical-equipment-handling", 3),
            ("biomedical-waste-handling", 3),
        ],
    ),
    (
        "retail-sales-associate-certificate",
        "retail-skills-council-academy",
        "Retail Sales Associate Certificate",
        "रिटेल सेल्स एसोसिएट प्रमाणपत्र",
        "Customer handling, POS and store floor operations.",
        "ग्राहक प्रबंधन, पीओएस और स्टोर फ़्लोर संचालन।",
        "offline",
        "both",
        200,
        6500,
        3,
        [
            ("customer-service", 3),
            ("pos-operation", 3),
            ("cash-handling", 3),
            ("stock-replenishment", 2),
            ("upselling-and-cross-selling", 3),
        ],
    ),
    (
        "cashier-and-billing-operations",
        "retail-skills-council-academy",
        "Cashier and Billing Operations",
        "कैशियर एवं बिलिंग संचालन",
        "Billing accuracy, cash control and digital payments.",
        "बिलिंग सटीकता, नकद नियंत्रण और डिजिटल भुगतान।",
        "online",
        "hi",
        60,
        2200,
        3,
        [
            ("billing-and-invoicing", 3),
            ("cash-handling", 3),
            ("digital-payments-handling", 3),
            ("pos-operation", 3),
        ],
    ),
    (
        "visual-merchandising-fundamentals",
        "retail-skills-council-academy",
        "Visual Merchandising Fundamentals",
        "विज़ुअल मर्चेंडाइजिंग मूल बातें",
        "Display planning, layout and seasonal campaigns.",
        "प्रदर्शन योजना, लेआउट और मौसमी अभियान।",
        "hybrid",
        "en",
        90,
        5400,
        4,
        [("visual-merchandising", 4), ("product-demonstration", 3)],
    ),
    (
        "inventory-and-stock-control",
        "retail-skills-council-academy",
        "Inventory and Stock Control",
        "सूची एवं स्टॉक नियंत्रण",
        "Stock accuracy, cycle counting and shrinkage control.",
        "स्टॉक सटीकता, चक्र गणना और क्षति नियंत्रण।",
        "online",
        "both",
        80,
        3800,
        4,
        [
            ("inventory-management", 4),
            ("stock-replenishment", 3),
            ("documentation-and-reporting", 3),
        ],
    ),
    (
        "warehouse-operations-basics",
        "retail-skills-council-academy",
        "Warehouse Operations Basics",
        "गोदाम संचालन मूल बातें",
        "Receiving, putaway, picking and workplace safety.",
        "प्राप्ति, भंडारण, चयन और कार्यस्थल सुरक्षा।",
        "offline",
        "hi",
        120,
        4200,
        3,
        [
            ("inventory-management", 3),
            ("stock-replenishment", 3),
            ("workplace-safety", 3),
            ("teamwork", 2),
        ],
    ),
    (
        "spoken-english-for-frontline-roles",
        "skillbridge-institute",
        "Spoken English for Frontline Roles",
        "अग्रिम भूमिकाओं के लिए अंग्रेज़ी",
        "Practical workplace English for customer-facing work.",
        "ग्राहक-सम्मुख कार्य के लिए व्यावहारिक कार्यस्थल अंग्रेज़ी।",
        "online",
        "both",
        100,
        2900,
        3,
        [("spoken-english", 3), ("workplace-communication", 3), ("customer-service", 2)],
    ),
    (
        "digital-literacy-for-work",
        "skillbridge-institute",
        "Digital Literacy for Work",
        "कार्य के लिए डिजिटल साक्षरता",
        "Computers, digital payments and workplace software.",
        "कंप्यूटर, डिजिटल भुगतान और कार्यस्थल सॉफ़्टवेयर।",
        "online",
        "hi",
        60,
        1500,
        3,
        [
            ("basic-computer-operation", 3),
            ("digital-payments-handling", 3),
            ("documentation-and-reporting", 2),
        ],
    ),
    (
        "workplace-safety-and-first-aid",
        "retail-skills-council-academy",
        "Workplace Safety and First Aid",
        "कार्यस्थल सुरक्षा एवं प्राथमिक चिकित्सा",
        "Hazard awareness, safe practice and emergency first aid.",
        "ख़तरे की पहचान, सुरक्षित अभ्यास और आपातकालीन प्राथमिक चिकित्सा।",
        "hybrid",
        "both",
        40,
        1900,
        3,
        [("workplace-safety", 3), ("first-aid", 3), ("teamwork", 2)],
    ),
    # ------------------------------------------------------------------
    # Sprint 22.5: thirty courses authored against the gaps the seeded
    # vacancies actually leave.
    #
    # Not thirty arbitrary courses. Every mandatory standard across the twenty
    # vacancies now has at least one course teaching it, and the two that had
    # **none** -- SSC/N9001 (`time-management`) and SSD/VSQ/N0104
    # (`emergency-response-coordination`) -- are first. A gap panel that names a
    # standard and then offers nothing to close it is the recommendation engine
    # visibly failing at the one thing it is for.
    # ------------------------------------------------------------------
    (
        "ward-shift-management",
        "nsdc-healthcare-academy",
        "Ward Shift Management and Work Planning",
        "वार्ड शिफ़्ट प्रबंधन और कार्य योजना",
        "Planning a shift, meeting handover deadlines and recording what was done.",
        "शिफ़्ट की योजना, हैंडओवर समय-सीमा का पालन और किए गए कार्य का अभिलेखन।",
        "online",
        "both",
        60,
        3500,
        4,
        [
            ("time-management", 4),
            ("teamwork", 4),
            ("documentation-and-reporting", 3),
        ],
    ),
    (
        "hospital-emergency-preparedness",
        "nsdc-healthcare-academy",
        "Hospital Emergency Preparedness and Response",
        "अस्पताल आपातकालीन तैयारी और प्रतिक्रिया",
        "Codes, evacuation drills, triage support and the first ten minutes.",
        "कोड, निकासी अभ्यास, ट्राइएज सहायता और पहले दस मिनट।",
        "hybrid",
        "both",
        90,
        5500,
        4,
        [
            ("emergency-response-coordination", 4),
            ("first-aid", 4),
            ("cpr", 3),
        ],
    ),
    (
        "geriatric-home-care-advanced",
        "nsdc-healthcare-academy",
        "Advanced Geriatric Home Care",
        "उन्नत वृद्धजन गृह देखभाल",
        "Daily care for older adults at home, including feeding and mobility.",
        "घर पर वृद्धजनों की दैनिक देखभाल, जिसमें आहार और गतिशीलता शामिल है।",
        "offline",
        "both",
        240,
        9000,
        4,
        [
            ("elderly-care", 4),
            ("nutrition-and-feeding-support", 4),
            ("ambulation-assistance", 3),
        ],
    ),
    (
        "patient-transfer-and-handling",
        "nsdc-healthcare-academy",
        "Safe Patient Transfer and Handling",
        "सुरक्षित रोगी स्थानांतरण और हैंडलिंग",
        "Moving a patient between bed, trolley and chair without injuring either of you.",
        "बिस्तर, ट्रॉली और कुर्सी के बीच रोगी को बिना चोट पहुँचाए स्थानांतरित करना।",
        "offline",
        "both",
        120,
        4800,
        4,
        [
            ("patient-transfer-techniques", 4),
            ("patient-positioning", 4),
            ("patient-mobility-support", 3),
        ],
    ),
    (
        "ward-linen-and-patient-comfort",
        "nsdc-healthcare-academy",
        "Ward Linen and Patient Comfort",
        "वार्ड लिनन और रोगी आराम",
        "Bed making with an occupant, linen changes and comfort rounds.",
        "रोगी के लेटे रहते बिस्तर बनाना, लिनन बदलना और आराम राउंड।",
        "offline",
        "hi",
        80,
        2600,
        3,
        [
            ("bed-making", 3),
            ("patient-bathing-assistance", 3),
            ("infection-control", 3),
        ],
    ),
    (
        "clinic-front-desk-operations",
        "nsdc-healthcare-academy",
        "Clinic Front Desk Operations",
        "क्लिनिक फ़्रंट डेस्क संचालन",
        "Registration, appointments, queue handling and the hospital information system.",
        "पंजीकरण, अपॉइंटमेंट, कतार प्रबंधन और अस्पताल सूचना प्रणाली।",
        "hybrid",
        "both",
        150,
        6200,
        4,
        [
            ("hospital-front-desk-operations", 4),
            ("customer-service", 4),
            ("basic-computer-operation", 3),
        ],
    ),
    (
        "phlebotomy-refresher",
        "skillbridge-institute",
        "Phlebotomy Refresher and Best Practice",
        "फ़्लेबोटॉमी रिफ़्रेशर और सर्वोत्तम अभ्यास",
        "Difficult draws, order of draw, labelling at the bedside and waste segregation.",
        "कठिन नमूना संग्रह, ड्रॉ का क्रम, बेडसाइड लेबलिंग और अपशिष्ट पृथक्करण।",
        "offline",
        "both",
        90,
        4200,
        4,
        [
            ("blood-sample-collection", 4),
            ("specimen-labelling", 4),
            ("biomedical-waste-handling", 3),
        ],
    ),
    (
        "urinalysis-and-sample-handling",
        "skillbridge-institute",
        "Urinalysis and Sample Handling",
        "मूत्र विश्लेषण और नमूना प्रबंधन",
        "Routine urine examination, dipstick reading and pre-analytical handling.",
        "नियमित मूत्र परीक्षण, डिपस्टिक रीडिंग और पूर्व-विश्लेषणात्मक प्रबंधन।",
        "offline",
        "both",
        120,
        5000,
        4,
        [
            ("urine-sample-analysis", 4),
            ("specimen-labelling", 3),
            ("laboratory-safety", 3),
        ],
    ),
    (
        "iv-therapy-and-injections",
        "skillbridge-institute",
        "IV Therapy and Injection Technique",
        "आईवी थेरेपी और इंजेक्शन तकनीक",
        "Cannulation, infusion monitoring and the five rights of medication.",
        "कैन्युलेशन, इन्फ़्यूज़न निगरानी और दवा के पाँच अधिकार।",
        "offline",
        "both",
        160,
        7500,
        5,
        [
            ("iv-cannulation", 4),
            ("injection-administration", 4),
            ("medication-administration", 3),
        ],
    ),
    (
        "ecg-technician-advanced",
        "skillbridge-institute",
        "Advanced ECG Technician",
        "उन्नत ईसीजी तकनीशियन",
        "Twelve-lead recording, artefact removal and recognising what needs a doctor now.",
        "बारह-लीड रिकॉर्डिंग, आर्टिफ़ैक्ट हटाना और यह पहचानना कि कब तुरंत डॉक्टर चाहिए।",
        "hybrid",
        "both",
        200,
        11000,
        5,
        [
            ("ecg-recording", 5),
            ("vital-signs-measurement", 4),
            ("cpr", 3),
        ],
    ),
    (
        "sterile-processing-essentials",
        "skillbridge-institute",
        "Sterile Processing Essentials",
        "स्टेराइल प्रोसेसिंग आवश्यक बातें",
        "Decontamination, packing, autoclave cycles and load release.",
        "विसंक्रमण, पैकिंग, ऑटोक्लेव चक्र और लोड रिलीज़।",
        "offline",
        "both",
        180,
        7000,
        4,
        [
            ("sterilisation-of-instruments", 4),
            ("medical-equipment-handling", 4),
            ("infection-control", 4),
        ],
    ),
    (
        "oxygen-and-airway-support",
        "skillbridge-institute",
        "Oxygen and Airway Support",
        "ऑक्सीजन और वायुमार्ग सहायता",
        "Delivery devices, flow rates, suction and escalation to life support.",
        "डिलीवरी उपकरण, फ़्लो दर, सक्शन और जीवन रक्षक सहायता तक वृद्धि।",
        "hybrid",
        "both",
        110,
        5800,
        4,
        [
            ("oxygen-therapy-support", 4),
            ("catheter-care", 3),
            ("basic-life-support", 4),
        ],
    ),
    (
        "visual-merchandising-foundations",
        "retail-skills-council-academy",
        "Visual Merchandising Foundations",
        "विज़ुअल मर्चेंडाइज़िंग की नींव",
        "Window schemes, planograms and how a display changes what sells.",
        "विंडो स्कीम, प्लानोग्राम और डिस्प्ले बिक्री को कैसे बदलता है।",
        "hybrid",
        "both",
        100,
        4500,
        4,
        [
            ("visual-merchandising", 4),
            ("product-demonstration", 3),
        ],
    ),
    (
        "store-operations-and-stock",
        "retail-skills-council-academy",
        "Store Operations and Stock Control",
        "स्टोर संचालन और स्टॉक नियंत्रण",
        "Goods inward, shelf replenishment, shrinkage and stock counts.",
        "माल प्राप्ति, शेल्फ़ पुनर्भरण, क्षति और स्टॉक गणना।",
        "offline",
        "both",
        140,
        4000,
        4,
        [
            ("inventory-management", 4),
            ("stock-replenishment", 4),
        ],
    ),
    (
        "billing-and-digital-payments",
        "retail-skills-council-academy",
        "Billing and Digital Payments",
        "बिलिंग और डिजिटल भुगतान",
        "Point of sale, GST invoicing, UPI reconciliation and end-of-day cash-up.",
        "पॉइंट ऑफ़ सेल, जीएसटी चालान, यूपीआई मिलान और दिन के अंत का नकद मिलान।",
        "online",
        "both",
        70,
        2400,
        4,
        [
            ("billing-and-invoicing", 4),
            ("digital-payments-handling", 4),
            ("pos-operation", 4),
        ],
    ),
    (
        "customer-service-excellence",
        "retail-skills-council-academy",
        "Customer Service Excellence",
        "उत्कृष्ट ग्राहक सेवा",
        "Greeting, questioning, handling a complaint and closing it properly.",
        "अभिवादन, प्रश्न पूछना, शिकायत सँभालना और उसे ठीक से बंद करना।",
        "online",
        "both",
        50,
        1800,
        4,
        [
            ("customer-service", 4),
            ("workplace-communication", 4),
            ("spoken-english", 3),
        ],
    ),
    (
        "retail-shift-planning",
        "retail-skills-council-academy",
        "Shift Planning for Store Teams",
        "स्टोर टीमों के लिए शिफ़्ट योजना",
        "Rosters, peak-hour cover and meeting the day's targets as a team.",
        "रोस्टर, व्यस्त समय की व्यवस्था और टीम के रूप में दिन के लक्ष्य पूरे करना।",
        "online",
        "both",
        45,
        1600,
        4,
        [
            ("time-management", 4),
            ("teamwork", 3),
        ],
    ),
    (
        "upselling-for-store-associates",
        "retail-skills-council-academy",
        "Upselling for Store Associates",
        "स्टोर सहयोगियों के लिए अपसेलिंग",
        "Reading a basket, suggesting the next item and demonstrating it well.",
        "बास्केट पढ़ना, अगली वस्तु सुझाना और उसका सही प्रदर्शन करना।",
        "hybrid",
        "both",
        60,
        2200,
        4,
        [
            ("upselling-and-cross-selling", 4),
            ("product-demonstration", 4),
            ("customer-service", 3),
        ],
    ),
    (
        "laboratory-microscopy-basics",
        "allied-health-skills-academy",
        "Laboratory Microscopy Basics",
        "प्रयोगशाला माइक्रोस्कोपी की मूल बातें",
        "Setting up, focusing and maintaining a compound microscope safely.",
        "कंपाउंड माइक्रोस्कोप को सुरक्षित रूप से सेट करना, फ़ोकस करना और रखरखाव।",
        "offline",
        "both",
        120,
        4600,
        4,
        [
            ("microscope-operation", 4),
            ("laboratory-safety", 4),
        ],
    ),
    (
        "specimen-transport-and-custody",
        "allied-health-skills-academy",
        "Specimen Transport and Chain of Custody",
        "नमूना परिवहन और अभिरक्षा शृंखला",
        "Moving samples between collection and bench without losing identity or integrity.",
        "संग्रह से बेंच तक नमूनों को पहचान और अखंडता खोए बिना पहुँचाना।",
        "hybrid",
        "both",
        80,
        3200,
        4,
        [
            ("specimen-labelling", 4),
            ("patient-transfer-techniques", 3),
            ("documentation-and-reporting", 3),
        ],
    ),
    (
        "medical-records-and-data-entry",
        "allied-health-skills-academy",
        "Medical Records and Data Entry",
        "चिकित्सा अभिलेख और डेटा प्रविष्टि",
        "Case sheets, retention rules and accurate entry into a hospital system.",
        "केस शीट, अभिलेख रखने के नियम और अस्पताल प्रणाली में सटीक प्रविष्टि।",
        "online",
        "both",
        90,
        3000,
        4,
        [
            ("medical-record-keeping", 4),
            ("basic-computer-operation", 4),
            ("documentation-and-reporting", 4),
        ],
    ),
    (
        "biomedical-waste-management",
        "allied-health-skills-academy",
        "Biomedical Waste Management",
        "जैव-चिकित्सा अपशिष्ट प्रबंधन",
        "Segregation by colour code, sharps handling and the statutory records.",
        "रंग कोड के अनुसार पृथक्करण, तीक्ष्ण वस्तुओं का प्रबंधन और वैधानिक अभिलेख।",
        "hybrid",
        "both",
        60,
        2800,
        5,
        [
            ("biomedical-waste-handling", 5),
            ("infection-control", 4),
            ("workplace-safety", 3),
        ],
    ),
    (
        "vitals-and-monitoring-refresher",
        "allied-health-skills-academy",
        "Vitals and Monitoring Refresher",
        "जीवन संकेत और निगरानी रिफ़्रेशर",
        "Taking, recording and escalating temperature, pulse, respiration and blood pressure.",
        "तापमान, नाड़ी, श्वसन और रक्तचाप लेना, दर्ज करना और आवश्यकता पर आगे बढ़ाना।",
        "offline",
        "both",
        70,
        2600,
        4,
        [
            ("vital-signs-measurement", 4),
            ("temperature-monitoring", 4),
            ("blood-pressure-measurement", 4),
        ],
    ),
    (
        "geriatric-nutrition-support",
        "allied-health-skills-academy",
        "Nutrition Support for Older Adults",
        "वृद्धजनों के लिए पोषण सहायता",
        "Assisted feeding, swallowing precautions and keeping an intake chart.",
        "सहायता से भोजन, निगलने संबंधी सावधानियाँ और आहार चार्ट रखना।",
        "offline",
        "hi",
        100,
        3400,
        4,
        [
            ("nutrition-and-feeding-support", 4),
            ("elderly-care", 4),
        ],
    ),
    (
        "warehouse-goods-handling",
        "logistics-retail-institute",
        "Warehouse Goods Handling",
        "गोदाम माल प्रबंधन",
        "Receiving, put-away, picking and counting, with safe manual handling throughout.",
        "प्राप्ति, रखरखाव, पिकिंग और गणना, साथ में सुरक्षित मैनुअल हैंडलिंग।",
        "offline",
        "both",
        120,
        3600,
        4,
        [
            ("inventory-management", 4),
            ("stock-replenishment", 4),
            ("workplace-safety", 4),
        ],
    ),
    (
        "workplace-safety-for-logistics",
        "logistics-retail-institute",
        "Workplace Safety for Logistics",
        "लॉजिस्टिक्स के लिए कार्यस्थल सुरक्षा",
        "Hazard spotting, evacuation, incident reporting and the first response on site.",
        "ख़तरे की पहचान, निकासी, घटना रिपोर्टिंग और स्थल पर पहली प्रतिक्रिया।",
        "hybrid",
        "both",
        80,
        3000,
        5,
        [
            ("workplace-safety", 5),
            ("emergency-response-coordination", 3),
            ("first-aid", 3),
        ],
    ),
    (
        "delivery-associate-essentials",
        "logistics-retail-institute",
        "Delivery Associate Essentials",
        "डिलीवरी सहयोगी आवश्यक बातें",
        "Route order, delivery windows, the handheld device and the customer at the door.",
        "रूट क्रम, डिलीवरी समय, हैंडहेल्ड उपकरण और दरवाज़े पर ग्राहक।",
        "online",
        "hi",
        40,
        1400,
        4,
        [
            ("time-management", 4),
            ("customer-service", 3),
            ("basic-computer-operation", 3),
        ],
    ),
    (
        "team-coordination-for-shift-work",
        "logistics-retail-institute",
        "Team Coordination for Shift Work",
        "शिफ़्ट कार्य के लिए टीम समन्वय",
        "Handovers that hold, escalation paths and communicating across a noisy floor.",
        "टिकाऊ हैंडओवर, वृद्धि के रास्ते और शोरगुल भरे फ़्लोर पर संवाद।",
        "online",
        "both",
        45,
        1500,
        4,
        [
            ("teamwork", 4),
            ("workplace-communication", 4),
            ("time-management", 3),
        ],
    ),
    (
        "cash-and-cod-handling",
        "logistics-retail-institute",
        "Cash and Cash-on-Delivery Handling",
        "नकद और डिलीवरी-पर-भुगतान प्रबंधन",
        "Collecting, reconciling and depositing, with a paper trail that survives an audit.",
        "संग्रह, मिलान और जमा, ऐसे अभिलेख के साथ जो ऑडिट में टिके।",
        "hybrid",
        "both",
        55,
        2000,
        4,
        [
            ("cash-handling", 4),
            ("digital-payments-handling", 3),
            ("billing-and-invoicing", 3),
        ],
    ),
    (
        "first-aid-at-work",
        "logistics-retail-institute",
        "First Aid at Work",
        "कार्यस्थल पर प्राथमिक चिकित्सा",
        "Bleeding, burns, choking and resuscitation, practised on a manikin.",
        "रक्तस्राव, जलन, दम घुटना और पुनर्जीवन, मैनिकिन पर अभ्यास सहित।",
        "offline",
        "both",
        30,
        1200,
        4,
        [
            ("first-aid", 4),
            ("cpr", 4),
            ("basic-life-support", 4),
        ],
    ),
]


async def _owner_for(db, tenant: Tenant, email: str) -> bool:  # type: ignore[no-untyped-def]
    """Give an organisation an owner account, the way the product does.

    `provision_organisation` is the shape being mirrored: a `User`, a `Tenant`
    and a `Membership(role="owner")`. It cannot simply be called, because it
    creates the tenant too and the tenant here already exists -- but the
    resulting three rows must be identical, or a seeded organisation behaves
    differently from a registered one in the console that reads them.

    Sprint 12's lesson, applied to organisations: a tenant with no membership is
    invisible to everything that reads one. Six seeded applications sat in the
    inboxes of member-less organisations, which is to say in nobody's inbox.

    Returns whether an account was created, for the run's own report.
    """
    user = await db.scalar(select(User).where(User.email == email))
    created = user is None
    if user is None:
        user = User(email=email)
        db.add(user)
    user.full_name = f"{tenant.name} team"
    # Seeded rather than verified through a code -- but the *state* must be the
    # verified one, or the account cannot sign in and the seed has produced
    # something the product would never produce.
    user.email_verified_at = user.email_verified_at or _now()
    # Consent is a record of an agreement, and these accounts are fixtures: the
    # current version is written because the fixture stands in for someone who
    # agreed, not backfilled onto a real account that never did.
    user.consent_version = PRIVACY_NOTICE_VERSION
    user.consented_at = user.consented_at or _now()
    await db.flush()

    member = await db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.tenant_id == tenant.id)
    )
    if member is None:
        db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
    else:
        member.role = "owner"
    await db.flush()
    return created


# One organisation with a real team, so the screen demonstrates from a cold
# start (Sprint 22.5's lesson: a feature nobody can reach in a demo may as well
# not have shipped). Apollo Care gets a second **owner** and a pending
# invitation, which is what makes both sides of the sole-owner rule visible:
# the deletion guard can be seen refusing, and seen relenting.
TEAM = [
    ("apollo-care-hospitals", "coordinator@apollo-care.example", "owner", "Hiring coordinator"),
    ("apollo-care-hospitals", "recruiter@apollo-care.example", "admin", "Recruiter"),
]

# Sent, never accepted -- so the Team screen has a pending row to show and to
# revoke. Its token is random and **deliberately not recoverable**: a fixture
# with a known invitation token is a working key sitting in a seed script, and
# demonstrating acceptance is better done by sending a fresh invitation from
# the interface, which is the flow worth showing anyway.
PENDING_INVITES = [("apollo-care-hospitals", "newjoiner@apollo-care.example", "member")]


async def _seed_team(db, tenants: dict[str, Tenant]) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Second members and one open invitation. Idempotent, like everything here.

    Until Sprint 25 every `Membership` in this file and in `api/` alike was
    written with `role="owner"`, so a seeded organisation could only ever
    contain one person -- and the console's team screen would have had nothing
    to render on a fresh database.
    """
    from api.modules.identity.models import INVITE_TTL_DAYS, Invitation

    members = 0
    for tenant_slug, email, role, full_name in TEAM:
        tenant = tenants.get(tenant_slug)
        if tenant is None:
            continue
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email)
            db.add(user)
        user.full_name = full_name
        # The verified, consented state a real account reaches by signing in --
        # a fixture that behaves differently from a registered account is not a
        # demonstration.
        user.email_verified_at = user.email_verified_at or _now()
        user.consent_version = PRIVACY_NOTICE_VERSION
        user.consented_at = user.consented_at or _now()
        await db.flush()

        membership = await db.scalar(
            select(Membership).where(
                Membership.user_id == user.id, Membership.tenant_id == tenant.id
            )
        )
        if membership is None:
            db.add(Membership(user_id=user.id, tenant_id=tenant.id, role=role))
            members += 1
        else:
            membership.role = role
        await db.flush()

    invites = 0
    for tenant_slug, email, role in PENDING_INVITES:
        tenant = tenants.get(tenant_slug)
        if tenant is None:
            continue
        existing = await db.scalar(
            select(Invitation).where(Invitation.tenant_id == tenant.id, Invitation.email == email)
        )
        if existing is not None:
            continue
        db.add(
            Invitation(
                tenant_id=tenant.id,
                email=email,
                role=role,
                token_hash=hash_secret(secrets.token_urlsafe(32)),
                expires_at=_now() + timedelta(days=INVITE_TTL_DAYS),
            )
        )
        invites += 1
    await db.flush()
    return members, invites


def _now() -> datetime:
    return datetime.now(UTC)


async def _translate(db, entity_type: str, row, fields: dict[str, str | None]) -> None:  # type: ignore[no-untyped-def]
    """Write this row's Hindi as translations (ADR-041).

    Flushes first: a row created moments ago has no id until it is, and a
    translation keyed on `None` would be silently useless.
    """
    await db.flush()
    for field, text in fields.items():
        if text:
            await localisation.upsert(db, entity_type, row.id, field, "hi", text, source="imported")


async def seed() -> dict[str, int]:
    stats = {
        "tenants": 0,
        "owners": 0,
        "teammates": 0,
        "invitations": 0,
        "jobs": 0,
        "courses": 0,
        "job_skills": 0,
        "course_skills": 0,
    }

    async with get_sessionmaker()() as db:
        # Inventory is anchored to real National Occupational Standards, not to
        # the hand-written Sprint 2 vocabulary. The job and course definitions
        # below still read in the curated terms because they are legible that
        # way; LEGACY_SKILL_MAP is the single place the translation happens, so
        # every anchor is auditable in one file instead of across 172 literals.
        by_nos = dict(
            (
                await db.execute(
                    select(Skill.nos_code, Skill.id).where(
                        Skill.source == "nsqf", Skill.nos_code.isnot(None)
                    )
                )
            ).all()  # type: ignore[arg-type]
        )
        if not by_nos:
            print(
                "No NSQF skills found. Run `make import-nsqf` before seeding the marketplace.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        referenced = {sl for j in JOBS for sl, _, _ in j[14]} | {
            sl for c in COURSES for sl, _ in c[11]
        }

        # Two ways this can be wrong, and both must stop the seed: a slug with
        # no mapping, or a mapping pointing at a standard the import did not
        # produce. Inventory with silently missing skills is invisible until
        # matching returns nothing for it.
        unmapped = sorted(referenced - LEGACY_SKILL_MAP.keys())
        if unmapped:
            print(f"Skill slugs with no NOS mapping: {', '.join(unmapped)}", file=sys.stderr)
            raise SystemExit(1)

        skills: dict[str, uuid.UUID] = {}
        dangling: list[str] = []
        for slug in referenced:
            code = LEGACY_SKILL_MAP[slug]
            if code in by_nos:
                skills[slug] = by_nos[code]
            else:
                dangling.append(f"{slug} -> {code}")
        if dangling:
            print(f"Mapped to unknown NOS codes: {', '.join(sorted(dangling))}", file=sys.stderr)
            raise SystemExit(1)

        tenants: dict[str, Tenant] = {}
        for slug, name, ttype, city, owner_email in TENANTS:
            t = await db.scalar(select(Tenant).where(Tenant.slug == slug))
            if t is None:
                t = Tenant(slug=slug)
                db.add(t)
                stats["tenants"] += 1
            t.name, t.tenant_type, t.city = name, ttype, city
            await db.flush()
            if await _owner_for(db, t, owner_email):
                stats["owners"] += 1
            tenants[slug] = t

        stats["teammates"], stats["invitations"] = await _seed_team(db, tenants)

        for (
            slug,
            tslug,
            t_en,
            t_hi,
            d_en,
            d_hi,
            state,
            district,
            etype,
            emin,
            emax,
            smin,
            smax,
            nsqf,
            skill_rows,
        ) in JOBS:
            job = await db.scalar(select(Job).where(Job.slug == slug))
            if job is None:
                job = Job(slug=slug)
                db.add(job)
                stats["jobs"] += 1
            job.tenant_id = tenants[tslug].id
            job.title, job.description = t_en, d_en
            # Hindi is a translation now, not a second column (ADR-041), and the
            # seed writes it the way the API does -- so a seeded listing and a
            # self-serve one stay indistinguishable here too.
            await _translate(db, "job", job, {"title": t_hi, "description": d_hi})
            job.location_state, job.location_district = state, district
            # Resolved through the same service the publishing path uses, so a
            # seeded listing and a self-serve one are indistinguishable on the
            # field that decides whether matching can find them (ADR-026).
            #
            # The seed set neither FK until Sprint 15. Seeded jobs got them only
            # from `_backfill_geography` inside `make import-nsqf` -- which must
            # run *before* `make seed`, so the backfill fired before the rows it
            # was meant to fix existed. A clean `import-nsqf && seed` therefore
            # left every seeded job visible at /jobs and invisible to
            # `match_jobs(state_id=...)`. It only ever looked right because the
            # importer happened to be re-run afterwards.
            located = await resolve_location(db, state, district)
            job.state_id, job.district_id = located.state_id, located.district_id
            job.employment_type = etype
            job.experience_min_years, job.experience_max_years = emin, emax
            job.salary_min_inr, job.salary_max_inr = smin, smax
            job.nsqf_level_min = nsqf
            job.status = "published"
            await db.flush()

            await db.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
            # Several curated skills can map to one standard -- a job listing
            # both "hand hygiene" and "infection control" needs HSS/N9618 once,
            # not twice. Merge on the strongest signal: the highest importance,
            # and mandatory beats optional. Understating either would weaken a
            # requirement the job actually has.
            merged: dict[uuid.UUID, tuple[int, bool]] = {}
            for sslug, importance, mandatory in skill_rows:
                sid = skills[sslug]
                prev_importance, prev_mandatory = merged.get(sid, (0, False))
                merged[sid] = (
                    max(importance, prev_importance),
                    mandatory or prev_mandatory,
                )
            for sid, (importance, mandatory) in merged.items():
                db.add(
                    JobSkill(
                        job_id=job.id,
                        skill_id=sid,
                        importance=importance,
                        is_mandatory=mandatory,
                    )
                )
                stats["job_skills"] += 1

        for (
            slug,
            tslug,
            t_en,
            t_hi,
            d_en,
            d_hi,
            mode,
            lang,
            hours,
            fee,
            nsqf,
            skill_rows,
        ) in COURSES:
            course = await db.scalar(select(Course).where(Course.slug == slug))
            if course is None:
                course = Course(slug=slug)
                db.add(course)
                stats["courses"] += 1
            course.tenant_id = tenants[tslug].id
            course.title, course.description = t_en, d_en
            await _translate(db, "course", course, {"title": t_hi, "description": d_hi})
            course.mode, course.language = mode, lang
            course.duration_hours, course.fee_inr = hours, fee
            course.nsqf_level = nsqf
            course.status = "published"
            await db.flush()

            await db.execute(delete(CourseSkill).where(CourseSkill.course_id == course.id))
            # Same collapse as jobs: keep the highest level taught, since a
            # course covering a standard to level 4 in one module and level 3 in
            # another does take the learner to 4.
            taught: dict[uuid.UUID, int | None] = {}
            for sslug, level in skill_rows:
                sid = skills[sslug]
                if sid not in taught or (level or 0) > (taught[sid] or 0):
                    taught[sid] = level
            for sid, level in taught.items():
                db.add(CourseSkill(course_id=course.id, skill_id=sid, level_taught=level))
                stats["course_skills"] += 1

        await db.commit()

    await dispose_engine()
    return stats


if __name__ == "__main__":
    r = asyncio.run(seed())
    print(
        f"tenants created: {r['tenants']}  owner accounts created: {r['owners']}  "
        f"teammates added: {r['teammates']}  invitations pending: {r['invitations']}  "
        f"jobs created: {r['jobs']}  "
        f"courses created: {r['courses']}  "
        f"job-skill links: {r['job_skills']}  course-skill links: {r['course_skills']}"
    )
