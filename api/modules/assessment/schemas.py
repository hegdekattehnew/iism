from pydantic import BaseModel


class AssessmentWebhookOut(BaseModel):
    """`written` is `True` iff a `CandidateSkill` was added or upgraded.

    A failed assessment attempt is a legitimate, successful call to this
    endpoint that writes nothing -- `written=False` with no error -- not a
    4xx. The route reserves 4xx for a payload this platform cannot act on at
    all: an unparseable body, an unknown candidate, an unknown standard.
    """

    written: bool
    added: int
    updated: int
