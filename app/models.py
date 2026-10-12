from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    driver_last_name: Optional[str] = Field(None, description="Surname of driver (required for checksum)")
    licence_number: Optional[str] = Field(None, description="UK driving licence number or CPC badge number")
    cpc_expiry_date: Optional[str] = Field(None, description="YYYY-MM-DD format if present")
    operator_licence_valid: Optional[bool] = Field(None, description="Whether operator licence status is valid")
    git_coverage_limit: Optional[str] = Field(None, description="Goods in Transit or Public Liability policy limit (e.g. £50,000)")
    policy_expiry_date: Optional[str] = Field(None, description="Insurance/accreditation expiration date in YYYY-MM-DD")
    verdict: ComplianceStatus = Field(description="PASSED if active, EXPIRED if past validity, FLAGGED if blurred/altered/suspicious")
    verdict_reasons: list[str] = Field(default_factory=list, description="Reasoning behind verdict")


class GateEvent(BaseModel):
    id: int
    driver_name: Optional[str]
    licence_number: Optional[str]
    status: str
    timestamp: Optional[str]
