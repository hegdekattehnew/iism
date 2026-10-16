"""Build the UI review's findings document and workbook (Sprint 68).

    .venv/bin/python scripts/build_ui_review.py

The findings live **here, as data**, so the markdown a person reads and the spreadsheet they filter
are one list that cannot disagree, and `tests/test_ui_review.py` can check each one: that its id is
unique, its severity and effort are from the closed sets, and every screenshot it cites exists. The
pictures and measurements it cites are written by `web/scripts/capture-review.mjs` into
`docs/design/screens/`. Standard library only (the workbook writer is `xlsx_min.py`).
"""

import json
from collections import Counter
from pathlib import Path

from xlsx_min import sheet, write_workbook

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "design"
SCREENS = DESIGN / "screens"

SEVERITIES = ("blocker", "major", "minor", "polish")
EFFORTS = ("S", "M", "L")
HEURISTICS = (
    "Task-first",
    "Scannability",
    "Trust",
    "Language",
    "Touch and low-end",
    "Hierarchy and brand",
    "Consistency",
    "Accessibility",
)

# id, surface, page, heuristic, severity, effort, finding, evidence (text), shots (files that must exist), fix, files
F = [
    (
        "UI-01",
        "Web",
        "Home",
        "Task-first",
        "major",
        "M",
        "The homepage is a brochure, not a tool. It is 7.7 screens tall in eight sections, and the one thing a visitor came to do (name a job, see the gap) is a search box under a jargon eyebrow. The 'I'm here to' chooser starts at the fold's edge. Proof (live counts, the framework, how it works, three sides) comes before any second action.",
        "home.light.en.jpg; measurements: home = 7.7 screens, 22 tap targets under 44 px",
        ["home.light.en.jpg", "home.dark.en.jpg"],
        "Task-first hero: the search with three or four example jobs as one-tap chips, the 'I'm here to' chooser directly under it, and the proof sections collapsed to one band; move the framework and live-count bands to About and the employers page.",
        "web/src/components/Hero.tsx, RoleChooser.tsx, StatsBand.tsx, HowItWorks.tsx, web/src/app/[locale]/page.tsx",
    ),
    (
        "UI-02",
        "Web",
        "Home",
        "Language",
        "major",
        "S",
        "The copy speaks in the product's vocabulary, not the seeker's: 'NSQF-aligned skill intelligence', 'Built on the national framework, not a guess', '21,303 national occupational standards', 'assessable criteria'. A person looking for a ward-boy job does not know what an NSQF standard is, and the numbers prove the product's depth to a funder, not to a seeker.",
        "home.light.en.jpg (eyebrow, 'Built on the national framework' band)",
        ["home.light.en.jpg", "home.hi.hi.jpg"],
        "Say what it does: 'Tell us your job, see what you are missing, find the course'. Keep 'NSQF' for the employer, provider and About pages, and translate the same plain framing into Hindi (not the framework's terms).",
        "web/src/messages/en.json and hi.json (hero, framework, howItWorks namespaces)",
    ),
    (
        "UI-03",
        "All",
        "Every page",
        "Hierarchy and brand",
        "major",
        "L",
        "No page shows a photograph, an illustration or an image of any kind: 0 images on all 52 captures, and at most 6 inline SVGs per page. The brand is a logo mark and one blue. Nothing carries emotion or recognition, and every surface is the same grey-and-white cards, so nothing has visual priority.",
        "measurements: images = 0 on every capture; svgs <= 6",
        ["home.light.en.jpg", "jobs.light.en.jpg"],
        "Owner decision first (name treatment, colour, launcher art). Then a small illustration set for empty states, hero and the three audiences, and employer logos where employers supply them.",
        "web/src/app/globals.css (tokens), web/public/, mobile/assets/",
    ),
    (
        "UI-04",
        "Web",
        "Jobs list",
        "Scannability",
        "major",
        "M",
        "A job card reads like a database row: a title, 'employer . city', a generated sentence, and two grey badges ('Full time', 'NSQF level 4 and above') that mean nothing to a seeker. No verified-employer mark, no posted date or closing date, no distance, no 'am I eligible'. A person cannot judge a card in two seconds.",
        "jobs.light.en.jpg, app-jobs.light.en.jpg (the app has the same card); measurements: jobs = 148 cards, each with two 11 px badges",
        ["jobs.light.en.jpg", "jobs.hi.hi.jpg", "app-jobs.light.en.jpg"],
        "Job card v2: title, employer with the verified mark, place, one pay line, one 'how soon' fact (posted or closing), and for a signed-in person the match score in place of the NSQF badge. Drop 'NSQF level' from the card.",
        "web/src/components/JobBrowser.tsx, web/src/components/ui/badge.tsx, mobile/app/(tabs)/jobs.tsx",
    ),
    (
        "UI-05",
        "Web and app",
        "Jobs list, job detail",
        "Language",
        "major",
        "S",
        "Pay is shown per year ('Rs 2,20,000-3,00,000 per year'). Blue-collar work in India is quoted per month, and a yearly figure forces the reader to divide.",
        "job-detail.light.en.jpg ('Salary')",
        ["job-detail.light.en.jpg", "jobs.light.en.jpg"],
        "Show the monthly figure first ('about Rs 18,000-25,000 a month') and keep the yearly on the detail page. If employers will post daily or hourly gig pay, add a pay period field later.",
        "web/src/lib/format.ts, mobile/src/core/format.ts (formatInr), job card and detail components",
    ),
    (
        "UI-06",
        "Web",
        "Jobs and courses lists",
        "Touch and low-end",
        "major",
        "M",
        "The lists have no pagination: /jobs requests limit=200 and draws all 148 cards at once, 42 screens of scrolling with 167 tap targets; /courses draws every course in 53 screens. The request is capped at 200, so a catalogue past 200 would silently lose vacancies with no message. On a low-end phone this is a long, heavy DOM.",
        "measurements: jobs = 42.3 screens, 167 tappable; courses = 53.4 screens, 199 tappable; JobBrowser.tsx and CourseBrowser.tsx request limit: 200",
        ["jobs.light.en.jpg"],
        "Page the lists (a server total, 'Show more' or infinite scroll with a count), and show how many there are. Keep filters sticky at the top.",
        "web/src/components/JobBrowser.tsx, CourseBrowser.tsx, api/modules/marketplace/routes.py (offset and total already exist)",
    ),
    (
        "UI-07",
        "Web",
        "Lists, matches",
        "Touch and low-end",
        "minor",
        "S",
        "Text under 12 px is used for badges and captions: 296 text nodes at 11 px on /jobs, 537 on /courses, 215 on /matches, 200 on /admin. It is the size a low-end phone in sunlight renders worst.",
        "measurements: tiny texts (under 12 px) per page",
        ["jobs.light.en.jpg", "matches.light.en.jpg"],
        "A 12 px floor in the type scale (13 for badges in Hindi), and fewer badges per card.",
        "web/src/components/ui/badge.tsx and the text-[11px] classes",
    ),
    (
        "UI-08",
        "Web and app",
        "Job detail",
        "Task-first",
        "major",
        "S",
        "On the vacancy page the apply button sits above the job's title and scrolls out of view; there is no sticky apply bar on a phone. The most important action is not where the thumb is, and disappears as soon as the person reads.",
        "job-detail.light.en.jpg ('Sign in to apply' above the h1)",
        ["job-detail.light.en.jpg"],
        "A sticky bottom bar on a phone with the pay line and 'Apply' (or 'Sign in to apply'); the button sits below the key facts, not above the title.",
        "web/src/components/ApplyPanel.tsx and the job page; mobile/src/ui/ApplyPanel.tsx",
    ),
    (
        "UI-09",
        "Web and app",
        "Job detail",
        "Language",
        "major",
        "M",
        "'Skills required' shows raw standard names: all capitals ('ADVANCE SKILL ENHANCEMENT ON TROUBLESHOOTING, ASSEMBLY ...-RACHA'), the same standard twice, and entries a seeker cannot read as a skill ('Employability skills 09', 'OJT 03'), every one 'Importance 5 of 5'. The 'what is this job' paragraph is a generated sentence about a 'real National Occupational Standard'.",
        "job-detail.light.en.jpg (skills block and description); app-job-detail.light.en.jpg",
        ["job-detail.light.en.jpg", "app-job-detail.light.en.jpg"],
        "Show each distinct standard once in sentence case, group the generic ones (employability, on-the-job training) under 'Also covered', show importance as a plain chip not a score, and let the employer's own description lead.",
        "web/src/components/SkillRequirements.tsx, mobile job detail, api listing serialiser (de-duplicate at display)",
    ),
    (
        "UI-10",
        "Web",
        "Job detail",
        "Trust",
        "minor",
        "S",
        "The page has no trust strip. The vacancy's own slug is printed as monospace text above the footer; the only safety cue is 'Sign in to report a listing'. The report reason 'asks for money' exists, but a seeker is never told 'you should never pay to apply'.",
        "job-detail.light.en.jpg (slug line, report link)",
        ["job-detail.light.en.jpg"],
        "Remove the slug; add a quiet trust strip (verified employer or 'not yet verified', 'Never pay to apply', report) near the apply bar.",
        "web/src/components/ReportListing.tsx and the job and course pages",
    ),
    (
        "UI-11",
        "Web",
        "Header, every page",
        "Touch and low-end",
        "major",
        "S",
        "The web header's controls are below the 44 px minimum on every page: the menu button is 38x38, the language select 33 px tall, the logo link 32 px, the nav links 32 px. Every captured page has 15 or more targets under 44 px (22 on the homepage, 45 on /matches, 181 on /admin on a phone). The phone app enforces 48 dp.",
        "measurements: smallTargets on all 52 captures; examples in measurements.json",
        ["home.light.en.jpg", "signin.light.en.jpg"],
        "A 44 px floor on the header, footer and inline action links (padding, not size), checked by the existing `checkPage`.",
        "web/src/components/Header.tsx, Footer.tsx, web/src/components/ui/button-variants.ts, web/e2e/support/test.ts (add a target-size check)",
    ),
    (
        "UI-12",
        "Web",
        "Matches",
        "Task-first",
        "major",
        "M",
        "The matches page opens with a dashboard (live matches, best score, a completeness ring, a funnel, a top-five chart) and the first real match starts about a screen down. The page is 15 screens long with 45 small targets and 215 text nodes under 12 px.",
        "matches.light.en.jpg; measurements: matches = 15 screens",
        ["matches.light.en.jpg"],
        "Matches first: a one-line summary strip (14 matches, best 87, profile 100%) that links to the dashboard, then the cards. Show five, 'Show more'.",
        "web/src/components/MatchBrowser.tsx, CandidateDashboard.tsx",
    ),
    (
        "UI-13",
        "Web and app",
        "Matches",
        "Language",
        "major",
        "M",
        "A match card is an expert's report: an NSQF level scale of ten chips, a 'YOU HAVE' list and a 'YOU NEED' list with full standard names and codes in monospace (HSS/N9618) in bordered boxes. A card runs to about a screen and a half. The person's question ('why 45%, and what do I do?') is answered at the bottom.",
        "matches.light.en.jpg",
        ["matches.light.en.jpg", "matches.hi.hi.jpg"],
        "A summary sentence first ('You have 4 of 5 required skills. Missing: infection control'), one primary action ('See courses that close this'), and the lists and codes behind an expander.",
        "web/src/components/MatchBrowser.tsx, GapPanel.tsx, charts/; mobile/src/ui/match.tsx",
    ),
    (
        "UI-14",
        "Web",
        "Employer workspace",
        "Hierarchy and brand",
        "minor",
        "S",
        "The funnel bars scale each row to itself, so Applied 2, Shortlisted 2, Hired 2 all draw at full width and read as the same thing; the vacancy pool bars switch between navy and amber with no legend.",
        "employer-home.desktop.en.jpg",
        ["employer-home.desktop.en.jpg"],
        "Scale funnel bars to the first step, add a legend for amber, and give the numbers weight over the bars.",
        "web/src/components/charts/status-funnel.tsx, ranked-bar-list.tsx",
    ),
    (
        "UI-15",
        "Web",
        "Employer workspace",
        "Scannability",
        "minor",
        "S",
        "Each vacancy row ends in five equal text links (Edit, Unpublish, Close vacancy, See candidates, View the public posting), about 20 px tall. The primary next step (See candidates) is not emphasised, and on a phone the page has 52 small targets.",
        "employer-home.desktop.en.jpg; measurements: employer-home = 52 small targets on a phone",
        ["employer-home.desktop.en.jpg", "employer-home.light.en.jpg"],
        "One primary button ('See candidates (n)') and an overflow menu for the rest.",
        "web/src/components/employer/ (vacancy list)",
    ),
    (
        "UI-16",
        "Web",
        "Operator /admin",
        "Task-first",
        "major",
        "M",
        "The back office is one scroll of 31 screens on a desktop (40 on a phone): overview, scarce standards, two selectors, then a verification queue of 100 rows, then the other queues. There are no tabs, section anchors or sticky navigation, so an operator scrolls to reach their queue.",
        "admin.desktop.en.jpg; measurements: admin = 31.2 screens desktop, 40.2 phone",
        ["admin.desktop.en.jpg"],
        "A section nav (tabs or sticky anchors): Overview, Verification, Certifications, Grievances, Reports, Programmes, Aliases, Enrolment; each queue opens on its own with a count and paging.",
        "web/src/app/[locale]/admin/page.tsx and web/src/components/ops/",
    ),
    (
        "UI-17",
        "Web",
        "Operator /admin",
        "Trust",
        "major",
        "S",
        "The verification queue says '100 organisations waiting' while the overview above it says 162 awaiting verification. The queue is capped at 100 by the API (limit=100) and the page prints the page length as if it were the total, so an operator believes 100 are waiting. The same pattern (a silent cap on a list) is in UI-06.",
        "admin.desktop.en.jpg (overview 162 vs queue 100); api/modules/operations/routes.py: limit=100",
        ["admin.desktop.en.jpg"],
        "Show 'showing 100 of 162' and page it. Add a test that a capped list never prints its length as its total.",
        "web/src/components/ops/ (queue), api/modules/operations/routes.py and service.py (return a total)",
    ),
    (
        "UI-18",
        "App",
        "Tab bar",
        "Hierarchy and brand",
        "major",
        "M",
        "The phone's tab bar has no icons: five words (Home, Jobs, Courses, Matches, Me). Icons were hidden on purpose (ADR-075: a badge hangs off an icon, so the unread count went into the label), but a text-only bar is slow to scan and gives the app no identity. The unread count reads 'Me (3)'.",
        "app-jobs.light.en.jpg, app-me.light.en.jpg (tab bar: five words, no icons); mobile/app/(tabs)/_layout.tsx tabBarIcon: () => null",
        ["app-jobs.light.en.jpg", "app-me.light.en.jpg"],
        "An icon set shared with the web, and a badge dot on 'Me' with the count kept in the accessible label.",
        "mobile/app/(tabs)/_layout.tsx, mobile/src/ui/, a shared icon sprite",
    ),
    (
        "UI-19",
        "App",
        "Home",
        "Task-first",
        "major",
        "M",
        "A signed-in person's home screen is the signed-out one with 'You are signed in' added: a search box, four browse buttons, language buttons. It does not show their top match, their profile completeness or their updates.",
        "app-home-signed-in.light.en.jpg (identical to the signed-out home plus 'You are signed in.')",
        ["app-home-signed-in.light.en.jpg", "app-home-signed-out.light.en.jpg"],
        "A signed-in home: top match with Apply, profile completeness with the next step, unread updates, and applications needing attention.",
        "mobile/app/(tabs)/index.tsx",
    ),
    (
        "UI-20",
        "App",
        "Me",
        "Hierarchy and brand",
        "minor",
        "S",
        "'Me' is eight identical outlined buttons stacked (Updates, My applications, Saved jobs, Courses I asked about, Where you could move next, Your account, Contact us, Sign out), with no grouping, icons or chevrons; Sign out has the same weight as My applications.",
        "app-me.light.en.jpg",
        ["app-me.light.en.jpg"],
        "Grouped list rows (Your activity, Your profile, Help) with icons and chevrons; Sign out as a quiet text row at the end.",
        "mobile/app/(tabs)/me.tsx",
    ),
    (
        "UI-21",
        "App",
        "Me and others",
        "Touch and low-end",
        "minor",
        "S",
        "A card whose content arrives late pushes the controls below it: on the Me tab the profile card grew about 150 px after the profile loaded, moving every button as the person reached for one. The web guards against this with a layout-shift budget; the phone has none.",
        "observed while driving the Me tab: the profile card grew after it loaded and the buttons moved (not captured as a still); app-me.light.en.jpg shows the loaded state",
        ["app-me.light.en.jpg"],
        "Reserve the card's height with a placeholder, and add the web's layout-shift check to the phone's browser run.",
        "mobile/app/(tabs)/me.tsx, mobile/src/ui/list.tsx",
    ),
    (
        "UI-22",
        "App",
        "Profile",
        "Task-first",
        "minor",
        "M",
        "The profile is one long scroll with four forms and two 'Save' buttons (basics and preferences), plus six history buttons. Nothing says what to do next except a completeness line.",
        "app-profile.light.en.jpg",
        ["app-profile.light.en.jpg"],
        "Sections with a progress header and one primary 'Next' action; save per section with a clear saved state.",
        "mobile/app/profile.tsx",
    ),
    (
        "UI-23",
        "App",
        "Launcher and splash",
        "Hierarchy and brand",
        "blocker",
        "L",
        "The app's icon, adaptive icon and splash are Expo's template artwork, not IISM's (found by `make check-release`, which fails a production build on it).",
        "scripts/check_release_config.py: template asset hashes; mobile/assets/",
        [],
        "Owner: brand identity and launcher art. Then export the five assets at the sizes the release check names.",
        "mobile/assets/*, mobile/app.json",
    ),
    (
        "UI-24",
        "All",
        "Cards and surfaces",
        "Hierarchy and brand",
        "minor",
        "M",
        "Every level of content is the same bordered rounded card on a white or grey ground, and cards sit inside cards (a match card inside the dashboard card, a course card inside a gap panel). With one border, radius and weight everywhere, nothing says 'look here first'.",
        "matches.light.en.jpg, employer-home.desktop.en.jpg",
        ["matches.light.en.jpg", "employer-home.desktop.en.jpg"],
        "Two or three surface levels (page, section, raised), a stronger primary-action treatment, and fewer nested cards.",
        "web/src/components/ui/card.tsx, globals.css tokens; mobile/src/ui/list.tsx (Card)",
    ),
    (
        "UI-25",
        "All",
        "Type scale",
        "Consistency",
        "minor",
        "S",
        "Sizes in use include 11, 12, 14, 16, 18 and 30 px with ad hoc classes, and Hindi text relies on a body line-height override rather than its own scale.",
        "measurements: font sizes on /jobs = 11, 12, 14, 16, 18, 30 px",
        ["jobs.hi.hi.jpg"],
        "A named type scale (caption, body, lead, title, display) with Hindi-aware line heights, shared with the phone through the token sync.",
        "web/src/app/globals.css, mobile/src/theme/index.tsx, scripts/sync_mobile_tokens.py",
    ),
    (
        "UI-26",
        "Web and app",
        "Seeded and generated copy",
        "Language",
        "major",
        "M",
        "Vacancy and course text is generated from the corpus ('Day-to-day responsibilities of the ... role, anchored to ...'; 'working to the standards a real National Occupational Standard for this role sets out'). It is boilerplate a seeker learns to skip, and bulk uploads inherit it when an employer leaves the description blank.",
        "job-detail.light.en.jpg, jobs.light.en.jpg",
        ["job-detail.light.en.jpg"],
        "A content rule: the employer's own description leads; the generated sentence is shown only as 'About this role (from the national standard)' and never as the card summary.",
        "api/modules/marketplace (bulk and publishing defaults), job and course cards",
    ),
    (
        "UI-27",
        "All",
        "Loading and empty states",
        "Hierarchy and brand",
        "polish",
        "S",
        "Loading states are grey skeleton blocks and empty states are one sentence and a button; there is no illustration, tone or help. They are correct (no layout shift) but cold for a first-time, low-literacy user.",
        "jobs.light.en.jpg (skeleton, captured before the list loaded in the earlier look)",
        ["applications.light.en.jpg", "saved.light.en.jpg", "notifications.light.en.jpg"],
        "Warm empty states with one illustration and the single next step; keep the skeletons.",
        "web/src/components/ui/skeleton.tsx, mobile/src/ui/list.tsx",
    ),
    (
        "UI-29",
        "App",
        "Match detail",
        "Consistency",
        "minor",
        "S",
        "FIXED IN THIS SPRINT. A defect from Sprint 67 that the review found by looking: a 100% match, with nothing missing, still showed the course-budget field and the line 'No course on the platform covers this gap yet', about a gap that does not exist.",
        "app-match-detail.light.en.jpg (captured before the fix)",
        ["app-match-detail.light.en.jpg"],
        "Show the courses section, and the budget field, only when something is missing. Done in mobile/app/match/[slug].tsx with a test that fails without it.",
        "mobile/app/match/[slug].tsx, mobile/src/test/matches.test.tsx",
    ),
    (
        "UI-28",
        "Web",
        "Sign-in and sign-up",
        "Task-first",
        "polish",
        "S",
        "Sign-in is short (1.5 screens) and clear, a strength. Small things remain: the 'Skip for now' target is 71x16, the language select 33 px, and the header offers the full site menu to somebody who only wants to sign in.",
        "signin.light.en.jpg; measurements: signup-seeker = 23 small targets",
        ["signin.light.en.jpg", "signup-seeker.light.en.jpg"],
        "A reduced header on the sign-in and sign-up pages; 44 px targets.",
        "web/src/components/SignInForm.tsx, SignUpForm.tsx, Header.tsx",
    ),
]
F.sort(key=lambda f: int(f[0].split("-")[1]))

# What Sprint 69 ("scannable jobs") did about a finding. A finding with no entry is open. Kept beside
# the findings, as data, so the markdown and the workbook cannot disagree about what is fixed, and
# `tests/test_ui_review.py` can check that every id named here is a finding.
FIXED = {
    "UI-04": "Fixed in Sprint 69 (web and phone): title, employer with a verified mark, place, pay, how soon it closes; the NSQF badge and the generated sentence are gone from the card. Still open: the match score on a signed-in card.",
    "UI-05": "Fixed in Sprint 69 (web and phone): 'about Rs 18,300-25,000 a month' on cards and on the vacancy, the yearly figure beneath it on the vacancy. A gig keeps its posted figure. Rule shared by one fixture (tests/fixtures/pay_cases.json).",
    "UI-06": "Fixed in Sprint 69 (web): 24 at a time, the server's total, 'Show more (n left)', a state filter that is the catalogue's own (GET /jobs/states). The phone already paged.",
    "UI-07": "Fixed in Sprint 69 (web): nothing under 12 px (35 literal sizes and the 2xs step), held by src/lib/type-floor.test.ts.",
    "UI-08": "Fixed in Sprint 69 (web and phone): a bar under the content that follows the person, Apply and Save side by side; none for an account that cannot apply. The match screen keeps its place on purpose.",
    "UI-09": "Fixed in Sprint 69 (web and phone, vacancy only): each standard once, sentence case, the generic ones under 'Also covered', a 'Must have' chip instead of a score. The standard's own page is unchanged.",
    "UI-10": "Fixed in Sprint 69 for vacancies: 'Verified employer' or 'Not yet verified' and 'Never pay to apply' with a way to report; the slug line is gone (also from the course page). A course page has no strip yet.",
    "UI-11": "Fixed in Sprint 69 (web): a 44 px floor on buttons, the header and the footer, checked on every page of the browser sweep (header and footer only; the rest of a page is still a count).",
    "UI-17": "Fixed in Sprint 69: both operator queues return their true size; the screen says 'Showing 100 of 162' and offers the rest.",
    "UI-01": "Fixed in Sprint 70 (web): the search first with five one-tap example jobs, the chooser under it, two small links for employers and providers. The 'three sides' cards and the framework band are off the homepage (the framework band is on About). The live people figures and the browse counts stay, by the owner's choice.",
    "UI-02": "Fixed in Sprint 70 (web, and the phone home's words): the hero, how it works and the browse panels no longer say NSQF, framework or taxonomy, held by a test in English, Hindi and Malay. The Hindi was written by the engineer and needs a native reader.",
    "UI-12": "Fixed in Sprint 70 (web): a one-line strip ('14 matches, best 87, profile 100% complete'), the charts one tap behind 'Your numbers', five cards then 'Show more'. Also fixed on the way: /me/matches answered total as the length of the page.",
    "UI-13": "Fixed in Sprint 70 (web and phone): each match says in a sentence what the person has and lacks, with one main action; the lists, codes and level scale are behind Details. The sentence leaves out the generic standards the score still counts, and says so.",
    "UI-19": "Fixed in Sprint 70 (phone): a signed-in seeker's home shows the best match with its sentence, profile completeness and the next step, new updates, and the applications an employer acted on in the last 14 days. Applying is not offered there: the match summary has no employer name for the consent step to name.",
}

GOOD = [
    "Sign-in, applications, saved, notifications and interests are short (1.3 to 1.5 screens) and clear.",
    "Light and dark themes both exist on every page, with measured contrast (axe, in the browser sweep).",
    "Hindi is a first-class locale: every captured page renders in Hindi with its own line height and font, without overflow (`overflowX` false on all 52 captures).",
    "No console errors on any of the 52 captures; no horizontal overflow; loading states are shaped like their content, so pages do not jump.",
    "62 colour tokens with dark twins, 11 shared primitives, and a mobile theme generated from the web's tokens: the foundation for a redesign exists and is checked.",
    "Trust machinery exists behind the screens (verified badge, report with an 'asks for money' reason, operator takedown); the work is to show it.",
]


def _metrics() -> dict:
    path = SCREENS / "measurements.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"results": []}


def _after(sprint: int = 69) -> dict:
    """A re-measurement, if it has been made (`measurements.sprint69.json`, `measurements.sprint70.json`)."""
    path = SCREENS / f"measurements.sprint{sprint}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(r["id"], r["variant"], r["locale"]): r for r in data["results"]}


def _table_rows() -> list[list[str]]:
    return [
        [i, s, p, h, sev, eff, finding, ev, ", ".join(shots), fix, files, FIXED.get(i, "Open")]
        for (i, s, p, h, sev, eff, finding, ev, shots, fix, files) in F
    ]


HEAD = [
    "ID",
    "Surface",
    "Page",
    "Heuristic",
    "Severity",
    "Effort",
    "Finding",
    "Evidence",
    "Screenshots",
    "Proposed fix",
    "Files",
    "Status",
]


def build_markdown() -> str:
    counts = Counter(f[4] for f in F)
    metrics = {(r["id"], r["variant"], r["locale"]): r for r in _metrics()["results"]}
    out = [
        "# UI review: web, phone app and back office\n",
        "*Sprint 68. Generated from `scripts/build_ui_review.py` (the findings are data there) and the captures in `docs/design/screens/`. Do not edit by hand.*\n",
        "**What this is.** One reviewer's evaluation of the product as a design, from screenshots and measurements on a **production build** of the web app against the demonstration database, at 375x812, English and Hindi, light and dark, signed out and as a seeded candidate, employer, provider and operator; plus the phone app through the browser. **What it is not:** user research. Nobody from the target group has used the product; each finding says what it rests on, and the closing section names what only users can settle.\n",
        f"**{len(F)} findings:** "
        + ", ".join(f"{counts.get(s, 0)} {s}" for s in SEVERITIES)
        + ".\n",
        "## The short version\n",
        "1. **The product is correct and accessible, but it is built as an expert's tool, not a job seeker's.** The first thing a seeker meets is a brochure (UI-01), jargon (UI-02), cards that read as database rows (UI-04, UI-13) and standards pasted in capitals (UI-09).",
        "2. **Three cheap, high-value fixes sit on the core loop:** monthly pay (UI-05), a sticky apply bar (UI-08) and 44 px targets (UI-11).",
        "3. **Three lists silently cap what they show** (UI-06 jobs and courses at 200; UI-17 the operator's verification queue at 100, printed as '100 waiting' against 162): a correctness defect that is also a design one.",
        "4. **The brand is missing** (UI-03, UI-23): no imagery anywhere, one blue, and the app's own icon is still Expo's. That is the owner's decision, and everything else waits less on it than it seems.",
        "5. **The back office and employer screens are tidy but long**: the operator's page is one 31-screen scroll (UI-16).\n",
        "## Built so far, and what is next\n",
        f"**Sprints 69 ('scannable jobs') and 70 ('a candidate's first minute') are done** ({len(FIXED)} of {len(F)} findings fixed; the Status column says how far each went). Sprint 69: UI-04 to 11 and UI-17 (job cards, monthly pay, paging with a total, the 12 px and 44 px floors, the apply bar, the standards list, the trust strip, the operator's totals). Sprint 70: UI-01, 02, 12, 13, 19 (the homepage, plain words, the matches page, a match said in a sentence, the signed-in phone home). **Still open:** {', '.join(i for i in (f[0] for f in F) if i not in FIXED)}; of these UI-03, 18, 20, 23, 24 and 27 wait on the owner's brand decision, and BL-16.4 (a five-person usability check) would settle which of the rest matter most.\n",
        "## Findings\n",
        "| " + " | ".join(HEAD[:6] + ["Finding", "Evidence", "Proposed fix", "Status"]) + " |",
        "|" + "---|" * 10,
    ]
    for i, s, p, h, sev, eff, finding, ev, _shots, fix, _files in F:
        status = FIXED.get(i, "Open")
        out.append(
            f"| **{i}** | {s} | {p} | {h} | {sev} | {eff} | {finding} | {ev} | {fix} | {status} |"
        )
    out += [
        "\nFiles each fix would touch are in the workbook (`IISM-UI-Review.xlsx`), column K; its Status is column L.\n",
        "## Measurements (phone width, production build, English, light)\n",
        "Page height in screens of 812 px; tap targets under 44 px; text under 12 px. The raw numbers, with examples, are in `docs/design/screens/measurements.json`.\n",
        "| Page | Screens | Tappable | Under 44 px | Text under 12 px | Images | SVGs |",
        "|---|---|---|---|---|---|---|",
    ]
    for (pid, variant, loc), r in sorted(metrics.items()):
        if variant == "light" and loc == "en":
            out.append(
                f"| {pid} | {r['screens']} | {r['interactive']} | {r['smallTargets']} | {r['textUnder12px']} | {r['images']} | {r['svgs']} |"
            )
    after = _after()
    if after:
        out += [
            "\n## After Sprint 69 (same pages, same method, same phone width, English, light)\n",
            "Re-measured with `web/scripts/capture-review.mjs` against a production build of the changed code. **Screens** is page height in screens of 812 px; the other columns are counts of elements on the page. The Sprint 68 numbers above are kept as the baseline.\n",
            "| Page | Screens before | after | Under 44 px before | after | Text under 12 px before | after |",
            "|---|---|---|---|---|---|---|",
        ]
        for (pid, variant, loc), r in sorted(after.items()):
            b = metrics.get((pid, variant, loc))
            if variant == "light" and loc == "en" and b:
                out.append(
                    f"| {pid} | {b['screens']} | {r['screens']} | {b['smallTargets']} | {r['smallTargets']} | {b['textUnder12px']} | {r['textUnder12px']} |"
                )
    after70 = _after(70)
    if after70:
        out += [
            "\n## After Sprint 70 (the homepage, About and matches; same method, phone width, English, light)\n",
            "Re-measured after the homepage lost its framework band and its three audience cards and the matches page opened on the matches. The baseline is the Sprint 68 capture. Sprint 69's 44 px footer made every page about 0.2 of a screen taller (the homepage was 7.9 just before this sprint), so the saving is a little more than shown.\n",
            "| Page | Screens before | after | Under 44 px before | after | Text under 12 px before | after |",
            "|---|---|---|---|---|---|---|",
        ]
        for pid in ("home", "about", "matches"):
            b, r = metrics.get((pid, "light", "en")), after70.get((pid, "light", "en"))
            if b and r:
                out.append(
                    f"| {pid} | {b['screens']} | {r['screens']} | {b['smallTargets']} | {r['smallTargets']} | {b['textUnder12px']} | {r['textUnder12px']} |"
                )
    out += [
        "\n## What is already good\n",
        *[f"- {g}" for g in GOOD],
        "\n## What only users can settle\n",
        "A five-person usability check on a cheap Android phone, in Hindi, with people who look for work this way today, would settle: whether the match score is understood or trusted (UI-13), whether monthly pay changes behaviour (UI-05), whether the apply bar and the trust strip are noticed (UI-08, UI-10), and whether icons help (UI-18). Until then the findings are expert judgement with measurements, not a verdict.\n",
        "## How this was captured\n",
        "`web/scripts/capture-review.mjs` (Playwright, read-only) signs in as seeded demonstration people with the development code, visits 31 pages (some in dark, Hindi and desktop), takes a picture capped at 2,400 px and measures each page. Re-running it overwrites the same files. The golden candidates and the owner's number are never used.\n",
    ]
    return "\n".join(out) + "\n"


def build_workbook() -> None:
    counts = Counter(f[4] for f in F)
    rows = [HEAD, *_table_rows()]
    sev_style = {"blocker": "red", "major": "amber", "minor": "normal", "polish": "grey"}
    styles = [["header"] * len(HEAD)] + [
        [
            "bold",
            "normal",
            "normal",
            "normal",
            sev_style[r[4]],
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
        ]
        for r in rows[1:]
    ]
    summary = [
        ["Question", "Answer"],
        [
            "What is this?",
            f"{len(F)} UI findings from a review of the web app, the phone app and the back office (Sprint 68). Evidence is screenshots and measurements in docs/design/screens/. It is expert judgement plus measurement, not user research.",
        ],
        ["Severity", ", ".join(f"{counts.get(s, 0)} {s}" for s in SEVERITIES)],
        [
            "Recommended first build",
            f"Sprints 69 ('scannable jobs') and 70 ('a candidate's first minute') are done ({len(FIXED)} findings; see the Status column). Brand-dependent and open: UI-03, 18, 20, 23, 24, 27.",
        ],
        [
            "Owner decisions",
            "Brand identity and launcher art (UI-03, UI-23); monthly pay display and removing NSQF jargon from seeker screens (UI-02, UI-05); review depth for employer and operator screens.",
        ],
        [
            "How to use",
            "Filter by Severity or Heuristic; each row names the screenshot (docs/design/screens/<name>) and the files a fix would touch.",
        ],
    ]
    sheets = [
        (
            "Summary",
            sheet(
                summary,
                [28, 120],
                freeze=False,
                filt=False,
                styles=[["header", "header"]] + [["bold", "normal"] for _ in summary[1:]],
            ),
        ),
        ("Findings", sheet(rows, [8, 12, 22, 20, 10, 8, 70, 46, 30, 60, 50, 60], styles=styles)),
    ]
    write_workbook(DESIGN / "IISM-UI-Review.xlsx", sheets)


if __name__ == "__main__":
    (DESIGN / "ui-review.md").write_text(build_markdown(), encoding="utf-8")
    build_workbook()
    print(f"{len(F)} findings -> docs/design/ui-review.md and IISM-UI-Review.xlsx")
