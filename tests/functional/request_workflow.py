"""Functional test of the request workflow against the running local API:
submission, classification and routing, access scope, status changes,
reclassification, notifications, admin functions and the audit trail."""

import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8000"
ENV = dict(
    line.split("=", 1)
    for line in (ROOT / ".env").read_text().splitlines()
    if "=" in line and not line.lstrip().startswith("#")
)
ADMIN = (ENV["SEED_ADMIN_EMAIL"].strip(), ENV["SEED_ADMIN_PASSWORD"].strip())
DEMO_PW = ENV["SEED_DEMO_PASSWORD"].strip()
THRESHOLD = 0.70
STAMP = str(int(time.time()))
results = []
TERMS_VERSION = "2026-10-01"
areas = {}
AREA = "?"


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None, form=None, raw=None, ctype=None):
        if path == "/api/auth/register" and isinstance(body, dict):
            body = {"terms_version": TERMS_VERSION, **body}
        data, headers = None, {}
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif raw is not None:
            data, headers["Content-Type"] = raw, ctype
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req) as r:
                b = r.read()
                return r.status, (json.loads(b) if b else None)
        except urllib.error.HTTPError as e:
            b = e.read()
            try:
                return e.code, json.loads(b)
            except Exception:
                return e.code, b.decode(errors="replace")

    def login(self, email, pw):
        status = self.call("POST", "/api/auth/login", form={"username": email, "password": pw})[0]
        if status == 204:
            # Test accounts accept the current terms, as a person would on the accept screen.
            self.call("POST", "/api/auth/terms", {"version": TERMS_VERSION})
        return status

    def upload(self, rid, filename, content, mime):
        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.call("POST", f"/api/requests/{rid}/attachments", raw=body,
                         ctype=f"multipart/form-data; boundary={boundary}")


def area(name):
    global AREA
    AREA = name
    areas.setdefault(name, [0, 0])


def check(label, got, want):
    ok = got == want
    results.append(ok)
    areas[AREA][0 if ok else 1] += 1
    print(f"{'PASS' if ok else 'FAIL'}  [{AREA}] {label}: got {got!r}" + ("" if ok else f", want {want!r}"))


def psql(sql):
    return subprocess.run(["docker", "exec", "gabai-db", "psql", "-U", "gabai", "-d", "gabai", "-At", "-c", sql],
                          capture_output=True, text=True).stdout.strip()


def wait_classified(c, rid):
    for _ in range(60):
        s, r = c.call("GET", f"/api/requests/{rid}")
        if r and r.get("status") not in ("submitted", None):
            return r
        time.sleep(0.5)
    return r


maria, ramon, divina, admin = Client(), Client(), Client(), Client()
maria.login("maria.santos@example.com", DEMO_PW)
ramon.login("ramon.delgado@example.com", DEMO_PW)
divina.login("divina.bautista@example.com", DEMO_PW)
admin.login(*ADMIN)
RAMON = ramon.call("GET", "/api/auth/me")[1]["id"]
rules = {r["category"]["slug"]: r["staff"]["id"]
         for r in admin.call("GET", "/api/admin/routing-rules")[1] if r["is_active"]}

# --- a second resident, approved through the staff sign-up queue -----------------
area("Registration and approval")
other = Client()
oemail = f"functional.{STAMP}@example.com"
s, u = other.call("POST", "/api/auth/register", {"email": oemail, "password": "tubig-walang-7",
                                                  "full_name": "Pedro Test", "residence": "Purok 5"})
check("resident registers", s, 201)
check("new account is pending", u["approval_status"], "pending")
check("pending account can't submit", (other.login(oemail, "tubig-walang-7"),
      other.call("POST", "/api/requests", {"description": "May tagas ang tubo sa kanto namin"})[0]), (204, 403))
psql(f"update users set is_verified=true where email='{oemail}'")  # email confirmation, tested separately
check("staff approve the sign-up", divina.call("PATCH", f"/api/registrations/{u['id']}", {"approval_status": "approved"})[0], 200)

# --- submission ------------------------------------------------------------------
area("Request submission")
check("description under 10 characters refused", maria.call("POST", "/api/requests", {"description": "butas"})[0], 422)
check("description over 5,000 characters refused",
      maria.call("POST", "/api/requests", {"description": "a" * 5001})[0], 422)
texts = [
    "May malaking butas sa kalsada sa harap ng bahay namin sa Purok 2, delikado na sa mga motor lalo na sa gabi.",
    "Tatlong araw na pong walang tubig sa amin sa Mabini St, may matatanda po kami dito.",
    "Ang ingay po ng videoke ng kapitbahay namin hanggang alas dos ng madaling araw araw-araw.",
    "Good morning po, ano po ang requirements para sa barangay clearance?",
    "Hindi pa rin nakokolekta ang basura sa kanto namin, isang linggo na at nangangamoy na.",
    "May nag-aaway po sa labas ng tindahan, may hawak na kutsilyo ang isa, pakibilisan po.",
]
made = []
for t in texts:
    s, r = maria.call("POST", "/api/requests", {"description": t})
    made.append((s, r))
check("all six submissions accepted", [s for s, _ in made], [201] * 6)
check("each gets a GAB-YYYY-NNNNN reference number",
      all(re.fullmatch(r"GAB-\d{4}-\d{5}", r["reference_number"]) for _, r in made), True)
check("reference returned before classification finishes", made[0][1]["status"], "submitted")

# --- classification and routing -----------------------------------------------------
area("Classification and routing")
done = [wait_classified(maria, r["id"]) for _, r in made]
check("every request classified", all(d["classified_at"] and d["predicted_category"] for d in done), True)
check("model version recorded", all("xlm-roberta-base-2026-09-22-r2321" in d["model_version"] for d in done), True)
gate_ok, route_ok = True, True
for d in done:
    low = min(d["category_confidence"], d["urgency_confidence"])
    want = "routed" if low >= THRESHOLD else "under_review"
    gate_ok &= d["status"] == want
    if d["status"] == "routed":
        route_ok &= (d["assigned_staff"] or {}).get("id") == rules[d["predicted_category"]["slug"]]
check("routed only when the lower confidence reaches 0.70, else review", gate_ok, True)
check("routed requests go to the staff member holding that category's rule", route_ok, True)
print("   outcomes:", [(d["predicted_category"]["slug"], d["predicted_urgency"],
                       round(min(d["category_confidence"], d["urgency_confidence"]), 2), d["status"]) for d in done])
rid = done[0]["id"]
sys_rows = psql(f"select count(*) from status_history_entries where request_id={rid} and actor_id is null")
check("system's routing transition recorded with no human actor", int(sys_rows) >= 1, True)

# --- attachments -----------------------------------------------------------------------
area("Attachments")
png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
check("image attachment accepted", maria.upload(rid, "butas.png", png, "image/png")[0], 201)
s, _ = maria.upload(rid, "tool.exe", b"MZ" + b"\x00" * 64, "application/x-msdownload")
check("executable refused", 400 <= s < 500, True)
s, _ = maria.upload(rid, "big.png", b"\x89PNG" + b"\x00" * (5 * 1024 * 1024 + 10), "image/png")
check("file over 5 MB refused", 400 <= s < 500, True)

# --- access scope ------------------------------------------------------------------------
area("Access control")
owner = rules[done[0]["predicted_category"]["slug"]] if done[0]["status"] == "routed" else None
check("resident sees own request", maria.call("GET", f"/api/requests/{rid}")[0], 200)
check("another resident gets 404 for it", other.call("GET", f"/api/requests/{rid}")[0], 404)
check("another resident's list excludes it",
      rid in [x["id"] for x in other.call("GET", "/api/requests")[1]["items"]], False)
if owner:
    mine, notmine = (ramon, divina) if owner == RAMON else (divina, ramon)
    check("assigned staff member sees it", mine.call("GET", f"/api/requests/{rid}")[0], 200)
    check("staff member without that category gets 404", notmine.call("GET", f"/api/requests/{rid}")[0], 404)
check("administrator sees it", admin.call("GET", f"/api/requests/{rid}")[0], 200)
check("resident can't open the review queue", maria.call("GET", "/api/review-queue")[0], 403)
check("staff can open the review queue", ramon.call("GET", "/api/review-queue")[0], 200)
check("resident can't change status",
      maria.call("PATCH", f"/api/requests/{rid}/status", {"to_status": "in_progress"})[0], 403)
check("staff can't read the audit log", ramon.call("GET", "/api/admin/audit-log")[0], 403)
check("staff can't change routing rules", ramon.call("GET", "/api/admin/routing-rules")[0], 403)
check("staff can't list accounts", ramon.call("GET", "/api/admin/users")[0], 403)

# --- staff queue order ----------------------------------------------------------------------
area("Staff work queue")
rank = {"high": 0, "medium": 1, "low": 2, None: 3}
items = ramon.call("GET", "/api/requests?limit=100")[1]["items"]
keys = [(rank[i["urgency"]], i["created_at"]) for i in items]
check("queue lists highest urgency first, oldest first within a level", keys == sorted(keys), True)

# --- status changes and notifications ----------------------------------------------------------
area("Status updates and notifications")
routed = next((d for d in done if d["status"] == "routed"), None)
staff = ramon if rules[routed["predicted_category"]["slug"]] == RAMON else divina
r2 = routed["id"]
before = maria.call("GET", "/api/notifications")[1]["total"]
check("routed to in progress", staff.call("PATCH", f"/api/requests/{r2}/status",
      {"to_status": "in_progress", "note": "Pupuntahan po bukas."})[0], 200)
check("skipping straight to closed is refused",
      staff.call("PATCH", f"/api/requests/{r2}/status", {"to_status": "closed"})[0], 409)
check("in progress to resolved", staff.call("PATCH", f"/api/requests/{r2}/status",
      {"to_status": "resolved", "note": "Naayos na po."})[0], 200)
s, fin = staff.call("PATCH", f"/api/requests/{r2}/status", {"to_status": "closed"})
check("resolved to closed", s, 200)
check("resolution time recorded", fin["resolved_at"] is not None, True)
hist = [h["to_status"] for h in maria.call("GET", f"/api/requests/{r2}")[1]["status_history"]]
check("resident sees the full status history", hist[-3:], ["in_progress", "resolved", "closed"])
after = maria.call("GET", "/api/notifications")[1]["total"]
check("resident notified of each staff status change", after - before, 3)
check("status changes written to the audit log with the staff actor", psql(
    f"select count(*) from audit_log_entries where action='request.status_changed' and object_id='{r2}' "
    f"and actor_id is not null"), "3")

# --- reclassification ------------------------------------------------------------------------------
area("Reclassification")
target = next(d for d in done if d["id"] not in (r2,) and d["status"] in ("routed", "under_review"))
cats = {c["slug"]: c["id"] for c in admin.call("GET", "/api/categories")[1]}
cur = (target["final_category"] or target["predicted_category"])["slug"]
new = "utilities" if rules[cur] != rules["utilities"] else "road_infrastructure"
before = maria.call("GET", "/api/notifications")[1]["total"]
s, rc = admin.call("PATCH", f"/api/requests/{target['id']}/classification",
                   {"final_category_id": cats[new], "final_urgency": "high"})
check("staff-set category accepted", s, 200)
check("request rerouted to the new category's handler", rc["assigned_staff"]["id"], rules[new])
check("model's original prediction kept", rc["predicted_category"]["slug"], target["predicted_category"]["slug"])
check("final category stored separately", rc["final_category"]["slug"], new)
check("resident told the request moved", maria.call("GET", "/api/notifications")[1]["total"] - before, 1)
check("reclassification audited", psql(
    f"select count(*) from audit_log_entries where action='request.reclassified' and object_id='{target['id']}'"), "1")

# --- administrator functions --------------------------------------------------------------------------
area("Administrator functions")
s, log = admin.call("GET", "/api/admin/audit-log?limit=50")
check("administrator reads the audit log", s, 200)
check("audit log includes the status changes above",
      any(e["action"] == "request.status_changed" and e["object_id"] == str(r2) for e in log["items"]), True)
s, current = admin.call("GET", "/api/admin/routing-rules")
active = [{"category_id": r["category"]["id"], "staff_id": r["staff"]["id"]} for r in current if r["is_active"]]
check("administrator saves the routing table", admin.call("PUT", "/api/admin/routing-rules", {"rules": active})[0], 200)
check("earlier rules kept as inactive, not deleted", int(psql("select count(*) from routing_rules where not is_active")) >= 7, True)
s, st = admin.call("POST", "/api/admin/users", {"email": f"staff.{STAMP}@example.com", "password": "Pansamantala-88",
                                                "full_name": "Staff Test", "role": "staff"})
check("administrator creates a staff account", s, 201)
check("administrator deactivates it", admin.call("PATCH", f"/api/admin/users/{st['id']}", {"is_active": False})[0], 200)
check("deactivated account can't sign in", Client().login(f"staff.{STAMP}@example.com", "Pansamantala-88") in (400, 401, 403), True)
some_cat = active[0]["category_id"]
swap = lambda staff_id: [dict(r, staff_id=staff_id) if r["category_id"] == some_cat else r for r in active]
check("routing can't be given to a deactivated account",
      admin.call("PUT", "/api/admin/routing-rules", {"rules": swap(st["id"])})[0], 422)
MARIA = maria.call("GET", "/api/auth/me")[1]["id"]
check("routing can't be given to a resident", admin.call("PUT", "/api/admin/routing-rules", {"rules": swap(MARIA)})[0], 422)
check("administrator reactivates it", admin.call("PATCH", f"/api/admin/users/{st['id']}", {"is_active": True})[0], 200)
check("reactivation is recorded",
      int(psql(f"select count(*) from audit_log_entries where action='user.reactivated' and object_id='{st['id']}'")), 1)

# A request that routed above, sent again after its category's handler is
# deactivated, then after the handler is changed to a resident.
routed = [(t, d) for t, d in zip(texts, done) if d["status"] == "routed"]
text, d = routed[0]
cat = d["predicted_category"]["id"]
moved = [dict(r, staff_id=st["id"]) if r["category_id"] == cat else r for r in active]
try:
    admin.call("PUT", "/api/admin/routing-rules", {"rules": moved})
    admin.call("PATCH", f"/api/admin/users/{st['id']}", {"is_active": False})
    check("routing table still saves with a handler deactivated after assignment",
          admin.call("PUT", "/api/admin/routing-rules", {"rules": moved})[0], 200)
    again = wait_classified(maria, maria.call("POST", "/api/requests", {"description": text})[1]["id"])
    check("a deactivated handler's category goes to review", again["status"], "under_review")
    s, rl = divina.call("PATCH", f"/api/requests/{again['id']}/classification",
                        {"final_category_id": cat, "final_urgency": "high"})
    check("staff labelling into that category also leaves it in review", (s, rl["status"]), (200, "under_review"))
    admin.call("PATCH", f"/api/admin/users/{st['id']}", {"is_active": True, "role": "citizen"})
    check("routing table still saves with a handler changed to a resident",
          admin.call("PUT", "/api/admin/routing-rules", {"rules": moved})[0], 200)
    again = wait_classified(maria, maria.call("POST", "/api/requests", {"description": text})[1]["id"])
    check("a former handler's category goes to review", again["status"], "under_review")
finally:
    check("routing table restored", admin.call("PUT", "/api/admin/routing-rules", {"rules": active})[0], 200)

print(f"\n{sum(results)}/{len(results)} checks passed")
for a, (p, f) in areas.items():
    print(f"  {a}: {p} passed, {f} failed")
