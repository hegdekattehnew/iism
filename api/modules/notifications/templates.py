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
        "organisation_invitation": (
            "You have been invited to join {organisation} on IISM",
            "You have been invited to join {organisation} on IISM as a "
            "{role}.\n\n"
            "Open this link to accept. It expires in seven days, and it works "
            "only once:\n{link}\n\n"
            "If you were not expecting this, you can ignore it -- nothing "
            "happens until you open the link.\n",
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
        "organisation_invitation": (
            "आपको IISM पर {organisation} में शामिल होने का निमंत्रण मिला है",
            "आपको IISM पर {organisation} में {role} के रूप में शामिल होने का "
            "निमंत्रण मिला है।\n\n"
            "स्वीकार करने के लिए यह लिंक खोलें। यह सात दिन में समाप्त हो जाएगा, और "
            "केवल एक बार काम करता है:\n{link}\n\n"
            "यदि आपको इसकी अपेक्षा नहीं थी, तो इसे अनदेखा कर सकते हैं — लिंक खोलने "
            "तक कुछ नहीं होता।\n",
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
