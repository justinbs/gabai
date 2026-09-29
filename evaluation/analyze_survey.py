"""Turn the survey export into the tables for Chapter 4, sections 4.1, 4.5, 4.6.

    python evaluation/analyze_survey.py responses.csv
    python evaluation/analyze_survey.py responses.csv --out evaluation/results

Reads the CSV that Google Forms downloads (File > Download > .csv), unchanged.
Standard library only, so it runs on any computer with Python 3.10 or later.

It finds the questions by their wording, so the form's question titles need to
contain the statements from Tables 3 and 4 of the paper. Answers can be the
numbers 1 to 5 or the words ("Strongly agree"). If a question is worded
differently, point at the column directly with --sus-cols and --trust-cols.

Everything follows section 3.10 of the paper:
- SUS: odd items score (answer - 1), even items (5 - answer), sum x 2.5,
  graded on Table 5.
- Trust scale: mean and SD per item and overall, read on the 1.80-point bands,
  with Cronbach's alpha checked against 0.70 before anything is interpreted.
- Demographics: frequency and percentage, % = f / N x 100.

A respondent missing any item of a scale is left out of that scale and counted,
since a SUS score from nine answers isn't a SUS score.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
from pathlib import Path

# Table 3, in order. Matched loosely, so punctuation and case don't matter.
SUS_ITEMS = [
    "I think that I would like to use this system frequently",
    "I found the system unnecessarily complex",
    "I thought the system was easy to use",
    "I think that I would need the support of a technical person to be able to use this system",
    "I found the various functions in this system were well integrated",
    "I thought there was too much inconsistency in this system",
    "I would imagine that most people would learn to use this system very quickly",
    "I found the system very cumbersome to use",
    "I felt very confident using the system",
    "I needed to learn a lot of things before I could get going with this system",
]

# Table 4, in order.
TRUST_ITEMS = [
    "I feel that my personal information is safe when using this system",
    "I trust that the government office responsible for this system will handle my requests properly",
    "I believe this system is secure enough for me to submit sensitive requests or complaints",
    "I would feel comfortable using this system to communicate with local government offices",
    "I am confident that unauthorized persons cannot access my submitted requests in this system",
]

# Table 5.
SUS_GRADES = [
    (90.0, "A+", "Best Imaginable"),
    (85.0, "A", "Excellent"),
    (80.0, "A-", "Excellent"),
    (70.0, "B", "Good"),
    (65.0, "C", "Okay"),
    (51.7, "D", "Poor"),
    (0.0, "F", "Awful"),
]

# Section 3.10 Likert bands.
LIKERT_BANDS = [
    (4.20, "Strongly Agree (Very High)"),
    (3.40, "Agree (High)"),
    (2.60, "Neutral (Moderate)"),
    (1.80, "Disagree (Low)"),
    (1.00, "Strongly Disagree (Very Low)"),
]

WORDS = {
    "strongly disagree": 1,
    "disagree": 2,
    "neutral": 3,
    "neither agree nor disagree": 3,
    "agree": 4,
    "strongly agree": 5,
}

SUS_BENCHMARK = 68.0
ALPHA_MINIMUM = 0.70


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_columns(headers: list[str], statements: list[str]) -> list[str | None]:
    found = []
    for statement in statements:
        key = squash(statement)
        match = next((h for h in headers if key in squash(h)), None)
        found.append(match)
    return found


def to_score(raw: str) -> int | None:
    value = raw.strip().lower()
    if not value:
        return None
    if value in WORDS:
        return WORDS[value]
    # "5", "5 - Strongly agree", "5.0"
    number = re.match(r"^\s*([1-5])(\.0)?\b", value)
    return int(number.group(1)) if number else None


def sus_score(answers: list[int]) -> float:
    total = 0
    for position, answer in enumerate(answers, start=1):
        total += (answer - 1) if position % 2 == 1 else (5 - answer)
    return total * 2.5


def sus_grade(score: float) -> tuple[str, str]:
    for floor, grade, adjective in SUS_GRADES:
        if score >= floor:
            return grade, adjective
    return SUS_GRADES[-1][1], SUS_GRADES[-1][2]


def likert_band(mean: float) -> str:
    for floor, label in LIKERT_BANDS:
        if mean >= floor:
            return label
    return LIKERT_BANDS[-1][1]


def sd(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def cronbach_alpha(rows: list[list[int]]) -> float | None:
    # alpha = k/(k-1) * (1 - sum of item variances / variance of totals),
    # sample variances throughout.
    if len(rows) < 2:
        return None
    k = len(rows[0])
    item_variances = [statistics.variance([r[i] for r in rows]) for i in range(k)]
    total_variance = statistics.variance([sum(r) for r in rows])
    if total_variance == 0:
        return None
    return (k / (k - 1)) * (1 - sum(item_variances) / total_variance)


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, text: str = "") -> None:
        self.lines.append(text)
        print(text)

    def table(self, header: list[str], rows: list[list[str]]) -> None:
        self.add("| " + " | ".join(header) + " |")
        self.add("|" + "|".join("---" for _ in header) + "|")
        for row in rows:
            self.add("| " + " | ".join(row) + " |")
        self.add()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path)
    parser.add_argument("--out", type=Path, default=None, help="folder for the markdown and CSV tables")
    parser.add_argument("--group-col", default=None, help="column naming the respondent group")
    parser.add_argument("--sus-cols", nargs=10, default=None, metavar="COL")
    parser.add_argument("--trust-cols", nargs=5, default=None, metavar="COL")
    parser.add_argument("--demographic-cols", nargs="*", default=None, metavar="COL")
    args = parser.parse_args()

    with args.csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        responses = list(reader)
    if not responses:
        sys.exit("No responses in that file.")

    sus_cols = args.sus_cols or find_columns(headers, SUS_ITEMS)
    trust_cols = args.trust_cols or find_columns(headers, TRUST_ITEMS)
    missing = [SUS_ITEMS[i] for i, c in enumerate(sus_cols) if c is None] + [
        TRUST_ITEMS[i] for i, c in enumerate(trust_cols) if c is None
    ]
    if missing:
        print("Couldn't find these questions in the file's columns:")
        for statement in missing:
            print(f"  - {statement}")
        sys.exit("Rename the form questions to match, or pass --sus-cols / --trust-cols.")

    group_col = args.group_col or next(
        (h for h in headers if re.search(r"\b(group|role|respondent type)\b", h, re.I)), None
    )
    used = set(sus_cols) | set(trust_cols) | {group_col, "Timestamp"}
    demographic_cols = (
        args.demographic_cols
        if args.demographic_cols is not None
        else [h for h in headers if h not in used and not re.search(r"name|pseudonym|email|consent", h, re.I)]
    )

    def group_of(row: dict) -> str:
        return (row.get(group_col) or "").strip() or "(no group)" if group_col else "All respondents"

    groups = sorted({group_of(r) for r in responses})
    report = Report()
    report.add(f"# Survey results, {len(responses)} responses")
    report.add()
    report.add(f"Group column: {group_col or 'none found, treated as one group'}")
    report.add()

    sus_rows_out = [["Group", "n", "Mean SUS", "SD", "Median", "Grade", "Adjective", f"At or above {SUS_BENCHMARK:g}"]]
    trust_item_rows = [["Group", "Item", "Statement", "Mean", "SD", "Interpretation"]]

    for group in groups + (["All respondents"] if len(groups) > 1 else []):
        members = responses if group == "All respondents" else [r for r in responses if group_of(r) == group]
        report.add(f"## {group} (N = {len(members)})")
        report.add()

        # SUS
        scores, excluded = [], 0
        item_answers: list[list[int]] = [[] for _ in range(10)]
        for row in members:
            answers = [to_score(row.get(c, "")) for c in sus_cols]
            if None in answers:
                excluded += 1
                continue
            scores.append(sus_score(answers))
            for i, a in enumerate(answers):
                item_answers[i].append(a)
        if scores:
            mean = statistics.mean(scores)
            grade, adjective = sus_grade(mean)
            above = sum(1 for s in scores if s >= SUS_BENCHMARK)
            report.add(f"SUS: mean {mean:.2f}, SD {sd(scores):.2f}, median {statistics.median(scores):.2f}, "
                       f"grade {grade} ({adjective}), n = {len(scores)}"
                       + (f", {excluded} left out for a missing item" if excluded else ""))
            report.add()
            report.table(
                ["Item", "Statement", "Mean", "SD"],
                [[str(i + 1), SUS_ITEMS[i], f"{statistics.mean(v):.2f}", f"{sd(v):.2f}"]
                 for i, v in enumerate(item_answers)],
            )
            sus_rows_out.append([group, str(len(scores)), f"{mean:.2f}", f"{sd(scores):.2f}",
                                 f"{statistics.median(scores):.2f}", grade, adjective,
                                 f"{above} ({100 * above / len(scores):.1f}%)"])
        else:
            report.add("SUS: no complete responses")
            report.add()

        # Trust and security perception
        complete, excluded = [], 0
        for row in members:
            answers = [to_score(row.get(c, "")) for c in trust_cols]
            if None in answers:
                excluded += 1
                continue
            complete.append(answers)
        if complete:
            alpha = cronbach_alpha(complete)
            overall = [statistics.mean(r) for r in complete]
            if alpha is None:
                alpha_text = "not computable (fewer than 2 responses, or no variation)"
            else:
                verdict = "acceptable" if alpha >= ALPHA_MINIMUM else f"BELOW {ALPHA_MINIMUM}, don't interpret the scale yet"
                alpha_text = f"{alpha:.3f}, {verdict}"
            report.add(f"Trust and security: overall mean {statistics.mean(overall):.2f}, SD {sd(overall):.2f}, "
                       f"{likert_band(statistics.mean(overall))}; Cronbach's alpha {alpha_text}"
                       + (f"; {excluded} left out for a missing item" if excluded else ""))
            report.add()
            rows = []
            for i in range(5):
                values = [r[i] for r in complete]
                m = statistics.mean(values)
                rows.append([str(i + 1), TRUST_ITEMS[i], f"{m:.2f}", f"{sd(values):.2f}", likert_band(m)])
                trust_item_rows.append([group] + rows[-1])
            report.table(["Item", "Statement", "Mean", "SD", "Interpretation"], rows)
        else:
            report.add("Trust and security: no complete responses")
            report.add()

    # Demographics, section 4.1
    if demographic_cols:
        report.add("## Respondent profile")
        report.add()
        for column in demographic_cols:
            counts: dict[str, int] = {}
            for row in responses:
                answer = (row.get(column) or "").strip() or "(no answer)"
                counts[answer] = counts.get(answer, 0) + 1
            total = len(responses)
            report.add(f"### {column}")
            report.add()
            report.table(
                ["Response", "f", "%"],
                [[k, str(v), f"{100 * v / total:.1f}"] for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
                + [["Total", str(total), "100.0"]],
            )

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "survey_report.md").write_text("\n".join(report.lines) + "\n", encoding="utf-8")
        for name, table in (("sus_by_group.csv", sus_rows_out), ("trust_items.csv", trust_item_rows)):
            with (args.out / name).open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerows(table)
        print(f"\nWrote {args.out / 'survey_report.md'}, sus_by_group.csv, trust_items.csv")


if __name__ == "__main__":
    main()
