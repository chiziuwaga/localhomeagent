"""
Top-level launcher for PyInstaller-bundled binaries.

Two responsibilities:

1.  Resolve the relative-import problem that prevented ``app/main.py`` from
    being run as a top-level script.  By importing ``app.main`` from this
    wrapper, the relative imports inside ``app/`` resolve correctly.

2.  Bootstrap first-run secrets so the desktop binary "just works" when a
    user double-clicks it.  ``app/main.py`` requires ``PASSPHRASE`` and
    ``ADMIN_PIN`` environment variables and refuses to start without them
    (correct stance for headless deployments).  For the desktop binary we
    generate cryptographically-random values on first run, persist them to
    ``~/.local-home-agent/secrets.json`` (mode 600 on POSIX), and surface
    them via ``~/.local-home-agent/FIRST_RUN_CREDENTIALS.txt`` so the user
    can find their initial admin PIN.  Subsequent runs reuse the same
    config; the captive-portal setup wizard at ``/setup`` lets the user
    rotate everything.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path


CONFIG_DIR_NAME = ".local-home-agent"
SECRETS_FILE = "secrets.json"
CREDENTIALS_FILE = "FIRST_RUN_CREDENTIALS.txt"


def _config_dir() -> Path:
    return Path.home() / CONFIG_DIR_NAME


def _generate_pin() -> str:
    """8-digit numeric PIN, cryptographically random."""
    return "".join(str(secrets.randbelow(10)) for _ in range(8))


def _bootstrap_secrets() -> None:
    cfg_dir = _config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    secrets_path = cfg_dir / SECRETS_FILE

    cfg: dict[str, str] = {}
    if secrets_path.exists():
        try:
            cfg = json.loads(secrets_path.read_text(encoding="utf-8"))
            if not isinstance(cfg, dict):
                cfg = {}
        except (json.JSONDecodeError, OSError):
            cfg = {}

    fresh_pin: str | None = None
    changed = False

    if not os.environ.get("PASSPHRASE"):
        if not cfg.get("passphrase"):
            cfg["passphrase"] = secrets.token_urlsafe(32)
            changed = True
        os.environ["PASSPHRASE"] = cfg["passphrase"]

    if not os.environ.get("ADMIN_PIN"):
        if not cfg.get("admin_pin"):
            cfg["admin_pin"] = _generate_pin()
            fresh_pin = cfg["admin_pin"]
            changed = True
        os.environ["ADMIN_PIN"] = cfg["admin_pin"]

    if not os.environ.get("JWT_SECRET"):
        if not cfg.get("jwt_secret"):
            cfg["jwt_secret"] = secrets.token_urlsafe(48)
            changed = True
        os.environ["JWT_SECRET"] = cfg["jwt_secret"]

    if changed:
        secrets_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        try:
            os.chmod(secrets_path, 0o600)
        except OSError:
            pass
        if fresh_pin is not None:
            (cfg_dir / CREDENTIALS_FILE).write_text(
                "Local Home Agent — first-run credentials\n"
                "==========================================\n\n"
                f"Admin PIN: {fresh_pin}\n\n"
                "Open http://localhost:8000/setup in a browser to set\n"
                "your own admin PIN and passphrase. The values above are\n"
                "auto-generated on first run and stored in this folder.\n",
                encoding="utf-8",
            )
            print(
                f"\n*** First-run admin PIN: {fresh_pin} ***\n"
                f"    (also written to {cfg_dir / CREDENTIALS_FILE})\n",
                file=sys.stderr,
                flush=True,
            )


def main() -> None:
    _bootstrap_secrets()

    # Import AFTER env populated — app.main raises at import time if
    # PASSPHRASE / ADMIN_PIN are missing.
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
