"""Time how long the application takes to decrypt one stored value (paper Section 4.2).

    cd backend && DATA_KEYS=... .venv/Scripts/python ../tests/load/time_decrypt.py

Uses the application's own crypto module and a throwaway key if DATA_KEYS is not set.
"""
import base64
import os
import sys
import time
from pathlib import Path

if not os.environ.get("DATA_KEYS"):
    os.environ["DATA_KEYS"] = "1:" + base64.b64encode(os.urandom(32)).decode()
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core import crypto  # noqa: E402

value = crypto.encrypt_text("May malaking butas sa kalsada sa harap ng barangay hall, delikado na sa gabi. " * 2)
crypto.decrypt_text(value)
n = 20000
start = time.perf_counter()
for _ in range(n):
    crypto.decrypt_text(value)
print(f"decrypting one value: {(time.perf_counter() - start) / n * 1e6:.1f} microseconds (average of {n})")
