"""
Shared pytest config:

  - prepends the repo root to sys.path so ``from app.X import …`` works
    without requiring a packaged install
  - sets test-only PASSPHRASE / ADMIN_PIN / JWT_SECRET so ``app.main`` can
    import (it raises at import time without them)
  - flips ``app.main._FIRST_RUN_COMPLETE = True`` once at session start so
    the bulk of the test suite (which exercises post-setup behaviour) is
    not blocked by the first-run gate. Tests that specifically verify the
    gate (``test_first_run_setup.py``) override per-test via monkeypatch.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("PASSPHRASE", "test-passphrase-do-not-use")
os.environ.setdefault("ADMIN_PIN", "12345678")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-do-not-use")

# Importing app.main is what triggers the env-var requirement check.
from app import main as _app_main  # noqa: E402

# Default to "past first-run" for every existing test file. Per-test
# overrides via monkeypatch in test_first_run_setup.py still work because
# monkeypatch saves+restores around its own setattr calls.
_app_main._FIRST_RUN_COMPLETE = True
