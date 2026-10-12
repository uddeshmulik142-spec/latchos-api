from datetime import datetime, timezone

import httpx

from app.config import DISPATCH_WEBHOOK_URL
from app.models import ComplianceStatus, ComplianceVerificationResult


async def trigger_gate_barrier_action(
    result: ComplianceVerificationResult, filename: str
) -> dict:
    """Log the gate decision and dispatch to an external webhook if configured."""
    timestamp = datetime.now(timezone.utc).isoformat()

    event_payload = {
        "event": "GATE_ACCESS_EVALUATION",
        "timestamp": timestamp,
        "filename": filename,
        "document_type": result.document_type.value,
        "driver_name": result.driver_full_name,
        "licence_no": result.licence_number,
        "verdict": result.verdict.value,
        "gate_action": "OPEN_BARRIER" if result.verdict == ComplianceStatus.PASSED else "HOLD_GATE_INSPECT",
        "notes": result.verdict_reasons,
    }

    # Terminal log for live depot monitoring
    if result.verdict == ComplianceStatus.PASSED:
        print(f"\n🟢 [GATE DISPATCH - ACCESS GRANTED] Barrier Relay: OPEN -> Driver: {result.driver_full_name}")
    elif result.verdict == ComplianceStatus.EXPIRED:
        print(f"\n🔴 [GATE DISPATCH - DENIED] Barrier Relay: LOCKED -> Reason: Document Expired")
    else:
        print(f"\n🟡 [GATE DISPATCH - MANUAL REVIEW] Barrier Relay: LOCKED -> Reason: Visual Flag / Incomplete")

    if DISPATCH_WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(DISPATCH_WEBHOOK_URL, json=event_payload)
        except Exception as exc:
            print(f"⚠️ Failed to deliver gate webhook: {exc}")

    return event_payload
