# Survey analysis

Turns the evaluation survey into the tables for Chapter 4: the respondent
profile, the SUS results and the trust and security perception results.

## Before sending the form

Each SUS and trust question in the Google Form needs the statement from
Tables 3 and 4 in its title, word for word. The script finds the questions that
way. Answers can be 1 to 5 or the words, "Strongly agree" and so on.

Add one question asking which group the respondent is in (citizen, LGU staff or
IT admin). The script looks for a column with "group" or "role" in its title.

## After collecting responses

In Google Forms: Responses, the three dots, Download responses (.csv). Then:

```bash
python evaluation/analyze_survey.py responses.csv --out evaluation/results
```

Only Python 3.10 or later is needed, nothing to install.

You get `survey_report.md` with every table, plus `sus_by_group.csv` and
`trust_items.csv` to paste into the paper.

## What it computes

Everything in section 3.10 of the paper:

- **SUS score** per respondent, then mean, SD and median per group, graded on
  Table 5, with the count at or above 68.
- **Trust and security perception** mean and SD per item and overall, read on
  the section 3.10 bands.
- **Cronbach's alpha** for the trust scale. Below 0.70 it says so, and the scale
  shouldn't be interpreted until that's addressed.
- **Frequency and percentage** for each profile question.

Anyone who skipped a question is left out of that scale and counted in the
report, since a SUS score needs all ten answers. Names and pseudonyms never
appear in the output.
