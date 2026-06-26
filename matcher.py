"""Pick the transaction in history that the complaint most likely refers to."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_PHONE_RE = re.compile(r"\+?\d{10,15}")


def _amounts(text: str) -> List[float]:
    candidates = re.findall(r"\b\d{2,7}(?:\.\d{1,2})?\b", text.replace(",", ""))
    out: List[float] = []
    for c in candidates:
        try:
            v = float(c)
        except ValueError:
            continue
        if 5 <= v <= 5_000_000:
            out.append(v)
    return out


def _phones(text: str) -> List[str]:
    return _PHONE_RE.findall(text)


def _norm_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    return digits[-10:] if len(digits) >= 10 else digits


def _score(complaint: str, tx: Dict[str, Any]) -> int:
    score = 0
    cp_phone = _norm_phone(str(tx.get("counterparty") or ""))
    for p in _phones(complaint):
        if _norm_phone(p) and _norm_phone(p) == cp_phone:
            score += 5
            break

    tx_amt = tx.get("amount")
    if isinstance(tx_amt, (int, float)):
        for a in _amounts(complaint):
            if abs(float(a) - float(tx_amt)) < 0.01:
                score += 3
                break

    tx_id = str(tx.get("transaction_id") or "")
    if tx_id and tx_id.lower() in complaint.lower():
        score += 8

    tx_type = str(tx.get("type") or "")
    if tx_type == "transfer" and any(k in complaint.lower() for k in ("transfer", "sent", "পাঠাই", "pathano", "pathaisi", "pathacchi")):
        score += 1
    if tx_type == "payment" and any(k in complaint.lower() for k in ("payment", "pay", "বিল", "bill")):
        score += 1
    if tx_type == "cash_in" and any(k in complaint.lower() for k in ("cash in", "cash-in", "deposit", "deposited", "ক্যাশ ইন", "জমা", "এজেন্ট")):
        score += 1
    if tx_type == "settlement" and any(k in complaint.lower() for k in ("settlement", "settle", "সেটেলমেন্ট")):
        score += 1
    if tx_type == "refund" and any(k in complaint.lower() for k in ("refund", "রিফান্ড", "ফেরত")):
        score += 1

    # Merchant-context boost: if the only transaction in history is a settlement
    # and the complaint mentions "merchant" or "settlement", trust the match.
    if tx_type == "settlement" and (
        "merchant" in complaint.lower()
        or "settlement" in complaint.lower()
        or "settle" in complaint.lower()
        or "shop" in complaint.lower()
        or "মার্চেন্ট" in complaint.lower()
    ):
        score += 3

    return score


def find_relevant_transaction(
    complaint: str,
    history: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not complaint or not history:
        return None

    # When the complaint talks about being charged "twice" / "duplicate",
    # the *latest* transaction is the one the agent typically needs to
    # investigate and reverse. Pick by score first; tie-break toward the
    # chronologically-latest transaction in duplicate-payment complaints.
    duplicate_terms = ("twice", "double charged", "duplicate", "charged twice",
                       "two times", "দুইবার", "ডাবল", "ডুপ্লিকেট")
    is_duplicate = any(t in (complaint or "").lower() for t in duplicate_terms)

    scored = sorted(
        ((_score(complaint, tx), tx) for tx in history),
        key=lambda pair: (
            pair[0],
            pair[1].get("timestamp", "") if is_duplicate else "",
        ),
        reverse=True,
    )
    best_score, best = scored[0]
    return best if best_score >= 3 else None
