# HealthMind

Minimal README for the HealthMind repository.

## Project
- HealthMind: medical knowledge RAG API and web frontend.
- Backend: FastAPI app at [app/main.py](app/main.py#L1-L200).
- Frontend: single-page app in `frontend/` (Vite + React).

## Requirements
- Python 3.10+ (virtualenv recommended)
- Node.js 18+ (for frontend)
- Install Python deps:

```bash
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run backend (development)
```bash
# from repo root, with venv active
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Open the API docs at http://localhost:8000/docs

## Run frontend (development)
```bash
cd frontend
npm install
npm run dev
```
- Frontend calls `/api/v1` by default and Vite proxies `/api` to `http://localhost:8000` in development.
- Set `VITE_API_URL` in `frontend/.env` if you want to point the UI at a different backend.

## Data and local DB
- The app uses a local SQLite DB by default at `./data/healthmind_main.db` and a Qdrant collection under `data/qdrant/`.
- Ensure `data/` exists and is writable before starting the app.

## Scripts & one-off utilities
- [scripts/create_admin.py](scripts/create_admin.py) — helper to create an admin user.
- [scratch/list_users.py](scratch/list_users.py#L1-L13) — ad-hoc script that prints rows from the local `users` table:

```bash
python scratch/list_users.py
```

Notes: `scratch/` contains quick experiments and one-off utilities. Move useful scripts into `scripts/` if you want to keep them long-term.

## Contributing
- Create a feature branch from `main`, open a PR, and reference any issue IDs.
