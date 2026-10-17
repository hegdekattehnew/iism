# Design brief and direction (Epic B19, story BL-19.2)

*Sprint 76, 2026-10-17. **Signed off by the Product Owner on 2026-10-17** (see "Sign-off" at the end). Nothing here is built: the live preview shown with it was a throwaway script run in the browser against the dev site (injected CSS and a rearranged card), not a code change. It follows `docs/design/competitor-review.md` and the scope agreed for the epic: web and phone, a refresh within today's blue (no new identity), frontend only.*

## Why

The product is correct, accessible and light: on the same measuring function our jobs page has 1 control under 44 px of 45, no image and 4 icons, while every competitor page reached has 49 to 93 percent of its controls under 44 px and most carry far more icons (27 to 581 inline SVGs on their home pages; Naukri draws its icons as images). What it lacks is **look and scannability**: a card is three lines of text with no mark, no icon, no colour. The review's ten recommendations ask for icons beside facts, an employer mark, a chip row for filters, a bottom bar on the mobile web, a visible language choice, an icon-tile entry, one interruption at a time, and a card pattern for dated, located offers. None needs a new identity. All need a design system the product does not have yet (Sprint 68 found one blue with no ramp, no named type scale, no icons, one flat card style).

## Principles

1. **A low-end Android phone on mobile data is the target.** Weight and tap size stay where they are (we lead on both); the new look must not cost bytes the first-load budget does not have (the profile page has about 3 KB).
2. **Hindi is a first-class language.** Every type and spacing decision is checked in Devanagari at 360 px and 200% text.
3. **Text-light.** Facts get icons, tasks get large tiles, status gets a shape as well as a word (the text-free-interface research found graphics and voice beat text for first-time users).
4. **Honest wording stays.** A card never accuses, pay is a month, a date is never invented, a provider's claim is labelled theirs. Colour and icons do not change what a screen is allowed to say.
5. **One interruption at a time, never over the main action.** No install bars, no stacked sheets, no floating buttons over controls.
6. **A token is the only place a value is chosen.** Colour, type, radius, spacing, elevation and motion are tokens shared with the phone; a test fails when a screen invents one.

## The token direction (what the Product Owner is asked to sign off)

Values were computed, not eyeballed; contrast ratios are against white unless stated.

**Brand ramp** (hue 209, the saturation of today's blue, 700 is today's `#1f4e79`): 50 `#eff5fa`, 100 `#dce9f4`, 200 `#b9d2ea`, 300 `#89b7e1`, 400 `#5497d3`, 500 `#3078bb` (4.64:1), 600 `#266196` (6.50:1), **700 `#1f4e79` (8.66:1)**, 800 `#153451` (12.79:1), 900 `#0c1f31` (16.72:1). Primary actions stay 700; chips and tints use 50 to 200; links 600. Dark theme mirrors it with 400 as the primary.

**Neutral ramp**, tinted to the brand hue at low saturation so greys sit with the blue: 50 `#f8f9fa`, 100 `#eff1f3`, 200 `#dfe3e7`, 300 `#c5ccd3`, 400 `#96a4b0`, 500 `#6e8091`, 600 `#586774`, 700 `#424d57`, 800 `#2c333a`, 900 `#181c20`. The page background moves from white to neutral 50 so white cards read as cards (the preview used exactly this); borders become neutral 200 and control edges stay at the existing 3:1 token.

**Semantic tones** (success, warning, danger, info) keep their three-value shape and gain a solid fill each, which they have; each pairing is contrast-tested in both themes.

**Type scale** (named steps, shared with the phone): caption 13/18, small 15/22, **body 16/24**, lead 18/28, title 24/32, display 30/38; Devanagari gets +0.1 line height. Today 461 places use a 14 px secondary size and 238 use 12 px; the proposal lifts secondary text to 15 and keeps 12 px as a hard floor only for legal and meta lines. This is the largest visible change after the card, and it is why the Hindi fold budget is re-measured first.

**Radius**: 6, 10, 16, full (today `rounded-lg`/`-xl` are 8 and 12 px by default; the preview used 12 and 16). **Surface levels**: page, section, raised, interactive (hover/press). **Elevation**: soft and raised, plus a card shadow so cards stop depending on a border alone. **Motion**: 120 and 200 ms eases, and none under a reduced-motion preference.

## The component direction (each is a build story, not part of this brief)

- **Card v3** (BL-19.11, 19.15): an employer mark (a logo where one exists; a coloured initial avatar where not, because remote images are blocked by our content security policy), the title, **pay as a tinted chip**, **place as an icon chip**, and a muted line for experience and how long ago. About 30 icons for the whole product (BL-19.7).
- **Filters** (BL-19.15): a horizontally scrolling chip row (Job type, Place, Pay, Posted) opening a bottom sheet, replacing the stacked selects that push the first result about 480 px down a 812 px screen.
- **Navigation** (BL-19.13): the current page marked, a reduced header on sign-in and sign-up, and a decision on a **bottom tab bar for signed-in job seekers on the mobile web** (Jobs, Courses, Matches, Profile) with the same four on the phone app.
- **First run and language** (BL-19.13, 19.15): "Choose your language / अपनी भाषा चुनिए" as a single bottom sheet at first use, and a visible translate icon in the header.
- **Home** (BL-19.15): the search and the five example jobs stay; four to six large icon tiles (Find a job, Find a course, Check my match, My applications) are added inside the existing fold budget.
- **A dated, located offer card** (BL-19.11, for Epics B18 and B20): starts on, seats left, distance, fee, verified. Not built now; the pattern is reserved so those epics land on the system.
- **Empty states and illustration** (BL-19.12): icon-led first; illustration art is the Product Owner's and is a drop-in.

## What the preview showed, and what it did not

On the jobs page, in light theme at 375 px: the page tint, rounder cards with a soft shadow, a coloured initial avatar, the pay as a tinted chip, the place with a pin, a muted line for experience and recency, and a chip row for filters. It also showed a cost: the card came out about 30 percent **taller** than today's (the avatar's indent wrapped long titles onto three lines), so the real card has to be designed for height, not just decoration. The mock's filter row replaced one of the stacked selects and left the other (a flaw of the throwaway script), so it did not demonstrate the saving in screen height. It did **not** show dark mode, Hindi, the home page tiles, the bottom bar or a real icon set, and the avatar letters and chip icons were placeholders.

## What this epic reverses, on purpose

The Sprint 68 design-system plan (`docs/design/design-system-plan.md`) excluded a second theme, a component-library swap, a native-only phone design, motion, and icons beyond a small set. This epic adds **icons, motion tokens, illustration slots and (optionally) a theme control**. It does not adopt a component library, a second brand or a native-only design.

## Decisions that were asked of the Product Owner (answered below)

1. **Direction:** approve the token direction above (a refresh within today's blue, the ramps, the type scale with a 15 px secondary size, the page tint) or ask for changes.
2. **Card and filters:** approve the avatar-and-icon-chip card and the filter-chip row as the pattern to build.
3. **Navigation:** ask for a bottom tab bar on the mobile web for signed-in job seekers (a decision, not yet a build).
4. **Theme control (BL-19.8):** keep it in the epic or cut it (the product follows the device's light or dark setting today).
5. **Not asked here:** the launcher and splash art (BL-19.24), illustration art (BL-19.12) and the native Hindi reader (BL-19.25) stay the Product Owner's, whenever they arrive.

## Sign-off (2026-10-17)

The Product Owner, shown the throwaway preview in the browser pane, decided:

1. **Direction: approved as written.** A refresh within today's blue: the brand ramp, the tinted neutral ramp with a grey page and white cards, the named type scale (body 16, secondary 15), the radii and surface levels. Build stories BL-19.4 to BL-19.7 can start.
2. **Patterns to build:** the **avatar and icon-chip card**, the **filter-chip row with a filter sheet**, and a **bottom tab bar for signed-in job seekers on the mobile web**. The card is to be designed for height (the mock was about 30 percent taller).
3. **Not selected:** the first-run bilingual language sheet and the always-visible translate icon (recommendation 5 of the competitor review). The language control stays where it is until a later story proposes otherwise; BL-19.13 no longer carries it.
4. **Theme control (BL-19.8): kept**, scheduled last among the foundations.
5. Still the Product Owner's, whenever they arrive: launcher and splash art (BL-19.24), illustration art (BL-19.12), the native Hindi reader (BL-19.25), and the five-person usability check (BL-19.3).
