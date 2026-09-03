import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Enum, Numeric
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base

class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, index=True)
    file_hash = Column(String, index=True) # SHA256 of file contents
    mime_type = Column(String)
    file_size = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    transfer_id = Column(String, index=True) # Razorpay Route transfer
    total_amount = Column(Numeric(10, 2)) # Expected total value (Decimal)
    ordered_quantity = Column(Integer)

    evidence = relationship("FulfillmentEvidence", back_populates="document", uselist=False)
    validation = relationship("SafetyValidation", back_populates="document", uselist=False)
    decision = relationship("SettlementDecision", back_populates="document", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="document", order_by="AuditLog.sequence_number")
    
    @property
    def policy_math(self):
        if not self.decision or not self.total_amount:
            return None
        rev_pct = (self.decision.proposed_reversal_amount / self.total_amount) * 100
        from app.schemas.document import PolicyConfig
        return {
            "reversal_percentage": float(rev_pct),
            "maximum_auto_reversal_percentage": PolicyConfig().maximum_auto_reversal_percentage
        }


class FulfillmentEvidence(Base):
    __tablename__ = "fulfillment_evidence"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"))
    
    provider = Column(String)
    model_identifier = Column(String)
    
    # Detailed extracted fields with confidence and bounding boxes
    extracted_fields = Column(JSON) 
    
    # Optional denormalized fields for simple querying
    accepted_quantity = Column(Integer, nullable=True)
    damaged_quantity = Column(Integer, nullable=True)
    rejected_quantity = Column(Integer, nullable=True)
    
    overall_confidence = Column(Numeric(5, 4))
    raw_vlm_output = Column(JSON)

    document = relationship("Document", back_populates="evidence")


class SafetyValidation(Base):
    __tablename__ = "safety_validations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"))
    passed = Column(Boolean)
    failure_reasons = Column(JSON)
    unaccounted_quantity = Column(Integer, default=0) # Derived value
    checked_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="validation")


class SettlementDecision(Base):
    __tablename__ = "settlement_decisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"))
    transfer_id = Column(String)
    approved_release_amount = Column(Numeric(10, 2))
    proposed_reversal_amount = Column(Numeric(10, 2))
    requires_human_review = Column(Boolean)
    policy_version = Column(String)
    idempotency_key = Column(String, unique=True) # Used to prevent duplicate processing
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="decision")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"))
    sequence_number = Column(Integer)
    event_type = Column(String)
    details = Column(JSON)
    previous_event_hash = Column(String, nullable=True)
    event_hash = Column(String) # Tamper-evident hash
    timestamp = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="audit_logs")

class RouteAction(Base):
    __tablename__ = "route_actions"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"))
    decision_id = Column(String, ForeignKey("settlement_decisions.id"))
    transfer_id = Column(String)
    action_type = Column(String) # REVERSAL or RELEASE
    state = Column(String) # PENDING, EXECUTING, SUCCEEDED, FAILED, RECONCILIATION_REQUIRED
    amount = Column(Numeric(10, 2))
    external_id = Column(String, nullable=True)
    provider_response = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
