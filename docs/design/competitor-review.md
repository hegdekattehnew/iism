# Competitor UI/UX review (Epic B19, story BL-19.1)

*Sprint 76, 2026-10-17. Mobile web at an emulated 375 x 812 viewport in the built-in browser, with the Product Owner approving the sites. Anonymous visits only: nothing was signed up for, no personal data was typed, nothing was downloaded. On Indeed India I chose "Reject All" on the cookie dialog and "English" on the language sheet; on Apna I opened the apply sheet and left it empty. Every claim is marked **observed** (seen on the page during this session), **reported** (from a published source) or **inferred**.*

**Limits, said plainly.** This is a desktop browser engine emulating a phone, not a low-end Android on mobile data, so it says nothing about speed. Pages change daily. Screenshots were examined in the session and are **not committed** (they are third parties' pages); the measurement function used is `docs/design/competitor-measure.js`, so the numbers can be re-taken. **Not reviewed:** foundit (a maintenance page for the whole visit), Shine, LinkedIn (a sign-in wall), Udemy, upGrad, WorkIndia's job list (its mobile web sends job seekers to the Google Play listing), and the skilling portals' signed-in screens (they need Aadhaar sign-in).

## What was measured

Same function on every page (`docs/design/competitor-measure.js`): screens of scroll height at 812 px, interactive elements, those under 44 px in either dimension ("small"), text nodes under 12 px, images. "Small" here counts any link or control under 44 px in height **or** width, which is stricter than the count in our own Sprint 75 table; our page was re-measured with this same function to compare like with like.

| Site and page | Screens | Interactive | Small | Text under 12 px | Images |
|---|---|---|---|---|---|
| Apna home | 9.7 | 315 | 153 | 2 | 213 |
| Apna job list | 10.6 | 209 | 179 | 0 | 137 |
| Apna job detail | 5.6 | 173 | 157 | n/a | n/a |
| WorkIndia home | 11.8 | 182 | 153 | 5 | 55 |
| National Career Service home | 10.3 | 164 | 117 | 1 | 86 |
| Skill India Digital Hub home | 9.1 | 100 | 84 | 15 | 54 |
| Naukri home | 3.0 | 76 | 71 | 13 | 76 |
| Indeed India home | 1.9 | 162 | 132 | 0 | 2 |
| Indeed India results (Pune) | 7.9 | 109 | 62 | 0 | 3 |
| Practo results (Pune) | 10.8 | 112 | 80 | n/a | 76 |
| Coursera results | 12.7 | 133 | 106 | n/a | 47 |
| **IISM `/en/jobs` (dev, dark)** | **7.6** | **45** | **1** | **0** | **0** |

Observed: every competitor page has between **49% and 93%** of its interactive elements under 44 px (Apna home 49%, Indeed results 57%, Practo 71%, Coursera 80%, Apna job list 86%, Naukri 93%); ours has 1 of 45. Our pages are the shortest and the lightest in scripts and images, and also the only ones with **no image and almost no icon** (4 inline SVGs against 27 to 581 on the competitors' home pages: Apna 581, WorkIndia 117, NCS 50, Indeed 31, SIDH 27; Naukri draws its icons as images). That is the gap the review is about: not accessibility or weight, where we lead, but look and scannability.

## Site by site

**Apna** (observed). A green-and-white palette with a photo hero, "India's #1 job platform", a single search box ("Search jobs by title"), a "Proud to support" row of government logos and a "trusted by" row of employer logos, then long lists (popular searches, ~40 departments, ~70 cities). A **fixed header and a fixed bottom "Download now" bar** (4.7 stars, 7 lakh reviews, 5 crore downloads) take roughly a quarter of the first screen. **No language control and no Devanagari anywhere on the page.** The job list has a **bottom tab bar with icons** (Jobs, Degree, Profile), a search box, a horizontally scrolling **filter-chip row** (a filter icon, Date posted, Salary, Work mode), and cards with a logo slot, title, employer, a pin-icon location, a rupee-icon pay line, and three **icon chips** (Field Job, Full Time, Any experience). Pay is shown as an **annual** range on the card (₹2,00,000 – ₹3,50,000) and the detail page labels the same annual figures "monthly*", which is wrong or at least confusing. The detail page has a "Job highlights" box with icons ("Urgently hiring", "Fast HR reply: HR responded to 100% of candidates in the last 13 days", "19 applicants"), tabs (Job details, About company), an FAQ, and a **sticky "Apply for job" bar**. Signed out, Apply opens a **bottom sheet asking only for a mobile number** (+91), with consent as a one-line "by continuing you agree". Reported (a 2022 third-party teardown, a concept proposal, not current): two to four screening questions before an employer can be contacted; users fear scams and callbacks that never come; no feedback from application to interview to hire.

**WorkIndia** (observed). Its mobile home is **employer-first** ("Get calls from candidates, start hiring"): a two-field job-title and city search to start hiring, with "Looking for a job? Find here" as a secondary link, which opens the **Google Play listing**; a job seeker on the mobile web is sent to the app. Stats strip (4 crore candidates, 45 lakh employers, 48 hr average hiring time). The Play listing's own hero banner says **"100% free, no money asked"** (observed), 4.3 stars from 354 thousand reviews, 50 million downloads. No Devanagari or language control on the home page.

**National Career Service** (observed). On load, a **full-screen "Beware of misleading communication" dialog**: NCS is free, never pays fees, job seekers should not pay employers, with the helpline 1514 and cyber-crime 1930. It is a strong trust statement and also a wall of 12 px text before any content. Behind it: a dark government bar with a **toll-free helpline and a visible translate icon (अ/A)**, and a hero ("Find your next career opportunity") with a scheme-banner carousel. Below it, a **3 x 2 grid of large tiles with three-dimensional icons**: Internships, Jobs, Career Guidance, Career Centers, AI Resume Building, Job Fairs. This is the most text-light entry screen of any site visited, and the nearest thing to the text-free principles below. Reported by the page text: an Employability Assessment, a Skill Quotient test and an AI interview coach (relevant to Epic B20); not opened. 117 of 164 controls are small, and many icon links have no text labels.

**Skill India Digital Hub** (observed; enrolment steps reported from NSDC's own guide). At phone size the **hero carousel is blank for a full screen** (it may be lazy loading; it was still blank after four seconds). The header stack holds a **location selector, an accessibility strip (screen-reader mode, text size, contrast, site map)**, a truncated "Skip to main conte(nt)" link, and **floating buttons for a WhatsApp channel and a language switch**. The language button **overlaps the sort control** on the course list. The course list is the most useful part: a search box, filter and sort controls, then **big poster cards**: an "Online" badge and a green "Free" tag on an image with the course title **baked into the picture**, the title again as text, the provider, the sector, language, duration, **an explicit "No Credit" line**, a **4.5 star rating (42 reviews)**, "Apply" and a "Compare" checkbox. Reported (the NSDC guide): Aadhaar e-KYC with two OTPs; **two different routes to find batches**; a batch list showing only **Batch ID, location and training centre**; a cap of five batches; a **three-party sequence** (candidate shows interest, centre approves, candidate accepts, centre enrols) **with no stated timelines or notifications**; name, date of birth, religion and mobile number that cannot be corrected.

**Naukri** (observed). The shortest page of all (**3 screens**). A search box and a "Get app" button in a compact header, a large illustration, and, on the home page itself, **a phone-number field with a Continue button, then Google and email as alternatives**: sign-up is the first call to action, not search. Then "Trending on Naukri today" cards. 13 text nodes under 12 px.

**Indeed India** (observed). Two stacked fields, **job title and city**, always visible at the top ("Enter city or locality"); a very light home (1.9 screens). The results page shows a **radius beside the location ("25 km")**, filter chips (Pay, Remote, Easily apply, Job type), cards with an "Easily apply" tag, a bookmark, title, employer, place and **pay as a monthly range** ("₹25,000 – ₹35,000 a month"). On first use it offers **"Choose your language / अपनी भाषा चुनिए" as a bottom sheet with English and हिन्दी**, then a toast "Your default language is set to English". It stacks **three interruptions** on one screen (the cookie dialog, the language sheet, then "Your job matches are better on the app" with Open or Continue), which is the pattern to avoid.

**Practo** (observed). The reference for "nearby and dated". An **In-person / Video consult toggle**, a filter button, and a **"Find doctors near you: skip the commute, book nearby" tile** that asks for location only when chosen. Each result card carries: photo, name, years of experience, **"98% recommended" with a count of patient stories**, a rating badge ("4.9 Excellence"), clinic and locality, **"~₹500 consultation fees"**, a **"Verified for quality care"** mark, and **"Next available at 05:15 PM, tomorrow"**, then two buttons: View profile and Book clinic visit. Sponsored cards are labelled "AD". A banner at the top says the privacy policy was updated "as per the DPDP Act, 2023". This is the closest model for a batch card (starts, seats left, distance, fee, verified).

**Coursera** (observed). A breadcrumb, a plain-language description of the subject, a search box with clear and search buttons, and filter chips (Filter and sort, Topic, Duration). Each card shows the **provider's logo and name, the title, "Skills you'll gain", then one line: rating (count) · level · credential type · duration**, and badges ("Trending right now", "Free trial"). Reported (page text): an intent question on arrival and a plain-language FAQ about what a certificate means.

**Microsoft Research on low-literacy interfaces** (reported; 570 participants in India, the Philippines and South Africa). Text-free designs combining graphics and voice were strongly preferred; text was unusable by first-time low-literacy users and error-prone for novices; **understanding hierarchical navigation is itself a cognitive skill that low-literacy users find hard**; a job-search prototype was built on these principles.

## What most competitors share

Observed on at least three of the pages reached: a **horizontally scrolling filter-chip row** instead of stacked selects (Apna, Indeed, Coursera); **icons beside every fact on a card** (Apna, NCS, SIDH, Practo); a **logo or photo slot** on every card (Apna, Coursera, SIDH, Practo); **one obvious primary action per card** (Apply, Book, Apply); a **persistent bottom bar or sticky apply bar** on mobile (Apna, Indeed); an **app-install prompt** on most of them (Apna's fixed bar, Naukri's "Get app", Indeed's "Open app" and sheet, WorkIndia's only route), a pattern we do not follow because the web is our product; **a phone-number-first sign-up** at the moment of intent (Apna's apply sheet, Naukri's home).

## What is distinctive and worth borrowing

1. NCS's icon-tile entry screen: six large tiles, one tap to the main tasks, no reading needed.
2. Practo's availability line on a result card ("Next available at ...") and Indeed's radius ("25 km") for a "near me" search.
3. Apna's response-rate and applicant-count highlights (needs data we do not hold; do not copy the claim without the data).
4. SIDH's accessibility strip (text size, contrast, screen-reader mode) and its explicit "No Credit".
5. Indeed's bilingual language sheet at first use, and NCS's and SIDH's always-visible translate icon.
6. WorkIndia's "100% free, no money asked" banner and NCS's scam dialog: both lead with "never pay".

## Common mistakes to avoid (all observed)

Stacked interruptions (Indeed); a fixed install bar over the first screen (Apna); a full-screen text wall before content (NCS's dialog); floating buttons that overlap controls (SIDH); a blank hero (SIDH); a pay unit that contradicts itself (Apna's annual figures labelled monthly); sign-up as the first thing on a home page that has nothing to show yet (Naukri); no language choice at all on a platform for India's blue-collar workforce (Apna and WorkIndia, as far as these pages show); a maintenance page with no alternative (foundit).

## Ten ranked recommendations for IISM

1. **Put icons beside the facts on a card** (place, pay, type, how soon) and a small coloured chip row. Evidence: Apna, Indeed, NCS, SIDH, Practo. Ours has none (4 inline SVGs on `/jobs`).
2. **Give every card an employer mark**: a logo where one exists and a coloured initial avatar where not (remote logos are blocked by our CSP, so the avatar is local). Evidence: Apna, Coursera, Practo. Ours shows text only.
3. **Replace the stacked selects on `/jobs` with a filter-chip row and a filter sheet.** Ours puts three controls and a sort above the first result (the first card starts about 480 px down on a 812 px screen); Apna and Indeed show chips and a result within the first screen.
4. **A bottom tab bar on the mobile web for signed-in job seekers** (Jobs, Courses, Matches, Profile), as Apna has for Jobs, Degree and Profile; our candidate pages sit behind a hamburger and an account menu.
5. **Offer the language as a bottom sheet at first use** ("Choose your language / अपनी भाषा चुनिए") **and keep a visible translate icon in the header**, as Indeed, NCS and SIDH do. Ours is a native select in the footer and the menu.
6. **A text-light entry screen: four to six large icon tiles on the home page** (Find a job, Find a course, Check my match, My applications), as NCS has, inside our existing fold budget (the search and the five example jobs stay).
7. **Make "never pay" visible on cards and the first screen**, not only on the vacancy page, in the way WorkIndia's banner and NCS's dialog do, but as one line, never a full-screen wall.
8. **A card pattern for dated, located offers** (a batch): starts on, seats left, distance, fee, verified. Model: Practo's availability line and Indeed's radius. This is the pattern Epics B18 and B20 will need, so the design system should hold it before they start.
9. **A course card that explains itself in one line**: level · credential · duration · credits, with "Skills you'll gain" (Coursera), and an explicit statement when there is no credit (SIDH). Ours is thin and, since Sprint 75, can show credits.
10. **One interruption at a time, and never over the primary action**: no install bar, no stacked sheets, no floating buttons over controls. Our current rule (a consent banner fixed to the window, "Not now" per session) is already the right shape; keep it the only one.

## What this review cannot tell us

Whether any of these patterns work for **our** users (that needs the five-person check, BL-19.3 / BL-16.4); how any of these sites perform on a low-end phone; what a competitor's signed-in experience is (profile building, alerts, employer side); and the visual language in detail (type and colour choices were looked at, not measured). Naukri and Indeed's applying flows, WorkIndia's job list and foundit were not reached.
