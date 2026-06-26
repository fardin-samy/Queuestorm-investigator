"""One-command integration check for the QueueStorm Investigator service.

Hits every endpoint the judges care about and prints a green/red verdict.
Exits non-zero on any failure so it works as a CI gate.

Usage:
    python smoke_test.py
    python smoke_test.py --url http://127.0.0.1:8000
    python smoke_test.py --skip-docker   # for use inside a running container
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def _http(method: str, url: str, body: Any = None, timeout: float = 15.0) -> Tuple[int, Any, Dict[str, str]]:
    data = None
    headers: Dict[str, str] = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                parsed = raw.decode("utf-8", errors="replace")
            return resp.status, parsed, dict(resp.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = raw.decode("utf-8", errors="replace")
        return exc.code, parsed, dict(exc.headers)


class Suite:
    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.results: List[str] = []

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            self.results.append(f"  {GREEN}PASS{RESET} {label}")
            if detail:
                self.results.append(f"        {detail}")
        else:
            self.failed += 1
            self.results.append(f"  {RED}FAIL{RESET} {label}")
            if detail:
                self.results.append(f"        {detail}")

    def report(self) -> int:
        total = self.passed + self.failed
        print(f"\n{GREEN}== {self.passed} passed{RESET} / {RED}{self.failed} failed{RESET} == total {total}")
        for line in self.results:
            print(line)
        return 0 if self.failed == 0 else 1


def run(url: str) -> int:
    print(f"\n{YELLOW}Smoke-testing {url}{RESET}\n")
    s = Suite()
    base = url.rstrip("/")

    # 1. /health
    status, body, _ = _http("GET", f"{base}/health")
    s.check("GET /health → 200", status == 200, f"status={status} body={body}")
    s.check("GET /health body == {'status':'ok'}", body == {"status": "ok"}, f"got={body}")

    # 2. /metrics is Prometheus exposition with a tickets_total counter.
    status, body, hdrs = _http("GET", f"{base}/metrics")
    s.check("GET /metrics → 200", status == 200, f"status={status}")
    s.check("GET /metrics body has queuestorm_tickets_total",
            "queuestorm_tickets_total" in (body or ""), f"head={body[:120] if body else ''}")

    # 3. /analyze-ticket: a known-spec wrong-transfer case.
    sample = {
        "ticket_id": "SMOKE-WT",
        "complaint": "I sent 5000 taka to a wrong number around 2pm today. Please refund.",
        "language": "en",
        "channel": "in_app_chat",
        "user_type": "customer",
        "transaction_history": [
            {"transaction_id": "TXN-SMOKE-1", "timestamp": "2026-04-14T14:08:22Z",
             "type": "transfer", "amount": 5000, "counterparty": "+8801719876543",
             "status": "completed"},
        ],
    }
    status, body, hdrs = _http("POST", f"{base}/analyze-ticket", sample)
    s.check("POST /analyze-ticket (wrong_transfer) → 200", status == 200, f"status={status}")
    s.check("case_type == wrong_transfer",
            isinstance(body, dict) and body.get("case_type") == "wrong_transfer",
            f"got={body.get('case_type') if isinstance(body, dict) else body}")
    s.check("department == dispute_resolution",
            isinstance(body, dict) and body.get("department") == "dispute_resolution",
            f"got={body.get('department') if isinstance(body, dict) else body}")
    s.check("relevant_transaction_id matches",
            isinstance(body, dict) and body.get("relevant_transaction_id") == "TXN-SMOKE-1",
            f"got={body.get('relevant_transaction_id') if isinstance(body, dict) else body}")
    # Headers that proxies can branch on without parsing the body.
    header_keys = {k.lower() for k in hdrs}
    for h in ("x-case-type", "x-severity", "x-department",
              "x-evidence-verdict", "x-human-review-required", "x-request-id"):
        s.check(f"response header {h}", h in header_keys, f"headers={sorted(header_keys)}")

    # 4. /analyze-ticket: empty-complaint rejection.
    status, body, _ = _http("POST", f"{base}/analyze-ticket",
                            {"ticket_id": "SMOKE-EMPTY", "complaint": ""})
    s.check("POST /analyze-ticket empty → 422",
            status == 422, f"status={status} body={body}")
    s.check("empty complaint error == empty_complaint",
            isinstance(body, dict) and body.get("error") == "empty_complaint",
            f"got={body}")

    # 5. /analyze-ticket: schema violation.
    status, body, _ = _http("POST", f"{base}/analyze-ticket", {"complaint": "no ticket_id"})
    s.check("POST /analyze-ticket missing ticket_id → 400",
            status == 400, f"status={status}")

    # 6. /analyze-tickets: batch endpoint.
    batch = {
        "tickets": [
            sample,
            {"ticket_id": "SMOKE-EMPTY-B", "complaint": ""},
            {"ticket_id": "SMOKE-PF",
             "complaint": "Payment failed but money deducted 200 taka",
             "language": "en", "channel": "in_app_chat", "user_type": "customer",
             "transaction_history": [
                 {"transaction_id": "TXN-PF", "timestamp": "2026-04-15T10:00:00Z",
                  "type": "payment", "amount": 200, "counterparty": "merchant_x",
                  "status": "failed"},
             ]},
        ],
    }
    status, body, _ = _http("POST", f"{base}/analyze-tickets", batch)
    s.check("POST /analyze-tickets → 200", status == 200, f"status={status}")
    s.check("batch count == 3",
            isinstance(body, dict) and body.get("count") == 3,
            f"got={body.get('count') if isinstance(body, dict) else body}")
    if isinstance(body, dict) and "results" in body:
        statuses = [r.get("status") for r in body["results"]]
        s.check("batch per-ticket statuses == [200, 422, 200]",
                statuses == [200, 422, 200], f"got={statuses}")

    # 7. /analyze-tickets: empty batch → 422.
    status, body, _ = _http("POST", f"{base}/analyze-tickets", {"tickets": []})
    s.check("POST /analyze-tickets empty → 422 empty_batch",
            status == 422 and isinstance(body, dict) and body.get("error") == "empty_batch",
            f"status={status} body={body}")

    # 8. /selftest: the bundled hostile pack must all pass.
    status, body, _ = _http("GET", f"{base}/selftest")
    s.check("GET /selftest → 200", status == 200, f"status={status}")
    if isinstance(body, dict):
        total = body.get("total")
        passed = body.get("passed")
        ok = body.get("ok")
        s.check(f"/selftest ok == True (got ok={ok}, passed={passed}/{total})",
                ok is True, f"failures={body.get('failures', [])[:3]}")

    return s.report()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000",
                    help="Base URL of the running service (default: http://127.0.0.1:8000)")
    args = ap.parse_args()
    started = time.time()
    rc = run(args.url)
    elapsed = time.time() - started
    print(f"\nFinished in {elapsed:.2f}s")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
