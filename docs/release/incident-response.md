# Incident and personal-data breach response: draft

*Sprint 72, ADR-082. A **draft for the owner and counsel to confirm.** The product holds personal data
(`privacy-and-data-safety.md` is the inventory), and the Digital Personal Data Protection Act, 2023 and
its Rules expect a fiduciary to be able to say what happened, to whom, and what was done. Nothing here
has been exercised in a real incident, and no deployment exists yet: the steps name the controls the
code already has, so a first drill needs no new tooling. `tests/test_release_docs.py` keeps the section
headings below, and keeps secrets, phone numbers and codes out of this file.*

**Timings and who must be told are the law's, not this file's.** The Rules set when the Data Protection
Board and each affected person must be told and what the report must contain (as understood at drafting:
affected people without delay, the Board without delay and a fuller report within a stated period).
**Confirm the current wording and periods with counsel and write them here before launch**; until then
assume the shortest.

## Who does what

One named **incident lead** decides and keeps the log (the owner until someone else is appointed), one
**engineer** investigates and contains, and the **grievance officer** (not yet appointed: `GRIEVANCE_OFFICER`
in `web/src/lib/legal.ts`) handles what people write in. One person may hold all three at the start;
the log says who decided what.

## Detect

What the product already gives you:

* **Structured logs**, one JSON line per request with `request_id`, `user_id` and `tenant_id` (ADR-040).
  A record the redaction filter had to touch carries `redacted=True`, so one query lists every place
  a value that should not be logged was about to be (ADR-023): treat a **new** call site there as a
  finding even when no breach followed.
* **Authorization denials** are logged (`_context_for`, `require`): a run of 404s on organisation
  slugs from one address is somebody guessing.
* **Rate-limit and budget refusals** (429 with `Retry-After`) on sign-in codes and the public forms:
  a spike is an attack on accounts or on the operator queue.
* **A person's or an organisation's report** through `/grievance` or `/contact`, and the operator
  queue's overdue marker.

## Triage

Within the first hour write down, in the log: what was seen and when; whether **personal data** was
involved (anything in the inventory); roughly **whose and how many** (by account, from the logs and the
database, never by guessing); whether it is **still happening**. Classify:

1. *Exposure*: data reached someone who should not have it (a leaked backup, a misconfigured bucket,
   a response that returned another person's row, a log line carrying a value).
2. *Access*: somebody acted as a person or organisation (a stolen token, a guessed sign-in code).
3. *Loss or corruption*: data gone or altered.
4. *Not a breach*: an outage, or an event with no personal data. Still logged, still reviewed.

## Contain

Do the least that stops it, and write each step down before and after.

* **Sessions:** `revoke_all_for_user` ends every session for one account; rotating `JWT_SECRET_KEY`
  ends them **all** (a deliberate, product-wide sign-out: say so to the people affected).
* **Sign-in:** confirm `OTP_EXPOSE_IN_RESPONSE` is off in production (the API refuses to start otherwise)
  and `REVIEWER_LOGIN_ENABLED=false` unless a store review is running; **rotate `REVIEWER_CODE`** after any
  suspicion it leaked.
* **Operators:** `scripts/grant_staff.py` is the only writer of `is_staff`; list who holds it, and remove
  anyone who should not. No HTTP route can grant it.
* **A leaking route or log line:** ship the fix, then confirm with a request that it no longer leaks.
* **A person who asks to stop:** they can withdraw consent (pause) or delete the account from their
  Account page; an operator never does it for them without their ask.

## Preserve

Before changing anything that holds evidence: copy the relevant log window, the request ids, the rows
involved (read-only), and note the commit and configuration that were running. **Do not delete
anything to "clean up"**, and do not restore over the evidence: `make restore-drill` restores into scratch
databases, which is how to look at a backup safely. Backups are encrypted and live outside the tree
(`backups/README.md`); the passphrase is held by the owner, not in this repository.

## Notify

Write the notices from the log, not from memory. Each says what happened, what data, what it may mean for
the person, what was done, what they can do (the Account page's export, correction, withdrawal and
deletion; the grievance officer), and who to ask. **Never put the data itself, a code or a token in the
notice.**

* **To affected people:** in the app and by email (the outbox, ADR-006) for people who have an address;
  an in-app notice reaches the rest when they open the app. A template and the wording for each channel
  are drafted by counsel and kept with this file.
* **To the Data Protection Board of India:** by the route and within the period the Rules set; include the
  nature, extent and timing, the likely consequences and the measures taken.
* **To the owner and any processor concerned** (cloud hosting, SMS, email): the same facts, the same day.

## Recover

Re-enable what was switched off only after the cause is fixed and shown fixed. If data was lost,
restore from the latest encrypted backup (`make restore-drill` first, into scratch); say plainly what
could not be recovered. If sessions were ended, say so on the sign-in screen.

## Review

Within two weeks: a written account of the timeline, the cause, what worked, what did not, and what
changes (a test, a control, a line in this file). A finding that a **test could have caught** gets that
test in the same change. Update `privacy-and-data-safety.md`, the notice and the ADR register if the
facts they state changed, and keep the log with this file's history.
