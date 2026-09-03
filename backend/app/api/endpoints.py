from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Document, DocumentStatus, AuditLog
from app.schemas.document import DocumentResponse
from app.core.config import settings
from decimal import Decimal
import shutil
import os
import uuid
import hashlib
from datetime import datetime
import json

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def generate_audit_hash(event_type: str, details: dict, prev_hash: str = None) -> str:
    content = f"{event_type}|{json.dumps(details, sort_keys=True)}|{prev_hash}"
    return hashlib.sha256(content.encode()).hexdigest()

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    transfer_id: str = Form(...),
    total_amount: Decimal = Form(...),
    ordered_quantity: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_content = await file.read()
    
    if ordered_quantity <= 0:
        raise HTTPException(status_code=400, detail="ordered_quantity must be a positive integer")
        
    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="total_amount must be positive")
    
    if len(file_content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES} bytes")
    
    # Robust MIME type checking
    import filetype
    kind = filetype.guess(file_content)
    if kind is None or kind.mime not in ['image/jpeg', 'image/png', 'application/pdf']:
        raise HTTPException(status_code=400, detail="Invalid file type. Supported types: JPEG, PNG, PDF")

    file_hash = hashlib.sha256(file_content).hexdigest()
    file_size = len(file_content)

    doc_id = str(uuid.uuid4())
    ext = kind.extension
    safe_filename = f"{doc_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file_content)

    new_doc = Document(
        id=doc_id,
        filename=safe_filename,
        file_hash=file_hash,
        mime_type=file.content_type,
        file_size=file_size,
        transfer_id=transfer_id,
        total_amount=total_amount,
        ordered_quantity=ordered_quantity,
        status=DocumentStatus.PENDING
    )
    db.add(new_doc)
    db.flush()

    event_details = {"filename": safe_filename, "hash": file_hash, "transfer_id": transfer_id}
    event_hash = generate_audit_hash("DOCUMENT_UPLOADED", event_details)
    audit = AuditLog(
        document_id=doc_id,
        sequence_number=1,
        event_type="DOCUMENT_UPLOADED",
        details=event_details,
        event_hash=event_hash
    )
    db.add(audit)

    db.commit()
    db.refresh(new_doc)
    return new_doc

@router.get("/", response_model=list[DocumentResponse])
async def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).all()

@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/{doc_id}/image")
def get_document_image(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image file not found")
        
    return FileResponse(file_path, media_type=doc.mime_type)

@router.post("/{doc_id}/process", response_model=DocumentResponse)
async def process_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.status != DocumentStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Document already processed (status: {doc.status})")

    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original file missing")
        
    with open(file_path, "rb") as f:
        image_bytes = f.read()

    # 1. VLM Extraction
    from app.services.vlm import get_vlm_provider
    from app.services.vlm.gemini import VLMException
    vlm = get_vlm_provider()
    
    try:
        evidence_schema = await vlm.extract_fulfillment_evidence(
            image_bytes=image_bytes,
            mime_type=doc.mime_type,
            ordered_quantity=doc.ordered_quantity
        )
        
        # Save Extraction Results
        from app.db.models import FulfillmentEvidence
        evidence_record = FulfillmentEvidence(
            document_id=doc.id,
            provider=evidence_schema.provider,
            model_identifier=evidence_schema.model_identifier,
            extracted_fields=evidence_schema.extracted_fields.model_dump(mode='json'),
            overall_confidence=evidence_schema.overall_confidence,
            raw_vlm_output=evidence_schema.raw_vlm_output
        )
        db.add(evidence_record)
        
        doc.status = DocumentStatus.PROCESSED
        event_type = "VLM_EXTRACTION_COMPLETED"
        event_details = {"overall_confidence": evidence_schema.overall_confidence, "provider": evidence_schema.provider}
    except VLMException as e:
        doc.status = DocumentStatus.FAILED
        event_type = "VLM_EXTRACTION_FAILED"
        event_details = {"error": str(e)}
    
    # Log Audit Event for VLM
    last_audit = db.query(AuditLog).filter(AuditLog.document_id == doc.id).order_by(AuditLog.sequence_number.desc()).first()
    prev_hash = last_audit.event_hash if last_audit else None
    seq_num = (last_audit.sequence_number + 1) if last_audit else 1
    
    event_hash = generate_audit_hash(event_type, event_details, prev_hash)
    audit = AuditLog(
        document_id=doc.id,
        sequence_number=seq_num,
        event_type=event_type,
        details=event_details,
        previous_event_hash=prev_hash,
        event_hash=event_hash
    )
    db.add(audit)
    
    db.commit()
    
    if doc.status == DocumentStatus.FAILED:
        db.refresh(doc)
        return doc
        
    # 2. Safety Validation Engine
    from app.services.safety.engine import SafetyEngine
    from app.schemas.document import PolicyConfig
    from app.db.models import SafetyValidation, SettlementDecision
    
    policy = PolicyConfig() # using defaults
    engine = SafetyEngine(policy)
    
    validation_result, decision_result = engine.evaluate(doc, evidence_schema)
    
    # Save Validation
    safety_record = SafetyValidation(
        document_id=doc.id,
        passed=validation_result.passed,
        failure_reasons=validation_result.failure_reasons,
        unaccounted_quantity=validation_result.unaccounted_quantity
    )
    db.add(safety_record)
    
    # Save Decision
    decision_record = SettlementDecision(
        id=decision_result.decision_id,
        document_id=decision_result.document_id,
        transfer_id=decision_result.transfer_id,
        approved_release_amount=decision_result.approved_release_amount,
        proposed_reversal_amount=decision_result.proposed_reversal_amount,
        requires_human_review=decision_result.requires_human_review,
        policy_version=decision_result.policy_version,
        idempotency_key=decision_result.idempotency_key
    )
    db.add(decision_record)
    
    # Update Document Status based on Engine
    doc.status = DocumentStatus.HUMAN_REVIEW if decision_result.requires_human_review else DocumentStatus.PROCESSED
    
    # Log Audit Event for Safety
    safety_event_details = {
        "passed": validation_result.passed,
        "failure_reasons": validation_result.failure_reasons,
        "requires_human_review": decision_result.requires_human_review,
        "approved_release_amount": float(decision_result.approved_release_amount),
        "proposed_reversal_amount": float(decision_result.proposed_reversal_amount)
    }
    
    prev_hash = event_hash
    seq_num += 1
    safety_hash = generate_audit_hash("SAFETY_VALIDATION_COMPLETED", safety_event_details, prev_hash)
    safety_audit = AuditLog(
        document_id=doc.id,
        sequence_number=seq_num,
        event_type="SAFETY_VALIDATION_COMPLETED",
        details=safety_event_details,
        previous_event_hash=prev_hash,
        event_hash=safety_hash
    )
    db.add(safety_audit)
    
    # Execute Route Action if auto-approved
    if not decision_result.requires_human_review:
        from app.services.route import get_route_adapter
        from app.schemas.document import RouteActionState
        adapter = get_route_adapter()
        route_results = await adapter.execute_settlement(db, decision_result)
        
        # Analyze results to see if overall succeeded
        all_succeeded = all(r.status == RouteActionState.SUCCEEDED for r in route_results)
        any_recon = any(r.status == RouteActionState.RECONCILIATION_REQUIRED for r in route_results)

        
        route_event_details = {
            "results": [r.model_dump(mode='json') for r in route_results]
        }
        
        if all_succeeded:
            doc.status = DocumentStatus.COMPLETED
            route_event_type = "ROUTE_ACTION_COMPLETED"
        elif any_recon:
            doc.status = DocumentStatus.FAILED # requires recon
            route_event_type = "ROUTE_ACTION_RECONCILIATION_REQUIRED"
        else:
            doc.status = DocumentStatus.FAILED
            route_event_type = "ROUTE_ACTION_FAILED"
            
        prev_hash = safety_hash
        seq_num += 1
        route_hash = generate_audit_hash(route_event_type, route_event_details, prev_hash)
        route_audit = AuditLog(
            document_id=doc.id,
            sequence_number=seq_num,
            event_type=route_event_type,
            details=route_event_details,
            previous_event_hash=prev_hash,
            event_hash=route_hash
        )
        db.add(route_audit)
    
    db.commit()
    db.refresh(doc)
    
    return doc

@router.post("/{doc_id}/human-review")
async def submit_human_review(
    doc_id: str, 
    approved_release_amount: Decimal, 
    proposed_reversal_amount: Decimal, 
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if doc.status != DocumentStatus.HUMAN_REVIEW:
        raise HTTPException(status_code=400, detail="Document is not pending human review")
    
    # Financial invariants
    if approved_release_amount + proposed_reversal_amount > doc.total_amount:
        raise HTTPException(status_code=400, detail="Amounts exceed total order amount")
    if approved_release_amount < 0 or proposed_reversal_amount < 0:
        raise HTTPException(status_code=400, detail="Amounts cannot be negative")

    # Check Idempotency
    from app.db.models import SettlementDecision
    from sqlalchemy.exc import IntegrityError
    
    idemp_key = f"{doc.transfer_id}_HUMAN_REVIEW_DECISION"
    existing_decision = db.query(SettlementDecision).filter(SettlementDecision.idempotency_key == idemp_key).first()
    if existing_decision:
        return {"message": "Decision already processed for this transfer (idempotent)."}
        
    decision = SettlementDecision(
        document_id=doc.id,
        transfer_id=doc.transfer_id,
        approved_release_amount=approved_release_amount,
        proposed_reversal_amount=proposed_reversal_amount,
        requires_human_review=False,
        policy_version="1.0-manual",
        idempotency_key=idemp_key
    )
    db.add(decision)
    
    doc.status = DocumentStatus.COMPLETED
    
    # Audit log
    last_audit = db.query(AuditLog).filter(AuditLog.document_id == doc.id).order_by(AuditLog.sequence_number.desc()).first()
    prev_hash = last_audit.event_hash if last_audit else None
    seq_num = (last_audit.sequence_number + 1) if last_audit else 1
    
    event_details = {
        "approved_release_amount": float(approved_release_amount),
        "proposed_reversal_amount": float(proposed_reversal_amount)
    }
    
    event_hash = generate_audit_hash("HUMAN_REVIEW_COMPLETED", event_details, prev_hash)
    audit = AuditLog(
        document_id=doc.id,
        sequence_number=seq_num,
        event_type="HUMAN_REVIEW_COMPLETED",
        details=event_details,
        previous_event_hash=prev_hash,
        event_hash=event_hash
    )
    db.add(audit)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"message": "Concurrent duplicate request rejected (idempotency key collision)."}
        
    # Execute Route Action
    from app.services.route import get_route_adapter
    from app.schemas.document import SettlementDecisionSchema, RouteActionState
    adapter = get_route_adapter()
    
    # We must construct a schema to pass to adapter
    decision_schema = SettlementDecisionSchema(
        document_id=decision.document_id,
        decision_id=decision.id,
        transfer_id=decision.transfer_id,
        approved_release_amount=decision.approved_release_amount,
        proposed_reversal_amount=decision.proposed_reversal_amount,
        requires_human_review=decision.requires_human_review,
        policy_version=decision.policy_version,
        idempotency_key=decision.idempotency_key
    )
    
    route_results = await adapter.execute_settlement(db, decision_schema)
    
    all_succeeded = all(r.status == RouteActionState.SUCCEEDED for r in route_results)
    any_recon = any(r.status == RouteActionState.RECONCILIATION_REQUIRED for r in route_results)
    
    route_event_details = {
        "results": [r.model_dump(mode='json') for r in route_results]
    }
    
    if all_succeeded:
        doc.status = DocumentStatus.COMPLETED
        route_event_type = "ROUTE_ACTION_COMPLETED"
    elif any_recon:
        doc.status = DocumentStatus.FAILED
        route_event_type = "ROUTE_ACTION_RECONCILIATION_REQUIRED"
    else:
        doc.status = DocumentStatus.FAILED
        route_event_type = "ROUTE_ACTION_FAILED"
        
    seq_num += 1
    route_hash = generate_audit_hash(route_event_type, route_event_details, event_hash)
    route_audit = AuditLog(
        document_id=doc.id,
        sequence_number=seq_num,
        event_type=route_event_type,
        details=route_event_details,
        previous_event_hash=event_hash,
        event_hash=route_hash
    )
    db.add(route_audit)
    db.commit()
        
    return {"message": f"Human review submitted securely. Route Action {'Succeeded' if all_succeeded else 'Failed'}"}
