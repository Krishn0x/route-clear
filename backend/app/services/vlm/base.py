from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.document import FulfillmentEvidenceSchema

class BaseVLMProvider(ABC):
    """
    Provider-independent interface for Vision-Language Models.
    Ensures that the application is not tightly coupled to any single vendor.
    """

    @abstractmethod
    async def extract_fulfillment_evidence(
        self, 
        image_bytes: bytes, 
        mime_type: str, 
        ordered_quantity: int
    ) -> FulfillmentEvidenceSchema:
        """
        Extracts fulfillment evidence from a scanned document/image.

        Args:
            image_bytes: The raw bytes of the image/document.
            mime_type: The MIME type of the document (e.g., 'image/jpeg').
            ordered_quantity: The expected ordered quantity for context.

        Returns:
            FulfillmentEvidenceSchema containing extracted fields, confidences,
            and bounding box evidence.
        """
        pass
