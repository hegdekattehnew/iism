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
