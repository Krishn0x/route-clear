import os
import requests
from pprint import pprint

BASE_URL = "http://127.0.0.1:8000/api/v1"

def run_demo(image_path: str):
    if not os.path.exists(image_path):
        print(f"Error: Could not find {image_path}")
        return

    print("--- Route-Clear VLM Demo ---")
    print(f"Uploading document: {image_path}")
    
    with open(image_path, "rb") as f:
        files = {"file": f}
        data = {
            "transfer_id": "tr_mock_demo123",
            "total_amount": "10000.00",
            "ordered_quantity": 100
        }
        
        response = requests.post(f"{BASE_URL}/documents/upload", files=files, data=data)
        if response.status_code != 200:
            print(f"Upload failed: {response.json()}")
            return
            
        doc_data = response.json()
        doc_id = doc_data['id']
        print(f"Document uploaded successfully! ID: {doc_id}")
        
    print("\nTriggering real VLM extraction (This may take several seconds)...")
    process_resp = requests.post(f"{BASE_URL}/documents/{doc_id}/process")
    
    if process_resp.status_code == 200:
        result = process_resp.json()
        print("\n--- VLM Extraction Result ---")
        print(f"Status: {result['status']}")
        if result['status'] == 'FAILED':
            print("Extraction failed. Note: no financial side-effects were executed.")
            print(result)
        else:
            print(f"Provider: {result['evidence']['provider']} | Model: {result['evidence']['model_identifier']}")
            print(f"Overall Confidence: {result['evidence']['overall_confidence']}")
            print("\nExtracted Fields:")
            pprint(result['evidence']['extracted_fields'])
            print("\nNotice: The VLM returned raw evidence (quantities, booleans, notes).")
            print("Notice: It did NOT return financial settlement amounts.")
    else:
        print(f"Processing error: {process_resp.text}")

if __name__ == "__main__":
    print("Please ensure the FastAPI server is running (`uvicorn app.main:app --reload`)")
    print("and GEMINI_API_KEY is set in .env with VLM_PROVIDER=gemini.")
    # Assuming user provides an image or we have a dummy one
    sample_path = input("Enter path to test image (e.g., sample_challan.jpg): ")
    run_demo(sample_path)
