"""What an employer sees of an applicant, built in exactly one place (Sprint 60, ADR-070).

`applicant_out` is the **one construction site** for an `ApplicantOut`: the rule that a
candidate's contact details, and the covering note they wrote, disappear the moment they withdraw is
a property of this function and of nothing else. The CSV export is built from the `ApplicantOut`
objects this makes, never from the rows beside it, so a withdrawn applicant is blank in a
spreadsheet for the same reason they are blank on the screen: there was nothing to write.

It lives in its own module, and not in the route file it came from, so the list and the export can
share it without a service importing a route.
"""

import csv
import io
from collections.abc import Sequence
from typing import Any

from api.core.text import csv_safe
from api.modules.applications.schemas import ApplicantOut, ContactOut
from api.modules.matching import candidate_card

CSV_COLUMNS = (
    "reference",
    "name",
    "phone",
    "email",
    "status",
    "score",
    "coverage_percent",
    "missing_mandatory",
    "applied_on",
    "candidate_note",
    "your_message_to_them",
    "your_private_note",
)


def applicant_out(
    application: Any, profile: Any, user: Any, result: Any, reviewed: bool = False
) -> ApplicantOut:
    """One applicant: the de-identified card plus the disclosure beside it."""
    live = application.contact_is_visible
    return ApplicantOut(
        application_id=application.id,
        status=application.status,
        applied_at=application.created_at,
        # The candidate's own words are part of what withdrawing takes back, exactly as
        # `interests.provider_routes._learner` already does.
        message=application.message if live else None,
        reviewed=reviewed,
        candidate=candidate_card(profile, result),
        contact=(
            ContactOut(full_name=user.full_name, phone=user.phone, email=user.email)
            if live
            else None
        ),
        # The employer's own words: theirs to keep after the candidate has gone.
        status_message=application.status_message,
        status_message_at=application.status_message_at,
        notes=application.employer_notes,
        notes_at=application.employer_notes_at,
    )


def applicants_csv(items: Sequence[ApplicantOut]) -> str:
    """The applicants as a spreadsheet, every cell safe to open (`core.text.csv_safe`)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for a in items:
        contact = a.contact
        writer.writerow(
            [
                csv_safe(v)
                for v in (
                    a.candidate.reference,
                    contact.full_name if contact else "",
                    contact.phone if contact else "",
                    contact.email if contact else "",
                    a.status,
                    a.candidate.score,
                    round(a.candidate.coverage * 100),
                    a.candidate.missing_mandatory,
                    a.applied_at.date().isoformat(),
                    a.message or "",
                    a.status_message or "",
                    a.notes or "",
                )
            ]
        )
    return out.getvalue()
