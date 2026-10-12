import json
from datetime import datetime, timezone

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL, MOCK_OCR
from app.models import (
    ComplianceStatus,
    ComplianceVerificationResult,
    DocumentType,
)
from app.services.validation import validate_uk_licence_checksum

_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def get_compliance_prompt() -> str:
    """Generate dynamic compliance prompt with the real current month and year."""
    current_date_str = datetime.now(timezone.utc).strftime("%B %Y")
    return (
        "You are the gate compliance intake engine for LatchOS. "
        "Inspect UK transport and industrial credentials (UK Driver Licences, Driver Qualification Cards / CPC, "
        "Goods in Transit (GIT) certificates, and Operator Licences). "
        "Strict rules:\n"
        f"1. Check all expiration dates against the current date ({current_date_str}).\n"
        "2. If expired, set verdict to 'EXPIRED'.\n"
        "3. If blurry, incomplete, altered, or required coverage is missing, set to 'FLAGGED'.\n"
        "4. Extract the driver's full name, AND extract just their surname into the 'driver_last_name' field.\n"
        "5. If valid, set to 'PASSED'.\n"
        "Extract the details and determine compliance. Follow the JSON schema strictly."
    )


MOCK_RESULT = ComplianceVerificationResult(
    document_type=DocumentType.UK_DRIVING_LICENCE,
    driver_full_name="JOHN SMITH",
    driver_last_name="SMITH",
    licence_number="SMITH705234JD9IJ",
    cpc_expiry_date="2028-09-15",
    operator_licence_valid=True,
    git_coverage_limit="£50,000",
    policy_expiry_date="2027-11-01",
    verdict=ComplianceStatus.PASSED,
    verdict_reasons=["Valid Category C+E entitlement", "CPC active until 2028"],
)


async def verify_document(file_bytes: bytes, mime_type: str) -> ComplianceVerificationResult:
    """Run OCR + compliance analysis on an uploaded document."""
    if MOCK_OCR:
        return MOCK_RESULT.model_copy()

    if _client is None:
        raise RuntimeError("GEMINI_API_KEY is not set — cannot run live OCR.")

    prompt = get_compliance_prompt()

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ComplianceVerificationResult,
        ),
    )
    clean_json = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    result = ComplianceVerificationResult.model_validate(json.loads(clean_json))

    # Apply UK licence checksum validation
    if result.document_type == DocumentType.UK_DRIVING_LICENCE:
        if result.licence_number and result.driver_last_name:
            if not validate_uk_licence_checksum(result.licence_number, result.driver_last_name):
                result.verdict = ComplianceStatus.FLAGGED
                result.verdict_reasons.append(
                    "SYSTEM FLAG: Licence number checksum failed. Potential forgery."
                )
        else:
            result.verdict = ComplianceStatus.FLAGGED
            result.verdict_reasons.append(
                "SYSTEM FLAG: Missing data for cryptographic checksum."
            )

    return result
