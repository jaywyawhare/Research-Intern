# AI Researcher

Stateful literature-research workspaces: ingest papers (arXiv and other sources), optional **HydraDB** memory and knowledge graph, OpenAI-compatible **LLM synthesis**, and a **Next.js** UI backed by a **FastAPI** service.

---

## Architecture

| Layer | Role |
|--------|------|
| **Frontend** (`frontend/`) | Next.js 15 (App Router). Browser calls same-origin `/v1/*`; Next rewrites to the API. |
| **Backend** (`backend/`) | FastAPI: sessions, agent turns, one-shot `/v1/research/run`. |
| **Core** (`core/`) | Literature fetch, workflow, LLM completion, Hydra bridge. |
| **Data** | **MongoDB** for durable sessions when `MONGODB_URI` is set; otherwise in-memory (lost on restart). |

Local development runs **uvicorn** and **next dev** side by side. Production can use the **Dockerfile** at the repo root to run both processes in one container (e.g. Render).

---

## Requirements

- **Python** 3.12+ (project targets 3.12; see `requirements.txt`)
- **Node** 20+ (for the frontend)
- **MongoDB** optional but recommended for persistence (Atlas works; TLS uses certifi in code)

---

## Quick start (local)

1. Clone and install Python deps from the **repository root**:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy env template and fill in secrets (never commit `.env`):

   ```bash
   cp .env.example .env
   ```

   At minimum for full functionality: an OpenAI-compatible key (`OPENAI_API_KEY` or `NVIDIA_API_KEY`), model/base URL as needed, and Hydra credentials if you use cloud memory (`HYDRADB_*`). See `.env.example` for the full list.

3. Frontend env (optional; defaults work for local):

   ```bash
   cp frontend/.env.example frontend/.env
   ```

   `RESEARCH_API_URL=http://127.0.0.1:8000` lets Next proxy `/v1` to the local API. Do **not** point `NEXT_PUBLIC_*` at `127.0.0.1:8000`—that is for the server-side rewrite only.

4. Run API + UI together:

   ```bash
   npm install
   npm run dev
   ```

   Or separately: `npm run dev:api` and `npm run dev:web`.

- API: `http://127.0.0.1:8000` (see `BACKEND_HOST` / `BACKEND_PORT` in `.env`)
- UI: `http://127.0.0.1:3000`
