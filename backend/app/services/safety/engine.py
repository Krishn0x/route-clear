import logging
import uuid
from decimal import Decimal
from typing import List, Tuple, Optional
from app.schemas.document import (
    FulfillmentEvidenceSchema, 
    PolicyConfig, 
    SafetyValidationResult, 
    SettlementDecisionSchema,
    FieldEvidence
)
from app.db.models import Document

logger = logging.getLogger(__name__)

class SafetyEngine:
    def __init__(self, policy: PolicyConfig):
        self.policy = policy

    def _get_val(self, field: Optional[FieldEvidence[int]], default: int = 0) -> int:
        return field.value if field and field.value is not None else default
        
    def _get_conf(self, field: Optional[FieldEvidence]) -> float:
        return field.confidence if field else 0.0

    def evaluate(
        self, 
        doc: Document, 
        evidence: FulfillmentEvidenceSchema
    ) -> Tuple[SafetyValidationResult, Optional[SettlementDecisionSchema]]:
        
        fields = evidence.extracted_fields
        failure_reasons: List[str] = []
        requires_human_review = False
        
        # 1. Extract values
        ordered = doc.ordered_quantity
        accepted = self._get_val(fields.accepted_quantity)
        damaged = self._get_val(fields.damaged_quantity)
        rejected = self._get_val(fields.rejected_quantity)
        
        # 2. Arithmetic & Unaccounted
        unaccounted = ordered - (accepted + damaged + rejected)
        
        if unaccounted != 0:
            msg = f"Unaccounted quantity detected: {unaccounted} (Ordered: {ordered}, A:{accepted}, D:{damaged}, R:{rejected})"
            if self.policy.require_human_review_for_unaccounted_quantity:
                requires_human_review = True
                failure_reasons.append(msg)
            else:
                logger.info(msg) # Log but don't fail if policy allows
                
        if accepted < 0 or damaged < 0 or rejected < 0:
            requires_human_review = True
            failure_reasons.append("Negative quantities detected.")
            
        if (accepted + damaged + rejected) > ordered:
            requires_human_review = True
            failure_reasons.append("Sum of accepted, damaged, and rejected exceeds ordered quantity.")

        # 3. Confidence Thresholds
        correction = fields.correction_detected
        has_correction = correction.value if correction else False
        
        threshold = (self.policy.handwritten_correction_confidence_threshold 
                     if has_correction else self.policy.base_confidence_threshold)
                     
        if evidence.overall_confidence < threshold:
            requires_human_review = True
            failure_reasons.append(f"Overall confidence {evidence.overall_confidence} below threshold {threshold}")
            
        # Check signature
        if self.policy.signature_required:
            sig = fields.signature_present
            if not sig or not sig.value:
                requires_human_review = True
                failure_reasons.append("Missing required signature.")
            elif sig.confidence < threshold:
                requires_human_review = True
                failure_reasons.append(f"Signature confidence {sig.confidence} below threshold {threshold}")

        passed = not requires_human_review
        
        validation_result = SafetyValidationResult(
            passed=passed,
            failure_reasons=failure_reasons,
            unaccounted_quantity=unaccounted
        )
        
        decision = None
        
        if passed:
            # 4. Financial Calculations
            unit_price = Decimal(doc.total_amount) / Decimal(doc.ordered_quantity)
            
            approved_release_amount = Decimal(accepted) * unit_price
            proposed_reversal_amount = Decimal(doc.total_amount) - approved_release_amount
            
            # Policy Financial Check
            reversal_percentage = (proposed_reversal_amount / Decimal(doc.total_amount)) * Decimal(100)
            if reversal_percentage > Decimal(self.policy.maximum_auto_reversal_percentage):
                requires_human_review = True
                validation_result.passed = False
                validation_result.failure_reasons.append(f"Reversal percentage {reversal_percentage:.2f}% exceeds auto maximum {self.policy.maximum_auto_reversal_percentage}%")
                
            if approved_release_amount > self.policy.maximum_auto_release_amount:
                requires_human_review = True
                validation_result.passed = False
                validation_result.failure_reasons.append(f"Release amount exceeds auto maximum {self.policy.maximum_auto_release_amount}")
            
            # Idempotency key (naive: transfer_id + "AUTO_SETTLEMENT")
            idemp_key = f"{doc.transfer_id}_AUTO_SETTLEMENT"
            
            if validation_result.passed:
                decision = SettlementDecisionSchema(
                    document_id=doc.id,
                    decision_id=str(uuid.uuid4()),
                    transfer_id=doc.transfer_id,
                    approved_release_amount=approved_release_amount,
                    proposed_reversal_amount=proposed_reversal_amount,
                    requires_human_review=False,
                    policy_version="1.0",
                    idempotency_key=idemp_key
                )
                
        if not validation_result.passed:
            # Default fallback decision requires human review
            decision = SettlementDecisionSchema(
                document_id=doc.id,
                decision_id=str(uuid.uuid4()),
                transfer_id=doc.transfer_id,
                approved_release_amount=Decimal(0),
                proposed_reversal_amount=Decimal(0),
                requires_human_review=True,
                policy_version="1.0",
                idempotency_key=f"{doc.transfer_id}_HUMAN_REVIEW"
            )

        return validation_result, decision
