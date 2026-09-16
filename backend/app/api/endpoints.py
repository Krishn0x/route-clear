from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Document, DocumentStatus, AuditLog
from app.schemas.document import DocumentResponse, TransferRecord, DocumentResponseV2, HumanReviewRequest
from app.data.transfer_registry import get_transfer, list_transfers
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

# ── Transfer registry endpoints ───────────────────────────────────────────────

@router.get("/transfers", response_model=list[TransferRecord])
async def list_available_transfers():
    return list_transfers()

@router.get("/transfers/{transfer_id}", response_model=TransferRecord)
async def get_transfer_metadata(transfer_id: str):
    record = get_transfer(transfer_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Transfer '{transfer_id}' not found. For the demo use: TRF_DEMO_SAFE, TRF_DEMO_REVIEW, or TRF_DEMO_CONFLICT"
        )
    return record


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    transfer_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    transfer = get_transfer(transfer_id)
    if not transfer:
        raise HTTPException(
            status_code=404,
            detail=f"Transfer '{transfer_id}' not found. For the demo use: TRF_DEMO_SAFE, TRF_DEMO_REVIEW, or TRF_DEMO_CONFLICT"
        )
    ordered_quantity = transfer.ordered_quantity
    total_amount = transfer.total_amount

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

@router.post("/{doc_id}/process", response_model=DocumentResponseV2)
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

    # 1. VLM Extraction (Two-Pass Verification)
    from app.services.vlm import get_vlm_provider
    from app.services.vlm.gemini import VLMException
    from app.services.vlm.comparator import compare_passes, resolve
    
    vlm = get_vlm_provider()
    
    try:
        # Pass 1
        pass1 = await vlm.extract_pass1(
            image_bytes=image_bytes,
            mime_type=doc.mime_type,
            ordered_quantity=doc.ordered_quantity
        )
        
        # Pass 2 (Independent)
        pass2 = await vlm.extract_pass2(
            image_bytes=image_bytes,
            mime_type=doc.mime_type,
            ordered_quantity=doc.ordered_quantity
        )
        
        # Deterministic Comparison & Resolution
        comp = compare_passes(pass1, pass2, [])
        res = resolve(pass1, pass2, comp)
        
        # Save Pass 1 as FulfillmentEvidence (for UI backward compatibility)
        from app.db.models import FulfillmentEvidence, VerificationResult
        evidence_record = FulfillmentEvidence(
            document_id=doc.id,
            provider=pass1.provider,
            model_identifier=pass1.model_identifier,
            extracted_fields=pass1.extracted_fields.model_dump(mode='json'),
            overall_confidence=pass1.overall_confidence,
            raw_vlm_output=pass1.raw_vlm_output
        )
        db.add(evidence_record)
        
        # Save VerificationResult (V2 Architecture)
        vr = VerificationResult(
            document_id=doc.id,
            pass1_raw=pass1.model_dump(mode='json'),
            pass2_raw=pass2.model_dump(mode='json'),
            pass2_triggered=True,
            pass2_trigger_reasons=[],
            comparison_result=comp.model_dump(mode='json'),
            resolution_result=res.model_dump(mode='json'),
            evidence_sufficient=not res.requires_human_review,
            sufficiency_failures=[res.human_review_reason] if res.human_review_reason else []
        )
        db.add(vr)
        
        doc.status = DocumentStatus.PROCESSED
        event_type = "VLM_VERIFICATION_COMPLETED"
        event_details = {
            "resolution_method": res.resolution_method,
            "requires_human_review": res.requires_human_review
        }
    except VLMException as e:
        doc.status = DocumentStatus.FAILED
        event_type = "VLM_VERIFICATION_FAILED"
        event_details = {"error": str(e)}
        res = None
        pass1 = None
    
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
        
    # Halt before SafetyEngine if human review is required
    if res.requires_human_review:
        doc.status = DocumentStatus.HUMAN_REVIEW
        db.commit()
        db.refresh(doc)
        return doc
        
    # 2. Safety Validation Engine
    from app.services.safety.engine import SafetyEngine
    from app.schemas.document import PolicyConfig
    from app.db.models import SafetyValidation, SettlementDecision
    
    policy = PolicyConfig() # using defaults
    engine = SafetyEngine(policy)
    
    # We pass pass1 as the evidence schema because AI is consistent and grounded
    validation_result, decision_result = engine.evaluate(doc, pass1)
    
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
    request: HumanReviewRequest, 
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if doc.status != DocumentStatus.HUMAN_REVIEW:
        raise HTTPException(status_code=400, detail="Document is not pending human review")
    
    # Check Idempotency
    from app.db.models import SettlementDecision, AuditLog
    from sqlalchemy.exc import IntegrityError
    
    idemp_key = f"{doc.transfer_id}_HUMAN_REVIEW_DECISION"
    existing_decision = db.query(SettlementDecision).filter(SettlementDecision.idempotency_key == idemp_key).first()
    if existing_decision:
        return {"message": "Decision already processed for this transfer (idempotent)."}
        
    # Construct synthetic evidence from human inputs
    from app.schemas.document import FulfillmentEvidenceSchema, FulfillmentFields, FieldEvidence
    evidence = FulfillmentEvidenceSchema(
        provider="human",
        model_identifier="human_reviewer",
        extracted_fields=FulfillmentFields(
            accepted_quantity=FieldEvidence[int](value=request.accepted_quantity, confidence=1.0),
            damaged_quantity=FieldEvidence[int](value=request.damaged_quantity, confidence=1.0),
            rejected_quantity=FieldEvidence[int](value=request.rejected_quantity, confidence=1.0),
            signature_present=FieldEvidence[bool](value=True, confidence=1.0),
            correction_detected=FieldEvidence[bool](value=False, confidence=1.0),
            document_type=FieldEvidence[str](value="human_verified", confidence=1.0),
            suspicious_content_detected=FieldEvidence[bool](value=False, confidence=1.0)
        ),
        overall_confidence=1.0,
        raw_vlm_output={"note": "Human reviewed"}
    )
    
    # Pass through deterministic Safety Engine
    from app.services.safety.engine import SafetyEngine
    from app.schemas.document import PolicyConfig
    
    engine = SafetyEngine(PolicyConfig())
    validation_result, decision_result = engine.evaluate(doc, evidence)
    
    if not validation_result.passed:
        raise HTTPException(status_code=400, detail=f"Human review failed safety policy: {validation_result.failure_reasons}")
    
    # Overwrite idempotency key on the decision
    decision_result.idempotency_key = idemp_key
    
    decision = SettlementDecision(
        document_id=doc.id,
        transfer_id=doc.transfer_id,
        approved_release_amount=decision_result.approved_release_amount,
        proposed_reversal_amount=decision_result.proposed_reversal_amount,
        requires_human_review=False,
        policy_version="1.0-manual-safety",
        idempotency_key=idemp_key
    )
    db.add(decision)
    
    doc.status = DocumentStatus.COMPLETED
    
    # Audit log
    last_audit = db.query(AuditLog).filter(AuditLog.document_id == doc.id).order_by(AuditLog.sequence_number.desc()).first()
    prev_hash = last_audit.event_hash if last_audit else None
    seq_num = (last_audit.sequence_number + 1) if last_audit else 1
    
    event_details = {
        "accepted_quantity": request.accepted_quantity,
        "damaged_quantity": request.damaged_quantity,
        "rejected_quantity": request.rejected_quantity,
        "approved_release_amount": float(decision_result.approved_release_amount),
        "proposed_reversal_amount": float(decision_result.proposed_reversal_amount),
        "safety_passed": True
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
    
    route_results = await adapter.execute_settlement(db, decision_result)
    
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
