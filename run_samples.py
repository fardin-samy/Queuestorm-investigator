"""POST every public sample case in SUST_Preli_Sample_Cases.json to the local service.

Usage:
    python run_samples.py
    python run_samples.py --input path/to/cases.json --output out.json --url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any, Dict


def _post(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(
        url=url.rstrip("/") + "/analyze-ticket",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="SUST_Preli_Sample_Cases.json")
    ap.add_argument("--output", default="sample_output.json")
    ap.add_argument("--url", default=os.environ.get("SERVICE_URL", "http://127.0.0.1:8000"))
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        pack = json.load(f)

    cases = pack.get("cases") if isinstance(pack, dict) else pack
    if not isinstance(cases, list):
        print("ERROR: cases not found in input file", file=sys.stderr)
        return 2

    results = []
    for i, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            continue
        payload = case.get("input", case)
        try:
            out = _post(args.url, payload)
        except Exception as exc:  # noqa: BLE001
            out = {"error": "request_failed", "detail": str(exc), "input_ticket_id": payload.get("ticket_id")}
        print(f"[{i}/{len(cases)}] {payload.get('ticket_id', '?')} -> "
              f"{out.get('case_type', out.get('error'))} / {out.get('evidence_verdict', '?')}")
        results.append({"input": payload, "output": out})

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(results)} results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
