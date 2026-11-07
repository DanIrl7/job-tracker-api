# Job Tracker API

A REST API for tracking your job applications. Each user registers, logs in with a JWT, and sees only their own applications. A follow-up endpoint lists active applications that need a reply soon.

Built with FastAPI, SQLAlchemy and PostgreSQL. Tested with pytest. Runs in Docker and in GitHub Actions.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/auth/register` | Create an account (email, password of 8+ characters) |
| POST | `/auth/login` | Get a bearer token |
| POST | `/applications` | Add an application |
| GET | `/applications` | List your applications, optionally `?status=interviewing` |
| GET | `/applications/follow-ups` | Active applications with a follow-up date in the next `days` days (default 7) |
| GET | `/applications/{id}` | Get one application |
| PATCH | `/applications/{id}` | Change some fields |
| DELETE | `/applications/{id}` | Delete an application |

Other users' applications return 404, the same as a missing one. Passwords are stored as salted PBKDF2 hashes.

## Run with Docker Compose

Set a secret key, then start the API and PostgreSQL:

```bash
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build
```

The API is at http://127.0.0.1:8000/docs.

## Run locally

Use Python 3.12 or newer. Without `DATABASE_URL`, the app uses a SQLite file called `tracker.db`.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY="a-long-random-string-of-at-least-32-characters"
uvicorn app.main:create_app --factory --reload
```

## Try it

```bash
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"a-long-password"}'

TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"a-long-password"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -X POST http://127.0.0.1:8000/applications -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company":"Acme","role_title":"Junior Developer","applied_on":"2026-11-01","follow_up_on":"2026-11-08"}'

curl "http://127.0.0.1:8000/applications/follow-ups?days=7" -H "Authorization: Bearer $TOKEN"
```

## Run the tests

```bash
python -m pytest -v
```

Locally the tests use a temporary SQLite file for each test. To run them against PostgreSQL, set `DATABASE_URL` first:

```bash
DATABASE_URL=postgresql+psycopg://tracker:tracker@localhost:5432/tracker python -m pytest -v
```

CI runs the suite against a PostgreSQL service container and builds the Docker image.

## Deploy on Render

`render.yaml` is a Render Blueprint. It creates a Postgres database, connects it to a Docker web service, and generates `SECRET_KEY`. Connect the repo in Render using "New Blueprint Instance".
