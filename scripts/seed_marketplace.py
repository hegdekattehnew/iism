"""Seed marketplace inventory: tenants, jobs and courses.

Idempotent by slug, like scripts/seed_skills.py — skill associations are
replaced wholesale on each run so this file stays the source of truth.

Every skill reference is a slug from the taxonomy. A typo fails loudly rather
than silently creating a job with no skills, because a job with no skills is
invisible to matching and the failure would not surface until Sprint 5.

    make seed
"""

import asyncio
import sys

from sqlalchemy import delete, select

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.identity.models import Tenant
from api.modules.marketplace.models import Course, CourseSkill, Job, JobSkill
from api.modules.skills.models import Skill

# slug, name, type, city
TENANTS = [
    ("apollo-care-hospitals", "Apollo Care Hospitals", "employer", "Chennai"),
    ("sunrise-multispeciality", "Sunrise Multispeciality Hospital", "employer", "Pune"),
    ("medlife-diagnostics", "MedLife Diagnostics", "employer", "Hyderabad"),
    ("greenmart-retail", "GreenMart Retail", "employer", "Bengaluru"),
    ("swift-logistics", "Swift Logistics India", "employer", "Nagpur"),
    ("nsdc-healthcare-academy", "NSDC Healthcare Academy", "course_provider", "Delhi"),
    ("skillbridge-institute", "SkillBridge Institute", "course_provider", "Jaipur"),
    ("retail-skills-council-academy", "Retail Skills Academy", "course_provider", "Mumbai"),
]

# slug, tenant, title_en, title_hi, desc_en, desc_hi, state, district,
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

# slug, tenant, title_en, title_hi, desc_en, desc_hi, mode, language,
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
]


async def seed() -> dict[str, int]:
    stats = {
        "tenants": 0,
        "jobs": 0,
        "courses": 0,
        "job_skills": 0,
        "course_skills": 0,
    }

    async with get_sessionmaker()() as db:
        skills = {s.slug: s.id for s in (await db.scalars(select(Skill)))}
        if not skills:
            print("No skills found. Run scripts/seed_skills.py first.", file=sys.stderr)
            raise SystemExit(1)

        # Fail loudly on a bad slug rather than creating skill-less inventory.
        referenced = {sl for j in JOBS for sl, _, _ in j[14]} | {
            sl for c in COURSES for sl, _ in c[11]
        }
        missing = sorted(referenced - skills.keys())
        if missing:
            print(f"Unknown skill slugs: {', '.join(missing)}", file=sys.stderr)
            raise SystemExit(1)

        tenants: dict[str, Tenant] = {}
        for slug, name, ttype, city in TENANTS:
            t = await db.scalar(select(Tenant).where(Tenant.slug == slug))
            if t is None:
                t = Tenant(slug=slug)
                db.add(t)
                stats["tenants"] += 1
            t.name, t.tenant_type, t.city = name, ttype, city
            await db.flush()
            tenants[slug] = t

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
            job.title_en, job.title_hi = t_en, t_hi
            job.description_en, job.description_hi = d_en, d_hi
            job.location_state, job.location_district = state, district
            job.employment_type = etype
            job.experience_min_years, job.experience_max_years = emin, emax
            job.salary_min_inr, job.salary_max_inr = smin, smax
            job.nsqf_level_min = nsqf
            job.status = "published"
            await db.flush()

            await db.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
            for sslug, importance, mandatory in skill_rows:
                db.add(
                    JobSkill(
                        job_id=job.id,
                        skill_id=skills[sslug],
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
            course.title_en, course.title_hi = t_en, t_hi
            course.description_en, course.description_hi = d_en, d_hi
            course.mode, course.language = mode, lang
            course.duration_hours, course.fee_inr = hours, fee
            course.nsqf_level = nsqf
            course.status = "published"
            await db.flush()

            await db.execute(delete(CourseSkill).where(CourseSkill.course_id == course.id))
            for sslug, level in skill_rows:
                db.add(CourseSkill(course_id=course.id, skill_id=skills[sslug], level_taught=level))
                stats["course_skills"] += 1

        await db.commit()

    await dispose_engine()
    return stats


if __name__ == "__main__":
    r = asyncio.run(seed())
    print(
        f"tenants created: {r['tenants']}  jobs created: {r['jobs']}  "
        f"courses created: {r['courses']}  "
        f"job-skill links: {r['job_skills']}  course-skill links: {r['course_skills']}"
    )
