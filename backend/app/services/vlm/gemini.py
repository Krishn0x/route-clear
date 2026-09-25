import json
import logging
from typing import Optional, List
from pydantic import BaseModel
from app.schemas.document import FulfillmentEvidenceSchema, FulfillmentFields
from app.services.vlm.base import BaseVLMProvider
from app.services.vlm.prompt import PASS1_PROMPT, PASS2_PROMPT
from app.core.config import settings
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)

class VLMException(Exception):
    pass

class VLMProviderFallbackRestart(VLMException):
    pass

class ExpectedVLMOutput(BaseModel):
    overall_confidence: float
    extracted_fields: FulfillmentFields

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

        self.primary_model = settings.GEMINI_MODEL_PRIMARY
        self.fallback_model = settings.GEMINI_MODEL_FALLBACK
        self.executor = ThreadPoolExecutor(max_workers=5)

    def _is_transient(self, e: Exception) -> bool:
        from google.genai.errors import APIError
        import urllib.error
        import socket

        if isinstance(e, (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError)):
            return True

        if isinstance(e, APIError):
            code = getattr(e, 'code', None)
            if code in (429, 500, 502, 503, 504):
                return True
            status = getattr(e, 'status', None)
            if status in (429, 500, 502, 503, 504):
                return True
            msg = str(getattr(e, 'message', ''))
            if any(str(c) in msg for c in (429, 500, 502, 503, 504)):
                return True

        err_str = str(e)
        if any(str(c) in err_str for c in (429, 500, 502, 503, 504)):
            return True
        if 'timeout' in err_str.lower() or 'connection' in err_str.lower():
            return True

        return False

    def _try_model_with_retries(self, model_name: str, formatted_prompt: str, image_part) -> FulfillmentEvidenceSchema:
        from google import genai

        max_retries = 2
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[formatted_prompt, image_part],
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ExpectedVLMOutput
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
                    model_identifier=model_name,
                    extracted_fields=parsed_json.get("extracted_fields", {}),
                    overall_confidence=parsed_json.get("overall_confidence", 0.0),
                    raw_vlm_output=parsed_json
                )
            except Exception as e:
                if not self._is_transient(e):
                    if isinstance(e, VLMException):
                        raise
                    raise VLMException(f"VLM Provider Failure: {str(e)}")

                logger.warning(f"Transient error for {model_name} on attempt {attempt + 1}: {str(e)}")
                last_exception = e

                if attempt < max_retries:
                    sleep_time = 1.0 * (2 ** attempt)
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Exhausted retries for {model_name}")
                    break

        raise last_exception

    def _sync_extract(self, prompt: str, image_bytes: bytes, mime_type: str, locked_model_name: Optional[str] = None) -> FulfillmentEvidenceSchema:
        from google import genai
        image_part = genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        schema_template = json.dumps(ExpectedVLMOutput.model_json_schema(), indent=2)
        formatted_prompt = prompt.replace("{schema_template}", schema_template)

        if locked_model_name:
            try:
                return self._try_model_with_retries(locked_model_name, formatted_prompt, image_part)
            except Exception as e:
                if isinstance(e, VLMException) and not isinstance(e, VLMProviderFallbackRestart):
                    raise
                if locked_model_name == self.primary_model:
                    raise VLMProviderFallbackRestart(f"Primary model unavailable, requesting restart: {str(e)}")
                raise VLMException("Gemini provider unavailable after bounded retries on locked model.")

        try:
            res = self._try_model_with_retries(self.primary_model, formatted_prompt, image_part)
            return res
        except Exception as e:
            if isinstance(e, VLMException):
                raise
            logger.warning(f"Primary model {self.primary_model} unavailable, activating fallback {self.fallback_model}")

        try:
            res = self._try_model_with_retries(self.fallback_model, formatted_prompt, image_part)
            return res
        except Exception as e:
            if isinstance(e, VLMException):
                raise
            raise VLMException("Gemini provider unavailable after bounded retries and fallback.")

    async def extract_pass1(
        self,
        image_bytes: bytes,
        mime_type: str,
        ordered_quantity: int,
        locked_model_name: Optional[str] = None
    ) -> FulfillmentEvidenceSchema:
        loop = asyncio.get_event_loop()
        prompt = PASS1_PROMPT.replace("{ordered_quantity}", str(ordered_quantity))
        return await loop.run_in_executor(
            self.executor,
            self._sync_extract,
            prompt,
            image_bytes,
            mime_type,
            locked_model_name
        )

    async def extract_pass2(
        self,
        image_bytes: bytes,
        mime_type: str,
        ordered_quantity: int,
        locked_model_name: Optional[str] = None
    ) -> FulfillmentEvidenceSchema:
        loop = asyncio.get_event_loop()
        prompt = PASS2_PROMPT.replace("{ordered_quantity}", str(ordered_quantity))
        return await loop.run_in_executor(
            self.executor,
            self._sync_extract,
            prompt,
            image_bytes,
            mime_type,
            locked_model_name
        )
