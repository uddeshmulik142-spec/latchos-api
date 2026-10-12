import json
import os
import traceback
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional, List
from datetime import datetime

import httpx
import psycopg2
from google import genai
from google.genai import types
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to enable audit logging.")
    return psycopg2.connect(database_url)


def init_db():
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS gate_events (
                        id SERIAL PRIMARY KEY,
                        driver_name VARCHAR(255),
                        license_number VARCHAR(255),
                        compliance_status VARCHAR(50),
                        scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
    finally:
        conn.close()


def log_gate_event(result: "ComplianceVerificationResult"):
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO gate_events (driver_name, license_number, compliance_status) "
                    "VALUES (%s, %s, %s)",
                    (result.driver_full_name, result.licence_number, result.verdict.value)
                )
    except psycopg2.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database logging failed: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await run_in_threadpool(init_db)
    yield


app = FastAPI(
    title="LatchOS Compliance Intake API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for browser requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    try:
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

            await run_in_threadpool(log_gate_event, verification_result)

            await trigger_gate_barrier_action(verification_result, file.filename)
            return verification_result

        prompt = (
            "You are the gate compliance intake engine for LatchOS. "
            "Inspect UK transport and industrial credentials (UK Driver Licences, Driver Qualification Cards / CPC, "
            "Goods in Transit (GIT) certificates, and Operator Licences). "
            "Strict rules:\n"
            "1. Check all expiration dates against the current date (October 2026).\n"
            "2. If expired, set verdict to 'EXPIRED'.\n"
            "3. If blurry, incomplete, altered, or required coverage is missing, set to 'FLAGGED'.\n"
            "4. If valid, set to 'PASSED'.\n"
            "Extract the driver's license details and determine compliance. "
            "Follow the JSON schema strictly."
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=file.content_type),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ComplianceVerificationResult
            )
        )
        clean_json = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        verification_result = ComplianceVerificationResult.model_validate(json.loads(clean_json))

        await run_in_threadpool(log_gate_event, verification_result)

        await trigger_gate_barrier_action(verification_result, file.filename)
        return verification_result

    except Exception as exc:
        print("====== LATCHOS CRASH REPORT ======")
        traceback.print_exc()
        print("==================================")
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health():
    return {"status": "ok", "engine": "LatchOS Vision Core v1"}


@app.get("/api/v1/gate-events")
def get_gate_events():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, driver_name, license_number, compliance_status, scan_time "
            "FROM gate_events ORDER BY scan_time DESC LIMIT 50"
        )
        rows = cur.fetchall()

        events = [
            {
                "id": row[0],
                "driver_name": row[1],
                "license_number": row[2],
                "status": row[3],
                "timestamp": row[4].isoformat() if row[4] else None
            }
            for row in rows
        ]
        return {"events": events}
    except psycopg2.Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve gate events: {exc}") from exc
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()