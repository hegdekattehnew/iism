# IISM mobile app (Android and iOS)

The job seeker's app, built with Expo and React Native. It is a **second client of the same API**
as `web/`, in the same repository (ADR-072). v1 is candidate-only: an organisation or an operator
signs in on the website.

## Status

**Sprint 62 (M1), completed.** The toolchain is installed and everything in this folder is checked
by `make mobile-check` (and by the `mobile` job in CI):

- strict `tsc` over the whole app, `eslint` (Expo's config), and **53 Jest tests**: the portable
  core (`src/core`, 39) and the two screens (sign-in 9, home 5) rendered in a React Native test
  renderer against the real catalogues;
- a **Metro bundle for Android and iOS** (`npx expo export`), which is what catches a missing
  import or an unresolvable asset.

**Not verified yet, and no automated check stands in for it:** a run on an emulator or a real
phone; whether Hermes (the phone's JavaScript engine) formats Hindi plurals and dates the way Node
does (`use-intl` relies on `Intl`; check on a device before trusting the shared catalogues);
TalkBack and VoiceOver; performance on a low-end Android. The first screen run on a device is M2's
first job.

## Layout

```
app/                  Expo Router screens (one file, one route). No test files here: a file in
                      app/ is a route.
src/core/             No React Native import: the API client, token store, sign-in flow, locale.
                      Put logic here, not in a screen.
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
