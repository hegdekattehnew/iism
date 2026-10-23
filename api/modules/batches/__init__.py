"""Public interface of the batches module (Sprint 98, ADR-103).

A batch is one run of one course at one centre. Depends on identity (the centre and organisation
rows), marketplace's models (the course), delivery (`authorises`, and the `on_ended` hook this
module registers so revoking an arrangement cancels the batches that have not started), analytics
and notifications. Other modules ask it two things -- `live_at_centre` (a centre cannot close from
under a batch) and `live_for_course` (a course cannot be deleted from under one) -- and
`tell_before_deleting` (erasure tells the learners). They import this package, never its service.
"""

from api.modules.batches import service
from api.modules.batches.routes import router
from api.modules.delivery import on_ended

# Delivery must not depend on batches (batches ask it `authorises`; the other direction is a
# cycle), so the dependency is inverted: batches say what must also happen when an approved
# arrangement ends. Registered at import, idempotently, and every entry point that builds the app
# imports this package.
on_ended(service.cancel_on_arrangement_ended)

live_at_centre = service.live_at_centre
live_for_course = service.live_for_course
tell_before_deleting = service.tell_before_deleting

__all__ = ["live_at_centre", "live_for_course", "router", "tell_before_deleting"]
