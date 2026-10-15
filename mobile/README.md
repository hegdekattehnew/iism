# IISM mobile app (Android and iOS)

The job seeker's app, built with Expo and React Native. It is a **second client of the same API**
as `web/`, in the same repository (ADR-072). v1 is candidate-only: an organisation or an operator
signs in on the website.

## Status

**Sprint 67 (M6), completed in a browser, not on a phone: candidate parity.** The four things the website's
candidate had and the phone lacked (ADR-078): the **six history sections** of the profile (work history,
education, certificates, languages, roles you want, places you would work), edited through **one table-driven
editor** whose limits a test compares with the server's schema; **"why not me"** on a rejected application;
**career paths**; and the **course budget** that reorders and labels suggested courses. The profile also gains
salary, notice period, work type, willingness to move and the alert opt-out. **No new package, no native code,
no migration, no endpoint:** five operations the website already calls joined the released surface (46 to 51,
additive). **Date of birth and gender stay on the website**, on purpose. A date is a **month and a year** (two
number fields, sent as the first of the month; an edit that does not change them sends the date the entry
already had). The budget is remembered on the phone, sent only as `?budget_inr=`, and **forgotten at sign-out**.
Run against the real API in a browser in both languages as a seeded candidate: add and remove an entry, open a
form, set a budget and see the labels and the request, read career paths with a flagged guess, sign out and see
the budget go. **Not done:** a device, TalkBack/VoiceOver, Hermes, the new screens at 200% font.

**Still on the website only:** date of birth and gender, linking a certificate to a standard, the staff-side and
organisation screens (the app is for job seekers).

Before it:

**Sprint 66 (M5), completed on the code side: store readiness.** The mobile programme's last planned
sprint adds no screen. It makes the app **impossible to release by accident** and leaves a runbook for
the day the accounts exist (ADR-077): a **release build refuses to start** on a missing, `http://` or
local origin (`src/core/release.ts`, a plain "not set up correctly" screen); **`eas.json`** (a `preview`
and a `production` profile, origins and store links per profile, never a default), a hardened
**`app.json`** (one Android permission, encryption declared, the splash, no Face ID string) checked by
running `expo prebuild` into a scratch copy; **`make check-release`** reports every defect and every
decision still open (`PROFILE=production` fails while any is, and **fails today on thirteen**: the
bundle id, the Expo template's artwork, no EAS project id, placeholder origins and store links, the
grievance officer); **`make check-mobile-budget`** (Android Hermes bundle 3.43 MB of a 3.8 MB ceiling);
an accessibility pass held by tests (48 dp targets, roles and names, text capped at 200%; `ACCESSIBILITY.md`
says what only a device can check); and **`docs/release/`**: the store listing in English and Hindi,
the privacy and Data Safety answers (derived from the data export and checked against it), the notes
for reviewers and the release runbook. **Not done, and not claimed:** an EAS build, a store submission, a
run on a device or emulator, TalkBack/VoiceOver, Hermes `Intl`, low-end timing, real push.

**A local release build needs `--clear`**: `EXPO_PUBLIC_*` values are inlined when a file is
transformed, and Metro's cache keeps the old ones (`npx expo export --clear`). EAS builds start clean.

Before it:

**Sprint 65 (M4), completed: updates, push, links, account and a way in for store reviewers.** On top
of M3 (the candidate's own side, ADR-074) a signed-in person now sees **their updates** (every notice,
paged, in the website's own words, with the number that are new on the Me tab), can **take their data
with them** through the share sheet and **delete their account** from inside the app, **write to the
team** and see where each message stands, **report a vacancy or a course**, and **open links** into
the app. Push notifications are built **except real delivery** (ADR-075), and a **store reviewer can
sign in** behind an explicit production switch (ADR-076). Everything here is checked by
`make mobile-check` (and by the `mobile` job in CI):

- strict `tsc`, `eslint` and **Jest tests** for the portable core (`src/core`, in plain Node) and the
  screens (rendered against the real catalogues);
- a **Metro bundle for Android and iOS** compiled to Hermes bytecode;
- Python guards in `tests/test_mobile_foundations.py` (generated files not stale, message keys exist,
  **one file per native module** (`push.ts` is the only one that touches `expo-notifications`), no
  import cycle, every write reports its failure, every personal query is keyed `"me"`).

**Run for real in a browser, not on a phone** (two seeded candidates, English and Hindi). A page
**reload signs the browser run out**, because `expo-secure-store` has no web backend: navigate by
tapping. The phone's Keychain and Keystore are unaffected.

**Notifications are best-effort until two owner-side things exist.** Registration is a **quiet no-op**
on the web and in a build with **no EAS project id** (`expo.extra.eas.projectId`, created with the
owner's Expo account: Expo needs it to issue a token); and the server's push provider is the console
one, which **refuses production**, until a vendor account and credentials exist. The in-app updates
need neither.

**Links open by the `iism://` scheme only.** `iism://job/<slug>`, `/course/…`, `/skill/…`, `/match/…`,
`/matches`, `/applications`, `/notices`, `/invite/<token>` and the website's own paths resolve to a
screen; **anything else is ignored** (`src/core/links.ts` is the whole table, `app/+native-intent.ts`
applies it). Links from the website's address (App Links, universal links) need a **domain** and its
association files: that belongs to the deployment and to M5. An invitation link opens a screen that says
the app is for job seekers and hands the invitation to the browser; it accepts nothing.

**Not verified yet, and no automated check stands in for it:** a run on an emulator or a real phone;
a real push, and the share sheet's behaviour on a real device; Hermes; TalkBack and VoiceOver;
performance on a low-end Android. **On the website only, for now:** the profile's history sections,
the course budget, "why not me" and career paths.

**Personal data is held in memory only** and dropped at sign-out; only queries keyed `"public"` are ever
written to the phone's storage (`src/core/me-keys.ts`, `src/core/persist.ts`). A push token is held in
memory too.

## Run it

**On a phone you own (about five minutes, no emulator).** Install Expo Go, start the API so the
phone can reach it, and point the app at this machine's address:

```bash
set -a; . ./.env; set +a
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000   # from the repo root
cd mobile
EXPO_PUBLIC_API_BASE_URL=http://<this machine's LAN address>:8000 npx expo start
# scan the QR code with Expo Go (Android) or the Camera app (iOS)
```

**Signing in on a development API.** With `OTP_EXPOSE_IN_RESPONSE=true` (the development default) the
code is printed on the sign-in screen. The seeded candidates are `9000000006` to `9000000020`; **do not
write through `9000000001`-`9000000005`**: `make evaluate` asserts on them. Applying and adding skills
change the demonstration database, so undo what you did.

**In a browser (what the sprint's checks used).** `react-native-web` renders the same screens. The
API refuses a browser origin it does not know, so start a second API with the web origin allowed:

```bash
set -a; . ./.env; set +a      # from the repo root
WEB_BASE_URL=http://localhost:8081 .venv/bin/uvicorn api.main:app --port 8101
cd mobile && EXPO_PUBLIC_API_BASE_URL=http://localhost:8101 npx expo start --web --port 8081
```

Restart Expo with `--clear` after changing a module under `src/core`: a stale Metro bundle hid a fix
once.

## Layout

```
app/                  Expo Router screens (one file, one route). No test files here: a file in
                      app/ is a route.
src/core/             No React Native import: the API client, token store, sign-in flow, locale,
                      formatting, labels, the public reads, the cache rules, the candidate's reads and
                      writes (me.ts), applying, the role picker, the profile rules, notices, links, push decisions, the account,
                      messages and reports. Put logic here, not in
                      a screen.
src/lib/              Query hooks: ["public", locale, ...] for a visitor, ["me", ...] for a person
                      (me-queries.ts is the only place a personal query is built)
src/auth/             The one file that touches the Keychain / Keystore
src/push.ts           The one file that touches expo-notifications (best effort, never shown)
src/test/             Screen tests and the render harness
src/api/schema.d.ts   GENERATED from the API: `make gen-api-mobile`
src/messages/         en, hi, ms GENERATED from web/src/messages (`make sync-mobile-messages`);
                      app.en.json / app.hi.json are the phone-only strings, edited here
src/theme/tokens.ts   GENERATED from web/src/app/globals.css (`scripts/sync_mobile_tokens.py`)
src/ui/               The few primitives every screen uses (tokens only, 48 dp targets)
contract/             The API operations the released app calls, and the snapshot of them
assets/               Expo's default icons: PLACEHOLDERS until the real artwork exists
```

## Working on it

```bash
cd mobile
npm ci                       # uses .npmrc (see below)
npx expo start               # then `a` (Android emulator) or `i` (iOS simulator); each needs its
                             # own SDK, which is not installed by npm
npm run typecheck && npx eslint . && npm test     # or, from the repo root: make mobile-check
```

**Always add an Expo package with `npx expo install <pkg>`**, never `npm install`: it picks the
version that matches the SDK. Expo's own `AGENTS.md` for the SDK says the same, and warns that
the API of an SDK release differs from what you remember: read the versioned docs.

`.npmrc` sets `legacy-peer-deps=true` because SDK 57 ships packages whose *optional* peer ranges
disagree (`react-native-worklets`: `expo-modules-core` asks for 0.10 or older, Reanimated for
0.13). `npx expo-doctor` passes; npm's strict resolver does not. Revisit when the SDK is bumped.

`jest` runs through `jest-expo`, whose preset moved to `@react-native/jest-preset`: **that package's
version must equal `react-native`'s** (a newer one fails with "Could not locate module
react-native/setup-env"). The i18n packages are ESM-only, so `package.json` lists them in
`transformIgnorePatterns`.

## Rules carried over from the web app

- **No screen names a colour.** Tokens only, generated from `globals.css`.
- **No user-facing string is hard-coded.** `use-intl`, with the web's catalogues.
- **No business logic in a screen.** It lives in `src/core/` and is tested.
- **Never throw away what the server said** (`ApiError`), and **401 and 403 are different answers**.
- **A signed-out person makes no request that can only answer 401.**
- **The API is additive-only for the operations in `contract/surface.txt`.** Add an operation there
  in the same change that makes the app call it, then `make snapshot-contract`. A change that would
  break an installed app fails `make check` (ADR-072).

## Known, not fixed

`npm audit --omit=dev` reports 24 advisories (14 high, 10 moderate). Every high one is Metro, the
Expo CLI or a dependency of them (`braces`, `node-forge` in code signing, `micromatch`): build
tooling that does not ship in the app. One moderate one (`decode-uri-component`, through
`expo-router`'s `query-string`) is in the app: a slow decode of a malformed deep link. All are
upstream; `npm audit fix --force` would break the SDK, so the fix is the next SDK. CI fails only on
`critical`.

The identifiers `in.iism.app` (bundle id and Android package), the name "IISM", the icons and the
store URLs in `src/config.ts` are **placeholders** until the store accounts exist (ADR-072).
