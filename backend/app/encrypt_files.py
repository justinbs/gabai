"""Encrypt uploaded files that were stored before encryption at rest.

    python -m app.encrypt_files            # lists what would change
    python -m app.encrypt_files --apply    # encrypts them

Run once after the deploy that adds encryption. Safe to run again: files that
already start with the encrypted header are skipped. Each file is written to a
temporary name and renamed only once complete. The site logo stays plain, since
it is public.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core import crypto
from app.core.eventloop import use_selector_loop_on_windows
from app.core.storage import UPLOAD_DIR
from app.db.session import AsyncSessionLocal
from app.models.attachment import Attachment


async def run(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        paths = (await db.execute(select(Attachment.stored_path))).scalars().all()
    plain, missing = [], 0
    for name in paths:
        path = UPLOAD_DIR / name
        if not path.exists():
            missing += 1
            continue
        with path.open("rb") as handle:
            if handle.read(len(crypto.FILE_HEADER)) != crypto.FILE_HEADER:
                plain.append(path)
    print(f"{len(paths)} attachments, {len(plain)} not yet encrypted, {missing} missing on disk")
    if not apply:
        print("Nothing changed. Run with --apply to encrypt them.")
        return
    for path in plain:
        temp = path.with_name(path.name + ".part")
        temp.write_bytes(crypto.encrypt_bytes(path.read_bytes()))
        temp.replace(path)
    print(f"Encrypted {len(plain)} files.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="encrypt the files; without it, only report")
    args = parser.parse_args()
    use_selector_loop_on_windows()
    asyncio.run(run(args.apply))


if __name__ == "__main__":
    main()
