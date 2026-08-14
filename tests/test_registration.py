import io
import logging
import re
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.modules.identity.models import Membership, ServiceAccount, Tenant, User


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def _register_org(client: AsyncClient, path: str, org_name: str) -> dict:
    response = await client.post(
        path,
        json={
            "email": _unique_email(),
            "password": "correct-horse-1",
            "full_name": "Org Admin",
            "organization_name": org_name,
        },
    )
    return response


async def _login_tokens(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    return response.json()


async def _make_super_admin() -> tuple[str, str]:
    email, password = _unique_email(), "super-admin-pw-1"
    async with async_session_factory() as db:
        db.add(
            User(
                email=email,
                full_name="Bootstrapped Super Admin",
                hashed_password=hash_password(password),
                platform_role="super_admin",
                is_email_verified=True,
            )
        )
        await db.commit()
    return email, password


async def _make_platform_admin() -> tuple[str, str]:
    email, password = _unique_email(), "platform-admin-pw-1"
    async with async_session_factory() as db:
        db.add(
            User(
                email=email,
                full_name="Bootstrapped Platform Admin",
                hashed_password=hash_password(password),
                platform_role="admin",
                is_email_verified=True,
            )
        )
        await db.commit()
    return email, password


async def _make_org_owner(tenant_type: str) -> tuple[str, str, uuid.UUID]:
    email, password = _unique_email(), "org-owner-pw-1"
    async with async_session_factory() as db:
        user = User(
            email=email,
            full_name="Org Owner",
            hashed_password=hash_password(password),
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()
        tenant = Tenant(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}", tenant_type=tenant_type)
        db.add(tenant)
        await db.flush()
        db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
        await db.commit()
        tenant_id = tenant.id
    return email, password, tenant_id


@pytest.mark.parametrize(
    ("path", "expected_type"),
    [
        ("/auth/register/employer", "employer"),
        ("/auth/register/course-provider", "course_provider"),
        ("/auth/register/assessment-provider", "assessment_provider"),
    ],
)
async def test_organization_self_registration(client: AsyncClient, path: str, expected_type: str):
    org_name = f"Org {uuid.uuid4().hex[:8]}"
    response = await _register_org(client, path, org_name)
    assert response.status_code == 201
    tokens = response.json()

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    memberships = me.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["role"] == "owner"

    async with async_session_factory() as db:
        tenant = await db.get(Tenant, uuid.UUID(memberships[0]["tenant_id"]))
        assert tenant.tenant_type == expected_type
        assert tenant.name == org_name


async def test_admin_organizations_rejects_non_admin(client: AsyncClient):
    reg = await client.post(
        "/auth/register",
        json={"email": _unique_email(), "password": "correct-horse-1", "full_name": "Plain User"},
    )
    tokens = reg.json()
    response = await client.post(
        "/admin/organizations",
        json={
            "email": _unique_email(),
            "full_name": "Gov Contact",
            "organization_name": "Ministry of Skills",
            "tenant_type": "government_agency",
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


async def test_admin_organizations_and_claim_flow(client: AsyncClient, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="iism.email")
    admin_email, admin_password = await _make_platform_admin()
    tokens = await _login_tokens(client, admin_email, admin_password)

    invite_email = _unique_email()
    response = await client.post(
        "/admin/organizations",
        json={
            "email": invite_email,
            "full_name": "Gov Contact",
            "organization_name": "Ministry of Skills",
            "tenant_type": "government_agency",
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 202

    login_before_claim = await client.post(
        "/auth/login", json={"email": invite_email, "password": "anything"}
    )
    assert login_before_claim.status_code == 401

    match = re.search(r"token=([\w-]+)", caplog.text)
    assert match is not None
    claim_token = match.group(1)

    confirm = await client.post(
        "/auth/claim-account/confirm", json={"token": claim_token, "password": "claimed-pw-1"}
    )
    assert confirm.status_code == 200

    login_after_claim = await client.post(
        "/auth/login", json={"email": invite_email, "password": "claimed-pw-1"}
    )
    assert login_after_claim.status_code == 200

    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.email == invite_email))
        assert user.is_email_verified is True
        membership = await db.scalar(select(Membership).where(Membership.user_id == user.id))
        assert membership.role == "owner"
        tenant = await db.get(Tenant, membership.tenant_id)
        assert tenant.tenant_type == "government_agency"


async def test_admin_staff_requires_super_admin(client: AsyncClient):
    admin_email, admin_password = await _make_platform_admin()
    tokens = await _login_tokens(client, admin_email, admin_password)

    response = await client.post(
        "/admin/staff",
        json={"email": _unique_email(), "full_name": "New Admin", "platform_role": "admin"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


async def test_admin_staff_creation_by_super_admin(client: AsyncClient, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="iism.email")
    super_email, super_password = await _make_super_admin()
    tokens = await _login_tokens(client, super_email, super_password)

    new_admin_email = _unique_email()
    response = await client.post(
        "/admin/staff",
        json={"email": new_admin_email, "full_name": "New Admin", "platform_role": "admin"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 202

    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.email == new_admin_email))
        assert user.platform_role == "admin"
        assert user.hashed_password is None


async def test_bulk_upload_creates_candidates_and_reports_duplicates(client: AsyncClient):
    owner_email, owner_password, tenant_id = await _make_org_owner("employer")
    tokens = await _login_tokens(client, owner_email, owner_password)

    dup_email = _unique_email()
    async with async_session_factory() as db:
        db.add(User(email=dup_email, full_name="Existing Candidate", hashed_password=hash_password("x")))
        await db.commit()

    fresh_email = _unique_email()
    csv_content = f"email,full_name\n{fresh_email},Fresh Candidate\n{dup_email},Dup Candidate\n,Missing Email\n"
    files = {"file": ("candidates.csv", io.BytesIO(csv_content.encode()), "text/csv")}

    response = await client.post(
        "/candidates/bulk-upload",
        files=files,
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "X-Tenant-Id": str(tenant_id),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert len(body["skipped"]) == 2

    async with async_session_factory() as db:
        created_user = await db.scalar(select(User).where(User.email == fresh_email))
        assert created_user is not None
        assert created_user.hashed_password is None


async def test_bulk_upload_rejects_wrong_role(client: AsyncClient):
    owner_email, owner_password, tenant_id = await _make_org_owner("employer")
    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.email == owner_email))
        membership = await db.scalar(select(Membership).where(Membership.user_id == user.id))
        membership.role = "member"
        await db.commit()

    tokens = await _login_tokens(client, owner_email, owner_password)
    csv_content = "email,full_name\n"
    files = {"file": ("candidates.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    response = await client.post(
        "/candidates/bulk-upload",
        files=files,
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "X-Tenant-Id": str(tenant_id),
        },
    )
    assert response.status_code == 403


async def test_service_account_creation_and_external_intake(client: AsyncClient):
    owner_email, owner_password, tenant_id = await _make_org_owner("employer")
    tokens = await _login_tokens(client, owner_email, owner_password)

    create_response = await client.post(
        f"/tenants/{tenant_id}/service-accounts",
        json={"name": "Partner ATS"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert create_response.status_code == 201
    api_key = create_response.json()["api_key"]

    candidate_email = _unique_email()
    intake_response = await client.post(
        "/candidates/external",
        json={"candidates": [{"email": candidate_email, "full_name": "External Candidate"}]},
        headers={"X-API-Key": api_key},
    )
    assert intake_response.status_code == 200
    assert intake_response.json()["created"] == 1

    async with async_session_factory() as db:
        service_account = await db.scalar(
            select(ServiceAccount).where(ServiceAccount.tenant_id == tenant_id)
        )
        assert service_account is not None
        created_user = await db.scalar(select(User).where(User.email == candidate_email))
        assert created_user is not None


async def test_external_intake_rejects_invalid_api_key(client: AsyncClient):
    response = await client.post(
        "/candidates/external",
        json={"candidates": [{"email": _unique_email(), "full_name": "X"}]},
        headers={"X-API-Key": "sk_live_not-a-real-key"},
    )
    assert response.status_code == 401
