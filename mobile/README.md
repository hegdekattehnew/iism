# IISM mobile app (Android and iOS)

The job seeker's app, built with Expo and React Native. It is a **second client of the same API**
as `web/`, in the same repository (ADR-072). v1 is candidate-only: an organisation or an operator
signs in on the website.

## Status

**Sprint 64 (M3), completed: the candidate's own side.** Sign in, build a profile by naming a job and
ticking the standards you hold, see ranked matches with the gap and the courses that close it, apply
(behind a confirmation that names what is shared), withdraw, save a vacancy, register interest in a
course, and see every application with what the employer said (ADR-074). Browsing without signing in
(Sprint 63, ADR-073) is unchanged. Everything here is checked by `make mobile-check` (and by the
`mobile` job in CI):

- strict `tsc`, `eslint` (Expo's config) and **329 Jest tests**: the portable core (`src/core`) in
  plain Node, and the screens rendered in a React Native test renderer against the real catalogues;
- a **Metro bundle for Android and iOS** compiled to Hermes bytecode (`npx expo export`), which
  catches a missing import or an unresolvable asset;
- Python guards in `tests/test_mobile_foundations.py` (generated files not stale, message keys exist,
  one file per native module, no import cycle, **every write reports its failure**, **every personal
  query is keyed `"me"`**).

**Run for real in a browser, not on a phone.** The same screens were run through `react-native-web` at
375x812 against the dev API as two seeded candidates, in English and Hindi. `expo-secure-store` has no
web backend, so a page **reload signs the browser run out**: navigate by tapping, not by URL. The phone's
Keychain and Keystore are unaffected.

**Not verified yet, and no automated check stands in for it:** a run on an emulator or a real phone;
whether Hermes formats and scrolls as expected; TalkBack and VoiceOver; performance on a low-end Android.
**On the website only, for now:** the work history, education, certificates and languages sections of the
profile, the course budget, "why not me" and career paths.

**Personal data is held in memory only** and dropped at sign-out; only queries keyed `"public"` are ever
written to the phone's storage (`src/core/me-keys.ts`, `src/core/persist.ts`).

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
                      writes (me.ts), applying, the role picker and the profile rules. Put logic here, not in
                      a screen.
src/lib/              Query hooks: ["public", locale, ...] for a visitor, ["me", ...] for a person
                      (me-queries.ts is the only place a personal query is built)
src/auth/             The one file that touches the Keychain / Keystore
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
