"""Read back every encrypted value and uploaded file in a restored database.

    python check_restored.py

Run from backend/ of the drill copy, with POSTGRES_PORT, POSTGRES_PASSWORD and
DATA_KEYS set. Prints counts and checksums only, never the decrypted text.
Exits 1 if anything can't be read.
"""
import hashlib
import sys

import psycopg

from app.core import crypto
from app.core.config import get_settings
from app.core.storage import UPLOAD_DIR

COLUMNS = [
    ("users", "full_name"), ("users", "residence"), ("requests", "description"),
    ("requests", "urgent_reason"), ("requests", "referral_note"),
    ("status_history_entries", "note"), ("attachments", "filename"),
]
MAGIC = {"image/jpeg": b"\xff\xd8", "image/png": b"\x89PNG", "application/pdf": b"%PDF", "image/webp": b"RIFF"}

s = get_settings()
bad = 0
with psycopg.connect(host=s.postgres_host, port=s.postgres_port, user=s.postgres_user,
                     password=s.postgres_password, dbname=s.postgres_db) as db:
    for table, col in COLUMNS:
        values = [r[0] for r in db.execute(f"select {col} from {table} where {col} is not null")]
        sealed = [v for v in values if crypto.is_encrypted_text(v)]
        ok = 0
        for v in sealed:
            try:
                crypto.decrypt_text(v)
                ok += 1
            except Exception:
                bad += 1
        print(f"{table}.{col}: {len(values)} values, {len(sealed)} encrypted, {ok} decrypted")

    files = list(db.execute("select id, request_id, stored_path, mime_type from attachments order by id"))
    missing = readable = 0
    newest = None
    for att_id, req_id, stored, mime in files:
        path = UPLOAD_DIR / stored
        if not path.exists():
            missing += 1
            continue
        try:
            data = crypto.decrypt_bytes(path.read_bytes())
        except Exception:
            bad += 1
            continue
        if data.startswith(MAGIC.get(mime, b"")):
            readable += 1
            newest = (req_id, att_id, hashlib.sha256(data).hexdigest())
        else:
            bad += 1
    print(f"attachments: {len(files)} rows, {missing} files missing, {readable} decrypted and match their type")
    if newest:
        print(f"newest attachment: request {newest[0]}, attachment {newest[1]}, sha256 {newest[2]}")

bad += missing
print("RESULT", "PASS" if bad == 0 else f"FAIL ({bad} unreadable or missing)")
sys.exit(1 if bad else 0)
