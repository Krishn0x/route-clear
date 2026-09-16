from abc import ABC, abstractmethod
from typing import Optional, List
from app.schemas.document import FulfillmentEvidenceSchema

class BaseVLMProvider(ABC):
    """
    Provider-independent interface for Vision-Language Models.
    Updated for V2 Two-Pass Architecture.
    """

    @abstractmethod
    async def extract_pass1(
        self, 
        image_bytes: bytes, 
        mime_type: str, 
        ordered_quantity: int
    ) -> FulfillmentEvidenceSchema:
        """
        Pass 1: Independent extraction of evidence from the original document.
        """
        pass

    @abstractmethod
    async def extract_pass2(
        self, 
        image_bytes: bytes, 
        mime_type: str,
        ordered_quantity: int
    ) -> FulfillmentEvidenceSchema:
        """
        Pass 2: Independent verification of the original document.
        Must NOT receive Pass 1 results or dynamic trigger reasons.
        """
        pass
