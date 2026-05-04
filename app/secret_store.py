"""
secret_store — single source of truth for the desktop binary's secrets.

Persists ``~/.local-home-agent/secrets.json`` with mode 600 on POSIX. The
file is written by ``run.py`` on first boot (random bootstrap secrets) and
later overwritten by the setup wizard / Security section once the user
sets their own values.

Schema::

    {
        "passphrase":          "<urlsafe token>",
        "admin_pin":           "<digits>",          # raw — bcrypt-hashed in memory
        "jwt_secret":          "<urlsafe token>",
        "first_run_complete":  false                # flips to true after /setup
    }
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Optional


CONFIG_DIR_NAME = ".local-home-agent"
SECRETS_FILE = "secrets.json"


def config_dir() -> Path:
    return Path.home() / CONFIG_DIR_NAME


def secrets_path() -> Path:
    return config_dir() / SECRETS_FILE


def read_secrets() -> dict:
    p = secrets_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def write_secrets(data: dict) -> None:
    p = secrets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def update(**kwargs) -> dict:
    data = read_secrets()
    data.update(kwargs)
    write_secrets(data)
    return data


def is_first_run_complete() -> bool:
    return bool(read_secrets().get("first_run_complete"))


def mark_first_run_complete() -> None:
    update(first_run_complete=True)


def get_passphrase() -> Optional[str]:
    return read_secrets().get("passphrase")


def get_admin_pin() -> Optional[str]:
    return read_secrets().get("admin_pin")


def generate_bootstrap_pin() -> str:
    """Cryptographically random 8-digit PIN."""
    return "".join(str(secrets.randbelow(10)) for _ in range(8))


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
