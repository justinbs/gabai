"""Download one attachment from the live site and from the restored copy, and compare.

    python compare_download.py <request id> <attachment id>

Asks for an administrator's email and password (typed, not shown), unless the
drill script already read them into DRILL_EMAIL and DRILL_PASSWORD. Signs in to
the live site (LIVE_URL, default https://gabai.help) and to the restored copy at
http://127.0.0.1:8100, opens the request on both, downloads the attachment from
both and compares SHA-256 values.
"""
import getpass
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

req_id, att_id = sys.argv[1], sys.argv[2]
email = os.environ.get("DRILL_EMAIL") or input("Administrator email: ").strip()
password = os.environ.get("DRILL_PASSWORD") or getpass.getpass("Password (not shown): ")
LIVE = os.environ.get("LIVE_URL", "https://gabai.help")


def fetch(base):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    form = urllib.parse.urlencode({"username": email, "password": password}).encode()
    op.open(urllib.request.Request(base + "/api/auth/login", data=form, method="POST"))
    detail = json.loads(op.open(base + f"/api/requests/{req_id}").read())
    data = op.open(base + f"/api/requests/{req_id}/attachments/{att_id}").read()
    return detail, hashlib.sha256(data).hexdigest()


results = {}
for name, base in (("live", LIVE), ("restored", "http://127.0.0.1:8100")):
    try:
        detail, digest = fetch(base)
    except urllib.error.HTTPError as e:
        sys.exit(f"{name}: HTTP {e.code} on {e.url}")
    readable = not detail["description"].startswith("gabai:enc:")
    print(f"{name}: request {detail['reference_number']} opened, description readable: {readable}, "
          f"attachment sha256 {digest}")
    results[name] = (readable, digest)

same = results["live"][1] == results["restored"][1]
print("RESULT", "PASS" if same and all(r[0] for r in results.values()) else "FAIL",
      "- checksums equal" if same else "- checksums differ")
