"""
Dev server launcher. Run this instead of `uvicorn app.main:app` directly —
on Windows, the bare CLI invocation lets uvicorn's own asyncio.run() create
the event loop (defaulting to ProactorEventLoop) BEFORE app.main gets
imported, meaning session.py's WindowsSelectorEventLoopPolicy fix runs too
late to matter — the loop already exists by then. Setting the policy here,
before uvicorn.run() is even called, guarantees it takes effect.
"""
import asyncio
import sys

import uvicorn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)