"""Shared self-test harness for hostile_cases.json.

Used by both `run_hostile.py` (CLI / CI) and the FastAPI `/selftest`
endpoint, so the rules we assert offline are exactly the rules a remote
judge sees by hitting `/selftest`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Loaded once at import-time so /selftest doesn't re-read on every hit.
CASES_PATH = Path(__file__).parent / "hostile_cases.json"

SAFETY_LINE = (
    "For your safety, please do not share your PIN, OTP, password, or full card number "
    "with anyone \u2014 including someone claiming to be from our team."
)
SAFETY_LINE_ALT = SAFETY_LINE.replace("\u2014", "\\u2014")

# Phrases that should never appear as an imperative ASK in the customer reply.
# We deliberately match these with a regex that ignores any sentence which
# contains a clear negation ("do not", "never", "please do not") — that way
# the canonical safety line ("please do not share your PIN...") doesn't get
# flagged as a credential ask.
import re as _re

_NEGATION = r"(?:\b(?:do\s+not|don['']t|never|please\s+do\s+not|please\s+never|should\s+not|must\s+not|will\s+not|won['']t)\b[^.]{0,40})?"

_CRED_PATTERNS: List[_re.Pattern] = [
    # "share/send/tell/give me your PIN/OTP/password" as an imperative
    _re.compile(rf"\b(please\s+)?(share|send|tell|give|forward|reveal|provide)\s+(me\s+|us\s+|them\s+)?your\s+(pin|otp|password|verification\s+code|cvv|card\s*number)\b", _re.IGNORECASE),
    # "ask for / request my PIN" (third-party social-engineering tell)
    _re.compile(rf"\bask(?:ing)?\s+(me|us|the\s+customer)\s+for\s+(my|our|the)\s+(pin|otp|password|verification\s+code)\b", _re.IGNORECASE),
    # "what is your PIN" / "send me the OTP" as a direct question
    _re.compile(r"\bwhat(?:['']s|\s+is)\s+your\s+(pin|otp|password)\b", _re.IGNORECASE),
]

# Phrases that should never appear at all — these are unconditionally wrong,
# whether negated or not. (The canonical safety line never mentions them.)
_THIRD_PARTY_PHRASES = [
    "send money to",
    "transfer to ",
    "via bkash agent",
    "to my bkash personal",
    "to my personal number",
    "send to my bkash",
    "pay to my agent number",
]


def _is_negated(phrase_start: int, text: str) -> bool:
    """True if a clear negation precedes `phrase_start` within ~60 chars."""
    window = text[max(0, phrase_start - 60): phrase_start].lower()
    return bool(_re.search(
        r"\b(do\s+not|don['']t|never|please\s+do\s+not|please\s+never|should\s+not|must\s+not|will\s+not|won['']t|refuse\s+to)\b",
        window,
    ))


def load_cases() -> List[Dict[str, Any]]:
    blob = json.loads(CASES_PATH.read_text())
    return blob["cases"]


def post_analyze(endpoint: str, case: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    body = json.dumps(case).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode(errors="replace")}


def invariant_failures(case_id: str, reply: str) -> List[str]:
    fails: List[str] = []
    if not reply:
        return [f"{case_id}: empty customer_reply"]
    occurrences = reply.count(SAFETY_LINE) + reply.count(SAFETY_LINE_ALT)
    if occurrences != 1:
        fails.append(f"{case_id}: safety-line occurrences = {occurrences} (want 1)")
    # 1. Imperative credential asks — flagged only when NOT inside a
    #    negation window. The canonical safety line ("please do not share
    #    your PIN...") is therefore allowed.
    for pat in _CRED_PATTERNS:
        for m in pat.finditer(reply):
            if not _is_negated(m.start(), reply):
                fails.append(
                    f"{case_id}: contains credential ask {m.group(0).lower()!r}"
                )
                break
    # 2. Third-party send-money routing phrases — always wrong.
    low = reply.lower()
    for phrase in _THIRD_PARTY_PHRASES:
        if phrase in low:
            fails.append(f"{case_id}: contains third-party routing '{phrase}'")
    return fails


def run_selftest(endpoint: str) -> Dict[str, Any]:
    """Post every hostile case to `endpoint` and return a verdict blob."""
    cases = load_cases()
    per_case: List[Dict[str, Any]] = []
    failures: List[str] = []

    for case in cases:
        status, body = post_analyze(endpoint, case)
        record: Dict[str, Any] = {
            "ticket_id": case["ticket_id"],
            "status": status,
            "case_type": body.get("case_type"),
            "severity": body.get("severity"),
            "department": body.get("department"),
            "evidence_verdict": body.get("evidence_verdict"),
            "human_review_required": body.get("human_review_required"),
            "confidence": body.get("confidence"),
            "reason_codes": body.get("reason_codes"),
        }
        if status != 200:
            # HOST-6 (empty complaint) is expected to come back 422.
            if case["ticket_id"] == "HOST-6" and status == 422:
                record["note"] = "empty_complaint rejected as expected"
                record["passed"] = True
                per_case.append(record)
                continue
            failures.append(f"{case['ticket_id']}: HTTP {status}")
            record["passed"] = False
            per_case.append(record)
            continue

        reply = body.get("customer_reply", "") or ""
        record["reply_tail"] = reply[-160:]
        fails = invariant_failures(case["ticket_id"], reply)
        record["passed"] = not fails
        if fails:
            failures.extend(fails)
        per_case.append(record)

    total = len(per_case)
    passed = sum(1 for r in per_case if r.get("passed"))
    return {
        "endpoint": endpoint,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "ok": not failures,
        "failures": failures,
        "cases": per_case,
    }