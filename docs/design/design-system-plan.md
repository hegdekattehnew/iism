# Design-system plan

*Sprint 68, the companion to `ui-review.md`. A **proposal**, not a build: what to decide, in what order, what each decision would touch and what would guard it. Owner-only decisions are marked **[owner]**.*

## Where the system stands

**Good foundations, checked in a browser.** 62 colour tokens in `web/src/app/globals.css`, each with a dark twin; the phone's `tokens.ts` is generated from them (`scripts/sync_mobile_tokens.py`, a test fails when it is stale); 11 shared primitives in `web/src/components/ui/` and the phone's `src/ui/primitives.tsx` and `list.tsx`; skeleton placeholders; a layout-shift budget; axe contrast in both themes; a Hindi line height.

**What is missing is the part a person *sees*:** no images (0 on all 52 web captures), at most six inline SVGs a page, no icon system, one blue, one card style at every level, a type scale that is a set of class names (11, 12, 14, 16, 18, 30 px), and copy written in the product's vocabulary.

## Decisions, in order

| # | Decision | Why first | Touches | Guard |
|---|---|---|---|---|
| 1 | **Brand identity [owner]**: name treatment, primary colour, launcher and splash art | Everything visual hangs off it; the app's icon is Expo's template, which `make check-release` already refuses for production | `mobile/assets/*`, `web/public/*`, `globals.css` `--brand*` | `make check-release` (template hashes), `tokens.test.ts` |
| 2 | **Plain words and pay [owner, then S]**: no 'NSQF' on seeker screens; monthly pay first | Costs nothing and changes what the first screen says (UI-02, UI-05) | `web/src/messages/*.json`, `format.ts`, `mobile/src/core/format.ts` | message-parity test; a unit test on the monthly figure; the sweep |
| 3 | **A 44 px touch floor and a 12 px text floor** | Cheap, global, measurable (UI-07, UI-11) | `button-variants.ts`, `Header.tsx`, `Footer.tsx`, badge classes | a target-size and font-size check added to `checkPage` in `web/e2e/support/test.ts`, proved able to fail on the old header |
| 4 | **A type scale**: caption 12, body 16, lead 18, title 24, display 30 (Hindi +2 line height) | Removes ad hoc sizes before components are redesigned (UI-25) | `globals.css`, `mobile/src/theme/index.tsx`, the token sync | `tokens.test.ts` extended to sizes |
| 5 | **An icon set**: about 24 inline SVGs in one sprite (nav, status, trust, actions), no package | Gives the tab bar, status chips and the trust strip something to show (UI-18) | `web/src/components/ui/icon.tsx`, `mobile/src/ui/Icon.tsx` (react-native-svg is already installed), sync script copies the path data | a test that every icon name used exists; axe name checks |
| 6 | **Surface levels**: page, section, raised; one primary-action treatment | Gives hierarchy without more colours (UI-24) | `card.tsx`, `Card` in `mobile/src/ui/list.tsx`, tokens | the sweep (no flush borders, contrast) |
| 7 | **Components**: job card v2, match summary, sticky apply bar, trust strip, list rows for the phone's Me | The user-visible win; built on 3-6 (UI-04, 08, 10, 13, 20) | `JobBrowser.tsx`, `MatchBrowser.tsx`, `ApplyPanel.tsx`; the phone's equivalents | component tests with rows in them; the browser sweep on a phone, English and Hindi |
| 8 | **Illustration and empty states [owner]**: a small set for the hero, the three audiences and empty lists | Warmth for a first-time, low-literacy user (UI-03, UI-27) | `web/public/`, `mobile/assets/`, empty-state components | review of the set by the owner; weight budget (`mobile/budget.json`, first-load budget) |
| 9 | **Content rules**: the employer's words lead, the generated sentence is labelled, standards are shown once and in sentence case (UI-09, UI-26) | Fixes what the layout cannot | `SkillRequirements.tsx`, the job and course serialisers, bulk-upload defaults | a test on de-duplication and casing |

## What each build sprint would be

- **Sprint 69, 'scannable jobs' (M to L):** decisions 2 (without the owner's wording, with a proposal), 3 and the parts of 7 on the jobs list, the vacancy page and the operator's totals: UI-04 to UI-11 and UI-17. Web and app together, no migration.
- **Sprint 70, 'a candidate's first minute' (M):** UI-01, UI-02, UI-12, UI-13, UI-19: the homepage, the matches page and the signed-in home.
- **After the owner's brand decision (L):** 1, 4, 5, 6, 8: the icon set, the type scale, surfaces, launcher art and illustration.

## What is deliberately not in this plan

A rewrite of the front end, a component library swap, a new framework, motion, a native-only design for the phone, or a second theme beyond light and dark. Each would cost more than it returns before anyone from the target group has used the product.

## Checking it with people, before the big build

Five people, a cheap Android phone, Hindi, thirty minutes each: find a job for a role they know, apply, and say what the match score means. Ten findings in `ui-review.md` depend on the answer; running it between Sprint 69 and Sprint 70 would tell us whether Sprint 70's homepage and matches work is the right work.
