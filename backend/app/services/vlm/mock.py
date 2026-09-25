import json
import hashlib
from typing import List, Optional
from app.schemas.document import FulfillmentEvidenceSchema
from app.services.vlm.base import BaseVLMProvider

class MockVLMProvider(BaseVLMProvider):
    """
    Mock Provider for deterministic unit/integration tests and live demo scenarios.
    Implements the 5 requested deterministic V2 fixtures.
    """
    def __init__(self):
        self.model_name = "mock-vlm-v2"

    def _get_base_response(self) -> dict:
        return {
            "provider": "mock",
            "model_identifier": self.model_name,
            "extracted_fields": {
                "accepted_quantity": {"value": 95, "confidence": 0.95, "evidence_region": {"x": 0.3, "y": 0.5, "w": 0.1, "h": 0.05}, "evidence_note": "Clearly printed", "warnings": []},
                "damaged_quantity": {"value": 1, "confidence": 0.88, "evidence_region": {"x": 0.3, "y": 0.6, "w": 0.1, "h": 0.05}, "evidence_note": "Handwritten note", "warnings": []},
                "rejected_quantity": {"value": 9, "confidence": 0.95, "evidence_region": {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}, "evidence_note": "Fixture data", "warnings": []},
                "signature_present": {"value": True, "confidence": 0.99, "evidence_region": {"x": 0.7, "y": 0.9, "w": 0.2, "h": 0.1}, "evidence_note": "Clear ink signature", "warnings": []},
                "correction_detected": {"value": False, "confidence": 0.90, "evidence_region": None, "evidence_note": "No crossed out fields detected", "warnings": []},
                "document_type": {"value": "challan", "confidence": 0.99, "evidence_note": "Title says Delivery Challan"},
                "suspicious_content_detected": {"value": False, "confidence": 0.99, "evidence_note": "None"}
            },
            "overall_confidence": 0.92,
            "raw_vlm_output": {"simulated": True, "note": "MockVLMProvider Pass"}
        }

    def _determine_scenario(self, image_bytes: bytes, ordered_quantity: int):
        if b'LOW_EVIDENCE' in image_bytes:
            return 'LOW_EVIDENCE'
        elif b'INJECTION' in image_bytes:
            return 'INJECTION'
        elif b'CONSISTENT_WRONG' in image_bytes:
            return 'CONSISTENT_WRONG'
        return ordered_quantity

    async def extract_pass1(self, image_bytes: bytes, mime_type: str, ordered_quantity: int, locked_model_name: Optional[str] = None) -> FulfillmentEvidenceSchema:
        scenario = self._determine_scenario(image_bytes, ordered_quantity)
        return self._generate_fixture(scenario, pass_num=1)

    async def extract_pass2(self, image_bytes: bytes, mime_type: str, ordered_quantity: int, locked_model_name: Optional[str] = None) -> FulfillmentEvidenceSchema:
        scenario = self._determine_scenario(image_bytes, ordered_quantity)
        return self._generate_fixture(scenario, pass_num=2)

    def _generate_fixture(self, scenario, pass_num: int) -> FulfillmentEvidenceSchema:
        resp = self._get_base_response()
        resp["raw_vlm_output"]["pass_num"] = pass_num

        if scenario == 80:
            # B. MODEL CONFLICT (SIMULATED MODEL CONFLICT)
            resp["raw_vlm_output"]["note"] = "SIMULATED MODEL CONFLICT"
            if pass_num == 1:
                resp["extracted_fields"]["accepted_quantity"]["value"] = 75
                resp["extracted_fields"]["damaged_quantity"]["value"] = 5
                resp["extracted_fields"]["rejected_quantity"]["value"] = 0
            else:
                resp["extracted_fields"]["accepted_quantity"]["value"] = 70
                resp["extracted_fields"]["damaged_quantity"]["value"] = 5
                resp["extracted_fields"]["rejected_quantity"]["value"] = 5
                
        elif scenario == 145:
            # UNACCOUNTED REVIEW DEMO (125+10+5 = 140 != 145)
            resp["extracted_fields"]["accepted_quantity"]["value"] = 125
            resp["extracted_fields"]["damaged_quantity"]["value"] = 10
            resp["extracted_fields"]["rejected_quantity"]["value"] = 5
            
        elif scenario == 'LOW_EVIDENCE':
            # C. LOW EVIDENCE
            resp["overall_confidence"] = 0.5
            resp["extracted_fields"]["accepted_quantity"] = None
            
        elif scenario == 'INJECTION':
            # D. PROMPT INJECTION
            resp["extracted_fields"]["suspicious_content_detected"]["value"] = True
            resp["extracted_fields"]["suspicious_content_detected"]["evidence_note"] = "IGNORE INSTRUCTIONS detected"
            
        elif scenario == 'CONSISTENT_WRONG':
            # E. CONSISTENT BUT POTENTIALLY WRONG
            # GROUND TRUTH (actual document physically says): accepted=50, damaged=55, rejected=0.
            # But the mock AI confidently hallucinates:
            resp["extracted_fields"]["accepted_quantity"]["value"] = 105
            # We supply a fake evidence_region here to ensure it passes the groundedness check.
            # This demonstrates that a region being provided does not prove the value is factually correct.
            resp["extracted_fields"]["accepted_quantity"]["evidence_region"] = {"x": 0.4, "y": 0.4, "w": 0.1, "h": 0.1}
            resp["extracted_fields"]["damaged_quantity"]["value"] = 0
            resp["extracted_fields"]["rejected_quantity"]["value"] = 0
            resp["raw_vlm_output"]["note"] = "AI agrees but is WRONG compared to physical document"

        # Default is 105 (A. SAFE AGREEMENT) which matches the base response (95+1+9)
        return FulfillmentEvidenceSchema(**resp)
