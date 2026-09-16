# Route-Clear: AI Fulfillment-to-Settlement Controller

**Route-Clear** is a prototype AI-driven finance controller built for the Razorpay AI Builder Internship 2026. It securely processes messy logistics fulfillment documents (e.g., Delivery Challans) and automates Razorpay Route settlement actions while strictly confining the AI's financial authority.

## Architectural Rule: AI interprets evidence. Deterministic code decides money.

Route-Clear enforces a strict boundary between visual extraction and financial execution through the following pipeline:

AI Evidence
    ↓
VLM Pass 1
    ↓
Independent VLM Pass 2
    ↓
Deterministic Comparator
    ↓
Evidence Groundedness Gate
    ↓
SafetyEngine
    ↓
Human Review when uncertain
    ↓
Deterministic financial calculation
    ↓
Razorpay Route Adapter

### Pipeline Principles
- **VLM Independence:** Pass 2 independently inspects the original image without receiving output from Pass 1.
- **Fail-Safe Conflict:** AI disagreement causes an immediate fallback to human review.
- **Evidence Verification:** Insufficient or ungrounded evidence causes an immediate fallback to human review.
- **No Direct Authority:** The AI never directly authorizes a financial action.
- **Restricted Human Review:** Human reviewers submit quantities, not financial amounts.
- **Server-Side Truth:** \ordered_quantity\ and \	otal_amount\ come from server-side transfer metadata.
- **Deterministic Math:** The SafetyEngine performs deterministic validation and financial calculation.
- **Safe Execution:** Route execution occurs only after SafetyEngine approval.
- **Idempotency:** Route idempotency and state-machine behavior are preserved.

## Setup Instructions

### 1. Backend Setup
\\ash
cd backend
python -m venv venv
source venv/bin/activate  # (or venv\Scriptsctivate on Windows)
pip install -r requirements.txt
\
Create a \.env\ file in the \ackend/\ directory:
\\env
# VLM Configuration
# Set to 'mock' for local testing without API keys.
# Set to 'gemini' for real extraction (requires GEMINI_API_KEY).
VLM_PROVIDER=mock
GEMINI_API_KEY=your_gemini_api_key_here

# Route API Configuration
# Set to 'simulated' to mock Razorpay responses.
# Set to 'sandbox' or 'live' to hit actual endpoints (requires keys).
ROUTE_MODE=simulated
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
\
Run the backend:
\\ash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
\
### 2. Frontend Setup
\\ash
cd frontend
npm install
npm run dev
\Visit \http://localhost:5173\ to access the Route-Clear Dashboard.

## Evaluation

The Route-Clear evaluation methodology explicitly distinguishes between:

1. **Deterministic SafetyEngine evaluation**
   - Evaluated against 150 synthetic ground-truth cases (including adversarial anomalies). Results show 150/150 correct policy decisions with 0 false-safes and 0 false-blocks.

2. **VLM mock/integration tests**
   - The backend CI suite (62 passing tests) validates the pipeline routing, fallback paths, and API logic using deterministic mock fixtures. These tests do not measure LLM capabilities.

3. **Real Gemini evaluation**
   - Real Gemini batch evaluation was limited by API quota. Therefore, no unsupported real-world VLM accuracy percentage is claimed.

## Known Limitations

- A perfectly consistent VLM hallucination cannot be proven physically correct by software alone; the two-pass agreement and evidence-grounding checks reduce risk but do not establish physical truth.
- Authentication is not yet implemented for the demo endpoints and is a production deployment limitation.
- Uploaded image provenance is not cryptographically attested.

## Project Structure
- \ackend/\: FastAPI application, SQLite models, deterministic Safety Engine, and Route Adapter.
- \rontend/\: React + Vite Dashboard for visualization and Manual Overrides.
- \dataset/\: Tools to generate synthetic logistics documents.
- \evaluation/\: The automated Evaluation Pipeline.
- \docs/\: Threat Models and Architectural Documentation.
