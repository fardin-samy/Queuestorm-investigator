"""QueueStorm Investigator — AI/API SupportOps copilot.

Exposes:
    GET  /health
    POST /analyze-ticket
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from classifier import classify
from matcher import find_relevant_transaction
from reply import build_outputs
from safety import enforce_safety

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("queuestorm")


class Transaction(BaseModel):
    transaction_id: str
    timestamp: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    counterparty: Optional[str] = None
    status: Optional[str] = None


class AnalyzeRequest(BaseModel):
    ticket_id: str
    complaint: str
    language: Optional[str] = None
    channel: Optional[str] = None
    user_type: Optional[str] = None
    campaign_context: Optional[str] = None
    transaction_history: list[Transaction] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


app = FastAPI(title="QueueStorm Investigator", version="1.0.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze-ticket")
async def analyze_ticket(req: Request) -> JSONResponse:
    raw: Any
    try:
        raw = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    if not isinstance(raw, dict):
        return JSONResponse(status_code=400, content={"error": "body_must_be_object"})

    try:
        parsed = AnalyzeRequest(**raw)
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "schema_violation", "detail": str(exc)},
        )

    if not parsed.complaint or not parsed.complaint.strip():
        return JSONResponse(
            status_code=422,
            content={"error": "empty_complaint", "ticket_id": parsed.ticket_id},
        )

    history = [tx.model_dump() for tx in parsed.transaction_history]
    match = find_relevant_transaction(parsed.complaint, history)
    decision = classify(
        complaint=parsed.complaint,
        history=history,
        relevant=match,
        channel=parsed.channel,
        user_type=parsed.user_type,
    )
    outputs = build_outputs(
        ticket_id=parsed.ticket_id,
        complaint=parsed.complaint,
        history=history,
        match=match,
        decision=decision,
    )
    outputs = enforce_safety(outputs)

    return JSONResponse(status_code=200, content=outputs.model_dump())


@app.exception_handler(Exception)
def _on_unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An unexpected error occurred."},
    )
