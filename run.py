"""
Top-level launcher for PyInstaller-bundled binaries.

Two responsibilities:

1.  Resolve the relative-import problem that prevented ``app/main.py`` from
    being run as a top-level script.  By importing ``app.main`` from this
    wrapper, the relative imports inside ``app/`` resolve correctly.

2.  Bootstrap secrets so the desktop binary boots out of the box.  ``app/main.py``
    requires ``PASSPHRASE`` and ``ADMIN_PIN`` env vars and refuses to start
    without them (correct stance for headless deployments).  On first run we
    generate cryptographically-random *bootstrap* values, persist them via
    ``app.secret_store``, and let the binary boot.  We mark the install as
    ``first_run_complete: false`` so the captive-portal redirects every
    request to ``/setup`` until the user picks their own PIN + passphrase.
    On subsequent runs we reuse what's on disk.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the bundled `app` package importable when this script is the
# PyInstaller entry point.  When run from source this is harmless because
# the repo root is already on sys.path via pytest / `python run.py`.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from app import secret_store  # noqa: E402


CREDENTIALS_FILE = "FIRST_RUN_CREDENTIALS.txt"


def _bootstrap_secrets() -> None:
    """Populate env vars from disk, generating fresh secrets on first launch."""
    cfg = secret_store.read_secrets()
    fresh_pin: str | None = None
    changed = False

    if not cfg.get("passphrase"):
        cfg["passphrase"] = secret_store.generate_token(32)
        changed = True
    if not cfg.get("admin_pin"):
        cfg["admin_pin"] = secret_store.generate_bootstrap_pin()
        fresh_pin = cfg["admin_pin"]
        changed = True
    if not cfg.get("jwt_secret"):
        cfg["jwt_secret"] = secret_store.generate_token(48)
        changed = True
    if "first_run_complete" not in cfg:
        cfg["first_run_complete"] = False
        changed = True

    if changed:
        secret_store.write_secrets(cfg)

    # Push to env *before* app.main is imported — main.py reads these at
    # module-import time and raises if missing.
    os.environ.setdefault("PASSPHRASE", cfg["passphrase"])
    os.environ.setdefault("ADMIN_PIN", cfg["admin_pin"])
    os.environ.setdefault("JWT_SECRET", cfg["jwt_secret"])

    if fresh_pin is not None:
        creds_path = secret_store.config_dir() / CREDENTIALS_FILE
        creds_path.write_text(
            "Local Home Agent -- first-run bootstrap PIN\n"
            "===========================================\n\n"
            f"Bootstrap admin PIN: {fresh_pin}\n\n"
            "This is a temporary PIN. Open http://localhost:8000/setup in\n"
            "a browser to choose your own PIN and passphrase. Setup is\n"
            "mandatory before the agent will accept any other request.\n",
            encoding="utf-8",
        )
        print(
            f"\n*** Bootstrap admin PIN: {fresh_pin} ***\n"
            f"    Use it once at http://localhost:8000/setup, then choose your own.\n"
            f"    (also written to {creds_path})\n",
            file=sys.stderr,
            flush=True,
        )


def main() -> None:
    _bootstrap_secrets()

    import uvicorn
    from app.main import app

    host = os.environ.get("LHA_HOST", "0.0.0.0")
    port = int(os.environ.get("LHA_PORT", "8000"))
    print(
        f"\n>>> Local Home Agent listening on http://{host}:{port}\n"
        f">>> Open http://localhost:{port} in your browser.\n",
        file=sys.stderr,
        flush=True,
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
