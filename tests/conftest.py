"""
Shared pytest config:

  - prepends the repo root to sys.path so ``from app.X import …`` works
    without requiring a packaged install
  - sets test-only PASSPHRASE / ADMIN_PIN / JWT_SECRET so ``app.main`` can
    import (it raises at import time without them)
  - flips ``app.main._FIRST_RUN_COMPLETE = True`` for every test by default
    so the bulk of the suite (which exercises post-setup behaviour) is not
    blocked by the first-run gate. Some test fixtures (e.g.
    test_platform_pairing) reload ``app.main`` inside their own setup,
    which re-executes the ``_FIRST_RUN_COMPLETE`` initializer and resets
    it to False — so this is implemented as an autouse function-scoped
    fixture that runs *after* such reloads.
    Tests that specifically verify the gate (``test_first_run_setup.py``)
    override per-test via monkeypatch.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("PASSPHRASE", "test-passphrase-do-not-use")
os.environ.setdefault("ADMIN_PIN", "12345678")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-do-not-use")


@pytest.fixture(autouse=True)
def _default_past_first_run(request):
    """
    Default ``_FIRST_RUN_COMPLETE = True`` for every test. Skip for the
    dedicated first-run test file which uses monkeypatch to flip it back
    to False inside each test.
    """
    if "test_first_run_setup" in request.node.nodeid:
        yield
        return

    # Lazy import — pytest may run tests in modules that do their own
    # reload(app.main) before this fixture body executes.
    from app import main as _app_main

    original = getattr(_app_main, "_FIRST_RUN_COMPLETE", False)
    _app_main._FIRST_RUN_COMPLETE = True
    try:
        yield
    finally:
        _app_main._FIRST_RUN_COMPLETE = original
