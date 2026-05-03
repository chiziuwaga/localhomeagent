# Local Home Agent

The Local Home Agent (LHA) is the offline AI companion for the Co-Living platform. It runs on the operator's own machine, talks to local LLMs (Ollama / LM Studio), exposes a captive-portal Wi-Fi onboarding flow, and integrates with smart-home devices.

This repository is the canonical home for both the agent runtime and its public marketing surface.

## Layout

| Path | Purpose |
| --- | --- |
| `app/` | FastAPI agent runtime — 25 modules covering auth, RBAC, encryption, LLM client, conversation cache, IoT discovery, voice, telemetry. Entry point: `app/main.py`. |
| `tests/` | Pytest suite (auth, conversation cache, system check, websocket chat, health, tool graph). |
| `static/`, `templates/` | Captive-portal UI assets served by FastAPI. |
| `config/` | Runtime config (yaml). Secrets land here at first run. |
| `installers/{windows,macos,linux}/` | Per-OS installer scaffolding (NSIS, pkg, .deb). |
| `installer.nsi` | NSIS installer script for Windows. |
| `build.spec`, `build-all.sh` | PyInstaller build orchestration. |
| `Dockerfile`, `docker-compose.yml` | Container deploy for telemetry / dev. |
| `requirements.txt` | Python deps (FastAPI, uvicorn, pydantic, jose, bcrypt, cryptography, sentry-sdk, …). |
| `site/` | Vite + React + Tailwind brutalist landing site. Deployed as a Render static service. |
| `docs/` | API docs, setup guide, development plan, deep TODO. |

## Run the agent locally

```
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `GET http://localhost:8000/api/health`
WebSocket chat: `ws://localhost:8000/ws`
Model recommender: `GET http://localhost:8000/api/system/recommend-model`

See `docs/SETUP_GUIDE.md` for the full first-run flow (Ollama install, model pull, pairing code).

## Run the marketing site

```
cd site
npm install
npm run dev      # http://localhost:5173
npm run build    # static output in site/dist
```

## Build a binary

```
./build-all.sh        # builds for current OS via PyInstaller
```

CI builds binaries for all three OSes on tag push (`v*`) and uploads them to GitHub Releases. See `.github/workflows/build-exe.yml` and `.github/workflows/build-installers.yml`.

## Integration with the Co-Living platform

The Co-Living platform at <https://coliving.fixitforme.ai> embeds the LHA download/setup UI at `/local-agent`. Download URLs on that page resolve to this repo's GitHub Releases:

```
https://github.com/chiziuwaga/localhomeagent/releases/latest/download/CoLiving-Home-Agent-Windows.exe
https://github.com/chiziuwaga/localhomeagent/releases/latest/download/CoLiving-Home-Agent-macOS
https://github.com/chiziuwaga/localhomeagent/releases/latest/download/CoLiving-Home-Agent-Linux
```

The Co-Living platform consumes this repo as a git submodule at `local-home-agent/`.

## License

MIT
