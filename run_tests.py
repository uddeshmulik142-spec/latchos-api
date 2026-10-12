"""Simple runner for the test suite without requiring pytest binary."""

import asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import ComplianceStatus, ComplianceVerificationResult, DocumentType, GateEvent
from app.services.validation import validate_uk_licence_checksum


def test_validation():
    print("\n--- Running Validation Tests ---")
    assert validate_uk_licence_checksum("SMITH705234JD9IJ", "SMITH") is True
    assert validate_uk_licence_checksum("JONES756234JD9IJ", "JONES") is True
    assert validate_uk_licence_checksum("LEE99705234JD9IJ", "LEE") is True
    assert validate_uk_licence_checksum("SMITH705234JD9IJ", "BROWN") is False
    assert validate_uk_licence_checksum("SMITH713234JD9IJ", "SMITH") is False
    assert validate_uk_licence_checksum("SMITH705", "SMITH") is False
    assert validate_uk_licence_checksum("", "") is False
    print(" 7 validation tests PASSED")


def test_models():
    print("\n--- Running Model Tests ---")
    res = ComplianceVerificationResult(
        document_type=DocumentType.UK_DRIVING_LICENCE,
        verdict=ComplianceStatus.PASSED,
    )
    assert res.verdict == ComplianceStatus.PASSED
    assert res.document_type == DocumentType.UK_DRIVING_LICENCE
    assert res.verdict_reasons == []

    event = GateEvent(
        id=1,
        driver_name="Jane Doe",
        licence_number="DOE99756234JD9IJ",
        status="PASSED",
        timestamp="2026-10-12T00:00:00Z",
    )
    assert event.id == 1
    print(" 2 model tests PASSED")


async def test_endpoints():
    print("\n--- Running Endpoint Tests ---")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Health
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        print(" /health returns 200")

        # 2. Mock credential upload
        files = {"file": ("test.png", b"fake-bytes", "image/png")}
        res = await client.post("/api/v1/verify-credential", files=files)
        assert res.status_code == 200
        assert res.json()["verdict"] == "PASSED"
        print(" /api/v1/verify-credential returns 200 with PASSED")

        # 3. Reject invalid mime
        files = {"file": ("test.txt", b"text", "text/plain")}
        res = await client.post("/api/v1/verify-credential", files=files)
        assert res.status_code == 400
        print(" /api/v1/verify-credential rejects text/plain with 400")

        # 4. Reject oversized payload (>20MB)
        huge_bytes = b"0" * (21 * 1024 * 1024)
        files = {"file": ("huge.png", huge_bytes, "image/png")}
        res = await client.post("/api/v1/verify-credential", files=files)
        assert res.status_code == 400
        print(" /api/v1/verify-credential rejects files > 20MB with 400")


def main():
    test_validation()
    test_models()
    asyncio.run(test_endpoints())
    print("\n ALL TESTS PASSED SUCCESSFULLY! ")


if __name__ == "__main__":
    main()
