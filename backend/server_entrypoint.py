"""Standalone Server Entrypoint for NEXORA.

Used for local standalone execution and single-file executable freezing via PyInstaller/Nuitka.
Enables multiprocessing freeze support for Windows and launches Uvicorn server programmatically.
"""

import argparse
import multiprocessing
import sys
import uvicorn

from backend.app.main import app


def main() -> None:
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="NEXORA Standalone Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--log-level", default="info", help="Log level (default: info)")
    args = parser.parse_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=False,
    )


if __name__ == "__main__":
    main()
