import httpx
import sys

def main():
    # 1. Upload
    print("Uploading...")
    with open("tests/test.png", "rb") as f:
        resp = httpx.post(
            "http://127.0.0.1:8000/api/documents/upload",
            data={"transfer_id": "tr_e2e", "total_amount": "100000.00", "ordered_quantity": "100"},
            files={"file": ("test.png", f, "image/png")}
        )
    
    if resp.status_code != 200:
        print("Upload failed:", resp.text)
        sys.exit(1)
        
    doc = resp.json()
    doc_id = doc["id"]
    print("Uploaded document:", doc_id)
    
    # 2. Process
    print("Processing...")
    resp = httpx.post(f"http://127.0.0.1:8000/api/documents/{doc_id}/process")
    if resp.status_code != 200:
        print("Process failed:", resp.text)
        sys.exit(1)
        
    processed_doc = resp.json()
    print("Status:", processed_doc.get("status"))
    print("Keys:", processed_doc.keys())
    print("Done")

if __name__ == "__main__":
    main()
