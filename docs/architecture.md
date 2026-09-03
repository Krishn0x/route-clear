# Architecture Overview

## The Execution Pipeline

The core philosophy of Route-Clear is that Large Language Models (VLMs) are unpredictable statistical engines and must never be given direct authority over financial actions.

The pipeline executes strictly sequentially per document:

1. **Upload & Storage**
   - Documents are uploaded via `POST /api/documents/upload`.
   - Hashes are generated and stored in a local SQLite Database to track progression.

2. **VLM Extraction (`VLMProvider`)**
   - The document is sent to a Vision Language Model (e.g., Gemini 1.5 Pro).
   - A highly constrained prompt forces the model to return JSON matching `FulfillmentEvidenceSchema`.
   - The VLM is instructed to ONLY transcribe visual data and provide `confidence` and `evidence_region` (bounding boxes). It is instructed *not* to perform math.

3. **Deterministic Validation (`SafetyEngine`)**
   - Pure, deterministic Python code validates the VLM's JSON.
   - Example rule: `unaccounted_quantity = ordered - (accepted + damaged + rejected)`.
   - It references a `PolicyConfig` to ensure confidence thresholds are met and required signatures are present.
   - If the validation fails, it flags `requires_human_review = True`.

4. **Decision Boundary (`SettlementDecision`)**
   - The system calculates the strict financial amounts (using `Decimal` arithmetic to avoid floating-point issues).
   - E.g., `approved_release_amount` = `accepted_quantity * unit_price`.
   - An `idempotency_key` is generated to prevent duplicate executions.

5. **External Financial Action (`RouteAdapter`)**
   - Bounded by the `SettlementDecision`, this adapter interfaces with Razorpay Route API.
   - If `proposed_reversal_amount > 0`, it issues a `POST /v1/transfers/{id}/reversals`.
   - It then issues a `PATCH /v1/transfers/{id}` (`{"on_hold": false}`) to release the remaining funds.
   - Includes a robust simulated mode for testing.

6. **Tamper-Evident Ledger (`AuditLog`)**
   - Every step of the pipeline produces an append-only Audit Log.
   - Cryptographic hashes are chained (`SHA256(event_type | details | previous_hash)`), ensuring that any manual tampering with the SQLite database immediately breaks the hash chain.
