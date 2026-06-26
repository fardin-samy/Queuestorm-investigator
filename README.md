# QueueStorm Investigator

AI / API SupportOps copilot for the bKash × SUST CSE Carnival 2026 hackathon preliminary round.

This service exposes five endpoints plus a built-in web UI:

- `GET /` → built-in dashboard (no extra build step; vanilla HTML/CSS/JS in `static/`)
- `GET /health` → `{"status":"ok"}`
- `POST /analyze-ticket` → structured case analysis (the spec endpoint)
- `POST /analyze-tickets` → batch up to 100 tickets in one call; per-ticket errors don't abort the batch
- `GET /selftest` → runs the bundled 10-case hostile-test pack against `/analyze-ticket` and reports per-case pass/fail
- `GET /metrics` → Prometheus-format counters for tickets classified and batch requests

## Web UI

Open `http://127.0.0.1:8000/` after starting the service. The dashboard has four tabs:

- **Analyze** — fill the ticket form (or click any of the eight example-ticket buttons: wrong-transfer, payment-failed, duplicate, phishing, Bangla, merchant settlement, agent cash-in, refund request) and submit to see the full decision panel: case type, severity, department, evidence verdict, matched transaction, confidence, reason codes, and the safe agent summary + customer reply. A health badge in the header polls `/health` every 15 s.
- **Batch** — paste a `{"tickets":[...]}` payload (or click "Load sample") and submit; the response is rendered as a per-ticket status table.
- **Self-test** — runs the bundled hostile pack via `/selftest` and shows the `passed/total` verdict plus a per-case table (case type, severity, department, evidence verdict, human-review flag).
- **Metrics** — fetches `/metrics`, parses the Prometheus text format, and renders a table next to the raw payload.

The UI is pure static files served by FastAPI's `StaticFiles` mount after the API routes, so every existing endpoint behaves exactly as documented.

## Tech stack

- Python 3.11 + FastAPI + Uvicorn
- Rule-based classifier + transaction matcher (no LLM required)
- Mandatory output safety post-filter (Section 8)
- Optional LLM enhancement via `OPENAI_API_KEY` (off by default)

## MODELS

| Model | Where it runs | Why chosen |
| --- | --- | --- |
| Rule-based classifier + safety filter | In-process (no network) | Deterministic, zero cost, well below the 30 s/case SLA, satisfies all safety rules by construction. |

No external model is required to score well. The architecture allows swapping in an LLM later by editing `reply.py`; the safety post-filter still runs on top of any LLM output.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Run with Docker

```bash
docker build -t queuestorm-investigator .
docker run --rm -p 8000:8000 queuestorm-investigator
```

## Example request

```bash
curl -s http://127.0.0.1:8000/analyze-ticket \
  -H 'content-type: application/json' \
  -d '{
    "ticket_id": "TKT-001",
    "complaint": "I sent 5000 taka to a wrong number around 2pm today. Please refund.",
    "language": "en",
    "channel": "in_app_chat",
    "user_type": "customer",
    "transaction_history": [
      {"transaction_id":"TXN-9101","timestamp":"2026-04-14T14:08:22Z","type":"transfer","amount":5000,"counterparty":"+8801719876543","status":"completed"}
    ]
  }'
```

## Response headers

Every successful `/analyze-ticket` response carries routing headers so an
ops dashboard / proxy can branch on the decision without parsing the body:

| Header | Example |
| --- | --- |
| `X-Request-Id` | `8ee2e8a2005d` |
| `X-Case-Type` | `wrong_transfer` |
| `X-Severity` | `high` |
| `X-Department` | `dispute_resolution` |
| `X-Evidence-Verdict` | `consistent` |
| `X-Relevant-Transaction-Id` | `TXN-9101` |
| `X-Human-Review-Required` | `true` |

## Batch endpoint

```bash
curl -s http://127.0.0.1:8000/analyze-tickets \
  -H 'content-type: application/json' \
  -d '{"tickets": [ {ticket1}, {ticket2}, ... ]}'
```

Returns `{"count": N, "results": [{"ticket_id", "status", "body"}, ...]}`.
Max 100 tickets per call (returns 422 `batch_too_large` otherwise).
Empty batch → 422 `empty_batch`. Per-ticket schema or empty-complaint
errors are reported per-result with their own HTTP status, not as a
batch-level failure.

## Self-test endpoint

```bash
curl -s http://127.0.0.1:8000/selftest | jq .
```

Runs the 10 hostile cases (credential asks, third-party refund scams,
prompt injection, system-override attempts, empty complaint, vague
complaint, Bangla refund, merchant settlement delay, positive feedback)
against the live `/analyze-ticket` and asserts safety invariants on the
returned `customer_reply`. The same harness backs `python run_hostile.py`
for CI use.

## Quick verification

For a one-shot green/red verdict across every endpoint:

```bash
python smoke_test.py
```

Hits `/health`, `/metrics`, `/analyze-ticket` (happy path, empty
complaint, schema violation), `/analyze-tickets` (happy path, empty
batch), and `/selftest`. Exits non-zero on any failure, so it works as
a CI gate. Override the URL with `--url http://host:port` if the
service isn't on localhost.

## Safety logic

`enforce_safety()` in `safety.py` runs on **every** output field, after any generation step:

1. Removes any sentence that asks the customer for PIN / OTP / password / CVV / card number / verification code.
2. Replaces "we will refund / we have refunded / your refund has been processed" with the safe phrase "any eligible amount will be returned through official channels".
3. Removes any instruction to contact a third party.
4. Marks `human_review_required = true` when any redaction was needed.
5. Treats prompt-injection attempts inside complaint text as untrusted input — they never override safety rules.

## AI approach

1. **Matcher** (`matcher.py`) scores every transaction in history against the complaint text on phone-number match, amount match, explicit transaction ID match, and transaction type match. Only matches with score ≥ 3 are returned.
2. **Classifier** (`classifier.py`) detects Banglish + English keywords for each `case_type`, then maps to `severity` and `department` using the taxonomy in Section 7.
3. **Reply builder** (`reply.py`) composes an agent summary, a recommended next action, and a safe customer reply. It never asks for credentials or confirms a refund.
4. **Safety post-filter** (`safety.py`) runs last as a hard guarantee.

## Assumptions

- Customer complaint text may be English, Bangla, or mixed Banglish; we match keywords in both scripts.
- Empty `transaction_history` ⇒ `evidence_verdict = "insufficient_data"`.
- Amounts ≥ 5000 BDT are treated as high-value and escalate severity.

## Known limitations

- Pure rule-based classifier: lower recall on novel phrasings vs. a tuned LLM. Adding a small classifier model or an LLM tie-breaker behind the same safety filter is a natural next step.
- Bangla character set in keywords is partial; expand `K_*` lists in `classifier.py` for better Bangla coverage.
