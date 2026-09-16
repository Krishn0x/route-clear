from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_upload_oversized_file():
    oversized_data = b"0" * (settings.MAX_UPLOAD_SIZE_BYTES + 1)
    
    # V2 contract: only transfer_id is supplied by the client
    response = client.post(
        "/api/documents/upload",
        data={
            "transfer_id": "TRF_DEMO_SAFE"
        },
        files={
            "file": ("test.jpg", oversized_data, "image/jpeg")
        }
    )
    
    assert response.status_code == 413
    assert "File size exceeds maximum allowed size" in response.json()["detail"]


def test_upload_invalid_file_type():
    # Adding a test for invalid file type, preserving the general validation coverage
    # that used to exist for quantities.
    invalid_data = b"This is just some text, not an image or PDF"
    
    resp = client.post(
        "/api/documents/upload",
        data={"transfer_id": "TRF_DEMO_SAFE"},
        files={"file": ("test.txt", invalid_data, "text/plain")}
    )
    assert resp.status_code == 400
    assert "Invalid file type" in resp.json()["detail"]


def test_upload_success():
    valid_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
    
    # Test valid upload using standard DB fixture
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
        resp = client.post(
            "/api/documents/upload",
            data={"transfer_id": "TRF_DEMO_SAFE"},
            files={"file": ("test.jpg", valid_data, "image/jpeg")}
        )
        assert resp.status_code == 200
        # Assert that it fetched the correct financial values from the registry
        assert resp.json()["ordered_quantity"] == 105
        assert float(resp.json()["total_amount"]) == 105000.0
    finally:
        del app.dependency_overrides[get_db]
        Base.metadata.drop_all(bind=test_engine)

