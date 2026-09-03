"""Seed the skill taxonomy.

Idempotent: re-running updates existing rows by slug and replaces their aliases,
so this can be run repeatedly without duplicating anything. That property matters
more than it looks — the real NSQF importer must behave the same way, because
Qualification Packs get revised and re-issued.

Sectors here are Healthcare (HSSC) and Retail (RASCI) plus cross-sector core
skills. The taxonomy itself is sector-agnostic (ADR-024); these are simply the
first sectors seeded.

    make seed
"""

import asyncio

from sqlalchemy import delete, select

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.skills.models import Skill, SkillAlias

# slug, en, hi, desc_en, desc_hi, type, nsqf, [(alias, script)]
# script: l = latin, d = devanagari, t = transliteration (Hindi in Latin script)
SKILLS: list[tuple] = [
    # ---------------------------------------------------------- healthcare
    (
        "patient-mobility-support",
        "Patient mobility support",
        "रोगी की गतिशीलता में सहायता",
        "Helping patients move, walk and change position safely.",
        "रोगियों को सुरक्षित रूप से चलने, हिलने-डुलने और स्थिति बदलने में सहायता करना।",
        "technical",
        3,
        [
            ("mobility assistance", "l"),
            ("रोगी सहायता", "d"),
            ("rogi sahayata", "t"),
            ("chalne mein madad", "t"),
        ],
    ),
    (
        "vital-signs-measurement",
        "Vital signs measurement",
        "महत्वपूर्ण संकेतों का मापन",
        "Measuring and recording pulse, temperature, respiration and blood pressure.",
        "नाड़ी, तापमान, श्वसन और रक्तचाप मापना और दर्ज करना।",
        "technical",
        4,
        [("vitals", "l"), ("महत्वपूर्ण संकेत", "d"), ("vital sign lena", "t")],
    ),
    (
        "blood-sample-collection",
        "Blood sample collection",
        "रक्त नमूना संग्रह",
        "Drawing venous blood samples safely and labelling them correctly.",
        "सुरक्षित रूप से शिरा से रक्त लेना और सही ढंग से लेबल लगाना।",
        "technical",
        4,
        [("phlebotomy", "l"), ("रक्त संग्रह", "d"), ("khoon nikalna", "t"), ("blood test lena", "t")],
    ),
    (
        "infection-control",
        "Infection control",
        "संक्रमण नियंत्रण",
        "Preventing the spread of infection in clinical settings.",
        "नैदानिक परिवेश में संक्रमण के प्रसार को रोकना।",
        "technical",
        4,
        [("संक्रमण रोकथाम", "d"), ("sankraman niyantran", "t")],
    ),
    (
        "hand-hygiene",
        "Hand hygiene",
        "हाथ की स्वच्छता",
        "Correct handwashing and sanitisation procedure.",
        "हाथ धोने और सैनिटाइज़ करने की सही प्रक्रिया।",
        "core",
        2,
        [("handwashing", "l"), ("हाथ धोना", "d"), ("haath dhona", "t")],
    ),
    (
        "biomedical-waste-handling",
        "Biomedical waste handling",
        "जैव-चिकित्सा अपशिष्ट प्रबंधन",
        "Segregating and disposing of clinical waste by category.",
        "श्रेणी के अनुसार चिकित्सा अपशिष्ट को अलग करना और निपटाना।",
        "technical",
        3,
        [("waste segregation", "l"), ("बायोमेडिकल कचरा", "d"), ("kachra prabandhan", "t")],
    ),
    (
        "patient-bathing-assistance",
        "Patient bathing and grooming",
        "रोगी स्नान एवं साज-सज्जा",
        "Assisting patients with bathing, oral care and grooming.",
        "रोगियों को स्नान, मुख देखभाल और साज-सज्जा में सहायता करना।",
        "technical",
        3,
        [("sponge bath", "l"), ("रोगी स्नान", "d"), ("snan karana", "t")],
    ),
    (
        "bed-making",
        "Bed making",
        "बिस्तर बनाना",
        "Making occupied and unoccupied hospital beds.",
        "खाली और भरे हुए अस्पताल बिस्तर तैयार करना।",
        "technical",
        2,
        [("बिस्तर तैयार करना", "d"), ("bistar banana", "t")],
    ),
    (
        "wound-dressing",
        "Wound dressing",
        "घाव की ड्रेसिंग",
        "Cleaning and dressing wounds using aseptic technique.",
        "रोगाणुरहित तकनीक से घाव साफ़ करना और पट्टी करना।",
        "technical",
        4,
        [("bandaging", "l"), ("पट्टी करना", "d"), ("ghav ki dressing", "t"), ("patti karna", "t")],
    ),
    (
        "medication-administration",
        "Medication administration",
        "दवा देना",
        "Giving prescribed medication by the correct route and dose.",
        "निर्धारित दवा सही मार्ग और मात्रा में देना।",
        "technical",
        5,
        [("दवा वितरण", "d"), ("dawa dena", "t"), ("medicine dena", "t")],
    ),
    (
        "injection-administration",
        "Injection administration",
        "इंजेक्शन लगाना",
        "Administering intramuscular and subcutaneous injections.",
        "इंट्रामस्क्युलर और सबक्यूटेनियस इंजेक्शन लगाना।",
        "technical",
        4,
        [("injections", "l"), ("सुई लगाना", "d"), ("injection lagana", "t"), ("sui lagana", "t")],
    ),
    (
        "iv-cannulation",
        "IV cannulation",
        "शिरा में कैनुला लगाना",
        "Inserting and securing an intravenous cannula.",
        "नस में कैनुला डालना और सुरक्षित करना।",
        "technical",
        5,
        [("intravenous cannulation", "l"), ("आईवी कैनुला", "d"), ("iv lagana", "t")],
    ),
    (
        "catheter-care",
        "Catheter care",
        "कैथेटर देखभाल",
        "Maintaining urinary catheters and monitoring output.",
        "मूत्र कैथेटर का रखरखाव और आउटपुट की निगरानी।",
        "technical",
        4,
        [("catheterisation", "l"), ("कैथेटर", "d"), ("catheter dekhbhal", "t")],
    ),
    (
        "oxygen-therapy-support",
        "Oxygen therapy support",
        "ऑक्सीजन थेरेपी सहायता",
        "Setting up and monitoring oxygen delivery devices.",
        "ऑक्सीजन उपकरण लगाना और निगरानी करना।",
        "technical",
        4,
        [("ऑक्सीजन देना", "d"), ("oxygen lagana", "t")],
    ),
    (
        "basic-life-support",
        "Basic life support",
        "बुनियादी जीवन रक्षा",
        "Recognising arrest and providing immediate life support.",
        "हृदयाघात पहचानना और तत्काल जीवन रक्षा प्रदान करना।",
        "technical",
        4,
        [("BLS", "l"), ("जीवन रक्षा", "d"), ("jeevan raksha", "t")],
    ),
    (
        "cpr",
        "Cardiopulmonary resuscitation",
        "कार्डियोपल्मोनरी पुनर्जीवन",
        "Performing chest compressions and rescue breaths.",
        "छाती पर दबाव और कृत्रिम श्वास देना।",
        "technical",
        4,
        [("CPR", "l"), ("सीपीआर", "d"), ("cpr dena", "t")],
    ),
    (
        "first-aid",
        "First aid",
        "प्राथमिक चिकित्सा",
        "Providing immediate care for injury or sudden illness.",
        "चोट या अचानक बीमारी में तत्काल देखभाल देना।",
        "core",
        3,
        [("प्राथमिक उपचार", "d"), ("prathmik chikitsa", "t"), ("first aid dena", "t")],
    ),
    (
        "patient-positioning",
        "Patient positioning",
        "रोगी की स्थिति निर्धारण",
        "Positioning patients to prevent pressure injury and aid comfort.",
        "दबाव घाव रोकने और आराम के लिए रोगी की स्थिति बदलना।",
        "technical",
        3,
        [("रोगी को लिटाना", "d"), ("rogi ki sthiti", "t")],
    ),
    (
        "specimen-labelling",
        "Specimen labelling and transport",
        "नमूना लेबलिंग एवं परिवहन",
        "Labelling, storing and transporting clinical specimens.",
        "नैदानिक नमूनों पर लेबल लगाना, रखना और भेजना।",
        "technical",
        3,
        [("sample handling", "l"), ("नमूना संभालना", "d"), ("sample bhejna", "t")],
    ),
    (
        "medical-record-keeping",
        "Medical record keeping",
        "चिकित्सा अभिलेख रखरखाव",
        "Maintaining accurate and confidential patient records.",
        "रोगी के सटीक और गोपनीय अभिलेख बनाए रखना।",
        "technical",
        4,
        [("patient records", "l"), ("मरीज़ रिकॉर्ड", "d"), ("record rakhna", "t")],
    ),
    (
        "sterilisation-of-instruments",
        "Sterilisation of instruments",
        "उपकरणों का रोगाणुनाशन",
        "Cleaning, autoclaving and storing surgical instruments.",
        "शल्य उपकरणों की सफ़ाई, ऑटोक्लेविंग और भंडारण।",
        "technical",
        4,
        [("autoclaving", "l"), ("उपकरण सफ़ाई", "d"), ("upkaran safai", "t")],
    ),
    (
        "medical-equipment-handling",
        "Medical equipment handling",
        "चिकित्सा उपकरण संचालन",
        "Operating and checking routine ward equipment safely.",
        "वार्ड के उपकरण सुरक्षित रूप से चलाना और जाँचना।",
        "technical",
        4,
        [("उपकरण संचालन", "d"), ("machine chalana", "t")],
    ),
    (
        "elderly-care",
        "Elderly care",
        "वृद्ध देखभाल",
        "Supporting the daily needs of older patients.",
        "वृद्ध रोगियों की दैनिक आवश्यकताओं में सहायता।",
        "technical",
        3,
        [("geriatric care", "l"), ("बुज़ुर्ग देखभाल", "d"), ("budhon ki dekhbhal", "t")],
    ),
    (
        "nutrition-and-feeding-support",
        "Nutrition and feeding support",
        "पोषण एवं आहार सहायता",
        "Assisting with feeding and monitoring dietary intake.",
        "भोजन में सहायता करना और आहार की निगरानी करना।",
        "technical",
        3,
        [("आहार सहायता", "d"), ("khana khilana", "t")],
    ),
    (
        "ambulation-assistance",
        "Ambulation assistance",
        "चलने में सहायता",
        "Helping patients walk safely, with or without aids.",
        "रोगियों को सुरक्षित रूप से चलने में सहायता करना।",
        "technical",
        3,
        [("walking support", "l"), ("चलाना", "d"), ("chalne mein sahayata", "t")],
    ),
    (
        "patient-transfer-techniques",
        "Patient transfer techniques",
        "रोगी स्थानांतरण तकनीक",
        "Moving patients between bed, chair and trolley safely.",
        "रोगी को बिस्तर, कुर्सी और ट्रॉली के बीच सुरक्षित ले जाना।",
        "technical",
        4,
        [("shifting", "l"), ("रोगी स्थानांतरण", "d"), ("shift karna", "t")],
    ),
    (
        "temperature-monitoring",
        "Temperature monitoring",
        "तापमान निगरानी",
        "Measuring and charting body temperature accurately.",
        "शरीर का तापमान सही ढंग से मापना और दर्ज करना।",
        "technical",
        2,
        [("बुखार नापना", "d"), ("bukhar napna", "t")],
    ),
    (
        "blood-pressure-measurement",
        "Blood pressure measurement",
        "रक्तचाप मापन",
        "Measuring blood pressure with a sphygmomanometer.",
        "स्फिग्मोमैनोमीटर से रक्तचाप मापना।",
        "technical",
        3,
        [("BP measurement", "l"), ("बीपी नापना", "d"), ("bp napna", "t")],
    ),
    (
        "ecg-recording",
        "ECG recording",
        "ईसीजी रिकॉर्डिंग",
        "Placing leads and recording a diagnostic-quality ECG.",
        "लीड लगाकर निदान-योग्य ईसीजी रिकॉर्ड करना।",
        "technical",
        5,
        [("EKG", "l"), ("ईसीजी", "d"), ("ecg karna", "t")],
    ),
    (
        "laboratory-safety",
        "Laboratory safety",
        "प्रयोगशाला सुरक्षा",
        "Following safety protocol when handling reagents and samples.",
        "अभिकर्मकों और नमूनों के साथ सुरक्षा नियमों का पालन।",
        "core",
        4,
        [("lab safety", "l"), ("लैब सुरक्षा", "d"), ("lab suraksha", "t")],
    ),
    (
        "microscope-operation",
        "Microscope operation",
        "सूक्ष्मदर्शी संचालन",
        "Preparing slides and operating a light microscope.",
        "स्लाइड तैयार करना और सूक्ष्मदर्शी चलाना।",
        "technical",
        4,
        [("microscopy", "l"), ("माइक्रोस्कोप", "d"), ("microscope chalana", "t")],
    ),
    (
        "urine-sample-analysis",
        "Urine sample analysis",
        "मूत्र नमूना विश्लेषण",
        "Performing routine urinalysis and recording results.",
        "नियमित मूत्र जाँच करना और परिणाम दर्ज करना।",
        "technical",
        4,
        [("urinalysis", "l"), ("पेशाब जाँच", "d"), ("urine test", "t")],
    ),
    (
        "patient-counselling",
        "Patient counselling",
        "रोगी परामर्श",
        "Explaining care instructions clearly and with empathy.",
        "देखभाल के निर्देश स्पष्ट और सहानुभूति से समझाना।",
        "core",
        5,
        [("रोगी को समझाना", "d"), ("rogi ko samjhana", "t")],
    ),
    (
        "hospital-front-desk-operations",
        "Hospital front desk operations",
        "अस्पताल स्वागत कक्ष संचालन",
        "Registration, appointments and patient enquiries.",
        "पंजीकरण, अपॉइंटमेंट और रोगी पूछताछ।",
        "technical",
        3,
        [("reception", "l"), ("रिसेप्शन", "d"), ("front desk", "l")],
    ),
    (
        "emergency-response-coordination",
        "Emergency response coordination",
        "आपातकालीन प्रतिक्रिया समन्वय",
        "Coordinating the ward response to a clinical emergency.",
        "नैदानिक आपात स्थिति में वार्ड की प्रतिक्रिया का समन्वय।",
        "core",
        5,
        [("आपातकालीन प्रबंधन", "d"), ("emergency sambhalna", "t")],
    ),
    # ---------------------------------------------------------------- retail
    (
        "customer-service",
        "Customer service",
        "ग्राहक सेवा",
        "Handling customer needs, questions and complaints.",
        "ग्राहकों की ज़रूरतें, प्रश्न और शिकायतें संभालना।",
        "core",
        3,
        [("customer handling", "l"), ("ग्राहक सेवा", "d"), ("grahak seva", "t")],
    ),
    (
        "billing-and-invoicing",
        "Billing and invoicing",
        "बिलिंग एवं चालान",
        "Preparing accurate bills and issuing invoices.",
        "सही बिल बनाना और चालान जारी करना।",
        "technical",
        3,
        [("billing", "l"), ("बिल बनाना", "d"), ("bill banana", "t")],
    ),
    (
        "pos-operation",
        "Point of sale operation",
        "पॉइंट ऑफ़ सेल संचालन",
        "Operating POS terminals for sales and returns.",
        "बिक्री और वापसी के लिए पीओएस टर्मिनल चलाना।",
        "technical",
        3,
        [("POS", "l"), ("बिलिंग मशीन", "d"), ("pos chalana", "t")],
    ),
    (
        "inventory-management",
        "Inventory management",
        "सूची प्रबंधन",
        "Tracking stock levels, receipts and issues.",
        "स्टॉक स्तर, प्राप्ति और निर्गम का लेखा रखना।",
        "technical",
        4,
        [("stock management", "l"), ("स्टॉक प्रबंधन", "d"), ("stock sambhalna", "t")],
    ),
    (
        "stock-replenishment",
        "Stock replenishment",
        "स्टॉक पुनःपूर्ति",
        "Restocking shelves and maintaining shelf availability.",
        "अलमारियों में सामान भरना और उपलब्धता बनाए रखना।",
        "technical",
        2,
        [("restocking", "l"), ("माल भरना", "d"), ("maal bharna", "t")],
    ),
    (
        "visual-merchandising",
        "Visual merchandising",
        "विज़ुअल मर्चेंडाइजिंग",
        "Arranging displays to present products attractively.",
        "उत्पादों को आकर्षक ढंग से प्रदर्शित करना।",
        "technical",
        4,
        [("display", "l"), ("सजावट", "d"), ("display lagana", "t")],
    ),
    (
        "cash-handling",
        "Cash handling",
        "नकदी प्रबंधन",
        "Handling cash, float and end-of-day reconciliation.",
        "नकदी, फ़्लोट और दिन के अंत का मिलान संभालना।",
        "technical",
        3,
        [("cash counter", "l"), ("नकद संभालना", "d"), ("cash sambhalna", "t")],
    ),
    (
        "product-demonstration",
        "Product demonstration",
        "उत्पाद प्रदर्शन",
        "Demonstrating product features to customers.",
        "ग्राहकों को उत्पाद की विशेषताएँ दिखाना।",
        "core",
        3,
        [("demo", "l"), ("उत्पाद दिखाना", "d"), ("product dikhana", "t")],
    ),
    (
        "upselling-and-cross-selling",
        "Upselling and cross-selling",
        "अपसेलिंग एवं क्रॉस-सेलिंग",
        "Recommending higher-value or complementary products.",
        "अधिक मूल्य या पूरक उत्पादों की सिफ़ारिश करना।",
        "core",
        4,
        [("upselling", "l"), ("अधिक बिक्री", "d"), ("zyada bechna", "t")],
    ),
    # ---------------------------------------------------------- cross-sector
    (
        "spoken-english",
        "Spoken English",
        "अंग्रेज़ी बोलना",
        "Communicating clearly in spoken English at work.",
        "कार्यस्थल पर अंग्रेज़ी में स्पष्ट संवाद करना।",
        "generic",
        3,
        [("english speaking", "l"), ("अंग्रेजी बोलना", "d"), ("english bolna", "t")],
    ),
    (
        "basic-computer-operation",
        "Basic computer operation",
        "बुनियादी कंप्यूटर संचालन",
        "Using a computer for everyday workplace tasks.",
        "रोज़मर्रा के कार्यों के लिए कंप्यूटर चलाना।",
        "generic",
        3,
        [("computer basics", "l"), ("कंप्यूटर चलाना", "d"), ("computer chalana", "t")],
    ),
    (
        "workplace-communication",
        "Workplace communication",
        "कार्यस्थल संचार",
        "Communicating clearly with colleagues and supervisors.",
        "सहकर्मियों और पर्यवेक्षकों से स्पष्ट संवाद करना।",
        "core",
        3,
        [("संवाद कौशल", "d"), ("baat cheet", "t")],
    ),
    (
        "teamwork",
        "Teamwork",
        "टीम वर्क",
        "Working effectively as part of a team.",
        "टीम के हिस्से के रूप में प्रभावी ढंग से काम करना।",
        "core",
        2,
        [("collaboration", "l"), ("टीम में काम", "d"), ("team mein kaam", "t")],
    ),
    (
        "time-management",
        "Time management",
        "समय प्रबंधन",
        "Planning and prioritising work within a shift.",
        "शिफ़्ट के भीतर कार्य की योजना और प्राथमिकता तय करना।",
        "core",
        3,
        [("समय प्रबंधन", "d"), ("samay prabandhan", "t")],
    ),
    (
        "workplace-safety",
        "Workplace safety",
        "कार्यस्थल सुरक्षा",
        "Following safety rules and reporting hazards.",
        "सुरक्षा नियमों का पालन और ख़तरों की सूचना देना।",
        "core",
        3,
        [("occupational safety", "l"), ("सुरक्षा नियम", "d"), ("kaam ki suraksha", "t")],
    ),
    (
        "digital-payments-handling",
        "Digital payments handling",
        "डिजिटल भुगतान प्रबंधन",
        "Accepting and reconciling UPI, card and wallet payments.",
        "यूपीआई, कार्ड और वॉलेट भुगतान लेना और मिलान करना।",
        "technical",
        3,
        [("UPI", "l"), ("डिजिटल भुगतान", "d"), ("online payment lena", "t")],
    ),
    (
        "documentation-and-reporting",
        "Documentation and reporting",
        "प्रलेखन एवं रिपोर्टिंग",
        "Recording work accurately and reporting it on time.",
        "कार्य को सही ढंग से दर्ज करना और समय पर रिपोर्ट करना।",
        "core",
        4,
        [("reporting", "l"), ("रिपोर्ट बनाना", "d"), ("report banana", "t")],
    ),
]

SCRIPT_NAMES = {"l": "latin", "d": "devanagari", "t": "transliteration"}


async def seed() -> tuple[int, int, int]:
    created = updated = alias_count = 0

    async with get_sessionmaker()() as db:
        for slug, en, hi, d_en, d_hi, stype, level, aliases in SKILLS:
            skill = await db.scalar(select(Skill).where(Skill.slug == slug))
            if skill is None:
                skill = Skill(slug=slug)
                db.add(skill)
                created += 1
            else:
                updated += 1

            skill.name_en = en
            skill.name_hi = hi
            skill.description_en = d_en
            skill.description_hi = d_hi
            skill.skill_type = stype
            skill.nsqf_level = level
            await db.flush()

            # Replace rather than merge: the source of truth is this file.
            await db.execute(delete(SkillAlias).where(SkillAlias.skill_id == skill.id))
            seen: set[str] = set()
            for form, script in aliases:
                if form in seen:
                    continue
                seen.add(form)
                db.add(
                    SkillAlias(
                        skill_id=skill.id,
                        surface_form=form,
                        script=SCRIPT_NAMES[script],
                    )
                )
                alias_count += 1

        await db.commit()

    await dispose_engine()
    return created, updated, alias_count


if __name__ == "__main__":
    c, u, a = asyncio.run(seed())
    print(f"skills created: {c}  updated: {u}  aliases: {a}")
