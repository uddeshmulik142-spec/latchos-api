from app.models import (
    ComplianceStatus,
    ComplianceVerificationResult,
    DocumentType,
)


def test_result_model_defaults():
    res = ComplianceVerificationResult(
        document_type=DocumentType.UK_DRIVING_LICENCE,
        verdict=ComplianceStatus.PASSED,
    )
    assert res.verdict == ComplianceStatus.PASSED
    assert res.document_type == DocumentType.UK_DRIVING_LICENCE
    assert res.verdict_reasons == []
    assert res.driver_full_name is None


def test_result_model_full():
    res = ComplianceVerificationResult(
        document_type=DocumentType.CPC_CARD,
        driver_full_name="JANE DOE",
        driver_last_name="DOE",
        licence_number="DOE99756234JD9IJ",
        cpc_expiry_date="2028-09-15",
        verdict=ComplianceStatus.PASSED,
        verdict_reasons=["Active CPC"],
    )
    assert res.driver_full_name == "JANE DOE"
    assert len(res.verdict_reasons) == 1
