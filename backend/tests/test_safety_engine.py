import pytest
from decimal import Decimal
from app.services.safety.engine import SafetyEngine
from app.schemas.document import PolicyConfig, FulfillmentEvidenceSchema, FulfillmentFields, FieldEvidence
from app.db.models import Document

def create_mock_document(ordered: int, total_amount: str = "100000.00") -> Document:
    return Document(
        id="test_doc",
        transfer_id="tr_123",
        ordered_quantity=ordered,
        total_amount=Decimal(total_amount)
    )

def create_mock_evidence(accepted: int, damaged: int, rejected: int, signature: bool = True) -> FulfillmentEvidenceSchema:
    return FulfillmentEvidenceSchema(
        provider="mock",
        model_identifier="mock-model",
        overall_confidence=0.95,
        extracted_fields=FulfillmentFields(
            accepted_quantity=FieldEvidence[int](value=accepted, confidence=0.95),
            damaged_quantity=FieldEvidence[int](value=damaged, confidence=0.95),
            rejected_quantity=FieldEvidence[int](value=rejected, confidence=0.95),
            signature_present=FieldEvidence[bool](value=signature, confidence=0.95),
            correction_detected=FieldEvidence[bool](value=False, confidence=0.95)
        )
    )

def test_case_1_valid_fulfillment():
    doc = create_mock_document(100)
    evidence = create_mock_evidence(90, 10, 0)
    engine = SafetyEngine(PolicyConfig())
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is True
    assert val.unaccounted_quantity == 0
    assert dec.approved_release_amount == Decimal("90000.00")
    assert dec.proposed_reversal_amount == Decimal("10000.00")
    assert dec.requires_human_review is False

def test_case_2_unaccounted_quantity():
    doc = create_mock_document(100)
    evidence = create_mock_evidence(70, 10, 0)
    engine = SafetyEngine(PolicyConfig(require_human_review_for_unaccounted_quantity=True))
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is False
    assert val.unaccounted_quantity == 20
    assert dec.requires_human_review is True

def test_case_3_exceeds_ordered():
    doc = create_mock_document(100)
    evidence = create_mock_evidence(110, 0, 0)
    engine = SafetyEngine(PolicyConfig())
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is False
    assert dec.requires_human_review is True
    assert any("Sum of accepted, damaged, and rejected exceeds ordered quantity" in r for r in val.failure_reasons)

def test_case_4_negative_quantity():
    doc = create_mock_document(100)
    evidence = create_mock_evidence(-5, 5, 0)
    engine = SafetyEngine(PolicyConfig())
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is False
    assert dec.requires_human_review is True
    assert any("Negative quantities detected" in r for r in val.failure_reasons)

def test_case_5_total_exceeds():
    doc = create_mock_document(100)
    evidence = create_mock_evidence(90, 20, 0)
    engine = SafetyEngine(PolicyConfig())
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is False
    assert dec.requires_human_review is True

def test_case_6_missing_signature():
    doc = create_mock_document(100)
    evidence = create_mock_evidence(90, 10, 0, signature=False)
    engine = SafetyEngine(PolicyConfig(signature_required=True))
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is False
    assert dec.requires_human_review is True
    assert any("Missing required signature" in r for r in val.failure_reasons)

def test_financial_calculations():
    # total=100000, ordered=100, accepted=90
    doc = create_mock_document(100, "100000.00")
    evidence = create_mock_evidence(90, 10, 0)
    engine = SafetyEngine(PolicyConfig())
    val, dec = engine.evaluate(doc, evidence)
    
    assert dec.approved_release_amount == Decimal("90000.00")
    assert dec.proposed_reversal_amount == Decimal("10000.00")
    assert dec.approved_release_amount + dec.proposed_reversal_amount == doc.total_amount

def test_financial_calculations_fraction():
    # total=100, ordered=3, accepted=1
    doc = create_mock_document(3, "100.00")
    evidence = create_mock_evidence(1, 2, 0)
    engine = SafetyEngine(PolicyConfig(maximum_auto_reversal_percentage=100.0))
    val, dec = engine.evaluate(doc, evidence)
    
    # 100 / 3 = 33.333... Decimal will retain precision during unit price * qty
    # But let's check how Decimal handles division. Python Decimal divides perfectly up to getcontext precision.
    # approved_release_amount = 1 * (100 / 3)
    # proposed_reversal = 100 - approved_release_amount
    assert dec.approved_release_amount + dec.proposed_reversal_amount == Decimal("100.00")

def test_case_7_missing_field_is_null():
    doc = create_mock_document(100)
    # accepted is None (missing field)
    evidence = FulfillmentEvidenceSchema(
        provider="mock",
        model_identifier="mock-model",
        overall_confidence=0.95,
        extracted_fields=FulfillmentFields(
            accepted_quantity=None, # Missing
            damaged_quantity=FieldEvidence[int](value=0, confidence=0.95),
            rejected_quantity=FieldEvidence[int](value=0, confidence=0.95),
            signature_present=FieldEvidence[bool](value=True, confidence=0.95),
            correction_detected=FieldEvidence[bool](value=False, confidence=0.95)
        )
    )
    engine = SafetyEngine(PolicyConfig())
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is False # Because accepted=0, damaged=0, rejected=0 => unaccounted = 100
    assert val.unaccounted_quantity == 100
    assert dec.requires_human_review is True

def test_case_8_explicit_zero():
    doc = create_mock_document(100)
    # accepted is 0, damaged is 100. Explicit zeros.
    evidence = FulfillmentEvidenceSchema(
        provider="mock",
        model_identifier="mock-model",
        overall_confidence=0.95,
        extracted_fields=FulfillmentFields(
            accepted_quantity=FieldEvidence[int](value=0, confidence=0.95),
            damaged_quantity=FieldEvidence[int](value=100, confidence=0.95),
            rejected_quantity=FieldEvidence[int](value=0, confidence=0.95),
            signature_present=FieldEvidence[bool](value=True, confidence=0.95),
            correction_detected=FieldEvidence[bool](value=False, confidence=0.95)
        )
    )
    # If reversal_limit is default 10.0%, rejecting 100 will fail auto-reversal
    engine = SafetyEngine(PolicyConfig())
    val, dec = engine.evaluate(doc, evidence)
    assert val.passed is False
    assert val.unaccounted_quantity == 0
    assert any("exceeds auto maximum" in r for r in val.failure_reasons)
    
def test_case_9_reversal_limit_check():
    doc = create_mock_document(100)
    # 50 damaged => 50% reversal
    evidence = create_mock_evidence(50, 50, 0)
    engine_strict = SafetyEngine(PolicyConfig(maximum_auto_reversal_percentage=10.0))
    val1, dec1 = engine_strict.evaluate(doc, evidence)
    assert val1.passed is False
    
    engine_lenient = SafetyEngine(PolicyConfig(maximum_auto_reversal_percentage=60.0))
    val2, dec2 = engine_lenient.evaluate(doc, evidence)
    assert val2.passed is True
