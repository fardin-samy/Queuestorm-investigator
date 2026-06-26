"""Output safety post-filter. Applied AFTER all generation, including any LLM."""
from __future__ import annotations

import re
from typing import List

from reply import Outputs


_FORBIDDEN_CREDENTIAL_PATTERNS = [
    r"\bpin\b",
    r"\botp\b",
    r"\bone[\s\-]?time[\s\-]?password\b",
    r"\bpassword\b",
    r"\bcvv\b",
    r"\bcard\s*number\b",
    r"\bverification\s*code\b",
    r"\bsecret\s*code\b",
]

_FORBIDDEN_CREDENTIAL_REPLIES = [
    r"share your (pin|otp|password|cvv|card number|verification code)",
    r"send (me|us) your (pin|otp|password|cvv|card number)",
    r"please (provide|give|tell) (me|us) your (pin|otp|password|cvv|card number)",
    r"verify your (pin|otp|password|cvv|card number)",
    r"confirm your (pin|otp|password|cvv|card number)",
    r"enter your (pin|otp|password|cvv|card number)",
    r"type your (pin|otp|password|cvv|card number)",
]

_FORBIDDEN_REFUND_PHRASES = [
    r"we will refund",
    r"we have refunded",
    r"we'll refund",
    r"your refund has been processed",
    r"refund has been initiated",
    r"reversal has been processed",
    r"we are refunding",
    r"money has been returned",
    r"account has been unblocked",
]

# Words that suggest a third-party contact instruction.
_THIRDPARTY_HINTS = [
    r"contact .* at .*phone",
    r"call .* at \+?\d",
    r"reach .* at \+?\d",
    r"meet .* at",
    r"go to .*agent",
    r"send (it|the money) to .*person",
]


def _scan(text: str, patterns: List[str]) -> List[str]:
    hits = []
    if not text:
        return hits
    lower = text.lower()
    for p in patterns:
        if re.search(p, lower, flags=re.IGNORECASE):
            hits.append(p)
    return hits


_ASK_VERBS = (
    r"please|kindly|kindly|verify|confirm|enter|provide|share|give|send|tell|"
    r"repeat|submit|type|input"
)
_CRED_WORDS = (
    r"pin|otp|one[\s\-]?time[\s\-]?password|password|cvv|card\s*number|"
    r"verification\s*code|secret\s*code"
)

# Imperative ask: "<verb> your <credential>" or "share/send ... <credential>"
_ASK_PATTERN = re.compile(
    r"\b(?:" + _ASK_VERBS + r")\b[^.?!]{0,60}?\b(?:" + _CRED_WORDS + r")\b[^.?!]*[.?!]",
    flags=re.IGNORECASE,
)

_SAFE_LINE = (
    "For your safety, please do not share your PIN, OTP, password, or "
    "full card number with anyone — including someone claiming to be from our team."
)

# Match any pre-existing "do not share / never share" safety sentence so we can
# collapse it before appending our canonical safety line.
_SAFETY_SENTENCE = re.compile(
    r"\s*For your safety,[^.]*?(?:do not share|never share)[^.]*?[.!?]",
    flags=re.IGNORECASE,
)


def _strip_safety_sentences(text: str) -> str:
    return _SAFETY_SENTENCE.sub("", text or "")


def _redact_credential_asks(text: str) -> tuple[str, int]:
    """Rewrite any imperative request for credentials. Returns (new_text, count)."""
    if not text:
        return text, 0
    new_text, n = _ASK_PATTERN.subn(
        "Please continue only through our official support channels.",
        text,
    )
    return new_text, n


def _redact_refund(text: str) -> tuple[str, int]:
    if not text:
        return text, 0
    n = 0
    new_text = text
    for p in _FORBIDDEN_REFUND_PHRASES:
        new_text, k = re.subn(
            p,
            "any eligible amount will be returned through official channels",
            new_text,
            flags=re.IGNORECASE,
        )
        n += k
    return new_text, n


def _thirdparty_prepend(text: str) -> tuple[str, int]:
    if not text:
        return text, 0
    hits = _scan(text, _THIRDPARTY_HINTS)
    if not hits:
        return text, 0
    new_text = (
        "Please continue to use our official support channels only — do not contact any "
        "third party for this issue. " + text
    )
    return new_text, len(hits)


def enforce_safety(out: Outputs) -> Outputs:
    """Apply safety rules from Section 8. Returns a new Outputs object."""
    reply = out.customer_reply or ""
    action = out.recommended_next_action or ""

    # 1) Strip any pre-existing safety sentences, redact credential asks.
    reply = _strip_safety_sentences(reply)
    reply, cred_hits = _redact_credential_asks(reply)

    # 2) Refund phrasing (before we add the safety line).
    reply, refund_hits = _redact_refund(reply)

    # 3) Third-party contact prepend.
    reply, thirdparty_hits = _thirdparty_prepend(reply)

    # 4) Append exactly one canonical safety line.
    reply = reply.rstrip()
    if reply and not reply.endswith((".", "!", "?")):
        reply += "."
    reply = f"{reply} {_SAFE_LINE}"

    # Internal next_action: also enforce refund phrasing.
    action, action_refund_hits = _redact_refund(action)

    violations = cred_hits + refund_hits + thirdparty_hits + action_refund_hits

    new_codes = list(out.reason_codes)
    if violations:
        new_codes.append(f"safety_redactions:{violations}")

    return Outputs(
        ticket_id=out.ticket_id,
        relevant_transaction_id=out.relevant_transaction_id,
        evidence_verdict=out.evidence_verdict,
        case_type=out.case_type,
        severity=out.severity,
        department=out.department,
        agent_summary=out.agent_summary,
        recommended_next_action=action,
        customer_reply=reply.strip(),
        human_review_required=out.human_review_required or violations > 0,
        confidence=out.confidence,
        reason_codes=new_codes,
    )
