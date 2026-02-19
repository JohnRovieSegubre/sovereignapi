# RFC: The Machine-First Economy (Sovereign Compute Protocol)

**Source:** Gemini (AI Economy) & Tech Lead
**Status:** Approved Strategy
**Identity Layer:** Bitcoin/Lightning (L402)
**Business Model:** Compute Dropshipping (Arbitrage Middleware)

## 1. The Core Business: "The Dropshipper"
We are **not** building an AI model. We are building the **"Checkout Counter for Robots"**.
We translate **Crypto Demand** (Agents) into **Fiat Supply** (DeepInfra/OpenRouter).

### The Architecture (Reverse Proxy)
1.  **Ingress:** `api.antigravity.io` (The Gateway)
    *   Listens for `POST /v1/chat/completions`.
    *   **Gatekeeper:** Checks for `Authorization: L402 <macaroon>`.
    *   **Denial:** If no payment -> Returns `402 Payment Required` with a Lightning Invoice.
2.  **Processing:**
    *   Verifies payment proof (Preimage).
    *   Validates "Speed Challenge" (Reverse Turing Test).
3.  **Egress (Dropshipping):**
    *   Forwards the validated request to **DeepInfra** (using *our* Credit Card/Key).
    *   Receives response.
4.  **Response:**
    *   Sends JSON back to the buying Agent.
    *   **Profit:** We keep the difference between the Invoice Amount and DeepInfra's bill.

## 2. The Stack
*   **Language:** Python (FastAPI) or Node.js (Express). *Decision Pending.*
*   **Payment Rail:** Alby API (for Beta) -> Self-Hosted LND (for Prod).
*   **Backend Provider:** **DeepInfra** (Price Leader) or **OpenRouter** (Compatibility Leader).

## 3. Implementation Phases
### Phase 1: The "Manual" Arbitrage
*   **Monitor Script:** `wallet_client.py` (The Buyer).
*   It buys compute from *other* gateways (if they exist) or simply acts as a consumer for now to test the wallet protocols.
*   *Wait, the prompt says WE are building the Gateway.*
*   **Gateway V1:** `gateway_server.py`.
    *   Simple FastAPI server.
    *   Mock L402 (for testing flow).
    *   Real Forwarding to DeepInfra.

## 4. Required Secrets (Technical Discovery)
*   `DEEPINFRA_API_KEY`: For the backend supply.
*   `ALBY_ACCESS_TOKEN`: For receiving Lightning payments.
