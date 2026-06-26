# QueueStorm Investigator

AI / API SupportOps copilot for the bKash × SUST CSE Carnival 2026 hackathon preliminary round.

This service exposes two endpoints:

- `GET /health` → `{"status":"ok"}`
- `POST /analyze-ticket` → structured case analysis (see `sample_output.json` for a real example)

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
