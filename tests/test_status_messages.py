"""A message with a status change, and a private note on an applicant (Sprint 60, ADR-070).

The rules worth pinning: the message is replaced, cleared or left alone by the right transitions;
**it never enters the notification outbox** (which holds no free text that may carry a phone
number); the candidate sees the employer's message and **never the employer's notes**; and a note
is deleted with the application and present in the person's own data export.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from api.modules.applications import Application
from api.modules.notifications.models import Notification
from tests.moderation_support import make_skill, organisation, person, published_job

INTERVIEW = (
    "Interview on Tuesday 14 Oct, 11 am, at our Kothrud clinic. Ask for Mr Rao: 98765 43210."
)


async def _applicant(client: AsyncClient, db: AsyncSession):
    headers, org = await organisation(client, db)
    job = await published_job(client, headers, org, await make_skill(db))
    candidate, user_id = await person(client)
    assert (
        await client.post("/me/applications", headers=candidate, json={"job_slug": job["slug"]})
    ).status_code == 201
    applicants = (
        await client.get(f"/org/{org}/jobs/{job['slug']}/applications", headers=headers)
    ).json()["items"]
    return headers, org, job, candidate, user_id, applicants[0]["application_id"]


def _url(org: str, job: dict, application_id: str, tail: str = "") -> str:
    return f"/org/{org}/jobs/{job['slug']}/applications/{application_id}{tail}"


async def _move(client, headers, org, job, application_id, status="shortlisted", **body):
    return await client.patch(
        _url(org, job, application_id), headers=headers, json={"status": status, **body}
    )


class TestTheMessage:
    async def test_it_reaches_the_candidate_on_their_application(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, candidate, _, aid = await _applicant(client, db)
        moved = await _move(client, headers, org, job, aid, message=INTERVIEW)
        assert moved.status_code == 200
        assert moved.json()["status_message"] == INTERVIEW and moved.json()["status_message_at"]
        mine = (await client.get("/me/applications", headers=candidate)).json()[0]
        assert mine["status"] == "shortlisted" and mine["status_message"] == INTERVIEW

    async def test_a_new_one_replaces_the_old_and_a_status_change_without_one_clears_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, candidate, _, aid = await _applicant(client, db)
        await _move(client, headers, org, job, aid, message="First, 10 am.")
        replaced = await _move(client, headers, org, job, aid, message="Moved to 2 pm.")
        assert replaced.json()["status_message"] == "Moved to 2 pm."
        cleared = await _move(client, headers, org, job, aid, status="hired")
        assert cleared.json()["status_message"] is None
        assert (await client.get("/me/applications", headers=candidate)).json()[0][
            "status_message"
        ] is None

    async def test_a_second_click_on_the_same_status_does_not_erase_it(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _, _, aid = await _applicant(client, db)
        await _move(client, headers, org, job, aid, message=INTERVIEW)
        again = await _move(client, headers, org, job, aid)  # same status, no message
        assert again.json()["status_message"] == INTERVIEW

    async def test_it_is_trimmed_and_bounded(self, client: AsyncClient, db: AsyncSession) -> None:
        headers, org, job, _, _, aid = await _applicant(client, db)
        blank = await _move(client, headers, org, job, aid, message="   ")
        assert blank.status_code == 200 and blank.json()["status_message"] is None
        padded = await _move(client, headers, org, job, aid, message="  Bring your ID.  ")
        assert padded.json()["status_message"] == "Bring your ID."
        assert (await _move(client, headers, org, job, aid, message="x" * 501)).status_code == 422
        assert (await _move(client, headers, org, job, aid, message="x" * 500)).status_code == 200

    async def test_the_words_are_never_in_the_outbox_only_that_there_are_some(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _, user_id, aid = await _applicant(client, db)
        await _move(client, headers, org, job, aid, message=INTERVIEW)
        notices = (
            await db.scalars(select(Notification).where(Notification.recipient_id == user_id))
        ).all()
        mine = [n for n in notices if n.template.startswith("application_status")]
        assert {n.channel for n in mine} == {"in_app", "email"}
        for n in mine:
            assert n.template == "application_status_message"
            assert n.payload["has_message"] is True
            assert "98765" not in str(n.payload) and "Rao" not in str(n.payload)

    async def test_a_move_without_a_message_keeps_the_plain_notice(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _, user_id, aid = await _applicant(client, db)
        await _move(client, headers, org, job, aid)
        templates = {
            n.template
            for n in (
                await db.scalars(select(Notification).where(Notification.recipient_id == user_id))
            ).all()
        }
        assert templates == {"application_status_changed"}

    async def test_a_withdrawn_application_cannot_be_messaged(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, candidate, _, aid = await _applicant(client, db)
        await client.post(f"/me/applications/{aid}/withdraw", headers=candidate)
        assert (await _move(client, headers, org, job, aid, message="Hello")).status_code == 409


class TestThePrivateNote:
    async def test_it_is_saved_trimmed_cleared_and_bounded(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, _, _, aid = await _applicant(client, db)
        saved = await client.put(
            _url(org, job, aid, "/notes"), headers=headers, json={"notes": "  Strong, call back.  "}
        )
        assert saved.status_code == 200 and saved.json()["notes"] == "Strong, call back."
        listed = (
            await client.get(f"/org/{org}/jobs/{job['slug']}/applications", headers=headers)
        ).json()["items"][0]
        assert listed["notes"] == "Strong, call back." and listed["notes_at"]
        cleared = await client.put(
            _url(org, job, aid, "/notes"), headers=headers, json={"notes": ""}
        )
        assert cleared.json()["notes"] is None and cleared.json()["notes_at"] is None
        assert (
            await client.put(
                _url(org, job, aid, "/notes"), headers=headers, json={"notes": "x" * 2001}
            )
        ).status_code == 422

    async def test_a_stranger_or_another_employer_finds_nothing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, candidate, _, aid = await _applicant(client, db)
        other, _ = await organisation(client, db)
        for who in (candidate, other):
            refused = await client.put(
                _url(org, job, aid, "/notes"), headers=who, json={"notes": "mine now"}
            )
            assert refused.status_code == 404
        assert (
            await client.put(_url(org, job, aid, "/notes"), json={"notes": "x"})
        ).status_code == 401

    async def test_a_note_survives_withdrawal_while_the_contact_does_not(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, candidate, _, aid = await _applicant(client, db)
        await client.put(
            _url(org, job, aid, "/notes"), headers=headers, json={"notes": "Reliable."}
        )
        await client.post(f"/me/applications/{aid}/withdraw", headers=candidate)
        row = (
            await client.get(f"/org/{org}/jobs/{job['slug']}/applications", headers=headers)
        ).json()["items"][0]
        assert row["contact"] is None and row["notes"] == "Reliable."

    async def test_the_candidate_never_sees_it_in_any_response_they_can_reach(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, candidate, _, aid = await _applicant(client, db)
        await client.put(
            _url(org, job, aid, "/notes"), headers=headers, json={"notes": "CONFIDENTIAL-NOTE"}
        )
        for path in ("/me/applications", "/me/applications/dashboard"):
            assert "CONFIDENTIAL-NOTE" not in (await client.get(path, headers=candidate)).text

    def test_no_response_model_under_me_carries_a_notes_field(self) -> None:
        """The structural guard: walk every schema reachable from a `/me/*` response."""
        spec = app.openapi()
        schemas = spec["components"]["schemas"]

        def refs(node: object) -> set[str]:
            found: set[str] = set()
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str):
                    found.add(ref.rsplit("/", 1)[-1])
                for v in node.values():
                    found |= refs(v)
            elif isinstance(node, list):
                for v in node:
                    found |= refs(v)
            return found

        roots: set[str] = set()
        walked = 0
        for path, item in spec["paths"].items():
            if path.startswith("/me/"):
                for op in item.values():
                    if isinstance(op, dict):
                        roots |= refs(op.get("responses", {}))
                        walked += 1
        assert walked > 20, "found the /me routes"
        seen: set[str] = set()
        stack = list(roots)
        while stack:
            name = stack.pop()
            if name in seen or name not in schemas:
                continue
            seen.add(name)
            props = set(schemas[name].get("properties", {}))
            assert not props & {"employer_notes", "notes", "notes_at"}, name
            stack.extend(refs(schemas[name]) - seen)
        assert "ApplicationOut" in seen

    async def test_it_is_in_the_persons_export_and_goes_with_the_application_on_erasure(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, org, job, candidate, _, aid = await _applicant(client, db)
        await _move(client, headers, org, job, aid, message=INTERVIEW)
        await client.put(
            _url(org, job, aid, "/notes"), headers=headers, json={"notes": "Call back."}
        )
        export = (await client.get("/me/account/export", headers=candidate)).json()
        (mine,) = [a for a in export["applications"] if a["vacancy"] == job["title"]]
        assert mine["employer_message"] == INTERVIEW and mine["employer_notes"] == "Call back."

        assert (await client.delete("/me/account", headers=candidate)).status_code in (200, 204)
        assert await db.get(Application, uuid.UUID(aid), populate_existing=True) is None


@pytest.mark.parametrize("tail", ["", "/notes"])
async def test_a_signed_out_caller_gets_401(client: AsyncClient, tail: str) -> None:
    url = f"/org/x/jobs/y/applications/{uuid.uuid4()}{tail}"
    response = (
        await client.patch(url, json={"status": "hired"})
        if tail == ""
        else await client.put(url, json={"notes": "x"})
    )
    assert response.status_code == 401
