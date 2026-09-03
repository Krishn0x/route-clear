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

