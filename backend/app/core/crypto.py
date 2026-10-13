"""Encryption of personal data at rest, AES-256-GCM.

Keys come from DATA_KEYS in the environment, never from the database or the
backups: "2:<base64 32 bytes>,1:<base64 32 bytes>". The first key encrypts new
data; every key listed can still decrypt, which is what allows rotation.

Stored text looks like "gabai:enc:<key id>:<base64 of nonce + ciphertext>".
Stored files start with FILE_HEADER, then the key id byte, nonce and ciphertext.
"""

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

TEXT_PREFIX = "gabai:enc:"
FILE_HEADER = b"GABAIENC1"
NONCE_BYTES = 12


class DataKeyError(ValueError):
    pass


@lru_cache
def _keys() -> tuple[int, dict[int, AESGCM]]:
    raw = get_settings().data_keys
    keys: dict[int, AESGCM] = {}
    current = None
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        key_id, _, encoded = part.partition(":")
        secret = base64.b64decode(encoded)
        if not key_id.isdigit() or not 0 < int(key_id) < 256 or len(secret) != 32:
            raise DataKeyError("Each DATA_KEYS entry must be <1-255>:<base64 of 32 bytes>")
        keys[int(key_id)] = AESGCM(secret)
        if current is None:
            current = int(key_id)
    if current is None:
        raise DataKeyError("DATA_KEYS is empty")
    return current, keys


def encrypt_text(value: str) -> str:
    key_id, keys = _keys()
    nonce = os.urandom(NONCE_BYTES)
    sealed = keys[key_id].encrypt(nonce, value.encode("utf-8"), None)
    return f"{TEXT_PREFIX}{key_id}:{base64.b64encode(nonce + sealed).decode('ascii')}"


def is_encrypted_text(value: str) -> bool:
    return value.startswith(TEXT_PREFIX)


def decrypt_text(value: str) -> str:
    # Anything without the prefix was written before encryption, or is a
    # retention marker, and is returned as it is.
    if not is_encrypted_text(value):
        return value
    key_id, _, encoded = value[len(TEXT_PREFIX):].partition(":")
    _, keys = _keys()
    key = keys.get(int(key_id))
    if key is None:
        raise DataKeyError(f"No key {key_id} in DATA_KEYS")
    blob = base64.b64decode(encoded)
    return key.decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], None).decode("utf-8")


def encrypt_bytes(data: bytes) -> bytes:
    key_id, keys = _keys()
    nonce = os.urandom(NONCE_BYTES)
    return FILE_HEADER + bytes([key_id]) + nonce + keys[key_id].encrypt(nonce, data, None)


def decrypt_bytes(data: bytes) -> bytes:
    # Files stored before encryption have no header and are returned as they are.
    if not data.startswith(FILE_HEADER):
        return data
    body = data[len(FILE_HEADER):]
    key_id, nonce, sealed = body[0], body[1:1 + NONCE_BYTES], body[1 + NONCE_BYTES:]
    _, keys = _keys()
    key = keys.get(key_id)
    if key is None:
        raise DataKeyError(f"No key {key_id} in DATA_KEYS")
    return key.decrypt(nonce, sealed, None)
