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
        "course_interest_registered": (
            "Somebody is interested in {course}",
            "Somebody has registered interest in {course}.\n\n"
            "Open your interested learners to see how to reach them:\n{link}\n",
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
        "course_interest_registered": (
            "{course} में किसी की रुचि है",
            "{course} में किसी ने रुचि दर्ज की है।\n\n"
            "उनसे कैसे संपर्क करें यह देखने के लिए अपने इच्छुक शिक्षार्थी खोलें:\n{link}\n",
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
