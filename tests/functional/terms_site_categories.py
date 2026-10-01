"""Functional test of iteration 6: terms acceptance, site settings and logo,
category management, against the running local API and database."""

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
ENV = dict(
    line.split("=", 1)
    for line in (ROOT / ".env").read_text().splitlines()
    if "=" in line and not line.lstrip().startswith("#")
)
ADMIN = (ENV["SEED_ADMIN_EMAIL"].strip(), ENV["SEED_ADMIN_PASSWORD"].strip())
DEMO_PW = ENV["SEED_DEMO_PASSWORD"].strip()
VERSION = "2026-10-01"
STAMP = str(int(time.time()))
results, areas, AREA = [], {}, "?"


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None, form=None, raw=None, ctype=None, raw_response=False):
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
                if raw_response:
                    return r.status, b
                return r.status, (json.loads(b) if b else None)
        except urllib.error.HTTPError as e:
            b = e.read()
            try:
                return e.code, json.loads(b)
            except Exception:
                return e.code, b

    def login(self, email, pw):
        return self.call("POST", "/api/auth/login", form={"username": email, "password": pw})[0]

    def accept(self):
        return self.call("POST", "/api/auth/terms", {"version": VERSION})[0]

    def upload_logo(self, name, content, mime):
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.call("PUT", "/api/admin/site/logo", raw=body, ctype=f"multipart/form-data; boundary={boundary}")


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


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

# ------------------------------------------------------------------ terms
area("Terms and privacy acceptance")
anon = Client()
s, site = anon.call("GET", "/api/site")
check("site details readable without signing in", s, 200)
check("site reports the current terms version", site["terms_version"], VERSION)
email = f"terms.{STAMP}@example.com"
reg = {"email": email, "password": "kalsada-butas-9", "full_name": "Terms Test", "residence": "Purok 1"}
check("sign-up without a terms version refused", anon.call("POST", "/api/auth/register", reg)[0], 422)
check("sign-up with an old version refused", anon.call("POST", "/api/auth/register", {**reg, "terms_version": "2020-01-01"})[0], 409)
s, u = anon.call("POST", "/api/auth/register", {**reg, "terms_version": VERSION})
check("sign-up with the current version accepted", s, 201)
check("acceptance recorded on the account", (u["terms_accepted_version"], u["terms_accepted_at"] is not None), (VERSION, True))
check("acceptance written to the audit log", psql(
    f"select count(*) from audit_log_entries where action='user.terms_accepted' and object_id='{u['id']}'"), "1")

# an existing account that hasn't accepted
psql("update users set terms_accepted_version=null, terms_accepted_at=null where email='maria.santos@example.com'")
maria = Client()
check("resident without acceptance can sign in", maria.login("maria.santos@example.com", DEMO_PW), 204)
s, me = maria.call("GET", "/api/auth/me")
check("/me works and shows no acceptance", (s, me["terms_accepted_version"]), (200, None))
s, err = maria.call("GET", "/api/requests")
check("data routes refused until accepted", (s, "terms" in str(err)), (403, True))
check("accepting an old version refused", maria.call("POST", "/api/auth/terms", {"version": "2020-01-01"})[0], 409)
check("accepting the current version works", maria.accept(), 200)
check("data routes open after accepting", maria.call("GET", "/api/requests")[0], 200)
check("accepting again is harmless", maria.accept(), 200)

# admin-created account: temporary password and terms, in that order
admin = Client()
admin.login(*ADMIN)
admin.accept()
s, st = admin.call("POST", "/api/admin/users", {"email": f"newstaff.{STAMP}@example.com", "password": "Pansamantala-88",
                                               "full_name": "New Staff", "role": "staff"})
check("admin creates a staff account", s, 201)
check("new account has no acceptance yet", st["terms_accepted_version"], None)
newstaff = Client()
newstaff.login(f"newstaff.{STAMP}@example.com", "Pansamantala-88")
s, err = newstaff.call("GET", "/api/requests")
check("temporary password is asked for first", (s, "password" in str(err)), (403, True))
newstaff.call("PUT", "/api/auth/password", {"current_password": "Pansamantala-88", "new_password": "tulay-bago-55"})
s, err = newstaff.call("GET", "/api/requests")
check("then the terms", (s, "terms" in str(err)), (403, True))
newstaff.accept()
check("then the account works", newstaff.call("GET", "/api/requests")[0], 200)

# ------------------------------------------------------------------ site settings
area("Site settings")
staff = Client()
staff.login("ramon.delgado@example.com", DEMO_PW)
staff.accept()
check("staff can't change site settings", staff.call("PATCH", "/api/admin/site", {"theme": "blue"})[0], 403)
check("residents can't change site settings", maria.call("PATCH", "/api/admin/site", {"theme": "blue"})[0], 403)
before_audit = int(psql("select count(*) from audit_log_entries where action='site.updated'"))
s, upd = admin.call("PATCH", "/api/admin/site", {"hotline": "0917 000 0000", "office_hours": "Mon to Fri, 8 AM to 5 PM",
                                                 "theme": "maroon"})
check("admin saves details and colour", (s, upd["hotline"], upd["theme"]), (200, "0917 000 0000", "maroon"))
check("change is public at once", anon.call("GET", "/api/site")[1]["theme"], "maroon")
check("change audited with the fields changed", psql(
    "select detail::text from audit_log_entries where action='site.updated' order by id desc limit 1").count("hotline"), 1)
check("one audit row for the change", int(psql("select count(*) from audit_log_entries where action='site.updated'")) - before_audit, 1)
admin.call("PATCH", "/api/admin/site", {"hotline": "0917 000 0000"})
check("saving the same value writes no audit row", int(psql("select count(*) from audit_log_entries where action='site.updated'")) - before_audit, 1)
s, upd = admin.call("PATCH", "/api/admin/site", {"hotline": None, "office_hours": "  "})
check("null or blank clears a contact field", (s, upd["hotline"], upd["office_hours"]), (200, None, None))
check("barangay name can't be emptied", admin.call("PATCH", "/api/admin/site", {"barangay_name": None})[0], 422)
check("a blank barangay name is refused, not a server error", admin.call("PATCH", "/api/admin/site", {"place": "   "})[0], 422)
check("unknown colour refused", admin.call("PATCH", "/api/admin/site", {"theme": "neon"})[0], 422)
admin.call("PATCH", "/api/admin/site", {"theme": "green"})

area("Logo")
check("no logo yet gives 404", anon.call("GET", "/api/site/logo", raw_response=True)[0], 404)
check("staff can't upload a logo", staff.upload_logo("logo.png", PNG, "image/png")[0], 403)
s, upd = admin.upload_logo("logo.png", PNG, "image/png")
check("admin uploads a PNG", (s, upd["logo_version"] is not None), (200, True))
first_path = psql("select logo_path from site_settings")
s, img = anon.call("GET", f"/api/site/logo?v={upd['logo_version']}", raw_response=True)
check("logo served publicly, byte for byte", (s, img == PNG), (200, True))
check("audit row for the upload", psql("select count(*) from audit_log_entries where action='site.logo_changed'") != "0", True)
check("a text file named .png is refused", admin.upload_logo("fake.png", b"not an image at all", "image/png")[0], 415)
check("a GIF is refused", admin.upload_logo("x.gif", b"GIF89a" + b"\x00" * 50, "image/gif")[0], 415)
check("over 1 MB is refused", admin.upload_logo("big.png", PNG + b"\x00" * (1024 * 1024), "image/png")[0], 413)
s, upd2 = admin.upload_logo("logo2.png", PNG + b"\x01", "image/png")
check("a second upload replaces the first", (s, upd2["logo_version"] != upd["logo_version"]), (200, True))
check("old logo file deleted", (ROOT / "backend" / "uploads" / first_path).exists(), False)
second_path = psql("select logo_path from site_settings")
s, upd3 = admin.call("DELETE", "/api/admin/site/logo")
check("admin goes back to the default logo", (s, upd3["logo_version"]), (200, None))
check("logo file deleted", (ROOT / "backend" / "uploads" / second_path).exists(), False)
check("no logo gives 404 again", anon.call("GET", "/api/site/logo", raw_response=True)[0], 404)

# ------------------------------------------------------------------ categories
area("Category management")
s, cats = admin.call("GET", "/api/admin/categories")
check("admin lists all seven categories", (s, len(cats)), (200, 7))
check("staff can't list the admin view", staff.call("GET", "/api/admin/categories")[0], 403)
road = next(c for c in cats if c["slug"] == "road_infrastructure")
utilities = next(c for c in cats if c["slug"] == "utilities")
s, c = admin.call("PATCH", f"/api/admin/categories/{road['id']}", {"name": "Roads and Bridges"})
check("admin renames a category", (s, c["name"], c["slug"]), (200, "Roads and Bridges", "road_infrastructure"))
check("rename audited", psql(f"select count(*) from audit_log_entries where action='category.updated' and object_id='{road['id']}'") != "0", True)
check("staff can't edit categories", staff.call("PATCH", f"/api/admin/categories/{road['id']}", {"name": "x"})[0], 403)
check("empty name refused", admin.call("PATCH", f"/api/admin/categories/{road['id']}", {"name": "  "})[0], 422)
check("unknown category is 404", admin.call("PATCH", "/api/admin/categories/9999", {"name": "x"})[0], 404)

s, c = admin.call("PATCH", f"/api/admin/categories/{road['id']}", {"is_active": False})
check("admin switches a category off", (s, c["is_active"]), (200, False))
check("it disappears from the public list", road["id"] in [x["id"] for x in maria.call("GET", "/api/categories")[1]], False)
s, req = maria.call("POST", "/api/requests", {"description": "May malaking butas sa kalsada sa harap ng bahay namin sa Purok 2, delikado na sa mga motor lalo na sa gabi."})
done = wait_classified(maria, req["id"])
check("a request the model puts there goes to review, not routed",
      (done["predicted_category"]["slug"], done["status"]), ("road_infrastructure", "under_review"))
check("staff can't relabel into a switched-off category",
      staff.call("PATCH", f"/api/requests/{req['id']}/classification", {"final_category_id": road["id"], "final_urgency": "high"})[0], 422)
check("an unknown category id is refused, not a server error",
      staff.call("PATCH", f"/api/requests/{req['id']}/classification", {"final_category_id": 9999, "final_urgency": "high"})[0], 422)
s, moved = staff.call("PATCH", f"/api/requests/{req['id']}/classification", {"final_category_id": utilities["id"], "final_urgency": "high"})
check("relabelling into a category that's on still works", (s, moved["status"]), (200, "routed"))

others = [x for x in cats if x["id"] != road["id"]]
for x in others[:-1]:
    admin.call("PATCH", f"/api/admin/categories/{x['id']}", {"is_active": False})
check("the last category that's on can't be switched off",
      admin.call("PATCH", f"/api/admin/categories/{others[-1]['id']}", {"is_active": False})[0], 409)

# put everything back
for x in cats:
    admin.call("PATCH", f"/api/admin/categories/{x['id']}", {"is_active": True, "name": x["name"], "description": x["description"]})
s, after = admin.call("GET", "/api/admin/categories")
check("categories restored", [(x["name"], x["is_active"]) for x in after], [(x["name"], True) for x in cats])

print(f"\n{sum(results)}/{len(results)} checks passed")
for a, (p, f) in areas.items():
    print(f"  {a}: {p} passed, {f} failed")
