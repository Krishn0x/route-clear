import os
import json
from decimal import Decimal
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.services.safety.engine import SafetyEngine
from app.schemas.document import FulfillmentEvidenceSchema, SafetyValidationResult, PolicyConfig

def run_safety_eval(dataset_dir: str):
    gt_file = os.path.join(dataset_dir, "ground_truth.json")
    with open(gt_file, "r") as f:
        metadata = json.load(f)

    metrics = {
        "evaluation_type": "deterministic_safety_only",
        "policy_thresholds": {
            "auto_reversal_limit": "50.0%"
        },
        "total": len(metadata),
        "valid_records": len(metadata),
        "approved": 0,
        "blocked": 0,
        "false_safes": 0,
        "false_blocks": 0,
        "perfect_safety": 0
    }
    
    scenario_metrics = {}
    failures = []

    for item in metadata:
        filename = item["filename"]
        gt = item["ground_truth"]
        scenario = item.get("scenario", "standard")
        
        if scenario not in scenario_metrics:
            scenario_metrics[scenario] = {"total": 0, "approved": 0, "blocked": 0, "false_safes": 0, "false_blocks": 0, "correct": 0}
            
        scenario_metrics[scenario]["total"] += 1
        
        # Construct evidence straight from Ground Truth (simulating PERFECT extraction)
        mock_evidence_fields = {
            "accepted_quantity": {"value": gt["accepted_quantity"], "confidence": 0.99, "warnings": []} if gt.get("accepted_quantity") is not None else None,
            "damaged_quantity": {"value": gt["damaged_quantity"], "confidence": 0.99, "warnings": []} if gt.get("damaged_quantity") is not None else None,
            "rejected_quantity": {"value": gt["rejected_quantity"], "confidence": 0.99, "warnings": []} if gt.get("rejected_quantity") is not None else None,
            "signature_present": {"value": gt.get("signature_present", True), "confidence": 0.99, "warnings": []},
            "correction_detected": {"value": False, "confidence": 0.99, "warnings": []}
        }
        
        evidence = FulfillmentEvidenceSchema(
            provider="ground_truth",
            model_identifier="gt-perfect",
            extracted_fields=mock_evidence_fields,
            overall_confidence=0.99,
            raw_vlm_output={}
        )
        
        engine = SafetyEngine(PolicyConfig())
        class MockDoc:
            ordered_quantity = gt["ordered_quantity"]
            total_amount = Decimal("100000.00")
            id = "mock"
            transfer_id = "mock_tr"
        
        result, decision = engine.evaluate(
            doc=MockDoc(),
            evidence=evidence
        )
        
        expected_passed = gt["expected_safety_passed"]
        actual_passed = result.passed
        
        if actual_passed:
            metrics["approved"] += 1
            scenario_metrics[scenario]["approved"] += 1
        else:
            metrics["blocked"] += 1
            scenario_metrics[scenario]["blocked"] += 1
            
        is_false_safe = actual_passed and not expected_passed
        is_false_block = not actual_passed and expected_passed
        
        if is_false_safe:
            metrics["false_safes"] += 1
            scenario_metrics[scenario]["false_safes"] += 1
            failures.append(f"{filename} [FALSE SAFE]: Expected BLOCKED, got APPROVED. Scenario: {scenario}")
        elif is_false_block:
            metrics["false_blocks"] += 1
            scenario_metrics[scenario]["false_blocks"] += 1
            failures.append(f"{filename} [FALSE BLOCK]: Expected APPROVED, got BLOCKED. Reasons: {result.failure_reasons}. Scenario: {scenario}")
        else:
            metrics["perfect_safety"] += 1
            scenario_metrics[scenario]["correct"] += 1
            
        # Verify Invariant: accepted + damaged + rejected <= ordered
        acc = gt.get("accepted_quantity") or 0
        dam = gt.get("damaged_quantity") or 0
        rej = gt.get("rejected_quantity") or 0
        unaccounted = gt["ordered_quantity"] - (acc + dam + rej)
        
        if (acc + dam + rej) > gt["ordered_quantity"]:
            metrics.setdefault("invariant_violations_in_dataset", 0)
            metrics["invariant_violations_in_dataset"] += 1
            
        if decision:
            if decision.requires_human_review != (not actual_passed):
                failures.append(f"{filename} [DECISION MISMATCH]: human_review={decision.requires_human_review} != blocked={not actual_passed}")
        else:
            if not actual_passed:
                failures.append(f"{filename} [DECISION MISSING]: Validation failed but no decision returned")
            
    print("--- 150-RECORD DETERMINISTIC SAFETY EVALUATION ---")
    print(json.dumps(metrics, indent=2))
    print("\n--- PER-SCENARIO METRICS ---")
    print(json.dumps(scenario_metrics, indent=2))
    
    if failures:
        print("\n--- FAILURES ---")
        for f in failures:
            print(f)
            
    with open("safety_eval_results.json", "w") as f:
        json.dump({"metrics": metrics, "scenario_metrics": scenario_metrics, "failures": failures}, f, indent=2)

if __name__ == "__main__":
    run_safety_eval("../dataset/images")
