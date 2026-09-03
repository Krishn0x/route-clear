import json
import logging
from typing import Optional
from app.schemas.document import FulfillmentEvidenceSchema
from app.services.vlm.base import BaseVLMProvider
from app.services.vlm.prompt import EXTRACTION_PROMPT
from app.core.config import settings
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class VLMException(Exception):
    pass

class GeminiVLMProvider(BaseVLMProvider):
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError("GEMINI_API_KEY is missing or invalid in environment variables.")
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except ImportError:
            raise ImportError("google-genai package is not installed.")
        self.model_name = settings.GEMINI_MODEL
        self.executor = ThreadPoolExecutor(max_workers=5)

    def _sync_extract(self, image_bytes: bytes, mime_type: str, ordered_quantity: int) -> FulfillmentEvidenceSchema:
        prompt = EXTRACTION_PROMPT.format(ordered_quantity=ordered_quantity)
        
        try:
            from google import genai
            # Prepare image part
            image_part = genai.types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, image_part],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            raw_text = response.text
            if not raw_text:
                raise VLMException("Empty response from Gemini API.")
                
            try:
                parsed_json = json.loads(raw_text)
            except json.JSONDecodeError:
                raise VLMException("Malformed JSON returned by Gemini API.")
            
            return FulfillmentEvidenceSchema(
                provider="gemini",
                model_identifier=self.model_name,
                extracted_fields=parsed_json.get("extracted_fields", {}),
                overall_confidence=parsed_json.get("overall_confidence", 0.0),
                raw_vlm_output=parsed_json
            )
            
        except Exception as e:
            logger.error(f"Gemini API Error: {str(e)}")
            raise VLMException(f"VLM Provider Failure: {str(e)}")

    async def extract_fulfillment_evidence(
        self, 
        image_bytes: bytes, 
        mime_type: str, 
        ordered_quantity: int
    ) -> FulfillmentEvidenceSchema:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self._sync_extract, 
            image_bytes, 
            mime_type, 
            ordered_quantity
        )
