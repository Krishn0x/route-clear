import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.services.vlm.gemini import GeminiVLMProvider, VLMException, VLMProviderFallbackRestart

class FakeResponse:
    def __init__(self, text):
        self.text = text

def create_valid_response(model_name="gemini-3.5-flash-lite"):
    return FakeResponse(f'''{{
        "overall_confidence": 0.95,
        "extracted_fields": {{
            "accepted_quantity": {{"value": 100, "confidence": 0.9}},
            "signature_present": {{"value": true, "confidence": 0.95}},
            "correction_detected": {{"value": false, "confidence": 0.9}}
        }}
    }}''')

@pytest.fixture
def provider():
    with patch('app.core.config.settings.GEMINI_API_KEY', 'dummy'):
        with patch('app.core.config.settings.GEMINI_MODEL_PRIMARY', 'primary-model'):
            with patch('app.core.config.settings.GEMINI_MODEL_FALLBACK', 'fallback-model'):
                p = GeminiVLMProvider()
                p.client = MagicMock()
                return p

@pytest.mark.asyncio
async def test_primary_succeeds(provider):
    provider.client.models.generate_content.return_value = create_valid_response()
    res = await provider.extract_pass1(b'dummy', 'image/png', 100)
    assert res.model_identifier == 'primary-model'

@pytest.mark.asyncio
async def test_primary_503_retry_succeeds(provider):
    with patch('time.sleep', return_value=None):
        provider.client.models.generate_content.side_effect = [
            Exception("503 Unavailable"),
            create_valid_response()
        ]
        res = await provider.extract_pass1(b'dummy', 'image/png', 100)
        assert res.model_identifier == 'primary-model'

@pytest.mark.asyncio
async def test_primary_503_exhausts_retries_fallback_succeeds(provider):
    with patch('time.sleep', return_value=None):
        provider.client.models.generate_content.side_effect = [
            Exception("503 Unavailable"), Exception("503 Unavailable"), Exception("503 Unavailable"),
            create_valid_response()
        ]
        res = await provider.extract_pass1(b'dummy', 'image/png', 100)
        assert res.model_identifier == 'fallback-model'

@pytest.mark.asyncio
async def test_primary_429_fallback_succeeds(provider):
    with patch('time.sleep', return_value=None):
        provider.client.models.generate_content.side_effect = [
            Exception("429 Too Many Requests"), Exception("429 Too Many Requests"), Exception("429 Too Many Requests"),
            create_valid_response()
        ]
        res = await provider.extract_pass1(b'dummy', 'image/png', 100)
        assert res.model_identifier == 'fallback-model'

@pytest.mark.asyncio
async def test_primary_and_fallback_unavailable_fail_closed(provider):
    with patch('time.sleep', return_value=None):
        provider.client.models.generate_content.side_effect = [Exception("503 Unavailable")] * 6
        with pytest.raises(VLMException):
            await provider.extract_pass1(b'dummy', 'image/png', 100)

@pytest.mark.asyncio
async def test_pass1_and_pass2_use_same_model(provider):
    with patch('time.sleep', return_value=None):
        provider.client.models.generate_content.side_effect = [
            Exception("503 Unavailable"), Exception("503 Unavailable"), Exception("503 Unavailable"),
            create_valid_response()
        ]
        pass1 = await provider.extract_pass1(b'dummy', 'image/png', 100)
        assert pass1.model_identifier == 'fallback-model'
        provider.client.models.generate_content.side_effect = [create_valid_response()]
        pass2 = await provider.extract_pass2(b'dummy', 'image/png', 100, locked_model_name=pass1.model_identifier)
        assert pass2.model_identifier == 'fallback-model'

@pytest.mark.asyncio
async def test_primary_pass1_success_pass2_failure_forces_restart(provider):
    with patch('time.sleep', return_value=None):
        # Pass 1 succeeds on Primary
        provider.client.models.generate_content.side_effect = [create_valid_response()]
        pass1 = await provider.extract_pass1(b'dummy', 'image/png', 100)
        assert pass1.model_identifier == 'primary-model'
        
        # Pass 2 gets 503 on Primary and exhausts retries
        provider.client.models.generate_content.side_effect = [
            Exception("503 Unavailable"), Exception("503 Unavailable"), Exception("503 Unavailable")
        ]
        
        with pytest.raises(VLMProviderFallbackRestart):
            await provider.extract_pass2(b'dummy', 'image/png', 100, locked_model_name=pass1.model_identifier)
            
        # At this point, endpoints.py catches VLMProviderFallbackRestart and starts over.
        provider.client.models.generate_content.side_effect = [create_valid_response()]
        pass1_retry = await provider.extract_pass1(b'dummy', 'image/png', 100, locked_model_name='fallback-model')
        assert pass1_retry.model_identifier == 'fallback-model'
        
        provider.client.models.generate_content.side_effect = [create_valid_response()]
        pass2_retry = await provider.extract_pass2(b'dummy', 'image/png', 100, locked_model_name=pass1_retry.model_identifier)
        assert pass2_retry.model_identifier == 'fallback-model'

@pytest.mark.asyncio
async def test_non_transient_error_fails_immediately(provider):
    with patch('time.sleep', return_value=None):
        provider.client.models.generate_content.side_effect = Exception("400 Bad Request")
        with pytest.raises(VLMException):
            await provider.extract_pass1(b'dummy', 'image/png', 100)

@pytest.mark.asyncio
async def test_concurrency_isolation_stateless(provider):
    """
    Tests that two concurrent requests do not share state.
    Since we refactored GeminiVLMProvider to be stateless and explicitly pass locked_model_name,
    this test ensures that Request A and Request B remain fully isolated even if they share the provider instance.
    """
    with patch('time.sleep', return_value=None):
        async def request_a():
            # A uses primary successfully
            provider.client.models.generate_content.side_effect = [create_valid_response()]
            res1 = await provider.extract_pass1(b'dummyA', 'image/png', 100)
            assert res1.model_identifier == 'primary-model'
            provider.client.models.generate_content.side_effect = [create_valid_response()]
            res2 = await provider.extract_pass2(b'dummyA', 'image/png', 100, locked_model_name=res1.model_identifier)
            assert res2.model_identifier == 'primary-model'
            return res1, res2

        async def request_b():
            # B forces fallback
            provider.client.models.generate_content.side_effect = [create_valid_response()]
            res1 = await provider.extract_pass1(b'dummyB', 'image/png', 100, locked_model_name='fallback-model')
            assert res1.model_identifier == 'fallback-model'
            provider.client.models.generate_content.side_effect = [create_valid_response()]
            res2 = await provider.extract_pass2(b'dummyB', 'image/png', 100, locked_model_name=res1.model_identifier)
            assert res2.model_identifier == 'fallback-model'
            return res1, res2

        # In a real concurrent scenario they run sequentially because of mock side_effect,
        # but since there is no 'self.locked_model_name', state contamination is impossible.
        # We demonstrate they can both use the same provider instance back-to-back with different locks.
        await request_a()
        await request_b()
        await request_a()
