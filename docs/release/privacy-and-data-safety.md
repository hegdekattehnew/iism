# Privacy labels and Data Safety answers: draft

*Sprint 66, BL-15.5, ADR-077. A **draft for the owner and a lawyer to confirm** against each store's
form on the day of submission (both forms change). It is derived from what the product actually holds:
the DPDP data export (`api/modules/privacy`, which `tests/test_privacy_coverage.py` keeps equal to the
schema) plus the sign-in and push flows. `tests/test_release_docs.py` fails when the export gains a
section that this inventory does not name, so the answers cannot quietly fall behind the data.*

## What the app does with data, in one paragraph

A person signs in with a **phone number** and a one-time code. They may add a name, a place (state and
district, typed), the standards they hold, and optional profile details. When they **apply**, the
employer sees their name and contact details for that vacancy only, and loses them when the application
is withdrawn. Registering interest in a course does the same for a training provider. The server
records some actions (which screens were used, for example) against the account to improve matching.
A phone registers a **push token** so updates can reach it. **There is no advertising, no tracking
across other companies' apps or sites, no sale of data, no crash-reporting or analytics SDK in the
app, and no device sensor, contacts, photo, camera, microphone or location permission.** All traffic is
HTTPS (a release build refuses to start otherwise: `core/release.ts`).

## Inventory (one row per section of the export)

Retention is stated for the product as built. "Account life" means until the person deletes the
account, which erases it (`DELETE /me/account`, in the app).

| Export key | What it holds | Purpose | Linked to the person | Retention |
|---|---|---|---|---|
| `account` | Phone, email (optional), name, language, when consent was given and to which notice, and when it was withdrawn | Sign in, contact, consent record | Yes | Account life |
| `memberships` | Organisations the person belongs to (the app is candidate-only; a person who also runs an organisation on the website appears here) | Authorisation | Yes | Account life |
| `candidate_profile` | Name, headline, state and district, years of experience, education, date of birth, gender, salary expectation, notice period, skills, experience, education, certificates, languages, preferred roles and places | Matching, the gap, applying | Yes | Account life |
| `agency_enrolment` | Whether an agency programme enrolled the person, the programme and the notice version it attested | Consent record for an assisted sign-up | Yes | Account life |
| `applications` | Vacancies applied to, status, the person's message, the employer's reply | Applying and the inbox | Yes | Account life |
| `saved_jobs` | Vacancies saved | Convenience | Yes | Account life |
| `course_interests` | Courses the person registered interest in | Telling the provider | Yes | Account life |
| `invitations_sent` | Invitations the person sent from an organisation they run (website only) | Team management | Yes | Account life |
| `activity` | Which product actions happened (matches viewed, course opened), without content | Improving matching and measuring it | Yes, until erasure | 365 days |
| `job_alerts` | Vacancies the person was alerted about | Alerts, a daily cap, never twice | Yes | Account life |
| `sponsorship_offers` | An employer's offer to pay for the one missing standard | Hire-and-train | Yes | Account life |
| `ratings_received` | Ratings of the person after a finished gig | Reputation | Yes | Account life |
| `grievances_raised` | Messages the person sent through contact or grievance | Responding, and the deadline we owe | Yes | One year after closing; open ones kept |
| `listing_reports_made` | Reports the person made about a vacancy or course | Moderation | Yes | 365 days |
| `notices` | The updates addressed to the person | The updates screen and push | Yes | 90 days once read or sent; 180 if never opened |
| `devices` | Platform, language and dates of each phone registered for push (the token itself is not exported) | Push delivery | Yes | Until sign-out or erasure |

## Consent: giving it, confirming it again, and withdrawing it (Sprint 72, ADR-082)

Signing up records the notice version and the moment (`users.consent_version`, `consented_at`); the
sentence agreed to also confirms the person is **18 or over**. When the notice changes, a signed-in
person is asked to read and confirm it (a banner; **nothing is switched off while they decide**).
Withdrawing consent is its own act and **keeps the account**: the person is **paused**, so
employers stop seeing them in candidate lists, no alert or push is sent, nothing is tracked, they cannot
apply or register interest, and applications and course interests that still show their details are
withdrawn. They can sign in, export, correct, delete, and restore by confirming the notice again.
**This is a pause, not an erasure**; whether it satisfies DPDP s.6(4) is a question for counsel, and
deletion sits beside it. The export says when consent was withdrawn (`account.consent_withdrawn_at`).

## Apple: App Privacy ("nutrition label")

Data **linked to the person**, none used for tracking, none used for third-party advertising:

| Apple category | Types to declare | Why |
|---|---|---|
| Contact Info | Name, Email Address, Phone Number | Account and applications |
| Identifiers | User ID; Device ID (the push token) | Account; push |
| User Content | Other User Content (profile, messages, the person's note on an application) | The product's function |
| Usage Data | Product Interaction | Improving matching |
| Location | **Coarse Location** (a district the person types; no device location is read) | Matching. *Confirm: Apple may not treat typed text as location data; declaring it is the cautious answer.* |
| Other Data | Date of birth, gender, education and work history, salary expectation | Matching and the profile |

**Not collected:** Health, Financial, Sensitive Info, Contacts, Browsing History, Search History
(the text of a search is not stored against the person; the recorded actions carry counts, never what was searched or which standards), Purchases, Diagnostics (no crash or performance
SDK ships), Precise Location.

Also required for Apple: `ITSAppUsesNonExemptEncryption` is `false` (HTTPS only; set in `app.json`),
the privacy policy URL is the website's `/privacy`, and each dependency ships its own privacy manifest
(`@react-native-async-storage`, `expo-notifications`, `expo-constants`, `expo-localization`, React
Native), merged into the build. **Check Xcode's generated Privacy Report on the first archive.**

## Google Play: Data safety form

| Play category | Types | Collected | Shared | Required or optional | Purpose |
|---|---|---|---|---|---|
| Personal info | Name, Email address, Phone number, User IDs | Yes | No (see note) | Phone required to sign in; name and email optional | Account management, App functionality |
| Personal info | Other info (date of birth, gender, education and work history, salary expectation) | Yes | No (see note) | Optional | App functionality |
| Location | Approximate location (a typed district; no device location) | Yes | No | Optional | App functionality |
| App activity | In-app actions | Yes | No | Required | Analytics, App functionality |
| App info and performance | none | No | | | |
| Device or other IDs | Device or other IDs (the push token) | Yes | No | Optional (push) | App functionality |

Answers to the form's three questions: **data is encrypted in transit** (yes, HTTPS enforced);
**people can request that their data be deleted** (yes: in the app, `Account`, and on the website);
**the app follows the Families policy** (not applicable: not designed for children).

*Note on "shared".* The employer or training provider receives a person's name and contact only when
that person applies or registers interest, after a confirmation that says exactly what is shared, and
loses it when they withdraw. Google's form excludes a transfer the person initiates with a prominent
disclosure; **confirm that reading against the form's current wording**, and if it does not apply,
declare name, phone and email as shared with "employers and training providers" for "App functionality".

## Things that make these answers change

1. **A push vendor is chosen** (ADR-075). Delivery is console-only today. The vendor receives the
   token and the fixed notice text; add its handling here and in the privacy notice before launch.
2. **An analytics or crash SDK is added** to the app. Today there is none.
3. **A new section appears in the export** (the test above).
4. **The privacy notice's version changes** (`PRIVACY_NOTICE_VERSION`; last bumped 2026-10-17 for the 18-and-over sentence). `tests/test_notice_covers_inventory.py` fails when a stored personal column is neither in the notice nor excused.
5. **Real SMS** (DLT) is switched on: the SMS provider processes the phone number.

## What is not here

Legal review of the notice and these answers, the appointed grievance officer (the website's
`web/src/lib/legal.ts` still says "to be appointed"), and the children's-data position. They are the
owner's, and `make check-release PROFILE=production` stays red until the officer is named.
