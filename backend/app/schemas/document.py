from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from app.db.models import DocumentStatus

T = TypeVar('T')

class FieldEvidence(BaseModel, Generic[T]):
    value: T
    confidence: float
    evidence_region: Optional[Dict[str, float]] = None # Expected to have x, y, w, h
    evidence_note: Optional[str] = None
    warnings: List[str] = []

class DocumentUploadRequest(BaseModel):
    transfer_id: str
    total_amount: Decimal = Field(..., max_digits=10, decimal_places=2)
    ordered_quantity: int

class FulfillmentFields(BaseModel):
    accepted_quantity: Optional[FieldEvidence[int]] = None
    damaged_quantity: Optional[FieldEvidence[int]] = None
    rejected_quantity: Optional[FieldEvidence[int]] = None
    missing_or_unaccounted_quantity: Optional[FieldEvidence[int]] = None
    unknown_quantity: Optional[FieldEvidence[int]] = None
    signature_present: FieldEvidence[bool]
    correction_detected: FieldEvidence[bool]
    document_type: Optional[FieldEvidence[str]] = None
    suspicious_content_detected: Optional[FieldEvidence[bool]] = None

class FulfillmentEvidenceSchema(BaseModel):
    provider: str
    model_identifier: str
    extracted_fields: FulfillmentFields
    overall_confidence: float
    raw_vlm_output: Optional[Dict[str, Any]] = None

class SafetyValidationResult(BaseModel):
    passed: bool
    failure_reasons: List[str]
    unaccounted_quantity: int

class SettlementDecisionSchema(BaseModel):
    document_id: str
    decision_id: str
    transfer_id: str
    approved_release_amount: Decimal
    proposed_reversal_amount: Decimal
    requires_human_review: bool
    policy_version: str
    idempotency_key: str

class AuditLogSchema(BaseModel):
    sequence_number: int
    event_type: str
    details: Dict[str, Any]
    previous_event_hash: Optional[str] = None
    event_hash: str
    timestamp: datetime

class PolicyConfig(BaseModel):
    base_confidence_threshold: float = 0.85
    handwritten_correction_confidence_threshold: float = 0.95
    maximum_auto_reversal_percentage: float = 50.0
    maximum_auto_release_amount: Decimal = Decimal('1000000.00')
    signature_required: bool = True
    require_human_review_for_unaccounted_quantity: bool = True

from enum import Enum as PyEnum

class RouteActionState(str, PyEnum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

class RouteActionResult(BaseModel):
    action_id: str
    provider: str
    mode: str
    transfer_id: str
    action_type: str
    status: RouteActionState
    external_id: Optional[str] = None
    amount: Decimal
    currency: str = "INR"
    response_metadata: Dict[str, Any] = {}
    error: Optional[str] = None
    executed_at: datetime

class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_hash: str
    mime_type: str
    file_size: int
    uploaded_at: datetime
    status: DocumentStatus
    transfer_id: str
    total_amount: Decimal
    ordered_quantity: int

    evidence: Optional[FulfillmentEvidenceSchema] = None
    validation: Optional[SafetyValidationResult] = None
    decision: Optional[SettlementDecisionSchema] = None
    audit_logs: List[AuditLogSchema] = []
    policy_math: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# ── V2 schemas ─────────────────────────────────────────────────────────────────

class TransferRecord(BaseModel):
    """
    Server-side transfer metadata fetched from the transfer registry.
    The ordered_quantity and total_amount are authoritative system values —
    they are never accepted as user-supplied financial inputs.
    """
    transfer_id: str
    total_amount: Decimal
    ordered_quantity: int
    vendor_name: str
    item_description: str


class FieldAgreement(BaseModel):
    """Comparison result for a single extracted field between Pass 1 and Pass 2."""
    field: str
    pass1_value: Optional[Any] = None
    pass2_value: Optional[Any] = None
    pass1_confidence: float
    pass2_confidence: float
    agreed: bool
    delta: Optional[float] = None   # numeric absolute difference if applicable


class ComparisonResult(BaseModel):
    """
    Deterministic comparison of Pass 1 vs Pass 2 outputs.
    Produced by the comparator — no AI involvement.
    """
    all_fields_agreed: bool
    disagreements: List[FieldAgreement]
    agreements: List[FieldAgreement]
    max_numeric_delta: Optional[int] = None
    comparison_triggered_by: List[str] = []  # reason codes that triggered Pass 2


class ResolutionResult(BaseModel):
    """
    Final resolved values after comparing Pass 1 and Pass 2.

    IMPORTANT: Agreement between Pass 1 and Pass 2 does NOT prove extraction
    accuracy.  Both passes may hallucinate consistently (optimistic hallucination).
    The SafetyEngine arithmetic invariant remains the authoritative financial check.
    This is documented as an accepted prototype limitation.
    """
    resolved_accepted: Optional[int] = None
    resolved_damaged:  Optional[int] = None
    resolved_rejected: Optional[int] = None
    resolved_signature: Optional[bool] = None
    resolution_method: str   # "ai_consistent_and_grounded" | "human_review_disagreement" | "human_review_insufficient"
    requires_human_review: bool
    human_review_reason: Optional[str] = None


class VerificationResultSchema(BaseModel):
    """Serialised form of the VerificationResult DB row for API responses."""
    pass2_triggered: bool
    pass2_trigger_reasons: List[str]
    comparison_result: Optional[ComparisonResult] = None
    resolution_result: Optional[ResolutionResult] = None
    evidence_sufficient: Optional[bool] = None
    sufficiency_failures: List[str] = []

    class Config:
        from_attributes = True


class DocumentResponseV2(DocumentResponse):
    """
    Extended document response including V2 verification fields.
    Backward-compatible: all new fields are optional.
    """
    verification_result: Optional[VerificationResultSchema] = None

    class Config:
        from_attributes = True

class HumanReviewRequest(BaseModel):
    accepted_quantity: int
    damaged_quantity: int
    rejected_quantity: int

