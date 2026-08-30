# GABAI

Citizen service request management for a barangay LGU. Residents submit free-text
requests in Filipino, English, or Taglish; a fine-tuned transformer classifies each
one by category and urgency and routes it to the responsible handler. Predictions
below a confidence threshold are diverted to a manual review queue instead of being
routed automatically.

Undergraduate thesis project — Mapúa University, School of Information Technology,
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
openapi.yaml       API contract — written before implementation
docker-compose.yml PostgreSQL for local development
```

`openapi.yaml` is the source of truth for the API. Frontend types are generated
from it (`npm run gen:api`), so a contract change that breaks the client fails at
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
uvicorn app.main:app --reload
```

API at `http://localhost:8000`, interactive docs at `/docs`.

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
baseline trained on the same split — see `ml/README.md`.

## Conventions

- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`)
- API responses are snake_case; timestamps are ISO-8601 UTC
- Authorization is enforced server-side on every endpoint
- Small, frequent commits; history is not squashed

## Authors

Jean Clarisse D. Dalu · Bart Daniel P. Dayao · Justin Brylle G. Salazar
Adviser: Dr. Mary Jane Samonte
