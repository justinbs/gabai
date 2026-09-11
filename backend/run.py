"""Dev server entrypoint.

    python run.py

Use this instead of `uvicorn app.main:app` on Windows. The event loop policy has
to be set before uvicorn builds its loop, and uvicorn imports the app after that,
so setting it inside the app is too late. Deployment on Linux is unaffected and
can call uvicorn directly.
"""

import uvicorn

from app.core.eventloop import use_selector_loop_on_windows

if __name__ == "__main__":
    use_selector_loop_on_windows()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
