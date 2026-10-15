# Notes for the store reviewers: draft

*Sprint 66, BL-15.5, ADR-076. Paste into App Store Connect's "App Review Information" and Play Console's
"App access". **The sign-in code is never written in this repository**: it is the deployment's
`REVIEWER_CODE`, typed into the console's credential fields by whoever submits. Rotate it after every
review (see the runbook).*

## What the app is

IISM is a job seeker's app. A person can browse vacancies, training courses and national skill
standards without an account. Signing in with a phone number lets them see how well each vacancy
matches their skills, apply, save vacancies, register interest in a course, and read replies. English
and Hindi.

## How to sign in (the credentials field)

The app signs in with a one-time code sent by SMS. A reviewer cannot receive it, so a demonstration
account is provided.

- **Phone number:** `<the reviewer phone, in the console's credential field>`
- **Code:** `<the reviewer code, in the console's credential field>`

Enter the phone number, tap **Send code**, enter the code above. The account is a demonstration job
seeker with a name, a place and a few declared skills, so matches appear. **It is not a real person
and contains no real personal data.**

## What to look at

1. **Account deletion** (Apple 5.1.1(v), Play's account-deletion policy): **Me → Account → Delete my
   account…** shows what will be erased and asks twice. *Please do not complete it on the demonstration
   account; use any new number if you wish to see the whole flow.*
2. **Reporting objectionable content** (Apple 1.2, Play's UGC policy): open any vacancy or course,
   scroll to the bottom, **Report this vacancy**. Reports go to a moderation queue; an operator can
   take a listing down.
3. **Data export:** **Me → Account → Download my data** opens the share sheet.
4. **Privacy notice and terms:** **Me → Account → Read the privacy notice** (the website).
5. **Contact and complaints:** **Me → Contact us**.

## Things a reviewer may ask

- *Do employers and training providers use this app?* No. They use the website; the app tells a person
  who signs in with an organisation account to do so.
- *What is shared when I apply?* The confirmation screen says: the employer sees your name and contact
  details for that vacancy, until you withdraw.
- *Are there purchases, ads or tracking?* None.
- *Does it use location, camera, contacts or the microphone?* No. The only permission requested is
  notifications.
- *Why does a vacancy have a score?* It is a deterministic comparison of the vacancy's required
  standards with the person's declared ones. No AI model decides it.
