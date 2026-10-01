"""Email confirmation and password reset. Runs the API in-process against the
local database; emails are read from the development log and their links
followed."""

import asyncio
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.core.eventloop import use_selector_loop_on_windows  # noqa: E402

use_selector_loop_on_windows()

import httpx  # noqa: E402

from app import mail  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ENV = dict(
    line.split("=", 1)
    for line in (ROOT / ".env").read_text().splitlines()
    if "=" in line and not line.lstrip().startswith("#")
)
DEMO_PW = ENV["SEED_DEMO_PASSWORD"].strip()
ADMIN = (ENV["SEED_ADMIN_EMAIL"].strip(), ENV["SEED_ADMIN_PASSWORD"].strip())
STAMP = str(int(time.time()))
results = []
inbox: list[str] = []


class Catch(logging.Handler):
    def emit(self, record):
        inbox.append(record.getMessage())


logging.getLogger("app.mail").addHandler(Catch())


def check(label, got, want):
    ok = got == want
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got {got!r}" + ("" if ok else f", want {want!r}"))


def mails_to(address):
    return [m for m in inbox if f"copy to {address}:" in m]


def token_in(message, path):
    found = re.search(rf"/{path}#token=([A-Za-z0-9_\-\.]+)", message)
    return found.group(1) if found else None


def psql(sql):
    return subprocess.run(
        ["docker", "exec", "gabai-db", "psql", "-U", "gabai", "-d", "gabai", "-At", "-c", sql],
        capture_output=True, text=True,
    ).stdout.strip()


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def settle():
    if mail._in_flight:
        await asyncio.gather(*list(mail._in_flight))


async def login(c, email, pw):
    r = await c.post("/api/auth/login", data={"username": email, "password": pw})
    if r.status_code == 204:
        await c.post("/api/auth/terms", json={"version": "2026-10-01"})
    return r.status_code


async def main():
    email = f"juan.{STAMP}@example.com"
    async with client() as anon, client() as res, client() as staff, client() as admin:
        # --- sign-up sends the confirmation email --------------------------------
        r = await anon.post("/api/auth/register", json={
            "email": email, "password": "kalsada-butas-9", "full_name": "Juan Dela Cruz", "residence": "Purok 2", "terms_version": "2026-10-01"})
        await settle()
        check("sign-up works and starts unconfirmed", (r.status_code, r.json()["is_verified"]), (201, False))
        sent = mails_to(email)
        check("one confirmation email went out", len(sent), 1)
        msg = sent[0] if sent else ""
        check("subject", "Confirm your email for GABAI" in msg, True)
        check("greets them by name", "Hi Juan Dela Cruz," in msg, True)
        check("link points at the site, token after #", "http://localhost:5173/verify-email#token=" in msg, True)
        check("bilingual", "Buksan ang link para makumpirma ang email ninyo" in msg, True)
        token = token_in(msg, "verify-email")

        # --- cooldown ----------------------------------------------------------------
        r = await anon.post("/api/auth/request-verify-token", json={"email": email})
        await settle()
        check("resend inside two minutes is still 202", r.status_code, 202)
        check("but no second email", len(mails_to(email)), 1)

        # --- staff can't approve until it's confirmed -----------------------------
        await login(staff, "ramon.delgado@example.com", DEMO_PW)
        uid = psql(f"select id from users where email='{email}'")
        r = await staff.patch(f"/api/registrations/{uid}", json={"approval_status": "approved"})
        check("approve before confirming is 409", (r.status_code, r.json().get("detail")),
              (409, "Their email isn't confirmed yet"))
        r = await staff.get("/api/registrations?limit=100")
        row = next((u for u in r.json()["items"] if u["id"] == uid), None)
        check("sign-ups list shows it unconfirmed", row and row["is_verified"], False)

        # --- confirm -------------------------------------------------------------------
        r = await anon.post("/api/auth/verify", json={"token": "not-a-token"})
        check("junk token refused", (r.status_code, r.json().get("detail")), (400, "VERIFY_USER_BAD_TOKEN"))
        r = await anon.post("/api/auth/verify", json={"token": token})
        check("the emailed link confirms it", (r.status_code, r.json().get("is_verified")), (200, True))
        r = await anon.post("/api/auth/verify", json={"token": token})
        check("second click says already confirmed", r.json().get("detail"), "VERIFY_USER_ALREADY_VERIFIED")
        r = await staff.patch(f"/api/registrations/{uid}", json={"approval_status": "approved"})
        check("now staff can approve", (r.status_code, r.json()["approval_status"]), (200, "approved"))

        # --- forgot password: no email to unknown or unconfirmed addresses --------------
        before = len(inbox)
        r = await anon.post("/api/auth/forgot-password", json={"email": f"nobody.{STAMP}@example.com"})
        await settle()
        check("unknown address still 202", r.status_code, 202)
        unconfirmed = f"pedro.{STAMP}@example.com"
        await anon.post("/api/auth/register", json={
            "email": unconfirmed, "password": "kalsada-butas-9", "full_name": "Pedro Test", "residence": "Purok 4", "terms_version": "2026-10-01"})
        await settle()
        after_signup = len(inbox)
        r = await anon.post("/api/auth/forgot-password", json={"email": unconfirmed})
        await settle()
        check("unconfirmed address still 202", r.status_code, 202)
        check("no reset email for unknown or unconfirmed", (after_signup - before, len(inbox) - after_signup), (1, 0))

        # --- forgot password: confirmed address gets a working link --------------------
        r = await anon.post("/api/auth/forgot-password", json={"email": email})
        await settle()
        resets = [m for m in mails_to(email) if "Reset your GABAI password" in m]
        check("confirmed address gets one reset email", len(resets), 1)
        reset_token = token_in(resets[0] if resets else "", "reset-password")
        check("reset link points at the site, token after #",
              bool(resets) and "http://localhost:5173/reset-password#token=" in resets[0], True)
        await anon.post("/api/auth/forgot-password", json={"email": email})
        await settle()
        check("no second reset email inside two minutes",
              len([m for m in mails_to(email) if "Reset your GABAI password" in m]), 1)

        r = await anon.post("/api/auth/reset-password", json={"token": reset_token, "password": "password"})
        check("weak password refused with the policy reason", (r.status_code, r.json()["detail"].get("reason")),
              (400, "That one's too common, pick another"))
        r = await anon.post("/api/auth/reset-password", json={"token": reset_token, "password": "ilog-baha-66"})
        check("good password accepted", r.status_code, 200)
        check("old password dead", await login(client(), email, "kalsada-butas-9"), 400)
        check("new password works", await login(res, email, "ilog-baha-66"), 204)
        r = await anon.post("/api/auth/reset-password", json={"token": reset_token, "password": "another-pass-12"})
        check("the link works only once", r.json().get("detail"), "RESET_PASSWORD_BAD_TOKEN")

        # --- email reset clears an admin's temporary password ---------------------------
        await login(admin, *ADMIN)
        r = await admin.post(f"/api/admin/users/{uid}/password")
        check("admin reset flags it", psql(f"select must_change_password from users where id='{uid}'"), "t")
        mail._last_sent.clear()
        await anon.post("/api/auth/forgot-password", json={"email": email})
        await settle()
        t2 = token_in([m for m in mails_to(email) if "Reset your GABAI password" in m][-1], "reset-password")
        r = await anon.post("/api/auth/reset-password", json={"token": t2, "password": "sariling-pass-21"})
        check("email reset accepted", r.status_code, 200)
        check("temporary-password flag cleared", psql(f"select must_change_password from users where id='{uid}'"), "f")

        # --- no reset tokens in the audit log, no emails in it either -------------------
        check("no token in audit rows", psql(f"select count(*) from audit_log_entries where detail::text like '%{t2[:20]}%'"), "0")

    print(f"\n{sum(results)}/{len(results)} passed")


asyncio.run(main())
