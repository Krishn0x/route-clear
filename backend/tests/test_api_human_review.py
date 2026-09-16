import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base, engine, get_db
from app.db.models import Document, DocumentStatus
from decimal import Decimal
import uuid

# Override DB for testing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite://", 
    connect_args={"check_same_thread": False}, 
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

def test_human_review_quantities():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test.jpg",
        transfer_id="TRF_DEMO_REVIEW",
        total_amount=Decimal("100000.00"),
        ordered_quantity=100,
        status=DocumentStatus.HUMAN_REVIEW, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    db.close()

    # Attempt: Invalid quantities (sum > ordered)
    resp = client.post(
        f"/api/documents/{doc_id}/human-review",
        json={"accepted_quantity": 90, "damaged_quantity": 20, "rejected_quantity": 0}
    )
    assert resp.status_code == 400
    assert "exceeds ordered quantity" in resp.json()['detail']

    # Attempt: Negative quantities
    resp = client.post(
        f"/api/documents/{doc_id}/human-review",
        json={"accepted_quantity": -10, "damaged_quantity": 0, "rejected_quantity": 0}
    )
    assert resp.status_code == 400
    assert "Negative quantities detected" in resp.json()['detail']

    # Attempt: Unaccounted quantities
    resp = client.post(
        f"/api/documents/{doc_id}/human-review",
        json={"accepted_quantity": 50, "damaged_quantity": 10, "rejected_quantity": 10}
    )
    # The SafetyEngine fails it due to unaccounted (70 != 100)
    assert resp.status_code == 400
    assert "Unaccounted quantity detected" in resp.json()['detail']

    # Attempt: Valid - exact match
    resp = client.post(
        f"/api/documents/{doc_id}/human-review",
        json={"accepted_quantity": 90, "damaged_quantity": 10, "rejected_quantity": 0}
    )
    assert resp.status_code == 200
    assert "submitted securely" in resp.json()['message']


def test_human_review_idempotency():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test_idemp.jpg",
        transfer_id="TRF_DEMO_REVIEW2",
        total_amount=Decimal("100000.00"),
        ordered_quantity=100,
        status=DocumentStatus.HUMAN_REVIEW, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    db.close()

    # First attempt - Success
    payload = {"accepted_quantity": 90, "damaged_quantity": 10, "rejected_quantity": 0}
    resp1 = client.post(f"/api/documents/{doc_id}/human-review", json=payload)
    assert resp1.status_code == 200

    # Second identical attempt - status guard triggers first
    resp2 = client.post(f"/api/documents/{doc_id}/human-review", json=payload)
    assert resp2.status_code == 400
    assert "not pending human review" in resp2.json()['detail']


def test_human_review_status_guard():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test_status.jpg",
        transfer_id="TRF_DEMO_SAFE",
        total_amount=Decimal("100000.00"),
        ordered_quantity=100,
        status=DocumentStatus.COMPLETED, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    db.close()

    payload = {"accepted_quantity": 100, "damaged_quantity": 0, "rejected_quantity": 0}
    resp = client.post(f"/api/documents/{doc_id}/human-review", json=payload)
    assert resp.status_code == 400
    assert "not pending human review" in resp.json()['detail']

def test_human_review_ignores_malicious_financial_payloads():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test_malicious.jpg",
        transfer_id="TRF_DEMO_REVIEW_MALICIOUS",
        total_amount=Decimal("100000.00"),
        ordered_quantity=100,
        status=DocumentStatus.HUMAN_REVIEW, file_hash='dummy', mime_type='image/jpeg', file_size=1000
    )
    db.add(doc)
    db.commit()
    db.close()

    # Payload contains valid quantities but attempts to inject malicious amounts and overrides
    malicious_payload = {
        "accepted_quantity": 90,
        "damaged_quantity": 10,
        "rejected_quantity": 0,
        "approved_release_amount": 9999999,  # Malicious amount
        "proposed_reversal_amount": 0,       # Malicious amount
        "ordered_quantity": 500,             # Attempt to override ordered_quantity
        "total_amount": 9999999              # Attempt to override total_amount
    }
    
    resp = client.post(f"/api/documents/{doc_id}/human-review", json=malicious_payload)
    assert resp.status_code == 200
    
    # Query the DB to ensure malicious amounts were ignored and true values were computed by SafetyEngine
    db = TestingSessionLocal()
    from app.db.models import SettlementDecision
    decision = db.query(SettlementDecision).filter(SettlementDecision.document_id == doc_id).first()
    
    assert decision is not None
    # 90 / 100 * 100000 = 90000
    assert decision.approved_release_amount == Decimal("90000.00")
    assert decision.proposed_reversal_amount == Decimal("10000.00")
    db.close()



