from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import MAX_FILE_SIZE_BYTES, SUPPORTED_MEDIA_TYPES
from app.database import execute_query
from app.dependencies import check_rate_limit, resolve_organization
from app.models import ComplianceVerificationResult, Organization
from app.services.gate import trigger_gate_barrier_action
from app.services.ocr import verify_document

router = APIRouter(prefix="/api/v1", tags=["credentials"])


@router.post(
    "/verify-credential",
    response_model=ComplianceVerificationResult,
    dependencies=[Depends(check_rate_limit)],
)
async def verify_credential(
    file: UploadFile = File(...),
    org: Organization = Depends(resolve_organization),
):
    if file.content_type not in SUPPORTED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {file.content_type}. Upload JPEG, PNG, WebP, or PDF.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    try:
        result = await verify_document(file_bytes, file.content_type)

        # Log to DB under the tenant's organization ID
        try:
            await execute_query(
                "INSERT INTO gate_events (org_id, driver_name, license_number, compliance_status) "
                "VALUES ($1, $2, $3, $4)",
                org.id,
                result.driver_full_name,
                result.licence_number,
                result.verdict.value,
            )
        except Exception as db_err:
            print(f"⚠️ Non-fatal audit log warning: {db_err}")

        # Trigger gate hardware/webhook
        await trigger_gate_barrier_action(result, file.filename or "unknown")

        return result

    except HTTPException:
        raise
    except Exception as exc:
        print(f"⚠️ Verification failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during credential verification.",
        ) from exc
