"""Entry point for `python -m local_home_agent` and PyInstaller's `--onefile` mode."""

from __future__ import annotations

import os

import uvicorn

from .main import app


def main() -> None:
    host = os.getenv("LOCAL_HOME_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("LOCAL_HOME_AGENT_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
