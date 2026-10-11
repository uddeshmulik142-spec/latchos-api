import base64
import os
from enum import Enum
from typing import Optional, List
from datetime import datetime

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from anthropic import Anthropic

app = FastAPI(title="LatchOS Compliance Intake API", version="1.0.0")

# Enable CORS for browser requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Anthropic()

# --- Schema Definitions ---

class ComplianceStatus(str, Enum):
    PASSED = "PASSED"
    FLAGGED = "FLAGGED"
    EXPIRED = "EXPIRED"

class DocumentType(str, Enum):
    UK_DRIVING_LICENCE = "UK_DRIVING_LICENCE"
    CPC_CARD = "CPC_CARD"
    INSURANCE_GIT = "INSURANCE_GIT"
    OPERATOR_LICENCE = "OPERATOR_LICENCE"
    UNKNOWN = "UNKNOWN"

class ComplianceVerificationResult(BaseModel):
    document_type: DocumentType = Field(description="Detected document classification")
    driver_full_name: Optional[str] = Field(None, description="Full name of driver or policy holder")
    licence_number: Optional[str] = Field(None, description="UK driving licence number or CPC badge number")
    cpc_expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD format if present")
    operator_licence_valid: Optional[bool] = Field(None, description="Whether operator licence status is valid")
    git_coverage_limit: Optional[str] = Field(None, description="Goods in Transit or Public Liability policy limit (e.g. £50,000)")
    policy_expiry_date: Optional[str] = Field(None, description="Insurance/accreditation expiration date in YYYY-MM-DD")
    verdict: ComplianceStatus = Field(description="PASSED if active, EXPIRED if past validity, FLAGGED if blurred/altered/suspicious")
    verdict_reasons: List[str] = Field(default_factory=list, description="Reasoning behind verdict")

# --- Gate Dispatch Configuration ---

DISPATCH_WEBHOOK_URL = None  # Replace with a real depot webhook, Slack/Teams incoming webhook, or hardware endpoint

async def trigger_gate_barrier_action(result: ComplianceVerificationResult, filename: str):
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    event_payload = {
        "event": "GATE_ACCESS_EVALUATION",
        "timestamp": timestamp,
        "filename": filename,
        "document_type": result.document_type,
        "driver_name": result.driver_full_name,
        "licence_no": result.licence_number,
        "verdict": result.verdict,
        "gate_action": "OPEN_BARRIER" if result.verdict == ComplianceStatus.PASSED else "HOLD_GATE_INSPECT",
        "notes": result.verdict_reasons
    }
    
    # Terminal Log for Live Depot Monitoring
    if result.verdict == ComplianceStatus.PASSED:
        print(f"\n🟢 [GATE DISPATCH - ACCESS GRANTED] Barrier Relay Triggered: OPEN -> Driver: {result.driver_full_name}")
    elif result.verdict == ComplianceStatus.EXPIRED:
        print(f"\n🔴 [GATE DISPATCH - DENIED] Barrier Relay: LOCKED -> Reason: Document Expired")
    else:
        print(f"\n🟡 [GATE DISPATCH - MANUAL REVIEW] Barrier Relay: LOCKED -> Reason: Visual Flag / Incomplete")

    # If an external webhook (e.g. Slack, depot TMS, IoT controller) is configured, POST to it
    if DISPATCH_WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client_http:
                await client_http.post(DISPATCH_WEBHOOK_URL, json=event_payload)
        except Exception as exc:
            print(f"⚠️ Failed to deliver gate webhook: {exc}")

    return event_payload

# --- Claude Extraction Engine ---

EXTRACT_TOOL_NAME = "record_compliance_data"

COMPLIANCE_TOOL = {
    "name": EXTRACT_TOOL_NAME,
    "description": "Extract parsed gate credentials and emit strict compliance verdict.",
    "input_schema": ComplianceVerificationResult.model_json_schema()
}

SUPPORTED_MEDIA_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "application/pdf": "application/pdf"
}

@app.post("/api/v1/verify-credential", response_model=ComplianceVerificationResult)
async def verify_credential(file: UploadFile = File(...)):
    if file.content_type not in SUPPORTED_MEDIA_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {file.content_type}. Upload JPEG, PNG, WebP, or PDF."
        )

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 20MB limit.")

    b64_data = base64.standard_b64encode(file_bytes).decode("utf-8")

    # Temporary Mock mode (used while waiting on live API credits)
    if os.getenv("MOCK_OCR", "true").lower() == "true":
        verification_result = ComplianceVerificationResult(
            document_type=DocumentType.UK_DRIVING_LICENCE,
            driver_full_name="JOHN SMITH",
            licence_number="SMITH705234JD9IJ",
            cpc_expiry_date="2028-09-15",
            operator_licence_valid=True,
            git_coverage_limit="£50,000",
            policy_expiry_date="2027-11-01",
            verdict=ComplianceStatus.PASSED,
            verdict_reasons=["Valid Category C+E entitlement", "CPC active until 2028"]
        )
        
        # Trigger gate dispatch action
        await trigger_gate_barrier_action(verification_result, file.filename)
        return verification_result

    # Process Document vs Image blocks for Claude
    if file.content_type == "application/pdf":
        media_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64_data
            }
        }
    else:
        media_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": file.content_type,
                "data": b64_data
            }
        }

    system_prompt = (
        "You are the gate compliance intake engine for LatchOS. "
        "Inspect UK transport and industrial credentials (UK Driver Licences, Driver Qualification Cards / CPC, "
        "Goods in Transit (GIT) certificates, and Operator Licences). "
        "Strict rules:\n"
        "1. Check all expiration dates against the current date (October 2026).\n"
        "2. If expired, set verdict to 'EXPIRED'.\n"
        "3. If blurry, incomplete, altered, or required coverage is missing, set to 'FLAGGED'.\n"
        "4. If valid, set to 'PASSED'.\n"
        "You must invoke the 'record_compliance_data' tool with the exact extracted parameters."
    )

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=system_prompt,
            tools=[COMPLIANCE_TOOL],
            tool_choice={"type": "tool", "name": EXTRACT_TOOL_NAME},
            messages=[
                {
                    "role": "user",
                    "content": [
                        media_block,
                        {
                            "type": "text",
                            "text": "Parse this transport gate document and return the structured compliance record."
                        }
                    ]
                }
            ]
        )

        tool_call = next(
            (block for block in response.content if block.type == "tool_use" and block.name == EXTRACT_TOOL_NAME),
            None
        )

        if not tool_call:
            raise HTTPException(status_code=502, detail="Failed to receive structured tool response from Claude.")

        verification_result = ComplianceVerificationResult(**tool_call.input)

        # Trigger gate dispatch action
        await trigger_gate_barrier_action(verification_result, file.filename)

        return verification_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "engine": "LatchOS Vision Core v1"}