# IISM mobile app (Android and iOS)

The job seeker's app, built with Expo and React Native. It is a **second client of the same API**
as `web/`, in the same repository (ADR-072). v1 is candidate-only: an organisation or an operator
signs in on the website.

> **Status (Sprint 62, M1): written, partly verified.** The toolchain has not been installed on
> the machine that wrote this, so **the React Native layer (`app/`, `src/ui`, `src/theme/index.tsx`,
> `src/i18n`, `src/runtime.ts`, `src/auth`) has never been compiled or run.** What *has* been
> checked, with the web app's TypeScript and Vitest: everything in `src/core/` (strict `tsc`, 39
> tests), plus the Python guards in `tests/test_mobile_foundations.py` and the API-side pieces
> (`tests/test_app_version.py`, `tests/test_api_contract.py`). Expect the first install to turn up
> version and typing fixes in the unverified layer; fix them, do not paper over them.

## Layout

```
app/                  Expo Router screens (one file, one route)
src/core/             No React Native import: the API client, token store, sign-in flow, locale.
                      Tested in Node. Put logic here, not in a screen.
src/auth/             The one file that touches the Keychain / Keystore
src/api/schema.d.ts   GENERATED from the API: `make gen-api-mobile`
src/messages/         en, hi, ms GENERATED from web/src/messages (`make sync-mobile-messages`);
                      app.en.json / app.hi.json are the phone-only strings, edited here
src/theme/tokens.ts   GENERATED from web/src/app/globals.css (`scripts/sync_mobile_tokens.py`)
src/ui/               The few primitives every screen uses (tokens only, 48 dp targets)
contract/             The API operations the released app calls, and the snapshot of them
```

## Rules carried over from the web app

- **No screen names a colour.** Tokens only, generated from `globals.css`.
- **No user-facing string is hard-coded.** `use-intl`, with the web's catalogues.
- **No business logic in a screen.** It lives in `src/core/` and is tested.
- **Never throw away what the server said** (`ApiError`), and **401 and 403 are different answers**.
- **A signed-out person makes no request that can only answer 401.**
- **The API is additive-only for the operations in `contract/surface.txt`.** Add an operation there
  in the same change that makes the app call it, then `make snapshot-contract`. A change that would
  break an installed app fails `make check` (ADR-072).

## First-time setup (needs the network; about 400 to 700 MB in `node_modules`)

```bash
# 1. Create the project skeleton in a scratch folder so Expo picks versions that agree with each other.
cd /tmp && npx create-expo-app@latest iism-bootstrap --template blank-typescript

# 2. Take its package.json (and lock file) into mobile/, keeping this folder's app.json,
#    tsconfig.json and babel.config.js. Rename the package to "iism-mobile".
cp /tmp/iism-bootstrap/package.json /tmp/iism-bootstrap/package-lock.json <repo>/mobile/

# 3. Add what this app uses. `expo install` picks the versions that match the Expo SDK.
cd <repo>/mobile
npx expo install expo-router expo-secure-store expo-constants expo-localization expo-linking \
  react-native-safe-area-context react-native-screens react-native-svg
npm install @tanstack/react-query openapi-fetch use-intl
npx expo install --dev jest-expo jest @types/jest @testing-library/react-native

# 4. In package.json set "main": "expo-router/entry" and add "test": "jest",
#    with  "jest": { "preset": "jest-expo", "testMatch": ["**/src/core/**/*.test.ts"] }
```

Then `npx expo start` (press `a` for an Android emulator, `i` for an iOS simulator; both need
their own SDKs and are not installed by the steps above).

The identifiers `in.iism.app` (bundle id and Android package), the name "IISM" and the store URLs
in `src/config.ts` are **placeholders** until the store accounts exist (ADR-072).
