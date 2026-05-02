# Local Home Agent

The Local Home Agent is the offline AI companion for the Co-Living platform. It runs on the operator's own machine, talks to local LLMs (Ollama, LM Studio), exposes a captive-portal Wi-Fi onboarding flow, and integrates with smart-home devices.

This repository hosts two surfaces:

- **`site/`** — the public marketing + download page deployed at <https://localhomeagent.fixitforme.ai>.
- **`agent/`** — the desktop agent itself (Python / FastAPI). Currently a scaffold; the runtime is under active development.

The repo is consumed as a git submodule by the main coliving platform at <https://github.com/chiziuwaga/colivingplatform>.

## Site

```
cd site
npm install
npm run dev      # http://localhost:5173
npm run build    # static output in site/dist
```

Deploys to Render as a static site (see `render.yaml`).

## Agent

```
cd agent
uv sync          # or: pip install -e .
uv run uvicorn local_home_agent.main:app --reload
```

Health check: `GET http://localhost:8000/health`.

## License

MIT
