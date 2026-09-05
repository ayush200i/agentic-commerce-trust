# Demo run: 2–4 minutes

The default rehearsal is intentionally labeled scripted and simulated. For a hackathon submission demonstrating Razorpay, switch to OpenAI agents and Razorpay test mode after connecting and validating both services. Do not present the rehearsal recording as a provider-verified payment.

A [silent technical rehearsal recording](rehearsal.webm) is included in the repository. It demonstrates the scripted/simulated flow and is not a substitute for a narrated, provider-verified final video.

1. **0:00–0:25 / Problem.** “When an agent buys from another agent, a payment receipt alone doesn't explain whether the purchase was allowed. Counterseal binds each purchase to a mandate and records the decisions that led to it.” Show the ₹5,000 cap, ₹3,000 approval threshold and category allowlist.
2. **0:25–1:05 / Negotiation.** Start the supplied keyboard-and-mat mandate. Explain the eligible catalog, the seller's bounded discount and why policy is enforced by code rather than a prompt. Expand one decision's evidence.
3. **1:05–1:35 / Failure.** Show the explicitly simulated stock change. The seller withdraws Arc 75; the buyer proposes Forma 75 within the same category and budget. The optional mat survives only if it fits the policy. No payment is attempted during recovery.
4. **1:35–2:15 / Approval and payment.** Approve the exact quote. Complete payment. For Razorpay mode, finish Standard Checkout with Razorpay's test flow; the backend checks the signature and provider amount, order and status through MCP. Watch the single ledger stamp on capture.
5. **2:15–2:50 / Evidence.** Verify the audit chain, export the receipt, and save its root separately. Run the independent verifier. Explain the limitation: this hash chain is tamper-evident against a retained head; it is not externally anchored yet.
6. **2:50–3:15 / Impact.** In the fixed rehearsal, the recovered keyboard/mat sale is ₹3,862.16 with ₹335.84 negotiated savings. These are demo transaction amounts, not measured merchant revenue uplift. “The same MCP tool layer lets the agent use merchant capabilities, with every payment action gated and recorded.”

## Repeatable recording

`npm run demo` executes the full rehearsal, saves full-page screenshots, records a WebM and attaches the independently verified audit JSON under `test-results/`. The automated test is a compact technical recording; add the above narration and pacing for a final submission video.

Playwright starts dedicated servers on ports 5174 and 8001 with a unique test database and empty provider credentials. You can leave the development servers running: the recording does not consume their inventory or change their sessions. These two test ports must be free.
