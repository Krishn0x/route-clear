from app.schemas.document import FulfillmentEvidenceSchema, ComparisonResult, ResolutionResult, FieldAgreement

MAX_ACCEPTABLE_DELTA = 0  # Zero tolerance for quantity disagreement in auto-approval

def compare_passes(pass1: FulfillmentEvidenceSchema, 
                   pass2: FulfillmentEvidenceSchema,
                   triggered_by: list[str]) -> ComparisonResult:
    """
    Deterministically compares Pass 1 and Pass 2 for exact agreement.
    No fuzzy matching for quantities.
    """
    quantity_fields = ["accepted_quantity", "damaged_quantity", "rejected_quantity"]
    disagreements = []
    agreements = []
    max_delta = 0

    # Compare quantity fields
    for field_name in quantity_fields:
        f1 = getattr(pass1.extracted_fields, field_name, None)
        f2 = getattr(pass2.extracted_fields, field_name, None)
        
        v1 = f1.value if f1 else None
        v2 = f2.value if f2 else None
        c1 = f1.confidence if f1 else 0.0
        c2 = f2.confidence if f2 else 0.0

        agreed = (v1 == v2)
        delta = abs(v1 - v2) if (v1 is not None and v2 is not None) else None
        if delta is not None:
            max_delta = max(max_delta, delta)

        fa = FieldAgreement(field=field_name, pass1_value=v1, pass2_value=v2,
                            pass1_confidence=c1, pass2_confidence=c2,
                            agreed=agreed, delta=delta)
        (agreements if agreed else disagreements).append(fa)

    # Compare signature
    s1 = pass1.extracted_fields.signature_present
    s2 = pass2.extracted_fields.signature_present
    sig_agreed = (s1.value == s2.value) if (s1 and s2) else False
    sig_fa = FieldAgreement(
        field="signature_present", 
        pass1_value=s1.value if s1 else None, 
        pass2_value=s2.value if s2 else None,
        pass1_confidence=s1.confidence if s1 else 0.0, 
        pass2_confidence=s2.confidence if s2 else 0.0,
        agreed=sig_agreed
    )
    (agreements if sig_agreed else disagreements).append(sig_fa)
    
    # Compare document type
    dt1 = pass1.extracted_fields.document_type
    dt2 = pass2.extracted_fields.document_type
    dt_agreed = (dt1.value == dt2.value) if (dt1 and dt2) else (dt1 is None and dt2 is None)
    dt_fa = FieldAgreement(
        field="document_type",
        pass1_value=dt1.value if dt1 else None,
        pass2_value=dt2.value if dt2 else None,
        pass1_confidence=dt1.confidence if dt1 else 0.0,
        pass2_confidence=dt2.confidence if dt2 else 0.0,
        agreed=dt_agreed
    )
    (agreements if dt_agreed else disagreements).append(dt_fa)

    all_fields_agreed = (len(disagreements) == 0)

    return ComparisonResult(
        all_fields_agreed=all_fields_agreed,
        disagreements=disagreements,
        agreements=agreements,
        max_numeric_delta=max_delta,
        comparison_triggered_by=triggered_by
    )

def is_evidence_sufficient(pass1: FulfillmentEvidenceSchema, pass2: FulfillmentEvidenceSchema, comparison: ComparisonResult) -> tuple[bool, list[str]]:
    """
    Evidence Sufficiency Gate.
    Determines if the agreed evidence is structurally sufficient to proceed to financial safety checks.
    """
    failures = []
    
    if not comparison.all_fields_agreed:
        failures.append("Pass 1 and Pass 2 disagreed on material fields")
        
    f1 = pass1.extracted_fields
    
    # Suspicious Content Check
    suspicious = getattr(f1, "suspicious_content_detected", None)
    if suspicious and suspicious.value is True:
        failures.append("Suspicious document content detected (potential prompt injection)")
        
    # Document Type Check
    doc_type = getattr(f1, "document_type", None)
    if not doc_type or doc_type.value == "unknown":
        failures.append("Document type is unknown or invalid")
        
    # Unresolved Corrections
    correction = getattr(f1, "correction_detected", None)
    if correction and correction.value is True:
        failures.append("Unresolved handwritten corrections detected on document")
        
    # Minimum Confidence Checks
    if pass1.overall_confidence < 0.88 or pass2.overall_confidence < 0.88:
        failures.append("Overall confidence below threshold")
        
    # Phase 2.5: Evidence Groundedness Check
    # Any non-zero quantity must provide an evidence_region.
    # Note: A region being present does NOT mean it is factually correct.
    # It only means the model supplied a spatial location for its claim, preserving auditability.
    for q_field in ["accepted_quantity", "damaged_quantity", "rejected_quantity"]:
        f_val = getattr(f1, q_field, None)
        if f_val and f_val.value is not None and f_val.value > 0:
            if not f_val.evidence_region:
                failures.append(f"Missing evidence region for {q_field}")
                
    return (len(failures) == 0, failures)

def resolve(pass1: FulfillmentEvidenceSchema, pass2: FulfillmentEvidenceSchema, comparison: ComparisonResult) -> ResolutionResult:
    """
    CRITICAL: Agreement between Pass 1 and Pass 2 does NOT prove truth.
    Both passes could hallucinate consistently (optimistic hallucination).
    The Safety Engine's arithmetic invariant is the last line of defense.
    We record the agreement/disagreement but do NOT treat agreement as ground truth.
    """
    sufficient, failures = is_evidence_sufficient(pass1, pass2, comparison)
    
    if not sufficient:
        return ResolutionResult(
            resolved_accepted=None, resolved_damaged=None,
            resolved_rejected=None, resolved_signature=None,
            resolution_method="human_review_insufficient" if comparison.all_fields_agreed else "human_review_disagreement",
            requires_human_review=True,
            human_review_reason="; ".join(failures)
        )

    f = pass1.extracted_fields
    return ResolutionResult(
        resolved_accepted=f.accepted_quantity.value if f.accepted_quantity else None,
        resolved_damaged=f.damaged_quantity.value if f.damaged_quantity else None,
        resolved_rejected=f.rejected_quantity.value if f.rejected_quantity else None,
        resolved_signature=f.signature_present.value if f.signature_present else None,
        resolution_method="ai_consistent_and_grounded",
        requires_human_review=False,
        human_review_reason=None
    )
