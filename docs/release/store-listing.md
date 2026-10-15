# Store listing: draft text (English and Hindi)

*Sprint 66, BL-15.5. A **draft for a person to confirm**, not a submission: the app's name is the
owner's decision (the working title is "IISM"), the store consoles change their limits, and nothing
here has been entered anywhere. `tests/test_release_docs.py` holds every field to the limits below,
requires both languages to carry every field, and refuses claims the product cannot back.*

**Limits used** (re-read each console at submission): Apple title 30, subtitle 30, promotional text
170, keywords 100, description 4000. Google Play title 30, short description 80, full description
4000, what's new 500. Characters are counted as Unicode code points, which is the stricter way for
Hindi.

**What the app is.** A job seeker's app: browse vacancies, courses and national skill standards
without an account; sign in with a phone number to see a match, the gap and the courses that close
it; apply, save, register interest in a course; read the employer's replies. English and Hindi.
Free, no ads, no purchases. **Employers and training providers use the website**, and the listing
says so.

**Never claim** (a test fails on these words): a guaranteed or assured job, a placement, a salary,
"100%", "No. 1" or "best", a government endorsement, or any number the app does not itself compute.

## English (en-IN)

### Title
IISM: Jobs, Skills, Courses

### Subtitle
Jobs that fit your skills

### Short description
See which jobs match your skills, what is missing and which courses close it.

### Promotional text
Browse vacancies and courses without signing in. Sign in with your phone number to see how well each vacancy matches you.

### Keywords
jobs,skills,courses,NSQF,vacancy,training,career,employment,skill gap,India

### Full description
IISM helps you find work that fits what you can actually do.

Browse vacancies, training courses and the national skill standards (NSQF) without signing in. Sign in with your phone number to see how well each vacancy matches you.

• See a match score for each vacancy, and exactly which skills you already have and which are missing.
• Find courses that teach the missing skills, with where they run, when the next batch starts, the fee and how many places are left.
• Apply in a few taps. You see what will be shared with the employer before you confirm, and you can withdraw an application while it is undecided.
• Save vacancies for later and read the employer's replies in one place.
• Use the app in English or Hindi.
• Report a vacancy or course that looks wrong. Export or delete your data from inside the app.

Your phone number is used to sign you in. An employer sees your name and contact details only for a vacancy you apply to, and only while your application stands. IISM shows no ads and does not sell your data.

IISM is for job seekers. Employers and training providers use the website.

### What's new
First release.

## Hindi (hi-IN)

### Title
IISM: नौकरी, कौशल, कोर्स

### Subtitle
अपने कौशल के अनुसार काम खोजें

### Short description
अपने कौशल से मेल खाती नौकरियाँ और कमी पूरी करने वाले कोर्स खोजें।

### Promotional text
साइन इन किए बिना नौकरियाँ और कोर्स देखें। अपने फ़ोन नंबर से साइन इन करें और जानें कि हर नौकरी आपसे कितनी मेल खाती है।

### Keywords
नौकरी,कौशल,कोर्स,NSQF,रोज़गार,प्रशिक्षण,करियर,भारत,स्किल

### Full description
IISM आपको वह काम खोजने में मदद करता है जो आप सचमुच कर सकते हैं।

साइन इन किए बिना नौकरियाँ, प्रशिक्षण कोर्स और राष्ट्रीय कौशल मानक (NSQF) देखें। अपने फ़ोन नंबर से साइन इन करें और जानें कि हर नौकरी आपसे कितनी मेल खाती है।

• हर नौकरी के लिए मिलान का स्कोर देखें, और यह भी कि कौन-से कौशल आपके पास हैं और कौन-से नहीं।
• वे कोर्स खोजें जो छूटे हुए कौशल सिखाते हैं: कहाँ चलते हैं, अगला बैच कब शुरू होगा, शुल्क कितना है और कितनी सीटें बची हैं।
• कुछ ही टैप में आवेदन करें। पुष्टि से पहले आप देखते हैं कि नियोक्ता को क्या बताया जाएगा, और निर्णय होने तक आवेदन वापस ले सकते हैं।
• नौकरियाँ बाद के लिए सहेजें और नियोक्ता के जवाब एक ही जगह पढ़ें।
• ऐप को अंग्रेज़ी या हिंदी में इस्तेमाल करें।
• कोई नौकरी या कोर्स गलत लगे तो उसकी शिकायत करें। अपना डेटा ऐप के भीतर से ही निर्यात करें या मिटाएँ।

आपका फ़ोन नंबर केवल साइन इन के लिए इस्तेमाल होता है। नियोक्ता आपका नाम और संपर्क विवरण सिर्फ़ उसी नौकरी के लिए देखता है जिसमें आपने आवेदन किया है, और केवल तब तक जब तक आपका आवेदन बना रहता है। IISM में कोई विज्ञापन नहीं है और यह आपका डेटा बेचता नहीं है।

IISM नौकरी खोजने वालों के लिए है। नियोक्ता और प्रशिक्षण संस्थाएँ वेबसाइट का उपयोग करें।

### What's new
पहला संस्करण।

## Screenshots (a shot list, because the images are the owner's to take)

Take them from the **reviewer demonstration account** (ADR-076) on a device, never from a real person's
account, in both languages, light theme, at the sizes each console asks for (Google: 1080x1920 or
larger phone; Apple: the 6.9-inch and 6.5-inch sets). No screenshot may show a real phone number,
name, employer or message.

1. Home, signed out: the search and the three entries (vacancies, courses, standards).
2. A vacancy's page: title, employer, place, the required standards.
3. Matches: the ranked list with scores.
4. A match: the score, the gap (what is missing) and what caps it.
5. Suggested courses on a match: where, when, fee, seats left.
6. The apply confirmation, naming what is shared with the employer.
7. Updates: a notice from an employer.
8. Account: export, delete.
