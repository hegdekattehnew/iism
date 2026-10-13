"""Sending us a message, and answering it (Sprint 57, BL-14.3, ADR-067).

The rules are here, each in one function, because a public endpoint that writes a row has more ways
to go wrong than a form suggests:

* **Who may send what** (`_may_send`): a data request is the account's, nobody else's.
* **No relay** (`submit`): the address a stranger types is shown to the operator and **never mailed
  by us**. An anonymous form that emails whatever address it is handed is a way to harass somebody
  else. Only a signed-in sender, at the address their own account already holds, is written to.
* **A budget and a honeypot** (`submit`): the form is public, so it is a spam sink unless somebody
  says how much.
* **A promise that can be measured** (`_overdue`): the grievance page says acknowledged within a
  day, resolved within fifteen; the queue reads the same two settings, so the page and the badge
  cannot disagree.
* **A state machine that does not go back** (`_close`, `acknowledge`): open, acknowledged, then
  resolved or dismissed, and a closed one is final.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException, status
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.notifications import get_email_provider
from api.core.config import get_settings
from api.core.redaction import mask_email, mask_phone
from api.core.security import enforce_budget
from api.modules.grievances.models import CLOSED, Grievance
from api.modules.grievances.schemas import (
    GrievanceAccountOut,
    GrievanceIn,
    GrievanceQueueItem,
    GrievanceQueueOut,
    GrievanceSubmittedOut,
)
from api.modules.identity.models import User
from api.modules.notifications import enqueue

log = structlog.get_logger("iism.grievances")

# No 0, O, 1, I or L: a reference is read aloud and copied by hand.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _new_reference() -> str:
    return "GRV-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


def _may_send(kind: str, user: User | None, reply_to: str | None) -> None:
    if kind == "data_request" and user is None:
        # 401, not 422: the fix is to sign in. The account is the proof of who is asking, and a
        # stranger asking to see or erase somebody's data is the attack this exists to stop.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in to make a request about your data, so we know it is you asking.",
        )
    if user is None and reply_to is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Give an email address or a mobile number we can write back to.",
        )


_ACK_SUBJECT = {
    "en": "We have your message ({reference})",
    "hi": "हमें आपका संदेश मिल गया ({reference})",
}
_ACK_BODY = {
    "en": (
        "We received your message. Its reference is {reference}; quote it if you write to us "
        "again.\n\nWe acknowledge it within {hours} hours and aim to resolve it within {days} "
        "days. You will see where it stands on the grievance page when you are signed in.\n\n"
        "If you did not write to us, you can ignore this."
    ),
    "hi": (
        "हमें आपका संदेश मिल गया। इसका संदर्भ {reference} है; दोबारा लिखें तो इसे बताएँ।\n\n"
        "हम इसे {hours} घंटे के भीतर स्वीकार करते हैं और {days} दिन में हल करने का प्रयास करते हैं। "
        "साइन इन करने पर आप शिकायत पृष्ठ पर देख सकते हैं कि यह कहाँ पहुँचा।\n\n"
        "अगर आपने हमें नहीं लिखा, तो इसे अनदेखा कर सकते हैं।"
    ),
}


async def _acknowledge_by_email(user: User, reference: str, locale: str) -> None:
    """Best effort, and only to the address the account already holds and has proved.

    Never to an address somebody typed into the form (see the module's no-relay rule), and never
    a reason for the message to fail: it is already stored and the sender already has the
    reference on screen.
    """
    if not user.email or user.email_verified_at is None:
        return
    settings = get_settings()
    lang = locale if locale in _ACK_SUBJECT else "en"
    try:
        await get_email_provider().send_email(
            user.email,
            _ACK_SUBJECT[lang].format(reference=reference),
            _ACK_BODY[lang].format(
                reference=reference,
                hours=settings.grievance_acknowledge_hours,
                days=settings.grievance_resolve_days,
            ),
        )
    except Exception:  # noqa: BLE001 - an acknowledgement must never undo the message
        log.warning("grievance.acknowledgement_failed", reference=reference)


async def submit(
    db: AsyncSession,
    payload: GrievanceIn,
    *,
    user: User | None,
    client: str,
    locale: str,
) -> GrievanceSubmittedOut:
    settings = get_settings()
    done = GrievanceSubmittedOut(
        reference="",
        kind=payload.kind,
        acknowledge_within_hours=settings.grievance_acknowledge_hours,
        resolve_within_days=settings.grievance_resolve_days,
    )

    if payload.website:
        # A person never sees this field. Answer as though it worked, so the bot learns nothing,
        # and keep nothing.
        log.info("grievance.honeypot", kind=payload.kind)
        done.reference = _new_reference()
        return done

    _may_send(payload.kind, user, payload.reply_to)

    # Per address, and per account or reply address: carrier-grade NAT puts many strangers behind
    # one address, so the second budget stops one person without throttling their neighbours.
    limit, window = settings.grievance_submissions_per_hour, 3600
    await enforce_budget(
        "grievance-ip", client, limit=limit, window_seconds=window, noun="messages"
    )
    who = f"user:{user.id}" if user is not None else f"reply:{payload.reply_to}"
    await enforce_budget("grievance-who", who, limit=limit, window_seconds=window, noun="messages")

    for _ in range(5):
        reference = _new_reference()
        grievance = Grievance(
            reference=reference,
            kind=payload.kind,
            body=payload.body,
            user_id=user.id if user is not None else None,
            # A signed-in sender is answered through their account; keeping a second copy of an
            # address we already hold would be data kept for nothing.
            reply_to=None if user is not None else payload.reply_to,
            locale=locale,
        )
        try:
            async with db.begin_nested():
                db.add(grievance)
            break
        except IntegrityError:  # the reference was taken a moment ago: draw another
            continue
    else:  # pragma: no cover - 32**6 references, five draws
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Try again in a moment.")
    await db.commit()

    # No body, no address: the reference and the kind are what an operator needs from a log line.
    log.info("grievance.received", reference=reference, kind=payload.kind)
    if user is not None:
        await _acknowledge_by_email(user, reference, locale)
    done.reference = reference
    return done


async def mine(db: AsyncSession, user: User) -> list[Grievance]:
    return list(
        (
            await db.scalars(
                select(Grievance)
                .where(Grievance.user_id == user.id)
                .order_by(Grievance.created_at.desc())
                .limit(50)
            )
        ).all()
    )


# ---------------------------------------------------------------- the operator's side


def _overdue(grievance: Grievance, now: datetime) -> tuple[bool, bool]:
    """Against what the grievance page promises. A contact message promises nothing, and a
    closed one is no longer late."""
    if grievance.kind == "contact" or grievance.status in CLOSED:
        return False, False
    settings = get_settings()
    age = now - grievance.created_at
    late_ack = grievance.status == "open" and age > timedelta(
        hours=settings.grievance_acknowledge_hours
    )
    late_resolve = age > timedelta(days=settings.grievance_resolve_days)
    return late_ack, late_resolve


def _item(grievance: Grievance, user: User | None, now: datetime) -> GrievanceQueueItem:
    late_ack, late_resolve = _overdue(grievance, now)
    account = None
    if user is not None:
        account = GrievanceAccountOut(
            phone=mask_phone(user.phone) if user.phone else None,
            email=mask_email(user.email) if user.email else None,
        )
    return GrievanceQueueItem(
        id=grievance.id,
        reference=grievance.reference,
        kind=grievance.kind,
        status=grievance.status,
        body=grievance.body,
        reply_to=grievance.reply_to,
        account=account,
        created_at=grievance.created_at,
        acknowledged_at=grievance.acknowledged_at,
        resolved_at=grievance.resolved_at,
        resolution_note=grievance.resolution_note,
        overdue_acknowledge=late_ack,
        overdue_resolve=late_resolve,
    )


async def queue(db: AsyncSession, *, status_filter: str | None, limit: int) -> GrievanceQueueOut:
    """Open first, and oldest first within a status: the one that has waited longest is the one
    that is nearest to breaking the page's promise."""
    now = datetime.now(UTC)
    query = select(Grievance, User).outerjoin(User, User.id == Grievance.user_id)
    if status_filter:
        query = query.where(Grievance.status == status_filter)
    # `open` before `acknowledged` is not alphabetical, so say it.
    order = case(
        {"open": 0, "acknowledged": 1, "resolved": 2, "dismissed": 3},
        value=Grievance.status,
        else_=9,
    )
    rows = (await db.execute(query.order_by(order, Grievance.created_at).limit(limit))).all()
    items = [_item(g, u, now) for g, u in rows]
    live = Grievance.status.in_(("open", "acknowledged"))
    settings = get_settings()
    late = (Grievance.kind != "contact") & (
        (Grievance.created_at < now - timedelta(days=settings.grievance_resolve_days))
        | (
            (Grievance.status == "open")
            & (Grievance.created_at < now - timedelta(hours=settings.grievance_acknowledge_hours))
        )
    )
    open_count = await db.scalar(select(func.count()).select_from(Grievance).where(live))
    overdue = await db.scalar(select(func.count()).select_from(Grievance).where(live, late))
    return GrievanceQueueOut(items=items, open=open_count or 0, overdue=overdue or 0)


async def _for_decision(db: AsyncSession, grievance_id: uuid.UUID) -> Grievance:
    grievance = await db.scalar(
        select(Grievance).where(Grievance.id == grievance_id).with_for_update()
    )
    if grievance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    return grievance


async def acknowledge(db: AsyncSession, grievance_id: uuid.UUID, *, actor: User) -> Grievance:
    grievance = await _for_decision(db, grievance_id)
    if grievance.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already {grievance.status}.")
    grievance.status = "acknowledged"
    grievance.acknowledged_at = datetime.now(UTC)
    grievance.handled_by_user_id = actor.id
    await _notify(db, grievance)
    await db.commit()
    return grievance


async def close(
    db: AsyncSession, grievance_id: uuid.UUID, *, outcome: str, note: str, actor: User
) -> Grievance:
    assert outcome in CLOSED
    grievance = await _for_decision(db, grievance_id)
    if grievance.status in CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already {grievance.status}.")
    now = datetime.now(UTC)
    grievance.status = outcome
    grievance.resolved_at = now
    # Closing an open one acknowledges it: it cannot have been decided without being seen.
    grievance.acknowledged_at = grievance.acknowledged_at or now
    grievance.resolution_note = note
    grievance.handled_by_user_id = actor.id
    await _notify(db, grievance)
    await db.commit()
    return grievance


async def _notify(db: AsyncSession, grievance: Grievance) -> None:
    if grievance.user_id is None:
        return
    await enqueue(
        db,
        recipient_kind="user",
        recipient_id=grievance.user_id,
        channel="in_app",
        template="grievance_update",
        # The reference and where it stands: not the operator's note, which is the operator's
        # evidence and may name other people.
        payload={"reference": grievance.reference, "status": grievance.status},
        locale=grievance.locale,
    )


# ------------------------------------------------------------ retention and the person's rights


async def purge_expired(db: AsyncSession, *, retention_days: int) -> int:
    """Delete a closed grievance a year after it was closed. An open one is never deleted, however
    old: it is still owed an answer."""
    result = await db.execute(
        delete(Grievance).where(
            Grievance.status.in_(CLOSED),
            Grievance.resolved_at < func.now() - timedelta(days=retention_days),
        )
    )
    await db.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def export_for_user(db: AsyncSession, user: User) -> list[dict[str, object]]:
    """What the person wrote and where each stands. The operator's note is the operator's act and
    stays out, the way a verification note does."""
    return [
        {
            "reference": g.reference,
            "kind": g.kind,
            "message": g.body,
            "status": g.status,
            "sent_at": g.created_at.isoformat(),
            "acknowledged_at": g.acknowledged_at.isoformat() if g.acknowledged_at else None,
            "closed_at": g.resolved_at.isoformat() if g.resolved_at else None,
        }
        for g in await mine(db, user)
    ]


async def erase_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Explicitly, like every table the privacy service empties: not trusting a cascade."""
    await db.execute(delete(Grievance).where(Grievance.user_id == user_id))
