# Release runbook

*Sprint 66, BL-15.5, ADR-077. The steps between "the code is ready" and "it is in the stores". Nothing
here has been run: there is no Apple or Google account, no EAS project and no deployed API yet. Where a
command is shown it is the documented one for Expo SDK 57; read the versioned EAS docs again before
using it.*

**The gate.** `make check-release PROFILE=production` must print `0 defect(s), 0 owner item(s) open`
and exit 0. Until the owner's items below are done it exits 1 **by design**, naming each one.

## 0. Decisions only the owner can make (each one clears a line of the gate)

| Item | Where it goes |
|---|---|
| The app's name and the real bundle id / package (replacing `in.iism.app`) | `mobile/app.json` (`ios.bundleIdentifier`, `android.package`), `STORE_URL` fallbacks, `mobile/README.md` |
| Real icon, adaptive icon, splash artwork (today the Expo template's) | `mobile/assets/*`, sizes: icon 1024, adaptive layers 432+, splash 200+ |
| Apple Developer and Google Play accounts: **organisation** accounts avoid Play's 14-day closed test for new personal accounts | the consoles |
| An EAS account and project (`eas init` writes `extra.eas.projectId`) | `mobile/app.json` |
| A deployed HTTPS API and website, with their origins | `mobile/eas.json` `env`, API `WEB_BASE_URL` / `CORS` |
| A real SMS provider registered for DLT (without it a code cannot reach a real person) | `api/adapters/notifications` |
| A push vendor and credentials (delivery is console-only today) | `api/adapters/push`, ADR-075 |
| The appointed grievance officer | `web/src/lib/legal.ts` |
| Legal review of the privacy notice and `privacy-and-data-safety.md` | `docs/release/` |
| Domain-based links (universal and App Links) | needs the domain; `iism://` works today |

## 1. Before the first build

1. `make check`, `make mobile-check`, `make check-contract`, `make check-release` (preview), all green.
2. `eas init`, then commit the project id. `eas credentials` for iOS and Android signing.
3. Fill `eas.json`: the two origins per profile, the two store URLs for production, the Play service
   account key path, the App Store Connect app id. `make check-release PROFILE=production` is the proof.
4. A **staging** API with `REVIEWER_LOGIN_ENABLED=false` and a copy of nothing real in it. `preview`
   points at it.

## 2. Preview build and closed test

1. `eas build --profile preview --platform android` (an installable APK); sideload on a **low-end
   Android on mobile data**, the product's target device. Walk the list in `mobile/ACCESSIBILITY.md`
   (TalkBack, 200% font, Hindi) and the first-run checks: sign in, browse offline after one load, apply,
   withdraw, export, delete a throwaway account. **None of this has been done on a device yet.**
2. Fix what it finds. The first run on a phone is the largest unchecked risk (Hermes' `Intl`, scrolling,
   real push).
3. Google Play: create the app, upload an `internal` track build, then a closed test. **A new personal
   account needs 12 testers for 14 days before production access** (re-check the current rule).

## 3. The store review, and the reviewer login

The reviewer logs in with a fixed code (ADR-076). It is a standing way in, so it is **on only during a
review**.

1. On the production deployment set `REVIEWER_PHONES` to the numbers given to the stores, and a
   `REVIEWER_CODE` of `OTP_LENGTH` digits that is **not** guessable (the API refuses one repeated digit and
   a straight run, such as `000000` or `123456`, at startup).
2. `.venv/bin/python scripts/create_reviewer.py --phone <number>` (dry run), then `--apply --attest`.
   It only creates, never adopts an existing account.
3. Set `REVIEWER_LOGIN_ENABLED=true`, redeploy, and **prove it with the real app**: sign in on a fresh
   install with the phone and code.
4. Enter the phone and code in the consoles' credential fields (`review-notes.md`), submit.
5. **When the review ends, accepted or rejected:** set `REVIEWER_LOGIN_ENABLED=false`, rotate
   `REVIEWER_CODE`, redeploy, and confirm a request for the reviewer phone now sends an SMS (or a
   refusal) and the old code is dead. A resubmission starts again at step 1 with a new code.

## 4. Cutting a release

1. **Raise `version` in `mobile/app.json`** (the build number is EAS's, `appVersionSource: remote`).
2. **Contract.** `make check-contract` must pass against the snapshot of the *last* store release. When
   this release retires an old build, first raise `MOBILE_MIN_VERSION_ANDROID` / `_IOS` on the API
   (older builds then get the 426 "update the app" screen), and only then re-record the contract with
   `.venv/bin/python scripts/check_api_contract.py --release`. Commit the new snapshot with the version.
3. `eas build --profile production --platform all`. (EAS builds start clean. A **local** `expo export` or
   `expo run` reuses Metro's cache, and `EXPO_PUBLIC_*` values are inlined when a file is transformed, so
   a changed origin is silently ignored until the cache is cleared: add `--clear`. Found in this
   sprint's own check, where a build kept answering "api-missing" after the variable was set.) Then
   `eas submit` (or upload the bundle and the IPA).
4. Release notes: `docs/release/store-listing.md` "What's new" in both languages.

## 5. Rollback

An installed app cannot be recalled, so:

1. Stop the staged rollout in the console (Play) or remove the version from sale (App Store).
2. Do **not** remove or retype an API operation the released app calls: the contract test forbids it.
   Fix forward on the API side if the fault is there.
3. If the build is dangerous, raise `MOBILE_MIN_VERSION_*` above it: users see the update screen and
   the previous good build (or a fixed one) is the way out.

## 6. Go / no-go checklist

- [ ] `make check-release PROFILE=production` exits 0
- [ ] `make check`, `make mobile-check`, `make e2e`, `make check-contract` green on the release commit
- [ ] A real device run of the release candidate: sign in, browse, apply, withdraw, export, delete (throwaway account)
- [ ] TalkBack and VoiceOver pass over the list in `mobile/ACCESSIBILITY.md`
- [ ] Hindi checked on a device (Devanagari line height, plural forms)
- [ ] The data-safety answers re-read against each console's current form
- [ ] Reviewer login proved on a fresh install, **and a note of when it will be switched off**
- [ ] SMS reaches a real number (DLT); push reaches a real phone (or the listing says nothing about it)
- [ ] A backup and a restore drill run in the last week (`make restore-drill`)
