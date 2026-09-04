# Route-Clear: AI Fulfillment-to-Settlement Controller

**Route-Clear** is a prototype AI-driven finance controller built for the Razorpay AI Builder Internship 2026. It securely processes messy logistics fulfillment documents (e.g., Delivery Challans) and automates Razorpay Route settlement actions while strictly confining the AI's financial authority.

## Architectural Rule: The AI does not do math.
Route-Clear enforces a strict boundary between visual extraction and financial execution:
1. **Vision-Language Model (VLM)**: Extracts raw quantities and text from physical documents.
2. **Deterministic Safety Engine**: Validates invariants (e.g., `accepted + damaged + rejected = ordered`) using standard Python logic.
3. **Route Adapter**: Executes bounded Razorpay Route transfers (Partial Reversals and Releases) strictly based on the deterministic engine's decision, optionally escalating to a Human Review loop.

## Setup Instructions

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:
```env
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
```

Run the backend:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:5173` to access the Route-Clear Dashboard.

## Running the Evaluation Pipeline

Route-Clear includes tooling to synthetically generate delivery documents (including adversarial edge cases) and measure the deterministic engine's accuracy.

1. **Generate Dataset**:
   ```bash
   cd dataset/generator
   python generate.py
   ```
   *Generates 150 synthetic challans with noise, rotation, and calculated ground truth.*

2. **Run Evaluation**:
   Ensure the backend server is running.
   ```bash
   cd evaluation
   python eval_safety_only.py
   ```
   *This evaluates the Deterministic SafetyEngine against the ground truth dataset. Current results show 150/150 correct policy decisions with 0 false-safes and 0 false-blocks (see `evaluation/safety_eval_results.json`). This 150/150 result measures the deterministic financial-control layer assuming correct structured extraction; it is NOT a claim of 150/150 VLM extraction accuracy. Real-world Gemini VLM batch evaluation (`eval_pipeline.py`, `eval_stratified.py`) was stopped during development because of API quota limits, so automated VLM batch result artifacts are not committed to this repository. The VLM extraction capability is demonstrated through the real Gemini provider and the controlled deterministic demo path in the pitch.*

## Project Structure
- `backend/`: FastAPI application, SQLite models, deterministic Safety Engine, and Route Adapter.
- `frontend/`: React + Vite Dashboard for visualization and Manual Overrides.
- `dataset/`: Tools to generate synthetic logistics documents.
- `evaluation/`: The automated Evaluation Pipeline.
- `docs/`: Threat Models and Architectural Documentation.
