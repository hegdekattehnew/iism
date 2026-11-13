# Plain levels: the words, for a reader who knows the work

**Status: UNREVIEWED.** These words stand in for "NSQF level n" on a vacancy, a course, a standard, a search result, a match and a career path (Sprint 104, BL-22.5). They were written by the engineer. The number always stays beside them ("Skilled worker, level 4"), so a wrong word never hides the fact, but a wrong word is still wrong.

A half level (2.5, 3.5, 4.5, 5.5, 6.5) is real and is said as the space between its two neighbours ("Skilled worker to senior skilled worker, level 4.5"); it has no line of its own. The words live in `web/src/messages/{en,hi,ms}.json` under `levels`; change them there, then run `.venv/bin/python scripts/build_level_words_review.py`.

Please mark each row **keep**, **change** (and to what) or **retire**, in the last column, and say whether the *line* is true of someone at that step in the work you know.

## English

| Level | Name | One line | Keep / change / retire |
|---|---|---|---|
| 1 | Basic helper | Simple tasks with close guidance. | |
| 2 | Helper | Everyday tasks with some guidance. | |
| 3 | Semi-skilled worker | Does the job's usual tasks without constant supervision. | |
| 4 | Skilled worker | Does the job well on their own and handles usual problems. | |
| 5 | Senior skilled worker | Handles harder problems and can guide others. | |
| 6 | Supervisor or technician | Plans and supervises work, and fixes complex faults. | |
| 7 | Degree level | Needs a degree-level education. | |
| 8 | Master's level | Needs a master's-level education. | |
| 9 | Advanced specialist | Advanced specialist work. | |
| 10 | Doctoral level | Top-level specialist or research work. | |

Half level, joined: `{lower} to {upper}`. With the number: `{name}, level {level}`. A vacancy's floor: `{name} or above (level {level})`.

## Hindi

| Level | Name | One line | Keep / change / retire |
|---|---|---|---|
| 1 | प्रारंभिक सहायक | निकट मार्गदर्शन में सरल काम। | |
| 2 | सहायक | कुछ मार्गदर्शन के साथ रोज़ के काम। | |
| 3 | अर्ध-कुशल कामगार | काम के सामान्य कार्य बिना लगातार निगरानी के करते हैं। | |
| 4 | कुशल कामगार | काम खुद अच्छे से करते हैं और आम समस्याएँ सुलझा लेते हैं। | |
| 5 | वरिष्ठ कुशल कामगार | कठिन समस्याएँ सँभालते हैं और दूसरों को राह दिखा सकते हैं। | |
| 6 | पर्यवेक्षक या तकनीशियन | काम की योजना बनाते और निगरानी करते हैं, और जटिल ख़राबियाँ ठीक करते हैं। | |
| 7 | स्नातक स्तर | स्नातक स्तर की पढ़ाई चाहिए। | |
| 8 | स्नातकोत्तर स्तर | स्नातकोत्तर स्तर की पढ़ाई चाहिए। | |
| 9 | उन्नत विशेषज्ञ | उन्नत विशेषज्ञता का काम। | |
| 10 | डॉक्टरेट स्तर | शीर्ष स्तर का विशेषज्ञ या शोध कार्य। | |

Half level, joined: `{lower} से {upper} के बीच`. With the number: `{name}, स्तर {level}`. A vacancy's floor: `{name} या उससे ऊपर (स्तर {level})`.

## Malay (English until translated)

| Level | Name | One line | Keep / change / retire |
|---|---|---|---|
| 1 | Basic helper | Simple tasks with close guidance. | |
| 2 | Helper | Everyday tasks with some guidance. | |
| 3 | Semi-skilled worker | Does the job's usual tasks without constant supervision. | |
| 4 | Skilled worker | Does the job well on their own and handles usual problems. | |
| 5 | Senior skilled worker | Handles harder problems and can guide others. | |
| 6 | Supervisor or technician | Plans and supervises work, and fixes complex faults. | |
| 7 | Degree level | Needs a degree-level education. | |
| 8 | Master's level | Needs a master's-level education. | |
| 9 | Advanced specialist | Advanced specialist work. | |
| 10 | Doctoral level | Top-level specialist or research work. | |

Half level, joined: `{lower} to {upper}`. With the number: `{name}, level {level}`. A vacancy's floor: `{name} or above (level {level})`.
