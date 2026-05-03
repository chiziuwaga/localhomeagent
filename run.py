"""
Top-level launcher for PyInstaller-bundled binaries.

PyInstaller treats the entry script as a top-level module, so when it
invokes ``app/main.py`` directly the relative imports inside that file
(``from .llm_client import ...``) fail with::

    ImportError: attempted relative import with no known parent package

This wrapper imports the package the proper way, so the relative imports
inside ``app/`` resolve correctly.
"""

import os
import uvicorn

from app.main import app


def main() -> None:
    host = os.environ.get("LHA_HOST", "0.0.0.0")
    port = int(os.environ.get("LHA_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
