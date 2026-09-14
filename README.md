# GABAI

Citizen service request management for a barangay LGU. Residents submit free-text
requests in Filipino, English, or Taglish; a fine-tuned transformer classifies each
one by category and urgency and routes it to the responsible handler. Predictions
below a confidence threshold are diverted to a manual review queue instead of being
routed automatically.

Undergraduate thesis project, Mapúa University, School of Information Technology,
S.Y. 2026–2027. Partner Barangay: Barangay V "Singko", Amaya, Tanza, Cavite.

## Stack

| Layer | |
|---|---|
| Frontend | React 19, TypeScript, Tailwind CSS v4, Vite |
| Backend | FastAPI, SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL 16 |
| Classifier | Hugging Face transformer, fine-tuned; ONNX Runtime int8 at inference |

## Layout

```
frontend/          React SPA
backend/           FastAPI application and migrations
ml/                dataset, training, evaluation, ONNX export
openapi.yaml       API spec, written before implementation
docker-compose.yml PostgreSQL for local development
```

`openapi.yaml` is the source of truth for the API. Frontend types are generated
from it (`npm run gen:api`), so an API change that breaks the client fails at
compile time rather than in the browser.

## Prerequisites

Docker, Python 3.11+, Node 20+.

## Setup

```bash
cp .env.example .env
docker compose up -d
```

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed          # creates the first admin, see .env.example
python run.py               # Windows needs this, not uvicorn directly
```

API at `http://localhost:8000`, interactive docs at `/docs`.

On a server, run the migration and the seed the same way, then start it with
uvicorn directly:

```bash
alembic upgrade head
python -m app.seed
uvicorn app.main:app --host 0.0.0.0 --workers 1
```

One worker. The classifier loads a model per head per worker, so a second worker
doubles the model memory. onnxruntime releases the GIL and inference runs in a
threadpool, so one worker still serves concurrent requests.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

App at `http://localhost:5173`. Requests to `/api` are proxied to the backend, so
the dev server is same-origin. This mirrors production deliberately: session
cookies are `SameSite=Lax`, so the app and API are served from one origin in
every environment.

The classifier is fine-tuned separately, and benchmarked against a TF-IDF + SVM
baseline trained on the same split. See `ml/README.md`.

## Deployment architecture

One host runs the whole system. Caddy terminates TLS and serves the built React
app, proxying `/api/*` to the API on loopback. The API and Postgres run as
containers, and Postgres publishes no port, so it is reachable only over the
container network. Attachments and the exported models are mounted from disk
rather than built into the image, which makes a retrained model a file copy and
a restart.

The site and the API share one origin deliberately. The session cookie is
`SameSite=Lax`, so a browser would not send it to a separately hosted frontend
and every signed-in request would fail.

Keeping the classifier in the API process means there is no second service to
deploy or pay for. Quantizing it to int8 takes each head from 679 MB to 171 MB,
which is what lets the whole system run on a small CPU-only instance.

## Conventions

- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`)
- API responses are snake_case; timestamps are ISO-8601 UTC
- Authorization is enforced server-side on every endpoint
- Small, frequent commits; history is not squashed

## Authors

Jean Clarisse D. Dalu · Bart Daniel P. Dayao · Justin Brylle G. Salazar
Adviser: Dr. Mary Jane Samonte
