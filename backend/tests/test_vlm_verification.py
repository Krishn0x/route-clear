import pytest
from app.services.vlm.mock import MockVLMProvider
from app.services.vlm.comparator import compare_passes, is_evidence_sufficient, resolve
from app.services.vlm.verification import should_run_pass2
from app.schemas.document import FulfillmentEvidenceSchema

@pytest.mark.asyncio
async def test_pass1_and_pass2_schema_validation():
    provider = MockVLMProvider()
    image = b"NORMAL_IMAGE"
    ordered_quantity = 105
    
    pass1 = await provider.extract_pass1(image, "image/png", ordered_quantity)
    assert isinstance(pass1, FulfillmentEvidenceSchema)
    assert pass1.extracted_fields.accepted_quantity.value == 95
    assert pass1.extracted_fields.document_type.value == "challan"

    # independence: pass 2 doesn't receive pass 1 or trigger_reasons, only original image and ordered_quantity
    trigger, reasons = should_run_pass2(pass1)
    assert trigger is True

    pass2 = await provider.extract_pass2(image, "image/png", ordered_quantity)
    assert isinstance(pass2, FulfillmentEvidenceSchema)
    assert pass2.extracted_fields.accepted_quantity.value == 95
    assert pass2.raw_vlm_output["pass_num"] == 2

@pytest.mark.asyncio
async def test_pass_comparison_safe_agreement():
    provider = MockVLMProvider()
    image = b"NORMAL_IMAGE"
    ordered_quantity = 105
    
    pass1 = await provider.extract_pass1(image, "image/png", ordered_quantity)
    pass2 = await provider.extract_pass2(image, "image/png", ordered_quantity)
    
    comp = compare_passes(pass1, pass2, ["always_run_v2"])
    assert comp.all_fields_agreed is True
    assert comp.max_numeric_delta == 0
    
    suff, failures = is_evidence_sufficient(pass1, pass2, comp)
    assert suff is True
    assert len(failures) == 0
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is False
    assert res.resolution_method == "ai_consistent_and_grounded"
    assert res.resolved_accepted == 95

@pytest.mark.asyncio
async def test_quantity_disagreement_model_conflict():
    provider = MockVLMProvider()
    image = b"NORMAL_IMAGE" 
    ordered_quantity = 80 # ordered_quantity=80 is used to trigger conflict in mock
    
    pass1 = await provider.extract_pass1(image, "image/png", ordered_quantity)
    pass2 = await provider.extract_pass2(image, "image/png", ordered_quantity)
    
    # P1: accepted 75. P2: accepted 70.
    comp = compare_passes(pass1, pass2, [])
    assert comp.all_fields_agreed is False
    assert comp.max_numeric_delta == 5
    
    suff, failures = is_evidence_sufficient(pass1, pass2, comp)
    assert suff is False
    assert "Pass 1 and Pass 2 disagreed on material fields" in failures
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is True
    assert res.resolution_method == "human_review_disagreement"

@pytest.mark.asyncio
async def test_low_evidence():
    provider = MockVLMProvider()
    image = b"LOW_EVIDENCE"
    ordered_quantity = 105
    
    pass1 = await provider.extract_pass1(image, "image/png", ordered_quantity)
    pass2 = await provider.extract_pass2(image, "image/png", ordered_quantity)
    
    comp = compare_passes(pass1, pass2, [])
    # Even if they agree on being low confidence (null values), they fail sufficiency
    suff, failures = is_evidence_sufficient(pass1, pass2, comp)
    assert suff is False
    assert any("Overall confidence below threshold" in f for f in failures)
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is True

@pytest.mark.asyncio
async def test_prompt_injection_detection():
    provider = MockVLMProvider()
    image = b"INJECTION"
    ordered_quantity = 105
    
    pass1 = await provider.extract_pass1(image, "image/png", ordered_quantity)
    pass2 = await provider.extract_pass2(image, "image/png", ordered_quantity)
    
    comp = compare_passes(pass1, pass2, [])
    suff, failures = is_evidence_sufficient(pass1, pass2, comp)
    assert suff is False
    assert any("Suspicious document content detected" in f for f in failures)
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is True

@pytest.mark.asyncio
async def test_consistent_but_wrong():
    """
    CORRECTION 2: Explicitly documenting the 'consistent but wrong' scenario.

    Context:
      ordered_quantity = 105
      GROUND TRUTH (Actual physical document): accepted=50, damaged=55, rejected=0.
      
    Mock AI behavior:
      Pass 1 outputs: accepted=105, damaged=0, rejected=0
      Pass 2 outputs: accepted=105, damaged=0, rejected=0

    Purpose of this test:
      To prove that (Pass 1 == Pass 2) passing the evidence sufficiency gate
      does NOT prove the extracted values are the absolute truth.
      The AI verified itself, but both passes consistently hallucinated.

    Conclusion:
      Agreement is merely evidence of system consistency, not a proof of truth.
      The later deterministic Safety Engine must independently guard the financial action.
    """
    provider = MockVLMProvider()
    image = b"CONSISTENT_WRONG"
    ordered_quantity = 105
    
    pass1 = await provider.extract_pass1(image, "image/png", ordered_quantity)
    pass2 = await provider.extract_pass2(image, "image/png", ordered_quantity)
    
    # Prove that the comparator successfully agrees
    comp = compare_passes(pass1, pass2, [])
    assert comp.all_fields_agreed is True
    
    # Prove that the evidence sufficiency gate passes this!
    # (Because the gate checks structural sufficiency, not ground truth)
    suff, failures = is_evidence_sufficient(pass1, pass2, comp)
    assert suff is True
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is False
    assert res.resolved_accepted == 105
    
    # Explicitly asserting the note we added in the mock to document this limitation
    assert pass1.raw_vlm_output["note"] == "AI agrees but is WRONG compared to physical document"

def test_null_vs_value_disagreement():
    provider = MockVLMProvider()
    pass1 = provider._generate_fixture(105, 1)
    pass2 = provider._generate_fixture(105, 2)
    
    pass2.extracted_fields.accepted_quantity = None
    
    comp = compare_passes(pass1, pass2, [])
    assert comp.all_fields_agreed is False
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is True

def test_document_type_disagreement():
    provider = MockVLMProvider()
    pass1 = provider._generate_fixture(105, 1)
    pass2 = provider._generate_fixture(105, 2)
    
    pass2.extracted_fields.document_type.value = "invoice"
    
    comp = compare_passes(pass1, pass2, [])
    assert comp.all_fields_agreed is False
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is True

def test_correction_detection_forces_human_review():
    provider = MockVLMProvider()
    pass1 = provider._generate_fixture(105, 1)
    pass2 = provider._generate_fixture(105, 2)
    
    pass1.extracted_fields.correction_detected.value = True
    pass2.extracted_fields.correction_detected.value = True
    
    comp = compare_passes(pass1, pass2, [])
    assert comp.all_fields_agreed is True # they agree there is a correction
    
    suff, failures = is_evidence_sufficient(pass1, pass2, comp)
    assert suff is False
    assert any("Unresolved handwritten corrections" in f for f in failures)
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is True

def test_ungrounded_evidence_forces_human_review():
    provider = MockVLMProvider()
    pass1 = provider._generate_fixture(105, 1)
    pass2 = provider._generate_fixture(105, 2)
    
    # Simulate a hallucination without grounded evidence
    pass1.extracted_fields.accepted_quantity.evidence_region = None
    pass2.extracted_fields.accepted_quantity.evidence_region = None
    
    comp = compare_passes(pass1, pass2, [])
    assert comp.all_fields_agreed is True # They agree perfectly
    
    suff, failures = is_evidence_sufficient(pass1, pass2, comp)
    assert suff is False
    assert any("Missing evidence region for accepted_quantity" in f for f in failures)
    
    res = resolve(pass1, pass2, comp)
    assert res.requires_human_review is True
    assert res.resolution_method == "human_review_insufficient"

@pytest.mark.asyncio
async def test_vlm_timeout_error_propagation():
    import asyncio
    from app.services.vlm.gemini import GeminiVLMProvider, VLMException
    
    provider = GeminiVLMProvider()
    provider.api_key = "INVALID"
    
    with pytest.raises(VLMException):
        await provider.extract_pass1(b"image", "image/png", 105)
