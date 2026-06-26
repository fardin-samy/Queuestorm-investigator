"""Rule-based classifier, severity, department, and evidence verdict."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# --- keyword groups (English + Banglish) ------------------------------------

K_WRONG_TRANSFER = [
    "wrong number", "wrong recipient", "wrong person", "sent to wrong",
    "wrong transfer", "wrongly sent", "by mistake", "mistakenly",
    "ভুল নম্বর", "ভুল নাম্বার", "ভুল করে", "ভুলে পাঠিয়েছি", "ভুল ট্রান্সফার",
    "ভুল রিসিভার", "ভুল প্রাপক",
    "bhul", "bhul number", "bhul pathano", "bhul Kore", "bhul kore",
]

K_PAYMENT_FAILED = [
    "payment failed", "transaction failed", "failed but", "deducted",
    "balance deducted", "money deducted", "amount deducted",
    "but i didn't receive", "did not receive", "not received",
    "পেমেন্ট ফেইল", "লেনদেন ব্যর্থ", "কেটে নিয়েছে", "কেটে গেছে",
    "ব্যালেন্স কেটে", "টাকা কেটে", "পেয়েছি না",
    "taka kete", "kete geche", "kete niyeche", "paymnt fail", "txn fail",
]

K_REFUND_REQUEST = [
    "refund", "please return", "return my money", "give me back",
    "want my money back",
    "রিফান্ড", "ফেরত", "ফেরত দিন", "টাকা ফেরত",
]

K_DUPLICATE_PAYMENT = [
    "twice", "two times", "charged twice", "double charged", "duplicate",
    "দুইবার", "ডাবল", "ডুপ্লিকেট",
]

K_MERCHANT_SETTLEMENT = [
    "merchant", "settlement", "shop", "store payment", "payment to shop",
    "merchant payment", "received by shop",
    "মার্চেন্ট", "দোকান", "স্টোর",
]

K_AGENT_CASH_IN = [
    # English phrases (broad, to catch variants)
    "cash in", "cash-in", "cash deposit", "deposited", "deposit through",
    "through agent", "agent did not", "agent didn't", "agent deposit",
    "agent e", "via agent", "agent theke", "agent kache",
    # Bangla / Banglish
    "এজেন্ট", "ক্যাশ ইন", "এজেন্ট ক্যাশ", "এজেন্ট দিয়ে", "এজেন্টের কাছে",
    "ক্যাশ", "জমা", "এজেন্টে",
]

# Cashback / offer fulfillment problems are a refund_request in the spec's spirit.
K_CASHBACK = [
    "cashback", "cash back", "cash-back",
    "did not get cashback", "didn't get cashback", "not received the cashback",
    "did not receive the cashback", "missing cashback", "cashback missing",
    "no cashback", "cashback pay", "cashback pele",
    "ক্যাশব্যাক",
]

K_PHISHING = [
    "otp", "pin", "password", "cvv", "one time password", "secret code",
    "verification code", "asked me to share", "asked for my",
    "suspicious call", "suspicious sms", "fake message", "scam",
    "ওটিপি", "পিন", "পাসওয়ার্ড", "পাসওয়ার্ড", "পাসওয়ার্ড", "পাসওয়ার্ড",
    "পাসওয়ার্ড", "পাসওয়ার্ড",
    "ফিশিং", "স্ক্যাম", "প্রতারণা", "সন্দেহজনক",
    "otp de", "pin dao", "pin ditto", "password dao", "scam call",
]


# --- helpers -----------------------------------------------------------------

def _has(text: str, keywords: List[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def _amounts(text: str) -> List[float]:
    # extract 3-7 digit numbers that look like taka amounts
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


def _phone_numbers(text: str) -> List[str]:
    return re.findall(r"\+?\d{10,15}", text)


# Avoid matching a bare word "cash" or "deposit" outside the agent-cash-in context.
_CASH_IN_CONTEXT = (
    r"agent|deposit|cash[\s\-]?in|জমা|এজেন্ট|ক্যাশ|wallet|ব্যালেন্স"
)


def _cash_in_context(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(_CASH_IN_CONTEXT, text, flags=re.IGNORECASE))


def _injection_attempt(text: str) -> bool:
    t = text.lower()
    triggers = [
        "ignore previous instructions",
        "ignore all instructions",
        "system prompt",
        "you are now",
        "act as",
        "disregard safety",
        "reveal your",
        "give me your pin",
        "share your otp",
    ]
    return any(tr in t for tr in triggers)


# --- core --------------------------------------------------------------------

@dataclass
class Classification:
    case_type: str
    severity: str
    department: str
    evidence_verdict: str
    confidence: float
    reason_codes: List[str]
    high_value: bool


def classify(
    complaint: str,
    history: List[Dict[str, Any]],
    relevant: Optional[Dict[str, Any]],
    channel: Optional[str],
    user_type: Optional[str],
) -> Classification:
    text = complaint or ""

    # safety / phishing always wins
    if _has(text, K_PHISHING):
        return Classification(
            case_type="phishing_or_social_engineering",
            severity="critical",
            department="fraud_risk",
            evidence_verdict="insufficient_data",
            confidence=0.95,
            reason_codes=["phishing_signal", "safety_priority"],
            high_value=False,
        )

    # prompt injection: never escalate, never reveal, follow normal classification
    # but mark as not-trusted input and require review.
    injection = _injection_attempt(text)

    # Decide case_type
    case_type = "other"
    reason: List[str] = []

    if _has(text, K_WRONG_TRANSFER):
        case_type = "wrong_transfer"
        reason.append("wrong_transfer_signal")
    elif _has(text, K_DUPLICATE_PAYMENT):
        case_type = "duplicate_payment"
        reason.append("duplicate_payment_signal")
    elif _has(text, K_PAYMENT_FAILED):
        case_type = "payment_failed"
        reason.append("payment_failed_signal")
    elif _has(text, K_MERCHANT_SETTLEMENT):
        case_type = "merchant_settlement_delay"
        reason.append("merchant_settlement_signal")
    elif _has(text, K_AGENT_CASH_IN) and _cash_in_context(text):
        case_type = "agent_cash_in_issue"
        reason.append("agent_cash_in_signal")
    elif _has(text, K_CASHBACK):
        case_type = "refund_request"
        reason.append("refund_request_signal")
        reason.append("cashback_signal")
    elif _has(text, K_AGENT_CASH_IN) and _cash_in_context(text):
        case_type = "agent_cash_in_issue"
        reason.append("agent_cash_in_signal")
    elif _has(text, K_REFUND_REQUEST):
        case_type = "refund_request"
        reason.append("refund_request_signal")

    # evidence verdict
    if not history:
        evidence = "insufficient_data"
        reason.append("empty_history")
    elif relevant is None:
        evidence = "insufficient_data"
        reason.append("no_history_match")
    else:
        evidence = "consistent"
        reason.append("history_match")

    # severity
    amount = None
    if relevant and isinstance(relevant.get("amount"), (int, float)):
        amount = float(relevant["amount"])
    elif _amounts(text):
        amount = max(_amounts(text))

    high_value = bool(amount and amount >= 5000)

    if case_type in ("wrong_transfer", "payment_failed"):
        severity = "high" if high_value or evidence == "inconsistent" else "medium"
    elif case_type == "phishing_or_social_engineering":
        severity = "critical"
    elif case_type == "duplicate_payment":
        # Spec expects medium for the canonical duplicate-payment case; only
        # escalate to high if the combined duplicate amount crosses the
        # high-value threshold (>= 5000).
        severity = "high" if high_value else "medium"
    elif case_type == "merchant_settlement_delay":
        severity = "medium" if not high_value else "high"
    elif case_type == "agent_cash_in_issue":
        severity = "medium"
    elif case_type == "refund_request":
        severity = "medium" if not high_value else "high"
    else:
        severity = "low"

    # department mapping (see Section 7.2)
    # Refund eligibility against campaign / policy is fundamentally a
    # dispute-resolution call, so we always route refund_request there
    # (not customer_support). This matches the spec's expected output.
    dept_map = {
        "wrong_transfer": "dispute_resolution",
        "refund_request": "dispute_resolution",
        "payment_failed": "payments_ops",
        "duplicate_payment": "payments_ops",
        "merchant_settlement_delay": "merchant_operations",
        "agent_cash_in_issue": "agent_operations",
        "phishing_or_social_engineering": "fraud_risk",
        "other": "customer_support",
    }
    department = dept_map[case_type]

    confidence = 0.9 if relevant else 0.6
    if injection:
        confidence = min(confidence, 0.5)
        reason.append("prompt_injection_signal")

    return Classification(
        case_type=case_type,
        severity=severity,
        department=department,
        evidence_verdict=evidence,
        confidence=confidence,
        reason_codes=reason,
        high_value=high_value,
    )
