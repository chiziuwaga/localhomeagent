"""FastAPI entrypoint for the Local Home Agent.

This is a scaffold. Only /health is implemented today. Runtime, pairing, captive portal,
and smart-home integrations are tracked in the README roadmap.
"""

from fastapi import FastAPI

from . import __version__

app = FastAPI(
    title="Local Home Agent",
    version=__version__,
    description="Offline AI agent for the Co-Living platform.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
