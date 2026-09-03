import os
import json
import httpx
import time
from typing import Dict, Any

API_URL = "http://127.0.0.1:8000/api"

def evaluate_smoke(image_path: str, ground_truth: Dict[str, Any]) -> Dict[str, Any]:
    print(f"Testing {os.path.basename(image_path)}...")
    
    start_time = time.time()
    
    import uuid
    # 1. Upload
    with open(image_path, "rb") as f:
        resp = httpx.post(
            f"{API_URL}/documents/upload",
            data={
                "transfer_id": f"tr_eval_{os.path.basename(image_path)}_{uuid.uuid4().hex[:8]}",
                "total_amount": "100000.00",
                "ordered_quantity": str(ground_truth["ordered_quantity"])
            },
            files={"file": (os.path.basename(image_path), f, "image/png")}
        )
        
    if resp.status_code != 200:
        return {"error": f"Upload failed: {resp.text}"}
        
    doc = resp.json()
    doc_id = doc["id"]
    
    # 2. Process
    process_start = time.time()
    try:
        resp = httpx.post(f"{API_URL}/documents/{doc_id}/process", timeout=30.0)
    except Exception as e:
        return {"error": f"Process request failed: {str(e)}"}
        
    latency = time.time() - process_start
    total_latency = time.time() - start_time
    
    if resp.status_code != 200:
        return {"error": f"Process API failed (Status {resp.status_code}): {resp.text}"}
        
    processed_doc = resp.json()
    evidence = processed_doc.get("evidence", {})
    validation = processed_doc.get("validation", {})
    decision = processed_doc.get("decision", {})
    
    if not evidence:
        return {"error": "No evidence extracted"}
        
    extracted = evidence.get("extracted_fields", {})
    
    def get_val(field_name):
        field = extracted.get(field_name)
        return field["value"] if field else None
        
    def get_conf(field_name):
        field = extracted.get(field_name)
        return field["confidence"] if field else None

    # We assume 'ordered' is just what we provided to the API, but let's see if the schema outputs it
    
    result = {
        "filename": os.path.basename(image_path),
        "latency": latency,
        "total_latency": total_latency,
        "ground_truth": ground_truth,
        "extracted": {
            "accepted_quantity": get_val("accepted_quantity"),
            "damaged_quantity": get_val("damaged_quantity"),
            "rejected_quantity": get_val("rejected_quantity"),
            "signature_present": get_val("signature_present")
        },
        "confidence": {
            "accepted_quantity": get_conf("accepted_quantity"),
            "damaged_quantity": get_conf("damaged_quantity"),
            "rejected_quantity": get_conf("rejected_quantity"),
            "signature_present": get_conf("signature_present")
        },
        "validation": validation,
        "decision": decision
    }
    
    return result

def run_smoke_test(dataset_dir: str):
    gt_file = os.path.join(dataset_dir, "ground_truth.json")
    with open(gt_file, "r") as f:
        metadata = json.load(f)
        
    results = []
    
    for item in metadata[:5]: # ONLY FIRST 5
        img_path = os.path.join(dataset_dir, item["filename"])
        res = evaluate_smoke(img_path, item["ground_truth"])
        results.append(res)
        
    with open(os.path.join(dataset_dir, "smoke_test_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_smoke_test("../dataset/images")
