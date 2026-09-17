"""
Phase 1 Tests — Transfer Registry and Upload Endpoint V2

These tests verify:
1. The transfer registry returns correct records
2. The GET /api/documents/transfers endpoint works
3. The POST /api/documents/upload endpoint now uses server-side transfer metadata
   (ordered_quantity and total_amount are NOT accepted from the client)
4. Uploading with an unknown transfer_id is rejected with 404
"""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.data.transfer_registry import get_transfer, list_transfers, SIMULATED_TRANSFERS

client = TestClient(app, headers={"x-demo-token": "demo_mode_local"})


# ── Transfer registry unit tests ───────────────────────────────────────────────

class TestTransferRegistry:

    def test_get_known_transfer_safe(self):
        record = get_transfer("TRF_DEMO_SAFE")
        assert record is not None
        assert record.transfer_id == "TRF_DEMO_SAFE"
        assert record.ordered_quantity == 105
        assert record.total_amount == Decimal("105000.00")
        assert "Sharma" in record.vendor_name

    def test_get_known_transfer_review(self):
        record = get_transfer("TRF_DEMO_REVIEW")
        assert record is not None
        assert record.ordered_quantity == 145
        assert record.total_amount == Decimal("145000.00")

    def test_get_known_transfer_conflict(self):
        record = get_transfer("TRF_DEMO_CONFLICT")
        assert record is not None
        assert record.ordered_quantity == 80
        assert record.total_amount == Decimal("80000.00")

    def test_get_unknown_transfer_returns_none(self):
        assert get_transfer("NONEXISTENT") is None
        assert get_transfer("") is None
        assert get_transfer("tr_demo_12345") is None

    def test_list_transfers_returns_all(self):
        records = list_transfers()
        assert len(records) == len(SIMULATED_TRANSFERS)
        ids = {r.transfer_id for r in records}
        assert "TRF_DEMO_SAFE" in ids
        assert "TRF_DEMO_REVIEW" in ids
        assert "TRF_DEMO_CONFLICT" in ids

    def test_ordered_quantity_is_positive(self):
        for record in list_transfers():
            assert record.ordered_quantity > 0, \
                f"{record.transfer_id} has non-positive ordered_quantity"

    def test_total_amount_is_positive(self):
        for record in list_transfers():
            assert record.total_amount > 0, \
                f"{record.transfer_id} has non-positive total_amount"


# ── API endpoint tests ─────────────────────────────────────────────────────────

class TestTransferEndpoints:

    def test_list_transfers_endpoint(self):
        resp = client.get("/api/documents/transfers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        ids = {r["transfer_id"] for r in data}
        assert "TRF_DEMO_SAFE" in ids

    def test_get_transfer_endpoint_known(self):
        resp = client.get("/api/documents/transfers/TRF_DEMO_SAFE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["transfer_id"] == "TRF_DEMO_SAFE"
        assert data["ordered_quantity"] == 105
        assert float(data["total_amount"]) == 105000.00
        assert "vendor_name" in data
        assert "item_description" in data

    def test_get_transfer_endpoint_unknown(self):
        resp = client.get("/api/documents/transfers/DOES_NOT_EXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_transfer_endpoint_demo_hint_in_error(self):
        """The error message should hint at valid demo IDs."""
        resp = client.get("/api/documents/transfers/UNKNOWN")
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert "TRF_DEMO_SAFE" in detail


# ── Upload endpoint V2 tests ───────────────────────────────────────────────────

class TestUploadEndpointV2:
    """
    V2: upload accepts only transfer_id + file.
    Financial fields come from the server-side registry.
    """

    @pytest.fixture(autouse=True)
    def setup_test_db(self):
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
        yield
        del app.dependency_overrides[get_db]
        Base.metadata.drop_all(bind=test_engine)

    DUMMY_PNG = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x00\x00\x00\x00:~\x9bU\x00\x00'
        b'\x00\nIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
        b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    def test_upload_with_valid_transfer_id(self):
        resp = client.post(
            "/api/documents/upload",
            data={"transfer_id": "TRF_DEMO_SAFE"},
            files={"file": ("test.png", self.DUMMY_PNG, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        # ordered_quantity must match server-side registry, not any client value
        assert data["ordered_quantity"] == 105
        assert float(data["total_amount"]) == 105000.00
        assert data["status"] == "PENDING"
        assert data["transfer_id"] == "TRF_DEMO_SAFE"

    def test_upload_rejects_unknown_transfer(self):
        resp = client.post(
            "/api/documents/upload",
            data={"transfer_id": "INVENTED_TRANSFER"},
            files={"file": ("test.png", self.DUMMY_PNG, "image/png")},
        )
        assert resp.status_code == 404

    def test_upload_with_review_transfer_uses_server_qty(self):
        resp = client.post(
            "/api/documents/upload",
            data={"transfer_id": "TRF_DEMO_REVIEW"},
            files={"file": ("test.png", self.DUMMY_PNG, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Must be 145 from registry, not any user-supplied value
        assert data["ordered_quantity"] == 145
        assert float(data["total_amount"]) == 145000.00

    def test_upload_ordered_quantity_not_from_client(self):
        """
        V2 security property: client cannot supply ordered_quantity.
        Even if a client crafts a multipart form with ordered_quantity=9999,
        the server ignores it and uses the registry value.
        """
        resp = client.post(
            "/api/documents/upload",
            data={"transfer_id": "TRF_DEMO_SAFE", "ordered_quantity": "9999"},
            files={"file": ("test.png", self.DUMMY_PNG, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Must still be 105, not 9999
        assert data["ordered_quantity"] == 105

    def test_upload_total_amount_not_from_client(self):
        """Client-supplied total_amount is ignored; server uses registry value."""
        resp = client.post(
            "/api/documents/upload",
            data={"transfer_id": "TRF_DEMO_SAFE", "total_amount": "1.00"},
            files={"file": ("test.png", self.DUMMY_PNG, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["total_amount"]) == 105000.00

    def test_upload_invalid_mime_type(self):
        resp = client.post(
            "/api/documents/upload",
            data={"transfer_id": "TRF_DEMO_SAFE"},
            files={"file": ("test.txt", b"not an image", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_no_transfer_id(self):
        resp = client.post(
            "/api/documents/upload",
            data={},
            files={"file": ("test.png", self.DUMMY_PNG, "image/png")},
        )
        assert resp.status_code == 422  # FastAPI validation error
