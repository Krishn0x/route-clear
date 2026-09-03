from app.core.config import settings
from app.services.vlm.base import BaseVLMProvider

def get_vlm_provider() -> BaseVLMProvider:
    if settings.VLM_PROVIDER.lower() == "mock":
        from app.services.vlm.mock import MockVLMProvider
        import logging
        logging.getLogger(__name__).warning("WARNING: Using MockVLMProvider. This should only be used in tests.")
        return MockVLMProvider()
    elif settings.VLM_PROVIDER.lower() == "gemini":
        from app.services.vlm.gemini import GeminiVLMProvider
        return GeminiVLMProvider()
    else:
        raise ValueError(f"Unsupported VLM provider: {settings.VLM_PROVIDER}")
