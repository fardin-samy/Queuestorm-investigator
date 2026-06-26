# RUNBOOK — QueueStorm Investigator

A stranger should be able to bring this service up from a clean machine using only this file.

## Option A — Run locally (Python)

```bash
git clone <your-repo-url> queuestorm-investigator
cd queuestorm-investigator
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Sanity check:

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}
```

## Option B — Run with Docker

```bash
docker build -t queuestorm-investigator .
docker run --rm -p 8000:8000 queuestorm-investigator
```

Sanity check (in another terminal):

```bash
curl -s http://127.0.0.1:8000/health
```

## Environment variables

Copy `.env.example` to `.env` and fill in if you want LLM enhancement (off by default):

```
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=
```

When `OPENAI_API_KEY` is empty the service uses the rule-based engine. Nothing is required for the service to run.

## Submission paths

- **A. Live URL** — deploy the container to Render, Railway, Fly, Vercel, EC2, or any reachable HTTPS host. Expose port 8000 and point your URL at `/health` and `/analyze-ticket`.
- **B. Docker image** — `docker build -t <dockerhub-user>/queuestorm-investigator:1.0 . && docker push <dockerhub-user>/queuestorm-investigator:1.0`. Run command: `docker run --rm -p 8000:8000 <dockerhub-user>/queuestorm-investigator:1.0`.
- **C. Code with runbook** — this file plus the README is the runbook.

## How judges can re-run the public sample cases

```bash
python run_samples.py
```

This script POSTs each public sample case to `http://127.0.0.1:8000/analyze-ticket` and writes `sample_output.json`.

## One-command verification

```bash
python smoke_test.py
```

Hits every endpoint (`/health`, `/metrics`, `/analyze-ticket` happy/empty/malformed, `/analyze-tickets` happy/empty, `/selftest`) and prints a green/red verdict. Exits non-zero on any failure — safe for CI. Use `--url http://host:port` for remote services.

The Docker image also includes `smoke_test.py`, so judges can run:

```bash
docker run --rm queuestorm-investigator python smoke_test.py --url http://host:8000
```
