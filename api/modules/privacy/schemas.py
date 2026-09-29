from pydantic import BaseModel


class OrganisationFate(BaseModel):
    slug: str
    name: str
    # Vacancies and courses, published or not, that go with it.
    listings: int


class DeletionPreview(BaseModel):
    """What deleting this account takes with it -- shown *before* confirming.

    `organisations_deleted`: organisations this person is the only member of.
    Nobody else can administer them, so they and their listings are removed.
    `blocked_by`: organisations where others remain but nobody else is an
    owner. Deleting would leave them unowned, so deletion is refused until
    ownership is passed on.
    """

    organisations_deleted: list[OrganisationFate]
    blocked_by: list[OrganisationFate]


class OrganisationDeletionPreview(BaseModel):
    """What deleting **one organisation** takes with it.

    Distinct from `DeletionPreview`, which is about an account. This one is
    the answer to "I made an organisation by mistake, how do I get rid of just
    that?" -- a question the product had no answer to at all until now: there
    was no delete route, and `leave` refuses the only owner, so the sole escape
    was deleting the entire account and every other organisation with it.
    """

    slug: str
    name: str
    tenant_type: str
    jobs: int
    courses: int
    # People who applied or registered interest and will lose that record.
    # Shown because it is the part an owner does not think of, and the part
    # that belongs to somebody else.
    applications: int
    course_interests: int
    # Other members who lose their access. Deleting is still allowed -- it is
    # the owner's organisation -- but not without being told.
    other_members: int
