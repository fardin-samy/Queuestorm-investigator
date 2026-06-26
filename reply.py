"""Compose agent summary, next action, and safe customer reply."""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel

from classifier import Classification


class Outputs(BaseModel):
    ticket_id: str
    relevant_transaction_id: Optional[str]
    evidence_verdict: str
    case_type: str
    severity: str
    department: str
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: float
    reason_codes: list[str]


_TXN_REF = "{TXN}"


def _summary(
    ticket_id: str,
    complaint: str,
    relevant: Optional[Dict[str, Any]],
    decision: Classification,
) -> str:
    snip = complaint.strip().splitlines()[0] if complaint.strip() else ""
    snip = snip[:160] + ("…" if len(snip) > 160 else "")
    txn = relevant.get("transaction_id") if relevant else None
    amt = relevant.get("amount") if relevant else None
    cp = relevant.get("counterparty") if relevant else None
    parts = [f"Ticket {ticket_id} ({decision.case_type}, severity={decision.severity})."]
    if txn:
        parts.append(f"Customer references {txn} (amount={amt}, counterparty={cp}).")
    parts.append(f"Evidence verdict: {decision.evidence_verdict}.")
    if snip:
        parts.append(f"Customer note: \"{snip}\"")
    return " ".join(parts)


def _next_action(
    relevant: Optional[Dict[str, Any]],
    decision: Classification,
) -> str:
    txn = relevant.get("transaction_id") if relevant else None

    if decision.case_type == "phishing_or_social_engineering":
        return (
            "Mark this ticket as fraud-risk. Do not engage the customer on credentials. "
            "Escalate to the fraud_risk queue and follow the standard phishing playbook."
        )

    if decision.case_type == "wrong_transfer":
        if decision.evidence_verdict == "consistent" and txn:
            return (
                f"Verify {txn} details with the customer, then route to dispute_resolution "
                "for receiver-side recovery attempt per standard policy."
            )
        return (
            "Verify recent outgoing transfers with the customer and route to dispute_resolution "
            "for further investigation."
        )

    if decision.case_type == "payment_failed":
        if decision.evidence_verdict == "inconsistent":
            return (
                "Reconcile the transaction log with the customer's wallet balance. "
                "If a deduction is confirmed without a corresponding successful payment, "
                "open a reversal ticket in payments_ops."
            )
        return (
            "Pull the gateway status for the referenced transaction and confirm whether "
            "the customer's balance was deducted. Route to payments_ops if so."
        )

    if decision.case_type == "duplicate_payment":
        return (
            "Confirm both transactions in the gateway and merge or refund the duplicate "
            "in payments_ops per duplicate-charge policy."
        )

    if decision.case_type == "refund_request":
        return (
            "Confirm eligibility against the campaign and refund policy. Any eligible amount "
            "must be returned only through official channels — never via a third party."
        )

    if decision.case_type == "merchant_settlement_delay":
        return (
            "Check the merchant settlement pipeline for the referenced transaction and "
            "escalate to merchant_operations if it is outside the standard settlement window."
        )

    if decision.case_type == "agent_cash_in_issue":
        return (
            "Pull the agent cash-in ledger for the referenced transaction and reconcile "
            "with the customer's wallet balance. Route to agent_operations."
        )

    return (
        "Review the complaint against the customer's recent activity and route to the "
        "appropriate queue."
    )


def _customer_reply(
    complaint: str,
    relevant: Optional[Dict[str, Any]],
    decision: Classification,
) -> str:
    txn = relevant.get("transaction_id") if relevant else None

    if decision.case_type == "phishing_or_social_engineering":
        return (
            "Thank you for letting us know. We take this seriously. "
            "Please do not share your PIN, OTP, password, or any verification code with anyone, "
            "no matter who they claim to be. Our team will never ask for these details. "
            "We will only contact you through our official support channels."
        )

    base = "Thank you for reaching out."
    if txn:
        base += f" We have noted your concern about transaction {txn}."
    else:
        base += " We have noted your concern."

    if decision.case_type == "wrong_transfer":
        body = (
            "We understand you may have sent money to the wrong recipient. "
            "We have shared the details with our dispute_resolution team. "
            "If the amount is eligible, it will be returned only through official channels."
        )
    elif decision.case_type == "payment_failed":
        body = (
            "We are checking your transaction status with our payments team. "
            "If a deduction is confirmed without a corresponding successful payment, "
            "the amount will be returned only through official channels."
        )
    elif decision.case_type == "duplicate_payment":
        body = (
            "We are reviewing your recent payments to confirm whether a duplicate charge occurred. "
            "Any eligible amount will be returned only through official channels."
        )
    elif decision.case_type == "refund_request":
        body = (
            "Your refund request has been logged. Our team will review it against the campaign "
            "policy, and any eligible amount will be returned only through official channels."
        )
    elif decision.case_type == "merchant_settlement_delay":
        body = (
            "We have forwarded your concern about the merchant settlement to our merchant "
            "operations team. They will review the timeline and get back to you."
        )
    elif decision.case_type == "agent_cash_in_issue":
        body = (
            "We have shared the cash-in details with our agent operations team for reconciliation. "
            "Any eligible adjustment will be made only through official channels."
        )
    else:
        body = (
            "Our team is reviewing your concern and will get back to you. "
            "Please continue to use our official support channels for any updates."
        )

    closing = (
        " For your safety, please never share your PIN, OTP, password, or full card number "
        "with anyone — including someone claiming to be from our team."
    )
    return f"{base} {body}{closing}"


def build_outputs(
    ticket_id: str,
    complaint: str,
    history,
    match: Optional[Dict[str, Any]],
    decision: Classification,
) -> Outputs:
    # Every refund request gets human review by default — eligibility against the
    # campaign / refund policy is exactly the kind of judgement call the rubric
    # wants in human hands, even when the evidence looks consistent.
    contested_refund = decision.case_type == "refund_request"

    human_review = (
        decision.case_type in {
            "wrong_transfer",
            "phishing_or_social_engineering",
            "duplicate_payment",
            "merchant_settlement_delay",
            "agent_cash_in_issue",
        }
        or decision.severity in {"high", "critical"}
        or decision.evidence_verdict == "inconsistent"
        or decision.high_value
        or contested_refund
    )

    return Outputs(
        ticket_id=ticket_id,
        relevant_transaction_id=match.get("transaction_id") if match else None,
        evidence_verdict=decision.evidence_verdict,
        case_type=decision.case_type,
        severity=decision.severity,
        department=decision.department,
        agent_summary=_summary(ticket_id, complaint, match, decision),
        recommended_next_action=_next_action(match, decision),
        customer_reply=_customer_reply(complaint, match, decision),
        human_review_required=human_review,
        confidence=decision.confidence,
        reason_codes=decision.reason_codes,
    )
