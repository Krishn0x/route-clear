import json
import logging
from typing import Optional, List
from app.schemas.document import FulfillmentEvidenceSchema
from app.services.vlm.base import BaseVLMProvider
from app.services.vlm.prompt import PASS1_PROMPT, PASS2_PROMPT
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

    def _sync_extract(self, prompt: str, image_bytes: bytes, mime_type: str) -> FulfillmentEvidenceSchema:
        try:
            from google import genai
            # Prepare image part
            image_part = genai.types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            )
            
            # The schema_template is expected in the prompt. We provide a dummy one to avoid format error,
            # but ideally it would be generated using Pydantic. For this prototype, we'll just insert a generic template.
            # (Note: In a robust setup, you'd pass a JSON schema string here).
            schema_template = "{}"
            formatted_prompt = prompt.replace("{schema_template}", schema_template)
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[formatted_prompt, image_part],
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

    async def extract_pass1(
        self, 
        image_bytes: bytes, 
        mime_type: str, 
        ordered_quantity: int
    ) -> FulfillmentEvidenceSchema:
        loop = asyncio.get_event_loop()
        prompt = PASS1_PROMPT.replace("{ordered_quantity}", str(ordered_quantity))
        return await loop.run_in_executor(
            self.executor, 
            self._sync_extract,
            prompt,
            image_bytes, 
            mime_type
        )

    async def extract_pass2(
        self, 
        image_bytes: bytes, 
        mime_type: str,
        ordered_quantity: int
    ) -> FulfillmentEvidenceSchema:
        loop = asyncio.get_event_loop()
        prompt = PASS2_PROMPT.replace("{ordered_quantity}", str(ordered_quantity))
        return await loop.run_in_executor(
            self.executor, 
            self._sync_extract,
            prompt,
            image_bytes, 
            mime_type
        )
