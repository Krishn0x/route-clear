import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base, engine, get_db
from app.db.models import Document, DocumentStatus, AuditLog, SafetyValidation, FulfillmentEvidence, SettlementDecision, VerificationResult
from decimal import Decimal
import uuid
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    'sqlite://', 
    connect_args={'check_same_thread': False}, 
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    from app.api.endpoints import UPLOAD_DIR
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)

def test_process_safe_agreement_route_success():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id, filename=f'{doc_id}.jpg', transfer_id='TRF_DEMO_SAFE',
        total_amount=Decimal('105000.00'), ordered_quantity=105, status=DocumentStatus.PENDING, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    
    from app.api.endpoints import UPLOAD_DIR
    with open(os.path.join(UPLOAD_DIR, doc.filename), 'wb') as f:
        f.write(b'dummy content')
    
    resp = client.post(f'/api/documents/{doc_id}/process')
    assert resp.status_code == 200
    
    db.expire_all()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == DocumentStatus.COMPLETED
    
    vr = db.query(VerificationResult).filter(VerificationResult.document_id == doc_id).first()
    assert vr is not None and vr.pass2_triggered is True and vr.evidence_sufficient is True
    
    sv = db.query(SafetyValidation).filter(SafetyValidation.document_id == doc_id).first()
    assert sv is not None and sv.passed is True
    
    route_log = db.query(AuditLog).filter(AuditLog.document_id == doc_id, AuditLog.event_type == 'ROUTE_ACTION_COMPLETED').first()
    assert route_log is not None
    db.close()

def test_process_vlm_conflict_human_review():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id, filename=f'{doc_id}.jpg', transfer_id='TRF_DEMO_CONFLICT',
        total_amount=Decimal('80000.00'), ordered_quantity=80, status=DocumentStatus.PENDING, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    
    from app.api.endpoints import UPLOAD_DIR
    with open(os.path.join(UPLOAD_DIR, doc.filename), 'wb') as f:
        f.write(b'dummy content')
    
    resp = client.post(f'/api/documents/{doc_id}/process')
    assert resp.status_code == 200
    
    db.expire_all()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == DocumentStatus.HUMAN_REVIEW
    
    sv = db.query(SafetyValidation).filter(SafetyValidation.document_id == doc_id).first()
    assert sv is None
    
    route_log = db.query(AuditLog).filter(AuditLog.document_id == doc_id, AuditLog.event_type.like('ROUTE_ACTION%')).first()
    assert route_log is None
    db.close()

def test_process_safety_engine_rejection():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id, filename=f'{doc_id}.jpg', transfer_id='TRF_DEMO_REVIEW',
        total_amount=Decimal('145000.00'), ordered_quantity=145, status=DocumentStatus.PENDING, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    
    from app.api.endpoints import UPLOAD_DIR
    with open(os.path.join(UPLOAD_DIR, doc.filename), 'wb') as f:
        f.write(b'dummy content')
    
    resp = client.post(f'/api/documents/{doc_id}/process')
    assert resp.status_code == 200
    
    db.expire_all()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == DocumentStatus.HUMAN_REVIEW
    
    sv = db.query(SafetyValidation).filter(SafetyValidation.document_id == doc_id).first()
    assert sv is not None and sv.passed is False
    
    route_log = db.query(AuditLog).filter(AuditLog.document_id == doc_id, AuditLog.event_type.like('ROUTE_ACTION%')).first()
    assert route_log is None
    db.close()

def test_process_repeated_no_duplicate_route():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id, filename=f'{doc_id}.jpg', transfer_id='TRF_DEMO_SAFE',
        total_amount=Decimal('105000.00'), ordered_quantity=105, status=DocumentStatus.PENDING, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    
    from app.api.endpoints import UPLOAD_DIR
    with open(os.path.join(UPLOAD_DIR, doc.filename), 'wb') as f:
        f.write(b'dummy content')
    db.close()
    
    resp1 = client.post(f'/api/documents/{doc_id}/process')
    assert resp1.status_code == 200
    
    resp2 = client.post(f'/api/documents/{doc_id}/process')
    assert resp2.status_code == 400
    assert 'already processed' in resp2.json()['detail']

def test_vlm_failure_fail_closed():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id, filename=f'{doc_id}.jpg', transfer_id='TRF_DEMO_SAFE',
        total_amount=Decimal('105000.00'), ordered_quantity=105, status=DocumentStatus.PENDING, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    
    from app.api.endpoints import UPLOAD_DIR
    with open(os.path.join(UPLOAD_DIR, doc.filename), 'wb') as f:
        f.write(b'LOW_EVIDENCE')
        
    resp = client.post(f'/api/documents/{doc_id}/process')
    assert resp.status_code == 200
    
    db.expire_all()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == DocumentStatus.HUMAN_REVIEW
    
    route_log = db.query(AuditLog).filter(AuditLog.document_id == doc_id, AuditLog.event_type.like('ROUTE_ACTION%')).first()
    assert route_log is None
    db.close()

def test_human_review_correction_to_route():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id, filename=f'{doc_id}.jpg', transfer_id='TRF_DEMO_CONFLICT',
        total_amount=Decimal('80000.00'), ordered_quantity=80, status=DocumentStatus.HUMAN_REVIEW, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    db.close()

    payload = {'accepted_quantity': 80, 'damaged_quantity': 0, 'rejected_quantity': 0}
    resp = client.post(f'/api/documents/{doc_id}/human-review', json=payload)
    assert resp.status_code == 200
    
    db = TestingSessionLocal()
    db.expire_all()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == DocumentStatus.COMPLETED
    
    route_log = db.query(AuditLog).filter(AuditLog.document_id == doc_id, AuditLog.event_type == 'ROUTE_ACTION_COMPLETED').first()
    assert route_log is not None
    db.close()
