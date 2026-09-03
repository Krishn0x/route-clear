import json
from app.schemas.document import FulfillmentEvidenceSchema
from app.services.vlm.base import BaseVLMProvider

class MockVLMProvider(BaseVLMProvider):
    """
    Mock Provider for deterministic unit/integration tests.
    NEVER use this silently in production/demo mode.
    """
    def __init__(self):
        self.model_name = "mock-vlm-v1"

    async def extract_fulfillment_evidence(
        self, 
        image_bytes: bytes, 
        mime_type: str, 
        ordered_quantity: int
    ) -> FulfillmentEvidenceSchema:
        
        mock_response = {
            "provider": "mock",
            "model_identifier": self.model_name,
            "extracted_fields": {
                "accepted_quantity": {
                    "value": 90,
                    "confidence": 0.95,
                    "evidence_region": {"x": 0.3, "y": 0.5, "w": 0.1, "h": 0.05},
                    "evidence_note": "Clearly printed",
                    "warnings": []
                },
                "damaged_quantity": {
                    "value": 10,
                    "confidence": 0.88,
                    "evidence_region": {"x": 0.3, "y": 0.6, "w": 0.1, "h": 0.05},
                    "evidence_note": "Handwritten note indicating damage",
                    "warnings": ["Handwriting is slightly blurry"]
                },
                "signature_present": {
                    "value": True,
                    "confidence": 0.99,
                    "evidence_region": {"x": 0.7, "y": 0.9, "w": 0.2, "h": 0.1},
                    "evidence_note": "Clear ink signature",
                    "warnings": []
                },
                "correction_detected": {
                    "value": False,
                    "confidence": 0.90,
                    "evidence_region": None,
                    "evidence_note": "No crossed out fields detected",
                    "warnings": []
                }
            },
            "overall_confidence": 0.92,
            "raw_vlm_output": {"simulated": True, "note": "This is from MockVLMProvider"}
        }
        
        return FulfillmentEvidenceSchema(**mock_response)
