"""Accounts and passwords: sign-up, password rules, admin-created accounts,
temporary passwords and admin reset. Runs against the local API and database.
Reads the local admin login from .env and never prints it."""

import json
import subprocess
import time
import urllib.error
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
ADMIN_EMAIL, ADMIN_PW = ENV["SEED_ADMIN_EMAIL"].strip(), ENV["SEED_ADMIN_PASSWORD"].strip()
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
                return r.status, (json.loads(raw) if raw else None), dict(r.headers)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw.decode(errors="replace")
            return e.code, parsed, dict(e.headers)

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


import urllib.parse  # noqa: E402

anon = Client()

# --- Step 2: policy on register -------------------------------------------------
reg_email = f"maria.{STAMP}@example.com"
for pw, reason in [
    ("a", "Use at least 8 characters"),
    ("maria", "Use at least 8 characters"),
    ("password", "That one's too common, pick another"),
    (f"maria.{STAMP}x", "Don't put your email in your password"),
]:
    s, b, _ = anon.call("POST", "/api/auth/register", {"email": reg_email, "password": pw, "full_name": "Maria Test", "residence": "Purok 1"})
    check(f"register rejects {pw[:12]!r}", (s, b.get("detail") if isinstance(b, dict) else b), (422, reason))

s, b, _ = anon.call("POST", "/api/auth/register", {"email": reg_email, "password": "kalsada-butas-9", "full_name": "Maria Test", "residence": "Purok 1"})
check("register accepts a good password", (s, b["must_change_password"]), (201, False))

# --- Admin create goes through the same policy, and flags the account -----------
admin = Client()
check("admin signs in", admin.login(ADMIN_EMAIL, ADMIN_PW), 204)
staff_email = f"staff.{STAMP}@example.com"
s, b, _ = admin.call("POST", "/api/admin/users", {"email": staff_email, "password": "12345678", "full_name": "Staff Test", "role": "staff"})
check("admin create rejects '12345678'", (s, b.get("detail")), (422, "That one's too common, pick another"))
s, b, _ = admin.call("POST", "/api/admin/users", {"email": staff_email, "password": "a", "full_name": "Staff Test", "role": "staff"})
check("admin create rejects 'a'", (s, b.get("detail")), (422, "Use at least 8 characters"))
s, staff, _ = admin.call("POST", "/api/admin/users", {"email": staff_email, "password": "initial-pass-77", "full_name": "Staff Test", "role": "staff"})
check("admin create flags the new account", (s, staff["must_change_password"]), (201, True))

# --- Step 5: admin reset ---------------------------------------------------------
s, b, h = admin.call("POST", f"/api/admin/users/{staff['id']}/password")
temp = b["temporary_password"] if s == 200 else ""
check("reset returns 200", s, 200)
check("reset response is no-store", {k.lower(): v for k, v in h.items()}.get("cache-control"), "no-store")
check("temporary password is 10 chars with no 0O1lI", (len(temp), bool(set(temp) & set("0O1lI"))), (10, False))
check("the admin's chosen password no longer works", Client().login(staff_email, "initial-pass-77"), 400)

# --- Step 6: while flagged, only /me and password change work -------------------
staffc = Client()
check("temporary password signs in", staffc.login(staff_email, temp), 204)
s, b, _ = staffc.call("GET", "/api/auth/me")
check("/me works while flagged", (s, b["must_change_password"]), (200, True))
for path in ["/api/requests", "/api/review-queue", "/api/notifications", "/api/categories", "/api/admin/users"]:
    s, b, _ = staffc.call("GET", path)
    check(f"{path} is 403 while flagged", s, 403)

# --- Step 4: self-service change ------------------------------------------------
s, b, _ = staffc.call("PUT", "/api/auth/password", {"current_password": "wrong-one-123", "new_password": "tulay-sira-44"})
check("wrong current password is 400", (s, b.get("detail")), (400, "That's not your current password"))
s, b, _ = staffc.call("PUT", "/api/auth/password", {"current_password": temp, "new_password": temp})
check("new == current is refused", (s, b.get("detail")), (422, "That's your current one, pick a new one"))
s, b, _ = staffc.call("PUT", "/api/auth/password", {"current_password": temp, "new_password": "password"})
check("weak new password is 422", (s, b.get("detail")), (422, "That one's too common, pick another"))
s, b, _ = staffc.call("PUT", "/api/auth/password", {"current_password": temp, "new_password": "tulay-sira-44"})
check("good change is 204", s, 204)
s, b, _ = staffc.call("GET", "/api/auth/me")
check("flag cleared after change", b["must_change_password"], False)
s, b, _ = staffc.call("GET", "/api/requests")
check("data routes open again", s, 200)
check("temporary password is dead", Client().login(staff_email, temp), 400)
check("new password signs in", Client().login(staff_email, "tulay-sira-44"), 204)

# --- The approved side rules ----------------------------------------------------
s, b, _ = anon.call("PUT", "/api/auth/password", {"current_password": "x", "new_password": "y"})
check("change needs a session", s, 401)
s, b, _ = staffc.call("POST", f"/api/admin/users/{staff['id']}/password")
check("staff can't reset anyone", s, 403)

# --- Database: audit row and no plaintext anywhere ------------------------------
def psql(sql):
    return subprocess.run(
        ["docker", "exec", "gabai-db", "psql", "-U", "gabai", "-d", "gabai", "-At", "-c", sql],
        capture_output=True, text=True,
    ).stdout.strip()

row = psql(f"select action, coalesce(detail::text,'null') from audit_log_entries where object_id='{staff['id']}' and action='user.password_reset'")
check("audit row written with no detail", row, "user.password_reset|null")
leak = psql(f"select count(*) from audit_log_entries where detail::text like '%{temp}%'")
check("temporary password appears nowhere in audit_log", leak, "0")
own = psql(f"select count(*) from audit_log_entries where object_id='{staff['id']}' and action like 'user.password%' and actor_id=(select id from users where email='{staff_email}')")
check("self-service change wrote no audit row", own, "0")

print(f"\n{sum(results)}/{len(results)} passed")
