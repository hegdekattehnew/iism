"""What each notification says, per language.

Kept in Python rather than in `web/src/messages/`: these are sent by the
worker, which never loads the web app's catalogues, and an email whose wording
lives in the frontend is an email nobody can send from a cron job.

**No candidate detail appears in an employer's email.** It says that somebody
applied and links to the inbox; who they are belongs behind the sign-in, which
is where the disclosure ADR-041's sibling rule allows was made.
"""

from typing import Any

# locale -> template -> (subject, body). English is the fallback for any locale
# without an entry -- which today is Malay, deliberately (ADR-041).
TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "en": {
        "application_received": (
            "A new application for {vacancy}",
            "Somebody has applied for {vacancy}.\n\n"
            "Open your applicants to see how they match the standards you asked "
            "for, and how to reach them:\n{link}\n",
        ),
        "application_status_changed": (
            "An update on your application for {vacancy}",
            "{organisation} has moved your application for {vacancy} to: {status}.\n\n"
            "See your applications:\n{link}\n",
        ),
        "application_status_message": (
            "{organisation} left you a message about {vacancy}",
            "{organisation} has moved your application for {vacancy} to: {status}, and left you "
            "a message.\n\n"
            "Read it on your applications page:\n{link}\n",
        ),
        "course_interest_registered": (
            "Somebody is interested in {course}",
            "Somebody has registered interest in {course}.\n\n"
            "Open your interested learners to see how to reach them:\n{link}\n",
        ),
        "batch_interest_registered": (
            "Somebody is interested in a batch of {course}",
            "Somebody has registered interest in a batch of {course} at {centre}.\n\n"
            "Open your batches to see who, and how long they have waited:\n{link}\n",
        ),
        "job_alert": (
            "A new vacancy that matches you: {vacancy}",
            "{organisation} has published {vacancy}, and it matches the "
            "standards on your profile.\n\n"
            "See it and apply:\n{link}\n\n"
            "You can turn these off on your profile.\n",
        ),
        "vacancy_closed": (
            "{vacancy} is no longer taking applications",
            "The vacancy you applied for, {vacancy}, has been closed.\n\n"
            "See your applications:\n{link}\n",
        ),
        "organisation_invitation": (
            "You have been invited to join {organisation} on IISM",
            "You have been invited to join {organisation} on IISM as a "
            "{role}.\n\n"
            "Open this link to accept. It expires in seven days, and it works "
            "only once:\n{link}\n\n"
            "If you were not expecting this, you can ignore it -- nothing "
            "happens until you open the link.\n",
        ),
        # Sprint 43, BL-9.2. No operator note and no address: the note is the
        # operator's evidence, not the organisation's to read here.
        "organisation_verified": (
            "{organisation} is now verified on IISM",
            "{organisation} has been verified on IISM. The Verified badge now "
            "appears next to your organisation's name on its listings, so "
            "candidates and learners can see that we checked who you are.\n\n"
            "See your organisation profile:\n{link}\n",
        ),
        "organisation_verification_revoked": (
            "The Verified badge for {organisation} has been removed",
            "The Verified badge for {organisation} on IISM has been removed. "
            "Your vacancies and courses are still published, but they no longer "
            "carry the badge.\n\n"
            "See your organisation profile:\n{link}\n\n"
            "If you think this is a mistake, please contact the IISM team.\n",
        ),
        # Sprint 95. A centre's own mark says its **address** was checked, which is not what the
        # organisation's Verified badge says, so it has its own words. Addressed to the organisation
        # that runs the centre: a centre has no inbox and no members of its own yet.
        "centre_verified": (
            "The address of {organisation} has been checked on IISM",
            'We checked the address of {organisation} on IISM. The "Address checked" mark now '
            "appears next to it on your organisation's page, so learners can see that this "
            "centre is where you say it is.\n\n"
            "See your centres:\n{link}\n",
        ),
        "centre_verification_revoked": (
            'The "Address checked" mark for {organisation} has been removed',
            'The "Address checked" mark for {organisation} on IISM has been removed. The '
            "centre is still listed, but it no longer carries the mark. If its address changed, "
            "it is checked again once an operator has looked at the new one.\n\n"
            "See your centres:\n{link}\n\n"
            "If you think this is a mistake, please contact the IISM team.\n",
        ),
        "centre_manager_invitation": (
            "You have been asked to run {centre} on IISM",
            "{organisation} has asked you to be the manager of its training centre {centre} "
            "on IISM.\n\n"
            "As manager you can see the centre and keep its address up to date. Open this link "
            "to accept. It expires in seven days, and it works only once:\n{link}\n\n"
            "If you were not expecting this, you can ignore it -- nothing happens until you "
            "open the link.\n",
        ),
        "delivery_requested": (
            "{organisation} has asked to deliver your courses on IISM",
            "{organisation} has asked to deliver some or all of the courses you sell on IISM.\n\n"
            "Open the link to see what it asked for and to answer. Nothing changes until you "
            "approve it:\n{link}\n",
        ),
        "delivery_invited": (
            "{organisation} has authorised you to deliver its courses on IISM",
            "{organisation} has authorised your organisation to deliver some or all of the "
            "courses it sells on IISM. Nothing is expected of you: you can now run its courses at "
            "your centres, and you can end the arrangement at any time.\n\n"
            "See what it covers:\n{link}\n",
        ),
        "delivery_approved": (
            "{organisation} has approved your request to deliver its courses",
            "{organisation} has approved your request to deliver some or all of its courses on "
            "IISM. You can now run those courses at your centres.\n\n"
            "See what it covers:\n{link}\n",
        ),
        "delivery_declined": (
            "{organisation} has closed a delivery request on IISM",
            "{organisation} has closed a request about delivering courses. Nothing changes for "
            "your courses or your centres.\n\n"
            "See your arrangements:\n{link}\n",
        ),
        "delivery_revoked": (
            "{organisation} has ended an arrangement to deliver courses on IISM",
            "{organisation} has ended an arrangement about delivering courses on IISM. No new "
            "batches can be made under it. Classes already running are not stopped.\n\n"
            "See your arrangements:\n{link}\n",
        ),
        "ownership_received": (
            "You are now an owner of {organisation} on IISM",
            "You have been made an owner of {organisation} on IISM. Owners can "
            "manage the team, change the organisation's profile and delete the "
            "organisation.\n\n"
            "See the team:\n{link}\n\n"
            "If you were not expecting this, please contact the previous owner.\n",
        ),
        "grievance_update": (
            "An update on your message {reference}",
            "Your message {reference} is now: {status}.\n\nSee where it stands:\n{link}\n",
        ),
        "listing_removed": (
            "{listing} was removed from IISM",
            'Our team removed "{listing}" from IISM.\n\n'
            "The reason we recorded: {reason}\n\n"
            "It is no longer visible to anyone, and it cannot be published again until we have "
            "restored it. You can still open and edit it:\n{link}\n\n"
            "If you think this is a mistake, please reply to the IISM team and quote the "
            "listing's name.\n",
        ),
        "listing_restored": (
            "{listing} can be published again",
            'We reviewed "{listing}" and restored it. It is saved as a draft: nothing is '
            "visible until you publish it yourself.\n\nOpen it:\n{link}\n",
        ),
    },
    "hi": {
        "application_received": (
            "{vacancy} के लिए एक नया आवेदन",
            "{vacancy} के लिए किसी ने आवेदन किया है।\n\n"
            "यह देखने के लिए कि वे आपके माँगे गए मानकों से कितना मेल खाते हैं, और "
            "उनसे कैसे संपर्क करें, अपने आवेदक खोलें:\n{link}\n",
        ),
        "application_status_changed": (
            "{vacancy} के लिए आपके आवेदन पर अद्यतन",
            "{organisation} ने {vacancy} के लिए आपके आवेदन को इस स्थिति में बदला: {status}।\n\n"
            "अपने आवेदन देखें:\n{link}\n",
        ),
        "application_status_message": (
            "{organisation} ने {vacancy} के बारे में आपके लिए संदेश छोड़ा है",
            "{organisation} ने {vacancy} के लिए आपके आवेदन को इस स्थिति में बदला: {status}, और "
            "आपके लिए एक संदेश छोड़ा है।\n\n"
            "इसे अपने आवेदन पृष्ठ पर पढ़ें:\n{link}\n",
        ),
        "course_interest_registered": (
            "{course} में किसी की रुचि है",
            "{course} में किसी ने रुचि दर्ज की है।\n\n"
            "उनसे कैसे संपर्क करें यह देखने के लिए अपने इच्छुक शिक्षार्थी खोलें:\n{link}\n",
        ),
        "batch_interest_registered": (
            "{course} के एक बैच में किसी की रुचि है",
            "{centre} में {course} के एक बैच में किसी ने रुचि दर्ज की है।\n\n"
            "कौन है और कितने समय से प्रतीक्षा में है, यह देखने के लिए अपने बैच खोलें:\n{link}\n",
        ),
        "job_alert": (
            "आपसे मेल खाती एक नई रिक्ति: {vacancy}",
            "{organisation} ने {vacancy} प्रकाशित की है, और यह आपकी प्रोफ़ाइल के "
            "मानकों से मेल खाती है।\n\n"
            "इसे देखें और आवेदन करें:\n{link}\n\n"
            "आप इन्हें अपनी प्रोफ़ाइल पर बंद कर सकते हैं।\n",
        ),
        "vacancy_closed": (
            "{vacancy} अब आवेदन नहीं ले रही",
            "जिस रिक्ति {vacancy} के लिए आपने आवेदन किया था, वह बंद कर दी गई है।\n\n"
            "अपने आवेदन देखें:\n{link}\n",
        ),
        "organisation_invitation": (
            "आपको IISM पर {organisation} में शामिल होने का निमंत्रण मिला है",
            "आपको IISM पर {organisation} में {role} के रूप में शामिल होने का "
            "निमंत्रण मिला है।\n\n"
            "स्वीकार करने के लिए यह लिंक खोलें। यह सात दिन में समाप्त हो जाएगा, और "
            "केवल एक बार काम करता है:\n{link}\n\n"
            "यदि आपको इसकी अपेक्षा नहीं थी, तो इसे अनदेखा कर सकते हैं — लिंक खोलने "
            "तक कुछ नहीं होता।\n",
        ),
        "organisation_verified": (
            "{organisation} अब IISM पर सत्यापित है",
            "{organisation} को IISM पर सत्यापित कर दिया गया है। अब आपके संगठन के नाम "
            "के आगे उसकी सूचियों पर “सत्यापित” का निशान दिखता है, ताकि उम्मीदवार और "
            "शिक्षार्थी देख सकें कि हमने जाँचा है कि आप कौन हैं।\n\n"
            "अपने संगठन की प्रोफ़ाइल देखें:\n{link}\n",
        ),
        "organisation_verification_revoked": (
            "{organisation} का “सत्यापित” निशान हटा दिया गया है",
            "IISM पर {organisation} का “सत्यापित” निशान हटा दिया गया है। आपकी रिक्तियाँ और "
            "पाठ्यक्रम अब भी प्रकाशित हैं, पर उन पर यह निशान नहीं दिखेगा।\n\n"
            "अपने संगठन की प्रोफ़ाइल देखें:\n{link}\n\n"
            "यदि आपको लगता है कि यह गलती है, तो कृपया IISM टीम से संपर्क करें।\n",
        ),
        "centre_verified": (
            "IISM पर {organisation} का पता जाँच लिया गया है",
            "हमने IISM पर {organisation} का पता जाँच लिया है। अब आपके संगठन के पृष्ठ पर उसके "
            "आगे “पता जाँचा गया” का निशान दिखता है, ताकि शिक्षार्थी देख सकें कि यह केंद्र "
            "वहीं है जहाँ आप बताते हैं।\n\n"
            "अपने केंद्र देखें:\n{link}\n",
        ),
        "centre_verification_revoked": (
            "{organisation} का “पता जाँचा गया” निशान हटा दिया गया है",
            "IISM पर {organisation} का “पता जाँचा गया” निशान हटा दिया गया है। केंद्र अब भी "
            "सूचीबद्ध है, पर उस पर यह निशान नहीं दिखेगा। यदि उसका पता बदला है, तो ऑपरेटर के नया "
            "पता देख लेने पर उसे फिर जाँचा जाता है।\n\n"
            "अपने केंद्र देखें:\n{link}\n\n"
            "यदि आपको लगता है कि यह गलती है, तो कृपया IISM टीम से संपर्क करें।\n",
        ),
        "centre_manager_invitation": (
            "आपसे IISM पर {centre} चलाने के लिए कहा गया है",
            "{organisation} ने IISM पर अपने प्रशिक्षण केंद्र {centre} का प्रबंधक बनने के लिए "
            "आपसे कहा है।\n\n"
            "प्रबंधक के रूप में आप केंद्र देख सकते हैं और उसका पता अद्यतन रख सकते हैं। "
            "स्वीकार करने के लिए यह लिंक खोलें। यह सात दिन में समाप्त हो जाएगा, और केवल एक "
            "बार काम करता है:\n{link}\n\n"
            "यदि आपको इसकी अपेक्षा नहीं थी, तो इसे अनदेखा कर सकते हैं — लिंक खोलने तक कुछ "
            "नहीं होता।\n",
        ),
        "delivery_requested": (
            "{organisation} ने IISM पर आपके पाठ्यक्रम चलाने का अनुरोध किया है",
            "{organisation} ने IISM पर आप जो पाठ्यक्रम बेचते हैं, उनमें से कुछ या सभी को चलाने का "
            "अनुरोध किया है।\n\n"
            "उसने क्या माँगा है यह देखने और जवाब देने के लिए लिंक खोलें। आपके मंज़ूर करने तक "
            "कुछ नहीं बदलता:\n{link}\n",
        ),
        "delivery_invited": (
            "{organisation} ने IISM पर आपको अपने पाठ्यक्रम चलाने के लिए अधिकृत किया है",
            "{organisation} ने IISM पर अपने बेचे जाने वाले पाठ्यक्रमों में से कुछ या सभी को चलाने "
            "के लिए आपके संगठन को अधिकृत किया है। आपसे कुछ अपेक्षित नहीं है: अब आप उसके "
            "पाठ्यक्रम अपने केंद्रों पर चला सकते हैं, और इस व्यवस्था को कभी भी समाप्त कर सकते "
            "हैं।\n\n"
            "देखें कि इसमें क्या शामिल है:\n{link}\n",
        ),
        "delivery_approved": (
            "{organisation} ने अपने पाठ्यक्रम चलाने का आपका अनुरोध मंज़ूर कर लिया है",
            "{organisation} ने IISM पर अपने कुछ या सभी पाठ्यक्रम चलाने का आपका अनुरोध मंज़ूर कर "
            "लिया है। अब आप वे पाठ्यक्रम अपने केंद्रों पर चला सकते हैं।\n\n"
            "देखें कि इसमें क्या शामिल है:\n{link}\n",
        ),
        "delivery_declined": (
            "{organisation} ने IISM पर एक अनुरोध बंद कर दिया है",
            "{organisation} ने पाठ्यक्रम चलाने से जुड़ा एक अनुरोध बंद कर दिया है। आपके पाठ्यक्रमों "
            "या केंद्रों के लिए कुछ नहीं बदलता।\n\n"
            "अपनी व्यवस्थाएँ देखें:\n{link}\n",
        ),
        "delivery_revoked": (
            "{organisation} ने IISM पर पाठ्यक्रम चलाने की एक व्यवस्था समाप्त कर दी है",
            "{organisation} ने IISM पर पाठ्यक्रम चलाने से जुड़ी एक व्यवस्था समाप्त कर दी है। इसके "
            "अंतर्गत नए बैच नहीं बन सकते। चल रही कक्षाएँ रोकी नहीं जातीं।\n\n"
            "अपनी व्यवस्थाएँ देखें:\n{link}\n",
        ),
        "ownership_received": (
            "अब आप IISM पर {organisation} के स्वामी हैं",
            "आपको IISM पर {organisation} का स्वामी बनाया गया है। स्वामी टीम का "
            "प्रबंधन कर सकते हैं, संगठन की प्रोफ़ाइल बदल सकते हैं और संगठन को हटा "
            "सकते हैं।\n\n"
            "टीम देखें:\n{link}\n\n"
            "यदि आपको इसकी अपेक्षा नहीं थी, तो कृपया पिछले स्वामी से संपर्क करें।\n",
        ),
        "grievance_update": (
            "आपके संदेश {reference} की जानकारी",
            "आपका संदेश {reference} अब: {status}।\n\nदेखें कि यह कहाँ पहुँचा:\n{link}\n",
        ),
        "listing_removed": (
            "{listing} को IISM से हटा दिया गया",
            "हमारी टीम ने “{listing}” को IISM से हटा दिया है।\n\n"
            "दर्ज किया गया कारण: {reason}\n\n"
            "यह अब किसी को दिखाई नहीं देता, और हमारे बहाल करने तक इसे फिर प्रकाशित नहीं किया जा "
            "सकता। आप इसे अब भी खोलकर बदल सकते हैं:\n{link}\n\n"
            "यदि आपको लगता है कि यह गलती है, तो कृपया IISM टीम को उत्तर दें और सूची का नाम लिखें।\n",
        ),
        "listing_restored": (
            "{listing} फिर प्रकाशित किया जा सकता है",
            "हमने “{listing}” की समीक्षा की और उसे बहाल कर दिया। वह मसौदे के रूप में सहेजा गया है: "
            "जब तक आप स्वयं प्रकाशित नहीं करते, कुछ भी दिखाई नहीं देगा।\n\nखोलें:\n{link}\n",
        ),
    },
}

DEFAULT_LOCALE = "en"


def render(template: str, locale: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Subject and body, in the recipient's language where we have it.

    Falls back to English rather than failing: a notification nobody receives
    because its language is missing is worse than one in the wrong language.
    """
    catalogue = TEMPLATES.get(locale) or TEMPLATES[DEFAULT_LOCALE]
    subject, body = catalogue.get(template) or TEMPLATES[DEFAULT_LOCALE][template]
    return subject.format(**payload), body.format(**payload)


# ------------------------------------------------------------------------------- push (ADR-075)

# What a push says, per template and language: a fixed string, **never built from the payload**. A
# push is shown on a lock screen and kept by the operating system, so it names no vacancy, no
# organisation, no person and none of an employer's free text (ADR-070's reasoning: a regular
# expression cannot promise to keep a phone number out of free text, so none reaches it). The
# person opens the app to read the rest. A template with no entry here is never pushed.
PUSH_TEXT: dict[str, dict[str, tuple[str, str]]] = {
    "en": {
        "application_status_changed": ("Update on your application", "Open IISM to see it."),
        "application_status_message": ("A message about your application", "Open IISM to read it."),
        "job_alert": ("A new vacancy matches you", "Open IISM to see it."),
        "vacancy_closed": ("A vacancy you applied for has closed", "Open IISM for details."),
        "course_interest_status_changed": (
            "Update on a course you asked about",
            "Open IISM to see it.",
        ),
        "batch_interest_status_changed": (
            "Update on a batch you asked about",
            "Open IISM to see it.",
        ),
        "sponsor_offer": ("An employer has an offer for you", "Open IISM to see it."),
        "grievance_update": ("An update on your message to us", "Open IISM to see it."),
    },
    "hi": {
        "application_status_changed": ("आपके आवेदन पर नई जानकारी", "देखने के लिए IISM खोलें।"),
        "application_status_message": ("आपके आवेदन के बारे में संदेश", "पढ़ने के लिए IISM खोलें।"),
        "job_alert": ("एक नई रिक्ति आपसे मेल खाती है", "देखने के लिए IISM खोलें।"),
        "vacancy_closed": ("जिस रिक्ति में आपने आवेदन किया वह बंद हो गई", "विवरण के लिए IISM खोलें।"),
        "course_interest_status_changed": ("आपके पूछे पाठ्यक्रम पर नई जानकारी", "देखने के लिए IISM खोलें।"),
        "batch_interest_status_changed": ("आपके पूछे बैच पर नई जानकारी", "देखने के लिए IISM खोलें।"),
        "sponsor_offer": ("एक नियोक्ता के पास आपके लिए प्रस्ताव है", "देखने के लिए IISM खोलें।"),
        "grievance_update": ("हमें भेजे आपके संदेश पर जानकारी", "देखने के लिए IISM खोलें।"),
    },
}


def push_text(template: str, locale: str) -> tuple[str, str] | None:
    """Title and body for a push, or `None` for a template that is never pushed. English fills a
    missing language, like `render`."""
    catalogue = PUSH_TEXT.get(locale) or PUSH_TEXT[DEFAULT_LOCALE]
    return catalogue.get(template) or PUSH_TEXT[DEFAULT_LOCALE].get(template)


def in_app_path(value: object) -> str | None:
    """An in-app path from a payload, and nothing else: a push never links off-site (the web's
    `linkOf`). Anything not starting with a single `/` is dropped."""
    if isinstance(value, str) and value.startswith("/") and not value.startswith("//"):
        return value
    return None


def push_data(template: str, payload: dict[str, Any]) -> dict[str, str]:
    """What rides with a push beside its words: the template and an in-app path. Strings only."""
    path = "/grievance" if template == "grievance_update" else in_app_path(payload.get("path"))
    data = {"template": template}
    if path:
        data["path"] = path
    return data
