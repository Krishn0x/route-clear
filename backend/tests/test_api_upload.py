from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_upload_oversized_file():
    oversized_data = b"0" * (settings.MAX_UPLOAD_SIZE_BYTES + 1)
    
    response = client.post(
        "/api/documents/upload",
        data={
            "transfer_id": "tr_123",
            "total_amount": "100.00",
            "ordered_quantity": 10
        },
        files={
            "file": ("test.jpg", oversized_data, "image/jpeg")
        }
    )
    
    assert response.status_code == 413
    assert "File size exceeds maximum allowed size" in response.json()["detail"]

def test_upload_ordered_quantity_validation():
    valid_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
    
    # We don't need a DB for validation failures (0, -1)
    # Test ordered_quantity = 0
    resp_zero = client.post(
        "/api/documents/upload",
        data={"transfer_id": "tr_123", "total_amount": "100.00", "ordered_quantity": 0},
        files={"file": ("test.jpg", valid_data, "image/jpeg")}
    )
    assert resp_zero.status_code == 400
    assert "positive integer" in resp_zero.json()["detail"]

    # Test ordered_quantity = -1
    resp_neg = client.post(
        "/api/documents/upload",
        data={"transfer_id": "tr_123", "total_amount": "100.00", "ordered_quantity": -1},
        files={"file": ("test.jpg", valid_data, "image/jpeg")}
    )
    assert resp_neg.status_code == 400
    assert "positive integer" in resp_neg.json()["detail"]

    # Test ordered_quantity = 1 (should pass quantity validation)
    from app.db.session import Base, get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    try:
        resp_one = client.post(
            "/api/documents/upload",
            data={"transfer_id": "tr_123", "total_amount": "100.00", "ordered_quantity": 1},
            files={"file": ("test.jpg", valid_data, "image/jpeg")}
        )
        assert resp_one.status_code == 200
        assert resp_one.json()["ordered_quantity"] == 1
    finally:
        del app.dependency_overrides[get_db]
        Base.metadata.drop_all(bind=test_engine)

def test_upload_total_amount_validation():
    valid_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
    
    # Test total_amount = 0
    resp_zero = client.post(
        "/api/documents/upload",
        data={"transfer_id": "tr_123", "total_amount": "0", "ordered_quantity": 10},
        files={"file": ("test.jpg", valid_data, "image/jpeg")}
    )
    assert resp_zero.status_code == 400
    assert "positive" in resp_zero.json()["detail"].lower()

    # Test total_amount = -1
    resp_neg = client.post(
        "/api/documents/upload",
        data={"transfer_id": "tr_123", "total_amount": "-1", "ordered_quantity": 10},
        files={"file": ("test.jpg", valid_data, "image/jpeg")}
    )
    assert resp_neg.status_code == 400
    assert "positive" in resp_neg.json()["detail"].lower()
    
    # Test total_amount = 100000
    from app.db.session import Base, get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    try:
        resp_valid = client.post(
            "/api/documents/upload",
            data={"transfer_id": "tr_123", "total_amount": "100000", "ordered_quantity": 10},
            files={"file": ("test.jpg", valid_data, "image/jpeg")}
        )
        assert resp_valid.status_code == 200
        assert float(resp_valid.json()["total_amount"]) == 100000.0
    finally:
        del app.dependency_overrides[get_db]
        Base.metadata.drop_all(bind=test_engine)

