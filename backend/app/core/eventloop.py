"""Windows event loop fix, needed before anything opens a database connection.

Windows defaults to the proactor event loop. psycopg's async mode refuses to run
on it and raises `InterfaceError` on the first connection, so on Windows every
request that touches the database returns 500 without this.

No effect on Linux, which is where this deploys. It matters because both builders
develop on Windows.

Call it from an entrypoint before the loop starts, never from a library module.
"""

import asyncio
import sys


def use_selector_loop_on_windows() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
