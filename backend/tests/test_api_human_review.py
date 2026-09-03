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

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

def test_human_review_boundaries():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test.jpg",
        transfer_id="tr_hr123",
        total_amount=Decimal("100000.00"),
        ordered_quantity=100,
        status=DocumentStatus.HUMAN_REVIEW
    )
    db.add(doc)
    db.commit()
    db.close()

    # Attempt: release=120000, reversal=0 (exceeds total)
    resp = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=120000&proposed_reversal_amount=0")
    assert resp.status_code == 400
    assert "Amounts exceed total order amount" in resp.json()['detail']

    # Attempt: release=60000, reversal=60000 (exceeds total)
    resp = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=60000&proposed_reversal_amount=60000")
    assert resp.status_code == 400
    
    # Attempt: release=-100, reversal=0
    resp = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=-100&proposed_reversal_amount=0")
    assert resp.status_code == 400
    assert "Amounts cannot be negative" in resp.json()['detail']

    # Attempt: release=100000, reversal=10000 (exceeds total)
    resp = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=100000&proposed_reversal_amount=10000")
    assert resp.status_code == 400

    # Attempt: Valid - release=90000, reversal=10000
    resp = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=90000&proposed_reversal_amount=10000")
    assert resp.status_code == 200
    assert "submitted securely" in resp.json()['message']

def test_human_review_idempotency():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test_idemp.jpg",
        transfer_id="tr_idemp123",
        total_amount=Decimal("100000.00"),
        ordered_quantity=100,
        status=DocumentStatus.HUMAN_REVIEW
    )
    db.add(doc)
    db.commit()
    db.close()

    # First attempt - Success
    resp1 = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=90000&proposed_reversal_amount=10000")
    assert resp1.status_code == 200

    # Second identical attempt - Idempotent Catch
    resp2 = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=90000&proposed_reversal_amount=10000")
    assert resp2.status_code == 400
    assert "not pending human review" in resp2.json()['detail']


def test_human_review_status_guard():
    db = TestingSessionLocal()
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename="test_status.jpg",
        transfer_id="tr_status123",
        total_amount=Decimal("100000.00"),
        ordered_quantity=100,
        status=DocumentStatus.COMPLETED
    )
    db.add(doc)
    db.commit()
    db.close()

    resp = client.post(f"/api/documents/{doc_id}/human-review?approved_release_amount=90000&proposed_reversal_amount=10000")
    assert resp.status_code == 400
    assert "not pending human review" in resp.json()['detail']


