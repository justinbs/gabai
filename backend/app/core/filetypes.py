"""Checks a file's first bytes against its declared type."""

SIGNATURES = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/webp": b"RIFF",
    "application/pdf": b"%PDF-",
}


def matches(content_type: str | None, contents: bytes) -> bool:
    signature = SIGNATURES.get(content_type or "")
    if signature is None or not contents.startswith(signature):
        return False
    # A WebP is a RIFF file with WEBP at bytes 8 to 12; other RIFF files are not.
    if content_type == "image/webp":
        return contents[8:12] == b"WEBP"
    return True
