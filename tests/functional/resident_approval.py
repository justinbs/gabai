"""Resident approval: sign-up needs a purok or street, pending accounts are
blocked, staff approve or turn down. Runs against the local API and database."""

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
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
STAMP = str(int(time.time()))
results = []
TERMS_VERSION = "2026-10-01"


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None, form=None):
        if path == "/api/auth/register" and isinstance(body, dict):
            body = {"terms_version": TERMS_VERSION, **body}
        data, headers = None, {}
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw.decode(errors="replace")

    def login(self, email, pw):
        status = self.call("POST", "/api/auth/login", form={"username": email, "password": pw})[0]
        if status == 204:
            # Test accounts accept the current terms, as a person would on the accept screen.
            self.call("POST", "/api/auth/terms", {"version": TERMS_VERSION})
        return status


def check(label, got, want):
    ok = got == want
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got {got!r}" + ("" if ok else f", want {want!r}"))


def psql(sql):
    return subprocess.run(
        ["docker", "exec", "gabai-db", "psql", "-U", "gabai", "-d", "gabai", "-At", "-c", sql],
        capture_output=True, text=True,
    ).stdout.strip()


# --- the seeded accounts were backfilled, nobody got locked out ------------------
check("seeded accounts were backfilled as approved", psql(
    "select count(*) from users where email in ('maria.santos@example.com','ramon.delgado@example.com',"
    "'divina.bautista@example.com','teresa.ocampo@example.com') and approval_status='approved'"), "4")
check("demo resident Maria can still use the system", Client().login("maria.santos@example.com", DEMO_PW), 204)
m = Client()
m.login("maria.santos@example.com", DEMO_PW)
check("Maria's requests still load", m.call("GET", "/api/requests")[0], 200)

# --- sign-up needs a purok or street ---------------------------------------------
anon = Client()
email = f"resident.{STAMP}@example.com"
s, b = anon.call("POST", "/api/auth/register", {"email": email, "password": "kalsada-butas-9", "full_name": "Juan Test"})
check("sign-up without purok is refused", s, 422)
s, b = anon.call("POST", "/api/auth/register", {"email": email, "password": "kalsada-butas-9", "full_name": "Juan Test", "residence": "   "})
check("blank purok is refused", s, 422)
s, new = anon.call("POST", "/api/auth/register", {"email": email, "password": "kalsada-butas-9", "full_name": "Juan Test", "residence": "  Purok 3, Mabini St  "})
check("sign-up starts pending", (s, new["approval_status"], new["residence"]), (201, "pending", "Purok 3, Mabini St"))

# --- pending: can sign in, can see itself, nothing else --------------------------
res = Client()
check("pending resident can sign in", res.login(email, "kalsada-butas-9"), 204)
s, b = res.call("GET", "/api/auth/me")
check("/me says pending", (s, b["approval_status"]), (200, "pending"))
for method, path, body in [("GET", "/api/requests", None), ("GET", "/api/categories", None),
                           ("GET", "/api/notifications", None),
                           ("POST", "/api/requests", {"description": "may butas sa kalsada"})]:
    s, b = res.call(method, path, body)
    check(f"pending {method} {path} is 403", (s, b.get("detail") if isinstance(b, dict) else b),
          (403, "Waiting for the barangay to approve your account"))
check("pending resident can still change password",
      res.call("PUT", "/api/auth/password", {"current_password": "kalsada-butas-9", "new_password": "tulay-sira-55"})[0], 204)
pw = "tulay-sira-55"

# --- who may decide --------------------------------------------------------------
check("a resident can't list sign-ups", m.call("GET", "/api/registrations")[0], 403)
check("a resident can't approve", m.call("PATCH", f"/api/registrations/{new['id']}", {"approval_status": "approved"})[0], 403)
staff = Client()
check("staff sign in", staff.login("ramon.delgado@example.com", DEMO_PW), 204)
s, b = staff.call("GET", "/api/registrations?limit=100")
check("staff see the new sign-up in the waiting list", (s, any(u["id"] == new["id"] for u in b["items"])), (200, True))
check("list holds citizens only", all(u["role"] == "citizen" for u in b["items"]), True)
check("bad decision value is 422", staff.call("PATCH", f"/api/registrations/{new['id']}", {"approval_status": "pending"})[0], 422)

# --- turn down, then approve -----------------------------------------------------
s, b = staff.call("PATCH", f"/api/registrations/{new['id']}", {"approval_status": "rejected"})
check("staff turn it down", (s, b["approval_status"]), (200, "rejected"))
s, b = res.call("GET", "/api/auth/me")
check("resident sees turned down", b["approval_status"], "rejected")
check("turned down still can't reach data", res.call("GET", "/api/requests")[0], 403)
s, b = staff.call("GET", "/api/registrations?status=rejected")
check("it shows under turned down", any(u["id"] == new["id"] for u in b["items"]), True)
s, b = staff.call("PATCH", f"/api/registrations/{new['id']}", {"approval_status": "approved"})
check("unconfirmed email can't be approved", (s, b.get("detail")), (409, "Their email isn't confirmed yet"))
# The email flow has its own suite. Here, confirm it directly and carry on.
psql(f"update users set is_verified=true where id='{new['id']}'")
s, b = staff.call("PATCH", f"/api/registrations/{new['id']}", {"approval_status": "approved"})
check("a mistake can be undone, approve", (s, b["approval_status"]), (200, "approved"))

# --- approved: same session now works, no re-login --------------------------------
check("approved resident reaches requests with the same session", res.call("GET", "/api/requests")[0], 200)
s, b = res.call("POST", "/api/requests", {"description": "may malaking butas sa kalsada sa purok 3"})
check("approved resident can submit", s, 201)

# --- staff can't use this to lock out an approved resident ------------------------
s, b = staff.call("PATCH", f"/api/registrations/{new['id']}", {"approval_status": "rejected"})
check("can't turn down an approved resident", (s, b.get("detail")), (409, "Already approved"))
s, b = staff.call("PATCH", f"/api/registrations/{new['id']}", {"approval_status": "approved"})
check("approving twice is also 409", s, 409)

# --- staff and admin accounts are never subject to approval ----------------------
admin = Client()
admin.login(*ADMIN)
sid = next(u["id"] for u in admin.call("GET", "/api/admin/users?role=staff&limit=100")[1]["items"] if u["email"] == "ramon.delgado@example.com")
check("staff account isn't a registration", staff.call("PATCH", f"/api/registrations/{sid}", {"approval_status": "rejected"})[0], 404)
s, b = admin.call("POST", "/api/admin/users", {"email": f"newstaff.{STAMP}@example.com", "password": "initial-pass-78", "full_name": "New Staff", "role": "staff"})
check("admin-created account is approved", (s, b["approval_status"]), (201, "approved"))

# --- audit trail -----------------------------------------------------------------
rows = psql(f"select action from audit_log_entries where object_id='{new['id']}' and action like 'user.%ed' and action <> 'user.terms_accepted' order by created_at")
check("audit rows: turned down then approved", rows.split("\n"), ["user.rejected", "user.approved"])
actor = psql(f"select u.email from audit_log_entries a join users u on u.id=a.actor_id where a.object_id='{new['id']}' and a.action='user.approved'")
check("approval attributed to the staff member", actor, "ramon.delgado@example.com")

print(f"\n{sum(results)}/{len(results)} passed")
