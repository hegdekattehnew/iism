# Accessibility: what was checked and what only a device can

*Sprint 66 (ADR-077). The first pass is a **read of the code and a guard around it**; no screen reader
has been run, because no device or emulator has. Do not read this file as a conformance claim.*

## Checked in the code, and held by a test

| Rule | Where it is held |
|---|---|
| Every touch target is at least 48 dp tall (buttons, chips, text fields, the search box, the privacy link on sign-in). A chip was 40 dp until this sprint. | `src/test/a11y.test.tsx`; `tests/test_mobile_foundations.py` (no `MIN_TOUCH - n`, no literal `minHeight` under 48) |
| Every `Pressable` has an `accessibilityRole`; every `Switch` and `TextInput` has a label | `tests/test_mobile_foundations.py` |
| A button says when it is busy or disabled, and does not fire; a chip says whether it is selected | `a11y.test.tsx` |
| A spoken name may be longer than the visible label but **contains** it (WCAG 2.5.3) | `Button`'s `accessibilityLabel`, `a11y.test.tsx` |
| A title is a heading; a danger notice is an alert and one focusable item | `a11y.test.tsx` |
| Text follows the system font size up to **200%** and no further (`MAX_FONT_SCALE`), so a fixed-width badge or the tab bar does not break at the size somebody chose in order to read | `a11y.test.tsx`; `tests/test_mobile_foundations.py` (every text element in the shared primitives sets it; none turns scaling off) |
| A decorative mark (the tick in a checkbox) is hidden from the reader; its row carries the name and `checked` | `RolePicker.tsx` |
| The unread count is in the Me tab's **label** (the bar has no icons to hang a badge on), spoken in full | `src/test/tabs.test.tsx` |
| Colour is never the only signal; every colour comes from `tokens.ts`, which is generated from the web's palette (contrast was measured there, in the browser, in light and dark) | `tests/test_mobile_foundations.py` |
| Hindi has its own line height, and its plural forms are polyfilled | `ui/primitives.tsx`, `core/plural-polyfill.ts` |

## Not checked: needs a person with a phone

Run this on a **low-end Android** with TalkBack and on an iPhone with VoiceOver, in both languages.
Tick it off in the release runbook's go/no-go list.

- [ ] Swipe through Home, Jobs, a vacancy, Matches, a match, Me, Account, Updates: the order is the
      reading order, every control is announced with a role and a name, nothing is announced twice.
- [ ] The apply confirmation is read as a whole and the focus lands on it when it opens.
- [ ] A failed request is announced (the danger notice is a live region) without moving focus.
- [ ] The sign-in code field is filled from the SMS on Android and offered on iOS (`autoComplete`).
- [ ] The system font at **200%**: nothing is cut off on a 360 dp wide screen; the tab labels still fit.
- [ ] **Display size / zoom** at its largest on iOS.
- [ ] Dark theme and the system "bold text" and "high contrast" settings.
- [ ] Switch Access / a hardware keyboard reaches every control.
- [ ] Hindi: Devanagari is not clipped at the top or bottom of a line, in a button or a chip.
- [ ] Performance on the target device: first launch to usable list, scrolling a 50-row list without
      dropped frames, memory after ten minutes. `mobile/budget.json` only bounds the *download*.

## How to find the defect a read cannot

`npx expo start --web` renders the same screens with `react-native-web` and is what the sprint's browser
runs used: it shows layout, but it **does not** emulate TalkBack, VoiceOver, the system font scale or
Hermes. A finding here goes into the code and a test, never into an allow-list.
