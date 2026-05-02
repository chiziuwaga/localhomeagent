# Local Home Agent (runtime)

Offline AI agent for the Co-Living platform. Talks to local LLMs (Ollama, LM Studio),
runs a captive-portal Wi-Fi onboarding service, and integrates with smart-home devices.

This is a **scaffold**. Only `/health` is implemented. The runtime is under active
development and will land in subsequent commits.

## Develop

```bash
cd agent
uv sync             # or: pip install -e ".[dev]"
uv run uvicorn local_home_agent.main:app --reload --port 8000
```

Then: `curl http://localhost:8000/health` &rarr; `{"status":"ok"}`.

## Roadmap

- [ ] Ollama / LM Studio orchestration
- [ ] Pairing handshake with coliving.fixitforme.ai
- [ ] Captive portal (RADIUS / coova-chilli or pure-Python)
- [ ] Smart-home bridge (Home Assistant Supervisor compatibility)
- [ ] Packaging: PyInstaller for Windows, py2app for macOS, AppImage for Linux
