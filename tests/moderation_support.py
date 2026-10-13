"""Set-up shared by the takedown and report tests (Sprint 59): organisations, published listings,
candidates and operators, all made through the API the way a person would."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity import Tenant
from api.modules.identity.models import User
from api.modules.skills.models import Skill


async def make_skill(db: AsyncSession) -> str:
    n = uuid.uuid4().hex[:8]
    db.add(
        Skill(
            slug=f"mod-skill-{n}",
            name=f"Moderation standard {n}",
            skill_type="technical",
            nsqf_level=Decimal("4"),
            nos_code=f"MOD/N{n}",
            source="nsqf",
        )
    )
    await db.commit()
    return f"mod-skill-{n}"


async def organisation(
    client: AsyncClient, db: AsyncSession, kind: str = "employer"
) -> tuple[dict[str, str], str]:
    address = f"mod-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": f"Moderation Org {uuid.uuid4().hex[:6]}",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/auth/me", headers=headers)).json()
    slug = next(m["tenant"]["slug"] for m in me["memberships"])
    if kind != "employer":
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        tenant.tenant_type = kind
        await db.commit()
    return headers, slug


async def published_job(
    client: AsyncClient, headers: dict[str, str], org: str, skill: str, title: str | None = None
) -> dict[str, object]:
    created = await client.post(
        f"/org/{org}/jobs",
        headers=headers,
        json={
            "title": title or f"Ward assistant {uuid.uuid4().hex[:6]}",
            "skills": [{"skill_slug": skill, "importance": 4, "is_mandatory": True}],
        },
    )
    assert created.status_code == 201, created.text
    slug = created.json()["slug"]
    published = await client.post(f"/org/{org}/jobs/{slug}/publish", headers=headers)
    assert published.status_code == 200, published.text
    return published.json()


async def published_course(
    client: AsyncClient, headers: dict[str, str], org: str, skill: str
) -> dict[str, object]:
    created = await client.post(
        f"/org/{org}/courses",
        headers=headers,
        json={
            "title": f"Sterile technique {uuid.uuid4().hex[:6]}",
            "skills": [{"skill_slug": skill, "level_taught": 4}],
        },
    )
    assert created.status_code == 201, created.text
    slug = created.json()["slug"]
    published = await client.post(f"/org/{org}/courses/{slug}/publish", headers=headers)
    assert published.status_code == 200, published.text
    return published.json()


async def person(client: AsyncClient) -> tuple[dict[str, str], uuid.UUID]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    tokens = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/auth/me", headers=headers)).json()
    return headers, uuid.UUID(me["id"])


async def operator(client: AsyncClient, db: AsyncSession, tier: str = "support") -> dict[str, str]:
    headers, user_id = await person(client)
    user = await db.get(User, user_id)
    assert user is not None
    user.is_staff, user.staff_tier = True, tier
    await db.commit()
    return headers
