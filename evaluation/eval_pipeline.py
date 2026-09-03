import os
import json
import httpx
import time
from typing import Dict, Any
from datetime import datetime

API_URL = "http://127.0.0.1:8000/api"

def evaluate_document(image_path: str, ground_truth: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    print(f"Evaluating {os.path.basename(image_path)}...")
    
    # 1. Upload
    with open(image_path, "rb") as f:
        resp = httpx.post(
            f"{API_URL}/documents/upload",
            data={
                "transfer_id": f"tr_eval_{run_id}_{os.path.basename(image_path)}",
                "total_amount": "100000.00",
                "ordered_quantity": str(ground_truth["ordered_quantity"])
            },
            files={"file": (os.path.basename(image_path), f, "image/png")}
        )
        
    if resp.status_code != 200:
        return {"filename": os.path.basename(image_path), "error_type": "api_failure", "error_message": f"Upload failed: {resp.text}"}
        
    doc = resp.json()
    doc_id = doc["id"]
    
    # 2. Process
    try:
        resp = httpx.post(f"{API_URL}/documents/{doc_id}/process", timeout=60.0)
    except httpx.TimeoutException:
        return {"filename": os.path.basename(image_path), "error_type": "timeout", "error_message": "Request timed out after 60s"}
    except Exception as e:
        return {"filename": os.path.basename(image_path), "error_type": "api_failure", "error_message": f"Process request failed: {str(e)}"}
        
    if resp.status_code != 200:
        return {"filename": os.path.basename(image_path), "error_type": "api_failure", "error_message": f"Process failed: {resp.text}"}
        
    processed_doc = resp.json()
    
    if processed_doc.get("status") == "FAILED":
        return {"filename": os.path.basename(image_path), "error_type": "api_failure", "error_message": "VLM Exception inside backend"}
        
    evidence = processed_doc.get("evidence", {})
    validation = processed_doc.get("validation", {})
    
    if not evidence:
        return {"filename": os.path.basename(image_path), "error_type": "parsing_failure", "error_message": "No evidence extracted"}
        
    extracted = evidence.get("extracted_fields", {})
    
    # 3. Compare VLM Extraction
    def get_val(field_name):
        field = extracted.get(field_name)
        return field["value"] if field else None
        
    extraction_matches = {
        "accepted_quantity": get_val("accepted_quantity") == ground_truth["accepted_quantity"],
        "damaged_quantity": get_val("damaged_quantity") == ground_truth["damaged_quantity"],
        "rejected_quantity": get_val("rejected_quantity") == ground_truth["rejected_quantity"],
        "signature_present": get_val("signature_present") == ground_truth["signature_present"]
    }
    
    # 4. Compare Safety Engine Output
    actual_safety_passed = validation.get("passed", False)
    expected_safety_passed = ground_truth["expected_safety_passed"]
    
    safety_matches = {
        "passed_match": actual_safety_passed == expected_safety_passed,
        "false_safe": actual_safety_passed and not expected_safety_passed,
        "false_block": not actual_safety_passed and expected_safety_passed
    }
    
    return {
        "filename": os.path.basename(image_path),
        "status": "success",
        "extraction_matches": extraction_matches,
        "safety_matches": safety_matches,
        "provider": evidence.get("provider"),
        "model_identifier": evidence.get("model_identifier")
    }

def run_evaluation(dataset_dir: str):
    gt_file = os.path.join(dataset_dir, "ground_truth.json")
    if not os.path.exists(gt_file):
        print(f"Ground truth not found at {gt_file}")
        return
        
    with open(gt_file, "r") as f:
        metadata = json.load(f)
        
    results = []
    total = len(metadata)
    
    metrics = {
        "total": total,
        "successful_calls": 0,
        "timeouts": 0,
        "api_failures": 0,
        "parsing_failures": 0,
        "extraction_perfect": 0,
        "safety_perfect": 0,
        "false_safes": 0,
        "false_blocks": 0
    }
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    provider = "unknown"
    model_identifier = "unknown"
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for item in metadata:
            img_path = os.path.join(dataset_dir, item["filename"])
            futures.append(executor.submit(evaluate_document, img_path, item["ground_truth"], run_id))
            
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            
            if "error_type" in res:
                if res["error_type"] == "timeout":
                    metrics["timeouts"] += 1
                elif res["error_type"] == "api_failure":
                    metrics["api_failures"] += 1
                elif res["error_type"] == "parsing_failure":
                    metrics["parsing_failures"] += 1
            elif res.get("status") == "success":
                metrics["successful_calls"] += 1
                provider = res.get("provider", provider)
                model_identifier = res.get("model_identifier", model_identifier)
                
                if all(res["extraction_matches"].values()):
                    metrics["extraction_perfect"] += 1
                if res["safety_matches"]["passed_match"]:
                    metrics["safety_perfect"] += 1
                if res["safety_matches"]["false_safe"]:
                    metrics["false_safes"] += 1
                if res["safety_matches"]["false_block"]:
                    metrics["false_blocks"] += 1
            
    print(f"\n--- EVALUATION RESULTS ---")
    print(f"Total evaluated: {metrics['total']} | Success: {metrics['successful_calls']} | Timeouts: {metrics['timeouts']} | API Failures: {metrics['api_failures']} | Parsing Failures: {metrics['parsing_failures']}")
    if metrics['successful_calls'] > 0:
        print(f"Extraction Perfect Match: {metrics['extraction_perfect']}/{metrics['successful_calls']} ({metrics['extraction_perfect']/metrics['successful_calls']*100:.1f}%)")
        print(f"Safety Engine Accuracy: {metrics['safety_perfect']}/{metrics['successful_calls']} ({metrics['safety_perfect']/metrics['successful_calls']*100:.1f}%)")
    print(f"CRITICAL: False Safes: {metrics['false_safes']} | False Blocks: {metrics['false_blocks']}")
    
    output_data = {
        "metadata": {
            "evaluation_timestamp": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "vlm_provider": provider,
            "exact_model": model_identifier,
            "dataset_size": total
        },
        "metrics": metrics,
        "records": results
    }
    
    with open(os.path.join(dataset_dir, "eval_results.json"), "w") as f:
        json.dump(output_data, f, indent=2)

if __name__ == "__main__":
    run_evaluation("../dataset/images")
