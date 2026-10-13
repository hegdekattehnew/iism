"""What day it is in India.

Course start dates, closing dates and "started" are facts about a calendar day in the learner's own
time zone, not UTC: between 18:30 and midnight UTC the day in Delhi has already turned. One
function, so no module computes its own and drifts by a day at the edges. Pure code takes the date
as a parameter; this is read at the service boundary.
"""

from datetime import UTC, date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(UTC).astimezone(IST).date()
