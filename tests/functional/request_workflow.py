"""Functional test of the request workflow against the running local API:
submission, classification and routing, access scope, status changes,
reclassification, notifications, admin functions and the audit trail."""

import json
import os
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
PLACE = None  # set below if the admin has listed places
THRESHOLD = 0.70
LOW_URGENCY_MIN = 0.85
STAMP = str(int(time.time()))
results = []
TERMS_VERSION = "2026-10-16"
areas = {}
AREA = "?"


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None, form=None, raw=None, ctype=None):
        if path == "/api/auth/register" and isinstance(body, dict):
            body = {"terms_version": TERMS_VERSION, **body}
        # Once the admin lists places, a submission has to name one.
        if method == "POST" and path == "/api/requests" and isinstance(body, dict) and PLACE and "location_id" not in body:
            body = {**body, "location_id": PLACE}
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

    def get_bytes(self, path):
        try:
            with self.opener.open(BASE + path) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

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


def staff_queue_ids(c):
    # Every page: the local test database holds hundreds of requests from earlier runs.
    ids, offset = set(), 0
    while True:
        page = c.call("GET", f"/api/requests?limit=100&offset={offset}")[1]
        ids |= {i["id"] for i in page["items"]}
        offset += 100
        if offset >= page["total"]:
            return ids


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
PLACE = next((p["id"] for p in admin.call("GET", "/api/locations")[1]), None)
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
check("staff approve the sign-up", divina.call("PATCH", f"/api/registrations/{u['id']}", {"approval_status": "approved", "verification_method": "personally_known"})[0], 200)

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
check("each submission is audited without its text",
      psql(f"select count(*), count(*) filter (where coalesce(detail::text, 'null') <> 'null') from audit_log_entries where action='request.submitted' and object_id='{made[0][1]['id']}'"), "1|0")

# --- classification and routing -----------------------------------------------------
area("Classification and routing")
done = [wait_classified(maria, r["id"]) for _, r in made]
check("every request classified", all(d["classified_at"] and d["predicted_category"] for d in done), True)
check("model version recorded", all("xlm-roberta-base-2026-09-22-r2321" in d["model_version"] for d in done), True)
gate_ok, route_ok = True, True
for d in done:
    low = min(d["category_confidence"], d["urgency_confidence"])
    unsure_low = d["predicted_urgency"] == "low" and d["urgency_confidence"] < LOW_URGENCY_MIN
    want = "routed" if low >= THRESHOLD and not unsure_low else "under_review"
    gate_ok &= d["status"] == want
    if d["status"] == "routed":
        route_ok &= (d["assigned_staff"] or {}).get("id") == rules[d["predicted_category"]["slug"]]
check("routed only when the lower confidence reaches 0.70 (0.85 for a low urgency), else review", gate_ok, True)
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
s, _ = maria.upload(rid, "notes.png", b"just some text, not an image" * 4, "image/png")
check("text file named .png refused by its contents", s, 415)
pdf = b"%PDF-1.4\n" + b"\x00" * 64
check("PDF attachment accepted", maria.upload(rid, "resibo.pdf", pdf, "application/pdf")[0], 201)
check("another resident uploading to it gets 404", other.upload(rid, "x.png", png, "image/png")[0], 404)

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
OPEN = ("submitted", "under_review", "routed", "in_progress")


def queue_key(i):
    flagged = 0 if i["urgent_pinned"] else 1
    # A request left waiting sorts one level higher; the label itself stays.
    return (flagged, i["status"] == "resolved", rank[i["urgency"]] - (1 if i["aged"] else 0), i["created_at"])


def queue_ordered(c):
    items = c.call("GET", "/api/requests?limit=100")[1]["items"]
    keys = [queue_key(i) for i in items]
    return keys == sorted(keys)


check("queue lists highest urgency first, oldest first within a level", queue_ordered(ramon), True)

# --- urgency safeguards --------------------------------------------------------------------
area("Urgency safeguards")
routed_id = next((d["id"] for d in done if d["status"] == "routed"), None)
reason = "May matanda po kaming kasama na hindi makalakad"
check("staff can't use the resident's urgent flag",
      ramon.call("PUT", f"/api/requests/{rid}/urgent-flag", {"reason": reason})[0], 403)
check("another resident can't flag it (404)",
      other.call("PUT", f"/api/requests/{rid}/urgent-flag", {"reason": reason})[0], 404)
s, _ = other.call("POST", "/api/requests", {"description": "May sirang poste ng ilaw sa kanto ng Purok 5 namin"})
planted = [r for r in other.call("GET", "/api/requests")[1]["items"]][0]["id"]
check("a reason that looks like stored ciphertext is accepted and encrypted",
      other.call("PUT", f"/api/requests/{planted}/urgent-flag", {"reason": "gabai:enc:1:AAAAAAAAAAAA"})[0], 200)
check("the staff queue still loads after it", admin.call("GET", "/api/requests?limit=100")[0], 200)
check("the reason reads back as typed", admin.call("GET", f"/api/requests/{planted}")[1]["urgent_reason"], "gabai:enc:1:AAAAAAAAAAAA")
check("a blank reason is refused",
      maria.call("PUT", f"/api/requests/{rid}/urgent-flag", {"reason": "   "})[0], 422)
notes_before = None
if done[0]["status"] == "routed":
    handler = ramon if rules[done[0]["predicted_category"]["slug"]] == RAMON else divina
    notes_before = handler.call("GET", "/api/notifications")[1]["total"]
s, b = maria.call("PUT", f"/api/requests/{rid}/urgent-flag", {"reason": reason})
check("resident marks own request urgent", (s, b["urgent_flagged_at"] is not None, b["urgent_reason"]), (200, True, reason))
check("the urgency label is unchanged", b["urgency"], done[0]["urgency"])
check("marking it twice is refused", maria.call("PUT", f"/api/requests/{rid}/urgent-flag", {"reason": reason})[0], 409)
if notes_before is not None:
    check("the assigned staff member is notified", handler.call("GET", "/api/notifications")[1]["total"] - notes_before, 1)
check("the reason is stored encrypted",
      psql(f"select left(urgent_reason, 10) from requests where id={rid}"), "gabai:enc:")
check("the audit row has no reason text",
      psql(f"select coalesce(detail::text,'null') from audit_log_entries where action='request.flagged_urgent' and object_id='{rid}'"), "null")
check("flagged requests come first in the staff queue", queue_ordered(admin), True)
review = admin.call("GET", "/api/review-queue?limit=100")[1]["items"]
flags = [0 if i["urgent_pinned"] else 1 for i in review]
check("flagged requests come first in For review", flags == sorted(flags), True)
# Staff relabelling it, even to the same labels, means they've read the flag.
pin = admin.call("GET", f"/api/requests/{planted}")[1]
cat = pin["category"]["id"] if pin["category"] else admin.call("GET", "/api/categories")[1][0]["id"]
admin.call("PATCH", f"/api/requests/{planted}/classification", {"final_category_id": cat, "final_urgency": pin["urgency"] or "low"})
pin = admin.call("GET", f"/api/requests/{planted}")[1]
check("a staff action ends the pin, the flag itself stays", (pin["urgent_pinned"], pin["urgent_flagged_at"] is not None), (False, True))
check("the queue order still holds after", queue_ordered(admin), True)

# Waiting time: make one open request look untouched for three days. Status
# history refuses edits, so the suite lifts that protection for this one update,
# inside one transaction. Local test database only; never point this at the
# live server.
aged_one = next((d for d in done[1:] if d["status"] in ("routed", "under_review") and d["id"] != routed_id), None)
if aged_one:
    psql(f"update requests set final_urgency='low' where id={aged_one['id']}")
    psql("begin; alter table status_history_entries disable trigger status_history_entries_no_rewrite; "
         f"update status_history_entries set created_at = now() - interval '3 days' where request_id={aged_one['id']}; "
         "alter table status_history_entries enable trigger status_history_entries_no_rewrite; commit;")
    s, b = admin.call("GET", f"/api/requests/{aged_one['id']}")
    check("a low request untouched for 48 hours is marked as waiting", (b["urgency"], b["aged"]), ("low", True))
    check("waiting raises its place in the queue, not its label", queue_ordered(admin), True)

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
# Every page: earlier runs leave many open requests ahead of it.
queue, offset = [], 0
while True:
    page = staff.call("GET", "/api/requests?status=routed&status=in_progress&status=classified&status=resolved"
                             f"&limit=100&offset={offset}")[1]
    queue += page["items"]
    offset += 100
    if offset >= page["total"]:
        break
seen = [i["status"] == "resolved" for i in queue]
check("a resolved request stays in the staff queue, below the open ones",
      (r2 in [i["id"] for i in queue], seen == sorted(seen)), (True, True))
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

# --- referrals --------------------------------------------------------------------------
area("Referrals")
agencies = admin.call("GET", "/api/admin/agencies")[1]
meralco = next(a for a in agencies if a["name"] == "Meralco")
check("staff can list active agencies", ramon.call("GET", "/api/agencies")[0], 200)
check("a resident can't list agencies", maria.call("GET", "/api/agencies")[0], 403)
check("staff can't edit agencies", ramon.call("PATCH", f"/api/admin/agencies/{meralco['id']}", {"phone": "1"})[0], 403)
s, a = admin.call("PATCH", f"/api/admin/agencies/{meralco['id']}", {"phone": "0917 000 0000", "website": "https://example.com"})
check("admin saves contact details", (s, a["phone"]), (200, "0917 000 0000"))
check("a website that isn't http(s) is refused",
      admin.call("PATCH", f"/api/admin/agencies/{meralco['id']}", {"website": "javascript:alert(1)"})[0], 422)

ref = wait_classified(maria, maria.call("POST", "/api/requests", {"description": texts[1]})[1]["id"])
check("a resident can't refer", maria.call("PUT", f"/api/requests/{ref['id']}/referral", {"agency_id": meralco["id"]})[0], 403)
before = maria.call("GET", "/api/notifications")[1]["total"]
s, r = admin.call("PUT", f"/api/requests/{ref['id']}/referral", {"agency_id": meralco["id"], "note": "Meralco po ang may hawak"})
check("admin refers it", (s, r["status"], r["assigned_staff"], (r["referred_agency"] or {}).get("name")), (200, "referred", None, "Meralco"))
check("the resident is notified once", maria.call("GET", "/api/notifications")[1]["total"] - before, 1)
s, mine = maria.call("GET", f"/api/requests/{ref['id']}")
check("the resident sees the agency and its phone", (mine["referred_agency"]["phone"], mine["referral_note"]), ("0917 000 0000", "Meralco po ang may hawak"))
check("referring twice is refused", admin.call("PUT", f"/api/requests/{ref['id']}/referral", {"agency_id": meralco["id"]})[0], 409)
check("it can't be set in progress", admin.call("PATCH", f"/api/requests/{ref['id']}/status", {"to_status": "in_progress"})[0], 409)
check("it can't be relabelled while referred",
      admin.call("PATCH", f"/api/requests/{ref['id']}/classification", {"final_category_id": cats["utilities"], "final_urgency": "high"})[0], 409)
check("the resident can't flag it urgent", maria.call("PUT", f"/api/requests/{ref['id']}/urgent-flag", {"reason": "kailangan na po ito"})[0], 409)
check("the referral is audited", int(psql(f"select count(*) from audit_log_entries where action='request.referred' and object_id='{ref['id']}'")), 1)
check("the note is stored encrypted", psql(f"select left(referral_note, 10) from requests where id={ref['id']}"), "gabai:enc:")
s, back = admin.call("DELETE", f"/api/requests/{ref['id']}/referral")
check("taking it back re-routes it", (s, back["status"] in ("routed", "under_review"), back["referred_agency"]), (200, True, None))
check("taking back an unreferred request is refused", admin.call("DELETE", f"/api/requests/{ref['id']}/referral")[0], 409)
admin.call("PUT", f"/api/requests/{ref['id']}/referral", {"agency_id": meralco["id"]})
check("a referred request can be closed", admin.call("PATCH", f"/api/requests/{ref['id']}/status", {"to_status": "closed"})[0], 200)

admin.call("PATCH", f"/api/admin/agencies/{meralco['id']}", {"is_active": False})
spare = wait_classified(maria, maria.call("POST", "/api/requests", {"description": texts[1]})[1]["id"])
check("a switched-off agency can't be picked",
      admin.call("PUT", f"/api/requests/{spare['id']}/referral", {"agency_id": meralco["id"]})[0], 422)
admin.call("PATCH", f"/api/admin/agencies/{meralco['id']}", {"is_active": True})

# --- requests whose classification never ran ---------------------------------------------------
area("Requests left unclassified")


def in_review_queue(c, rid):
    ids, offset = [], 0
    while True:
        page = c.call("GET", f"/api/review-queue?limit=100&offset={offset}")[1]
        ids += [x["id"] for x in page["items"]]
        offset += 100
        if not page["items"] or offset >= page["total"]:
            return rid in ids


# Put a classified request back to submitted, as if the background step never ran.
sid = wait_classified(maria, maria.call("POST", "/api/requests", {"description": texts[1]})[1]["id"])["id"]
psql(f"update requests set status='submitted', assigned_staff_id=null where id={sid}")
check("a request at submitted for under 2 minutes is not in the review queue", in_review_queue(divina, sid), False)
psql(f"update requests set created_at=now() - interval '3 minutes' where id={sid}")
check("one at submitted for over 2 minutes is in the review queue", in_review_queue(divina, sid), True)
s, sl = divina.call("PATCH", f"/api/requests/{sid}/classification",
                    {"final_category_id": cats["utilities"], "final_urgency": "high"})
check("staff label it and it goes to that category's handler",
      (s, sl["status"], (sl["assigned_staff"] or {}).get("id")), (200, "routed", rules["utilities"]))
check("it leaves the review queue", in_review_queue(divina, sid), False)

# --- duplicate reports ----------------------------------------------------------------------
area("Duplicate reports")
water = [
    "Walang tubig sa buong Purok 4 mula pa kahapon, wala na po kaming maiinom at maipanligo.",
    "Wala pong tubig dito sa Purok 4 mula kahapon, wala na kaming maiinom.",
    "Purok 4 po, wala pa ring tubig mula kahapon, wala na kaming maiinom dito.",
]
d1 = wait_classified(maria, maria.call("POST", "/api/requests", {"description": water[0]})[1]["id"])
d2 = wait_classified(other, other.call("POST", "/api/requests", {"description": water[1]})[1]["id"])
d3 = wait_classified(maria, maria.call("POST", "/api/requests", {"description": water[2]})[1]["id"])
same_cat = d1["category"] and d2["category"] and d3["category"] and \
    d1["category"]["id"] == d2["category"]["id"] == d3["category"]["id"]
check("three reports of one problem land in one category", bool(same_cat), True)

sug2 = admin.call("GET", f"/api/requests/{d2['id']}/duplicate-suggestions")[1]
check("the second report suggests the first", d1["id"] in [s["candidate"]["id"] for s in sug2], True)
sug3 = admin.call("GET", f"/api/requests/{d3['id']}/duplicate-suggestions")[1]
check("the third report suggests both earlier ones",
      {d1["id"], d2["id"]} <= {s["candidate"]["id"] for s in sug3}, True)
check("a resident can't see suggestions", maria.call("GET", f"/api/requests/{d3['id']}/duplicate-suggestions")[0], 403)
# An earlier report still waiting for review can't take a report already routed,
# so it isn't offered. Local test database: statuses set back afterwards.
was1 = psql(f"select status from requests where id={d1['id']}")
was2 = psql(f"select status from requests where id={d2['id']}")
psql(f"update requests set status='under_review' where id={d1['id']}")
psql(f"update requests set status='routed' where id={d2['id']}")
check("an earlier report behind this one isn't offered to link it to",
      d1["id"] in [x["candidate"]["id"] for x in admin.call("GET", f"/api/requests/{d2['id']}/duplicate-suggestions")[1]],
      False)
psql(f"update requests set status='{was1}' where id={d1['id']}")
psql(f"update requests set status='{was2}' where id={d2['id']}")
to_d2 = next(s for s in sug3 if s["candidate"]["id"] == d2["id"])
check("staff mark one as not a duplicate",
      admin.call("PATCH", f"/api/requests/{d3['id']}/duplicate-suggestions/{to_d2['id']}", {"decision": "dismissed"})[0], 204)
sug3 = admin.call("GET", f"/api/requests/{d3['id']}/duplicate-suggestions")[1]
check("a dismissed suggestion stays gone", d2["id"] in [s["candidate"]["id"] for s in sug3], False)

before_other = other.call("GET", "/api/notifications")[1]["total"]
s, b = admin.call("PUT", f"/api/requests/{d2['id']}/duplicate-of", {"reference_number": d1["reference_number"]})
check("link the second report to the first", (s, (b.get("duplicate_of") or {}).get("id")), (200, d1["id"]))
check("the linked report takes the first one's category", b["category"]["id"], d1["category"]["id"])
check("the resident is told it's linked", other.call("GET", "/api/notifications")[1]["total"] - before_other, 1)
check("the main report counts it", admin.call("GET", f"/api/requests/{d1['id']}")[1]["linked_count"], 1)
check("a linked report leaves the staff queue", d2["id"] in staff_queue_ids(admin), False)
check("the resident still sees their linked report",
      d2["id"] in [i["id"] for i in other.call("GET", "/api/requests")[1]["items"]], True)
check("the resident sees which report it follows",
      other.call("GET", f"/api/requests/{d2['id']}")[1]["duplicate_of"]["reference_number"], d1["reference_number"])
check("linking to a report that's itself linked is refused",
      admin.call("PUT", f"/api/requests/{d3['id']}/duplicate-of", {"reference_number": d2["reference_number"]})[0], 409)
check("linking a report others follow is refused",
      admin.call("PUT", f"/api/requests/{d1['id']}/duplicate-of", {"reference_number": d3["reference_number"]})[0], 409)
# A main report has to be sorted first, so it has labels to pass on. Local test
# database: set the status back afterwards.
was = psql(f"select status from requests where id={d1['id']}")
psql(f"update requests set status='submitted' where id={d1['id']}")
check("a report can't be linked to one still being sorted",
      admin.call("PUT", f"/api/requests/{d3['id']}/duplicate-of", {"reference_number": d1["reference_number"]})[0], 409)
psql(f"update requests set status='{was}' where id={d1['id']}")
check("linking a report to itself is refused",
      admin.call("PUT", f"/api/requests/{d3['id']}/duplicate-of", {"reference_number": d3["reference_number"]})[0], 422)
check("an unknown reference number is 404",
      admin.call("PUT", f"/api/requests/{d3['id']}/duplicate-of", {"reference_number": "GAB-1999-99999"})[0], 404)
s, b = admin.call("PUT", f"/api/requests/{d3['id']}/duplicate-of", {"reference_number": d1["reference_number"]})
check("link the third report too", s, 200)
check("the main report now counts two", admin.call("GET", f"/api/requests/{d1['id']}")[1]["linked_count"], 2)
check("a linked report's status can't be changed on its own",
      admin.call("PATCH", f"/api/requests/{d2['id']}/status", {"to_status": "in_progress"})[0], 409)
check("an audit row records each link",
      int(psql(f"select count(*) from audit_log_entries where action='request.linked' and object_id in ('{d2['id']}','{d3['id']}')")), 2)

# Make sure the main report has a handler, then move it along.
main = admin.call("GET", f"/api/requests/{d1['id']}")[1]
if main["status"] != "routed":
    cat = main["category"]["id"] if main["category"]["slug"] in rules else \
        next(c["id"] for c in admin.call("GET", "/api/categories")[1] if c["slug"] in rules)
    main = admin.call("PATCH", f"/api/requests/{d1['id']}/classification",
                      {"final_category_id": cat, "final_urgency": "high"})[1]
for d in (d2, d3):
    child = admin.call("GET", f"/api/requests/{d['id']}")[1]
    check(f"linked report {d['reference_number']} has the main report's status and handler",
          (child["status"], (child["assigned_staff"] or {}).get("id")),
          (main["status"], (main["assigned_staff"] or {}).get("id")))
m_before = maria.call("GET", "/api/notifications")[1]["total"]
o_before = other.call("GET", "/api/notifications")[1]["total"]
s, b = admin.call("PATCH", f"/api/requests/{d1['id']}/status", {"to_status": "in_progress", "note": "Darating ang tubig bukas"})
check("the main report moves to in progress", s, 200)
check("the staff note reaches the linked reports too",
      [h["note"] for h in other.call("GET", f"/api/requests/{d2['id']}")[1]["status_history"]][-1], "Darating ang tubig bukas")
check("linked reports move with it",
      [admin.call("GET", f"/api/requests/{d['id']}")[1]["status"] for d in (d2, d3)], ["in_progress", "in_progress"])
check("a resident with two reports in the group hears once", maria.call("GET", "/api/notifications")[1]["total"] - m_before, 1)
check("the other resident hears once", other.call("GET", "/api/notifications")[1]["total"] - o_before, 1)
s, b = admin.call("DELETE", f"/api/requests/{d3['id']}/duplicate-of")
check("a link can be undone while the main report is open", (s, b.get("duplicate_of")), (200, None))
check("the unlinked report returns to the staff queue", d3["id"] in staff_queue_ids(admin), True)

# Five unlinked reports in one category within the hour show as a surge.
for t in water:
    wait_classified(maria, maria.call("POST", "/api/requests", {"description": t + " Pakiaksyunan po."})[1]["id"])
surges = admin.call("GET", "/api/request-surges")[1]
check("five reports about one problem in an hour show as a surge",
      any(x["category"]["id"] == d1["category"]["id"] and x["count"] >= 5 for x in surges), True)
check("a resident can't see surges", maria.call("GET", "/api/request-surges")[0], 403)

# Linking many at once, from the main report or the surge notice.
surge = next(x for x in surges if x["category"]["id"] == d1["category"]["id"])
# Earlier runs within the hour can be in the same surge, so only its shape is checked.
check("the surge names a report to link the others to", surge["main"] is not None, True)
check("a resident can't list reports to link", maria.call("GET", f"/api/requests/{d1['id']}/same-problem")[0], 403)
same = admin.call("GET", f"/api/requests/{d1['id']}/same-problem")[1]
fresh = [r for r in same if r["likely"] and r["id"] != d3["id"]]
check("the main report lists the new reports as likely the same", len(fresh) >= 2, True)
check("a report already linked isn't listed", d2["id"] in [r["id"] for r in same], False)
# One flood can be sorted into several categories. A matching report in another
# category is still listed as likely, and is linked with the rest below.
other_cat = next(c["id"] for c in admin.call("GET", "/api/categories")[1]
                 if c["id"] != d1["category"]["id"] and c["is_active"])
moved = fresh[1]
admin.call("PATCH", f"/api/requests/{moved['id']}/classification", {"final_category_id": other_cat, "final_urgency": "medium"})
again = {r["id"]: r for r in admin.call("GET", f"/api/requests/{d1['id']}/same-problem")[1]}
check("a matching report in another category is still listed as likely",
      (admin.call("GET", f"/api/requests/{moved['id']}")[1]["category"]["id"] != d1["category"]["id"],
       again.get(moved["id"], {}).get("likely")), (True, True))
held = fresh[-1]
# As if its classification had failed and it never left submitted.
psql(f"update requests set status='submitted' where id={held['id']}")
m_before = maria.call("GET", "/api/notifications")[1]["total"]
since = psql("select now()")
# Staff untick one as a different problem.
unticked = fresh[0]["id"]
picked = [r["id"] for r in fresh[1:]] + [d3["id"]]
s, res = admin.call("POST", f"/api/requests/{d1['id']}/linked-reports", {"request_ids": picked, "not_same": [unticked]})
check("one action links them all, one still being sorted included", (s, len(res["linked"]), res["skipped"]),
      (200, len(picked), []))
check("the resident hears once for all of their linked reports",
      maria.call("GET", "/api/notifications")[1]["total"] - m_before, 1)
check("an audit row records each one",
      int(psql(f"select count(*) from audit_log_entries where action='request.linked' and created_at >= '{since}' "
               f"and object_id in ({','.join(repr(str(i)) for i in picked)})")), len(picked))
time.sleep(3)
check("the classifier leaves the one that was still being sorted alone",
      admin.call("GET", f"/api/requests/{held['id']}")[1]["duplicate_of"]["id"], d1["id"])
main = admin.call("GET", f"/api/requests/{d1['id']}")[1]
check("the main report counts every linked report", main["linked_count"], 1 + len(picked))
check("linked reports all have the main report's status",
      {admin.call("GET", f"/api/requests/{i}")[1]["status"] for i in picked}, {main["status"]})
check("they leave the staff queue", any(i in staff_queue_ids(admin) for i in picked), False)
left = [r["id"] for r in admin.call("GET", f"/api/requests/{d1['id']}/same-problem")[1]]
check("nothing is left to link", [i for i in left if i in picked], [])
check("a report staff unticked isn't listed again", unticked in left, False)
after = next((x["count"] for x in admin.call("GET", "/api/request-surges")[1]
              if x["category"]["id"] == d1["category"]["id"]), 0)
check("linked reports no longer count toward the surge", after < surge["count"], True)

# A wrong link can be undone even after the job is finished.
admin.call("PATCH", f"/api/requests/{d1['id']}/status", {"to_status": "resolved", "note": "Naayos na po"})
s, b = admin.call("DELETE", f"/api/requests/{held['id']}/duplicate-of")
check("a wrong link is undone after the main report is resolved", (s, b["status"], b["assigned_staff"]),
      (200, "under_review", None))
check("it's back in For review",
      held["id"] in [i["id"] for i in admin.call("GET", "/api/review-queue?limit=100")[1]["items"]], True)
check("its resident is told it's being checked again",
      maria.call("GET", "/api/notifications?limit=1")[1]["items"][0]["message"], "Your request is being checked again")

# --- encryption at rest --------------------------------------------------------------------
area("Encryption at rest")
ENC = "gabai:enc:"
check("a request's text is stored encrypted",
      psql(f"select left(description, 10) from requests where id={rid}"), ENC)
check("and shown as plain text to the resident", maria.call("GET", f"/api/requests/{rid}")[1]["description"], texts[0])
check("a resident's name and purok are stored encrypted",
      psql(f"select left(full_name, 10) || '|' || left(residence, 10) from users where email='{oemail}'"), ENC + "|" + ENC)
check("staff notes are stored encrypted",
      psql(f"select count(*) from status_history_entries where note is not null and note not like '{ENC}%' "
           "and note <> '[Removed after the retention period]'"), "0")
check("attachment file names are stored encrypted",
      psql(f"select count(*) from attachments where filename not like '{ENC}%'"), "0")
att = next(a for a in maria.call("GET", f"/api/requests/{rid}")[1]["attachments"] if a["filename"] == "butas.png")
stored = psql(f"select stored_path from attachments where id={att['id']}")
on_disk = (ROOT / "backend" / "uploads" / stored).read_bytes()
check("an uploaded file is encrypted on disk", (on_disk[:9], b"PNG" in on_disk), (b"GABAIENC1", False))
s_, body = maria.get_bytes(f"/api/requests/{rid}/attachments/{att['id']}")
check("and downloads as the original file", (s_, body), (200, png))
found = admin.call("GET", "/api/admin/users?q=Pedro%20Test&limit=100")[1]["items"]
check("admin search still finds a resident by name", any(u["email"] == oemail for u in found), True)
boot = subprocess.run(
    [str(ROOT / "backend" / ".venv" / "Scripts" / "python"), "-c", "from app.core.config import Settings; Settings()"],
    cwd=ROOT / "backend", env={**os.environ, "DATA_KEYS": ""}, capture_output=True, text=True,
)
check("the server refuses to start without a data key", "DATA_KEYS is not set" in boot.stderr, True)

# --- administrator functions --------------------------------------------------------------------------
area("Administrator functions")
s, log = admin.call("GET", "/api/admin/audit-log?limit=100")
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
