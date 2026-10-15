"""Security tests, grouped by ISO 25010 security sub-characteristic.

    backend/.venv/Scripts/python tests/security/security_tests.py round1
    set LIVE_URL=https://gabai.help   (optional, adds passive header checks)

The argument is a label for the results files (round1, round2). Runs against the
local API and database only. Prints PASS or FAIL per check and writes
tests/security/results/<label>-tests.txt and .json.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8000"
LIVE = os.environ.get("LIVE_URL", "").rstrip("/")
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"
ENV = dict(
    line.split("=", 1)
    for line in (ROOT / ".env").read_text().splitlines()
    if "=" in line and not line.lstrip().startswith("#")
)
ADMIN = (ENV["SEED_ADMIN_EMAIL"].strip(), ENV["SEED_ADMIN_PASSWORD"].strip())
DEMO_PW = ENV["SEED_DEMO_PASSWORD"].strip()
STAMP = str(int(time.time()))
PW = "kalsada-butas-9"
UUID0 = "00000000-0000-0000-0000-000000000000"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
OUT, areas, failures, S = [], {}, [], {}
AUD = [0, 0]
AREA = "?"


def out(text):
    OUT.append(text)
    print(text)


def area(name):
    global AREA
    AREA = name
    areas.setdefault(name, [0, 0])
    out(f"\n== {name} ==")


def check(label, got, want):
    ok = got == want
    areas[AREA][0 if ok else 1] += 1
    if not ok:
        failures.append(f"[{AREA}] {label}")
    out(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f": got {repr(got)[:200]}, want {want!r}"))


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def parse(b):
    if not b:
        return None
    try:
        return json.loads(b)
    except Exception:
        return b.decode(errors="replace")


def lower(h):
    return {k.lower(): v for k, v in h.items()}


class Client:
    def __init__(self):
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None, form=None, raw=None, ctype=None, headers=None):
        data, h = None, dict(headers or {})
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        elif raw is not None:
            data, h["Content-Type"] = raw, ctype or "application/json"
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
        try:
            with self.opener.open(req) as r:
                return r.status, parse(r.read()), lower(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, parse(e.read()), lower(e.headers)

    def token(self):
        return next(c.value for c in self.jar if c.name == "gabai_session")


def login(c, email, pw):
    code = c.call("POST", "/api/auth/login", form={"username": email, "password": pw})[0]
    if code == 204:
        c.call("POST", "/api/auth/terms", {"version": S["terms"]})
    return code


def psql_raw(sql):
    p = subprocess.run(
        ["docker", "exec", "gabai-db", "psql", "-U", "gabai", "-d", "gabai", "-At", "-c", sql],
        capture_output=True, text=True,
    )
    return p.returncode, (p.stdout + p.stderr).strip()


def psql(sql):
    return psql_raw(sql)[1]


def submit(c, text):
    body = {"description": text}
    if S["place"]:
        body["location_id"] = S["place"]
    return c.call("POST", "/api/requests", body)


def upload(c, rid, filename, content, mime):
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return c.call("POST", f"/api/requests/{rid}/attachments", raw=body,
                  ctype=f"multipart/form-data; boundary={boundary}")


def wait_classified(c, rid):
    r = None
    for _ in range(60):
        r = c.call("GET", f"/api/requests/{rid}")[1]
        if isinstance(r, dict) and r.get("status") not in ("submitted", None):
            return r
        time.sleep(0.5)
    return r


def audit_check(label, action, do):
    before = int(psql(f"select count(*) from audit_log_entries where action='{action}'"))
    do()
    after = int(psql(f"select count(*) from audit_log_entries where action='{action}'"))
    row = psql(f"select actor_id is not null, ip_address is not null from audit_log_entries "
               f"where action='{action}' order by id desc limit 1")
    AUD[1] += 1
    ok = (after - before, row) == (1, "t|t")
    AUD[0] += ok
    check(f"{label}: one audit row, with actor and IP", (after - before, row), (1, "t|t"))


METHODS = ("get", "post", "put", "patch", "delete")
PUBLIC = {"/api/auth/register", "/api/auth/login", "/api/auth/forgot-password",
          "/api/auth/reset-password", "/api/auth/request-verify-token", "/api/auth/verify",
          "/api/site", "/api/site/logo", "/api/health"}
STAFF_PREFIX = ("/api/admin", "/api/review-queue", "/api/registrations", "/api/request-surges", "/api/agencies")
STAFF_PARTS = ("/status", "/classification", "/duplicate", "/referral")


def fill(p):
    return re.sub(r"\{[^}]+\}", "1", p.replace("{user_id}", UUID0))


def hit(c, m, p):
    return c.call(m, fill(p), body=None if m == "GET" else {})[0]


# ---------------------------------------------------------------------------- setup
def setup():
    anon = Client()
    S["anon"] = anon
    S["terms"] = anon.call("GET", "/api/site")[1]["terms_version"]
    psql("delete from sign_in_failures")
    S["maria"], S["ramon"], S["admin"] = Client(), Client(), Client()
    login(S["maria"], "maria.santos@example.com", DEMO_PW)
    login(S["ramon"], "ramon.delgado@example.com", DEMO_PW)
    login(S["admin"], *ADMIN)
    S["place"] = next((p["id"] for p in S["admin"].call("GET", "/api/locations")[1]), None)
    S["maria_id"] = S["maria"].call("GET", "/api/auth/me")[1]["id"]
    S["admin_id"] = S["admin"].call("GET", "/api/auth/me")[1]["id"]
    S["cats"] = {c["slug"]: c["id"] for c in S["admin"].call("GET", "/api/categories")[1]}
    # a second approved resident
    email = f"pedro.sec.{STAMP}@example.com"
    anon.call("POST", "/api/auth/register", {"email": email, "password": PW, "full_name": "Pedro Sec",
                                              "residence": "Purok 5", "terms_version": S["terms"]})
    pid = psql(f"select id from users where email='{email}'")
    psql(f"update users set is_verified=true where id='{pid}'")
    S["ramon"].call("PATCH", f"/api/registrations/{pid}",
                    {"approval_status": "approved", "verification_method": "personally_known"})
    S["pedro"] = Client()
    login(S["pedro"], email, PW)


# ------------------------------------------------------------------- CONFIDENTIALITY
def confidentiality():
    anon, maria, ramon, pedro, admin = (S[k] for k in ("anon", "maria", "ramon", "pedro", "admin"))
    spec = anon.call("GET", "/openapi.json")[1]
    eps = [(m.upper(), p) for p, ops in spec["paths"].items() for m in ops if m in METHODS]
    private = [(m, p) for m, p in eps if p not in PUBLIC]
    bad = [f"{m} {p}" for m, p in private if hit(Client(), m, p) not in (401, 403)]
    out(f"Coverage: {len(private)} non-public endpoints tested with no session")
    check("every non-public endpoint refuses a request with no session", bad, [])

    staff_only = [(m, p) for m, p in private if p.startswith(STAFF_PREFIX) or any(k in p for k in STAFF_PARTS)]
    bad = [f"{m} {p}" for m, p in staff_only if hit(maria, m, p) != 403]
    out(f"Coverage: {len(staff_only)} staff/admin endpoints tested as a resident")
    check("a resident is refused on every staff or admin endpoint", bad, [])
    admin_only = [(m, p) for m, p in private if p.startswith("/api/admin")]
    bad = [f"{m} {p}" for m, p in admin_only if hit(ramon, m, p) != 403]
    out(f"Coverage: {len(admin_only)} admin endpoints tested as staff")
    check("staff are refused on every admin endpoint", bad, [])
    check("staff can't submit requests (resident only)", ramon.call("POST", "/api/requests", {"description": "x" * 20})[0], 403)

    s, r, _ = submit(maria, "May butas sa kalsada sa harap ng bahay namin sa Purok 2, delikado na sa gabi.")
    rid = S["rid"] = r["id"]
    s, att, _ = upload(maria, rid, "butas.png", PNG, "image/png")
    S["att"] = att["id"]
    check("another resident gets 404 for my request", pedro.call("GET", f"/api/requests/{rid}")[0], 404)
    check("another resident's list excludes it",
          rid in [i["id"] for i in pedro.call("GET", "/api/requests?limit=100")[1]["items"]], False)
    check("another resident can't download my attachment", pedro.call("GET", f"/api/requests/{rid}/attachments/{S['att']}")[0], 404)
    check("another resident can't upload to my request", upload(pedro, rid, "x.png", PNG, "image/png")[0], 404)
    check("another resident can't flag my request urgent",
          pedro.call("PUT", f"/api/requests/{rid}/urgent-flag", {"reason": "bilis po ito dahil delikado"})[0], 404)

    check("request text is encrypted in the database", psql(f"select left(description, 10) from requests where id={rid}"), "gabai:enc:")
    check("resident name is encrypted in the database", psql(f"select left(full_name, 10) from users where id='{S['maria_id']}'"), "gabai:enc:")
    stored = psql(f"select stored_path from attachments where id={S['att']}")
    check("uploaded file is encrypted on disk", (ROOT / "backend" / "uploads" / stored).read_bytes()[:9], b"GABAIENC1")
    me = json.dumps(maria.call("GET", "/api/auth/me")[1])
    users = json.dumps(admin.call("GET", "/api/admin/users?limit=5")[1])
    check("no password hash in any user response", ("hashed_password" in me, "hashed_password" in users), (False, False))

    a = anon.call("POST", "/api/auth/login", form={"username": f"nobody.{STAMP}@example.com", "password": "wrong-pass-123"})
    b = anon.call("POST", "/api/auth/login", form={"username": "maria.santos@example.com", "password": "wrong-pass-123"})
    check("login: unknown email and wrong password look identical", (a[0], a[1]), (b[0], b[1]))
    f1 = anon.call("POST", "/api/auth/forgot-password", {"email": f"nobody.{STAMP}@example.com"})[0]
    f2 = anon.call("POST", "/api/auth/forgot-password", {"email": "maria.santos@example.com"})[0]
    check("forgot-password answers 202 for unknown and known emails", (f1, f2), (202, 202))
    s, body, _ = maria.call("GET", "/api/requests/abc")
    check("a bad id gives 422, not a server error", s, 422)
    s, body, _ = maria.call("POST", "/api/requests", raw=b"{bad json")
    check("malformed JSON gives 422 and no stack trace", (s, "Traceback" in str(body)), (422, False))
    s, _, h = Client().call("POST", "/api/auth/login", form={"username": "pedro.sec.%s@example.com" % STAMP, "password": PW})
    sc = h.get("set-cookie", "").lower()
    check("session cookie is HttpOnly and SameSite=Lax", ("httponly" in sc, "samesite=lax" in sc), (True, True))


def live_checks():
    if not LIVE:
        out("(LIVE_URL not set, live-site checks skipped)")
        return

    def fetch(url):
        req = urllib.request.Request(url, headers={"User-Agent": "gabai-security-test"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, lower(r.headers), r.read(30000).decode(errors="replace"), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, lower(e.headers), "", url

    s, h, body, _ = fetch(LIVE + "/")
    check("live: HTTPS works with a valid certificate", s, 200)
    for name in ("strict-transport-security", "content-security-policy", "x-content-type-options",
                 "x-frame-options", "referrer-policy", "permissions-policy", "cross-origin-opener-policy"):
        check(f"live: {name} header present", name in h, True)
    check("live: Server header hidden", "server" not in h, True)
    host = LIVE.split("://", 1)[1]
    check("live: http redirects to https", fetch("http://" + host + "/")[3].startswith("https://"), True)
    s, h, _, _ = fetch(LIVE + "/api/site")
    check("live: API responses are no-store", h.get("cache-control"), "no-store")
    s, h, body, _ = fetch(LIVE + "/openapi.json")
    check("live: API spec not exposed", "application/json" in h.get("content-type", ""), False)
    s, h, body, _ = fetch(LIVE + "/docs")
    check("live: Swagger UI not exposed", "swagger" in body.lower(), False)


# ------------------------------------------------------------------------ INTEGRITY
def integrity():
    anon, maria, ramon, admin = (S[k] for k in ("anon", "maria", "ramon", "admin"))
    rid = S["rid"]
    S["R"] = wait_classified(maria, rid)

    mal = S["mallory"] = f"mallory.sec.{STAMP}@example.com"
    s, b, _ = anon.call("POST", "/api/auth/register", {
        "email": mal, "password": PW, "full_name": "Mallory Test", "residence": "Purok 1",
        "terms_version": S["terms"], "role": "admin", "is_superuser": True, "is_verified": True,
        "is_active": True, "approval_status": "approved", "must_change_password": False})
    b = b if isinstance(b, dict) else {}
    check("mass assignment: sign-up can't set role, approval or verified",
          (s, b.get("role"), b.get("is_verified"), b.get("approval_status")), (201, "citizen", False, "pending"))
    check("mass assignment: sign-up can't make a superuser", psql(f"select is_superuser from users where email='{mal}'"), "f")
    check("weak password refused at sign-up",
          anon.call("POST", "/api/auth/register", {"email": f"w.{STAMP}@example.com", "password": "password",
                    "full_name": "W", "residence": "P1", "terms_version": S["terms"]})[0], 422)
    check("outdated terms version refused at sign-up",
          anon.call("POST", "/api/auth/register", {"email": f"o.{STAMP}@example.com", "password": PW,
                    "full_name": "O", "residence": "P1", "terms_version": "2020-01-01"})[0], 409)

    s, b, _ = admin.call("GET", "/api/admin/users?q=" + urllib.parse.quote("' OR '1'='1"))
    check("SQL injection in user search is harmless", s, 200)
    s, b, _ = admin.call("GET", "/api/admin/audit-log?action=" + urllib.parse.quote("' OR 1=1 --"))
    check("SQL injection in audit filter returns nothing", (s, b.get("total") if isinstance(b, dict) else None), (200, 0))
    payload = "'); DROP TABLE users;-- <script>alert(1)</script>"
    s, r, _ = submit(maria, payload + " may butas sa daan")
    s2, back, h = maria.call("GET", f"/api/requests/{r['id']}")
    check("injection text is stored as plain text and returned unchanged", (s, back["description"]), (201, payload + " may butas sa daan"))
    check("responses are JSON, so the browser never renders the text as HTML", "application/json" in h.get("content-type", ""), True)
    check("users table still exists after the injection attempt", int(psql("select count(*) from users")) > 0, True)
    check("description over 5000 characters refused", maria.call("POST", "/api/requests", {"description": "a" * 5001})[0], 422)

    check("executable refused", upload(maria, rid, "tool.exe", b"MZ" + b"\x00" * 64, "application/x-msdownload")[0], 415)
    check("text file declared as PNG refused", upload(maria, rid, "t.png", b"just text, not an image" * 4, "image/png")[0], 415)
    check("PDF declared as PNG refused", upload(maria, rid, "p.png", b"%PDF-1.4\n" + b"\x00" * 64, "image/png")[0], 415)
    check("file over 5 MB refused", upload(maria, rid, "big.png", PNG + b"\x00" * (5 * 1024 * 1024 + 10), "image/png")[0], 413)
    hostile = upload(maria, rid, "../../evil.png", PNG, "image/png")[1]
    check("hostile file name can't escape the upload folder",
          ((ROOT / "backend" / "evil.png").exists(), (ROOT / "evil.png").exists(),
           psql(f"select count(*) from attachments where id={hostile['id']} "
                "and (stored_path like '%/%' or stored_path like '%.%' or stored_path like '%\\%')")),
          (False, False, "0"))

    check("a resident can't change status", maria.call("PATCH", f"/api/requests/{rid}/status", {"to_status": "in_progress"})[0], 403)
    check("an illegal status jump is refused", admin.call("PATCH", f"/api/requests/{rid}/status", {"to_status": "closed"})[0], 409)
    check("staff can't promote an account to admin",
          ramon.call("PATCH", f"/api/admin/users/{S['maria_id']}", {"role": "admin"})[0], 403)

    s, _, h = S["anon"].call("GET", "/api/site", headers={"Origin": "http://evil.example"})
    check("CORS: a foreign origin is not allowed", h.get("access-control-allow-origin") in ("http://evil.example", "*"), False)


# ---------------------------------------------------------------- NON-REPUDIATION
def nonrepudiation():
    anon, maria, admin = S["anon"], S["maria"], S["admin"]
    R, rid = S["R"], S["rid"]
    staff_email = f"staff.sec.{STAMP}@example.com"

    def create():
        S["staff_id"] = admin.call("POST", "/api/admin/users", {
            "email": staff_email, "password": "Pansamantala-88", "full_name": "Staff Sec", "role": "staff"})[1]["id"]
    audit_check("create account", "user.created", create)
    S["staffc"] = Client()
    login(S["staffc"], staff_email, "Pansamantala-88")
    audit_check("reset password", "user.password_reset", lambda: admin.call("POST", f"/api/admin/users/{S['staff_id']}/password"))
    audit_check("deactivate account", "user.deactivated", lambda: admin.call("PATCH", f"/api/admin/users/{S['staff_id']}", {"is_active": False}))

    def reclass():
        S["rc"] = admin.call("PATCH", f"/api/requests/{R['id']}/classification",
                             {"final_category_id": S["cats"]["utilities"], "final_urgency": "high"})[1]
    audit_check("relabel a request", "request.reclassified", reclass)
    if isinstance(S.get("rc"), dict) and S["rc"].get("status") == "routed":
        audit_check("change request status", "request.status_changed",
                    lambda: admin.call("PATCH", f"/api/requests/{R['id']}/status", {"to_status": "in_progress"}))
    else:
        out("SKIP  status change audit (request was not routed to a handler)")
    audit_check("resident marks request urgent", "request.flagged_urgent",
                lambda: maria.call("PUT", f"/api/requests/{rid}/urgent-flag", {"reason": "May matanda po kaming kasama dito"}))
    audit_check("submit a request", "request.submitted", lambda: submit(maria, "Walang tubig sa amin tatlong araw na po, pakitingnan."))
    orig = anon.call("GET", "/api/site")[1]["hotline"]
    audit_check("change site details", "site.updated", lambda: admin.call("PATCH", "/api/admin/site", {"hotline": "0000 test"}))
    admin.call("PATCH", "/api/admin/site", {"hotline": orig})
    audit_check("attach a file to a request", "attachment.uploaded", lambda: upload(maria, rid, "a.png", PNG, "image/png"))
    out(f"Audit coverage: {AUD[0]}/{AUD[1]} state-changing actions left a complete audit row")


# ---------------------------------------------------------------- ACCOUNTABILITY
def accountability():
    admin, ramon, maria = S["admin"], S["ramon"], S["maria"]
    for m in ("POST", "PUT", "PATCH", "DELETE"):
        check(f"no endpoint can change the audit log ({m})", admin.call(m, "/api/admin/audit-log", {} if m != "DELETE" else None)[0], 405)
    check("staff can't read the audit log", ramon.call("GET", "/api/admin/audit-log")[0], 403)
    check("a resident can't read the audit log", maria.call("GET", "/api/admin/audit-log")[0], 403)
    code, text = psql_raw("UPDATE audit_log_entries SET action='x' WHERE id=(select max(id) from audit_log_entries)")
    check("the database refuses to edit an audit row", (code != 0, "append-only" in text), (True, True))
    code, text = psql_raw("DELETE FROM audit_log_entries WHERE id=(select max(id) from audit_log_entries)")
    check("the database refuses to delete an audit row", (code != 0, "append-only" in text), (True, True))
    check("audit actor is the real caller (not forgeable)",
          psql("select actor_id::text from audit_log_entries where action='request.submitted' order by id desc limit 1"), S["maria_id"])
    check("admin actions always name an actor",
          psql("select count(*) from audit_log_entries where action in ('user.created','user.password_reset','user.deactivated',"
               "'site.updated','request.reclassified') and actor_id is null"), "0")


# ------------------------------------------------------------------- AUTHENTICITY
def authenticity():
    maria = S["maria"]
    tok = maria.token()
    h, p, sig = tok.split(".")

    def with_cookie(t):
        return Client().call("GET", "/api/auth/me", headers={"Cookie": f"gabai_session={t}"})[0]

    check("control: a real session cookie works", with_cookie(tok), 200)
    flipped = sig[:-1] + ("A" if sig[-1] != "A" else "B")
    check("JWT with a tampered signature is refused", with_cookie(f"{h}.{p}.{flipped}"), 401)
    payload = json.loads(unb64(p))
    payload["sub"] = S["admin_id"]
    check("JWT with a changed user id is refused", with_cookie(f"{h}.{b64(json.dumps(payload).encode())}.{sig}"), 401)
    none_h = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    check("JWT with alg=none is refused", with_cookie(f"{none_h}.{p}."), 401)
    forged = b64(hmac.new(b"wrong-secret", f"{h}.{p}".encode(), hashlib.sha256).digest())
    check("JWT signed with the wrong key is refused", with_cookie(f"{h}.{p}.{forged}"), 401)
    check("a garbage cookie is refused", with_cookie("abc"), 401)
    check("a deactivated account's session stops working", S["staffc"].call("GET", "/api/auth/me")[0], 401)

    psql("delete from sign_in_failures")
    codes = [Client().call("POST", "/api/auth/login", form={"username": S["mallory"], "password": f"mali-{n}-pass"})[0] for n in range(5)]
    check("five wrong passwords are refused", codes, [400] * 5)
    check("the sixth try is locked out even with the right password",
          Client().call("POST", "/api/auth/login", form={"username": S["mallory"], "password": PW})[0], 429)
    psql("delete from sign_in_failures")

    mc = Client()
    login(mc, S["mallory"], PW)
    check("a pending (unapproved) resident can't reach data", mc.call("GET", "/api/requests")[0], 403)

    c = Client()
    login(c, "maria.santos@example.com", DEMO_PW)
    old = c.token()
    c.call("POST", "/api/auth/logout")
    check("a session cookie stops working after sign-out", with_cookie(old), 401)


AREAS = [("Confidentiality", confidentiality), ("Integrity", integrity), ("Non-repudiation", nonrepudiation),
         ("Accountability", accountability), ("Authenticity", authenticity), ("Confidentiality", live_checks)]


def finish():
    out("\n== Summary by ISO 25010 security area ==")
    out("| Area | Checks | Passed | Failed | Pass rate |")
    out("|---|---|---|---|---|")
    tp = tf = 0
    for name, (p, f) in areas.items():
        tp, tf = tp + p, tf + f
        out(f"| {name} | {p + f} | {p} | {f} | {100 * p / max(p + f, 1):.1f}% |")
    out(f"| Total | {tp + tf} | {tp} | {tf} | {100 * tp / max(tp + tf, 1):.1f}% |")
    if failures:
        out("\nFailed checks:")
        for line in failures:
            out(f"  - {line}")
    d = ROOT / "tests" / "security" / "results"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{LABEL}-tests.txt").write_text("\n".join(OUT), encoding="utf-8")
    (d / f"{LABEL}-tests.json").write_text(json.dumps({"label": LABEL, "areas": areas, "failures": failures,
                                                       "audit_coverage": AUD}, indent=2), encoding="utf-8")
    print(f"\nWrote tests/security/results/{LABEL}-tests.txt and .json")


def main():
    try:
        setup()
    except Exception as e:
        sys.exit(f"Setup failed ({e!r}). Is the API running on 127.0.0.1:8000 and the database up?")
    for name, fn in AREAS:
        area(name)
        try:
            fn()
        except Exception as e:
            check(f"{fn.__name__} stopped on a script error: {e!r}", False, True)
    psql("delete from sign_in_failures")
    finish()


main()