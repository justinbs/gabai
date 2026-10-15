"""Count scan alerts by severity.   python tests/security/summarize.py tests/security/results/round1"""
import json
import sys
from collections import Counter
from pathlib import Path

folder = Path(sys.argv[1])


def load(name):
    p = folder / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def show(title, counter):
    keys = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    parts = [f"{k} {counter.get(k, 0)}" for k in keys]
    print(f"{title:34} " + ", ".join(parts) + f"   (total {sum(counter.values())})")


b = load("bandit.json")
if b:
    show("Bandit (code)", Counter(r["issue_severity"] for r in b["results"]))
t = load("trivy.json")
if t:
    v, m, s = Counter(), Counter(), Counter()
    for r in t.get("Results", []):
        for x in r.get("Vulnerabilities") or []:
            v[x["Severity"]] += 1
        for x in r.get("Misconfigurations") or []:
            m[x["Severity"]] += 1
        for x in r.get("Secrets") or []:
            s[x["Severity"]] += 1
    show("Trivy (dependency CVEs)", v)
    show("Trivy (Docker/compose config)", m)
    show("Trivy (secrets in files)", s)
g = load("gitleaks.json")
print(f"{'gitleaks (secrets in history)':34} {len(g) if isinstance(g, list) else 0} findings")
z = load("zap-baseline.json")
if z:
    risk = {"3": "HIGH", "2": "MEDIUM", "1": "LOW", "0": "INFO"}
    c = Counter()
    for site in z.get("site", []):
        for a in site.get("alerts", []):
            c[risk.get(str(a.get("riskcode")), "INFO")] += 1
    show("ZAP passive (live site)", c)