from app.schemas.document import FulfillmentEvidenceSchema

PASS2_TRIGGER_CONDITIONS = [
    # Conditions that would force a pass 2 in an optimized architecture
    ("always_run_v2",             lambda ev: True),  # V2 Rule: Always run two passes
    ("overall_confidence_low",    lambda ev: ev.overall_confidence < 0.88),
    ("accepted_confidence_low",   lambda ev: ev.extracted_fields.accepted_quantity and
                                             ev.extracted_fields.accepted_quantity.confidence < 0.82),
    ("correction_detected",       lambda ev: ev.extracted_fields.correction_detected and
                                             ev.extracted_fields.correction_detected.value is True),
    ("suspicious_content",        lambda ev: getattr(ev.extracted_fields, "suspicious_content_detected", None) and
                                             ev.extracted_fields.suspicious_content_detected.value is True),
    ("document_type_unknown",     lambda ev: getattr(ev.extracted_fields, "document_type", None) and
                                             ev.extracted_fields.document_type.value == "unknown"),
]

def should_run_pass2(pass1: FulfillmentEvidenceSchema) -> tuple[bool, list[str]]:
    """
    Determines if Pass 2 should be run.
    For V2, this is ALWAYS True. We return the specific reasons to populate the audit log.
    """
    triggered = []
    for name, condition in PASS2_TRIGGER_CONDITIONS:
        try:
            if condition(pass1):
                triggered.append(name)
        except Exception:
            pass
            
    # In V2, we enforce a two-pass verification loop for ALL financially actionable documents
    return True, triggered
