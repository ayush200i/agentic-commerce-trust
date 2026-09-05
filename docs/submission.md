# Counterseal: judge's guide

**Project:** Agentic Commerce Trust Layer  
**Track:** Razorpay Hackathon, Track 1 — AI Growth & Agentic Commerce  
**Repository:** https://github.com/ayush200i/agentic-commerce-trust

## The problem and approach

An agent's payment receipt does not explain whether the purchase respected the buyer's intent, budget or approval rules. Counterseal adds a control room around a buyer–seller commerce workflow: a purchase mandate, server-enforced policy, quote-specific human approval and a hash-linked decision record.

The buyer and seller run as nodes in LangGraph. The buyer selects from an eligible merchant catalog; the seller proposes a bounded discount and an optional bundle. An injected stock change forces the buyer to find a replacement before checkout. The payment integration uses Razorpay's official remote MCP server, with the application enforcing payment permissions around each tool call.

## What is working and what remains

The complete **scripted rehearsal with simulated payment** runs locally without provider credentials. It exercises the real graph, policy checks, approval gate, SQLite persistence, inventory reservation and audit verification.

The OpenAI and Razorpay integrations are implemented, but the provider-backed end-to-end flow has **not yet been validated**. The configured OpenAI key authenticates but generation returned exhausted API credits. Razorpay test credentials have not been configured. Passing fixture tests and the rehearsal recording do not establish a successful OpenAI negotiation or Razorpay test capture.

There is no hosted URL, blockchain anchor, digital-signature identity system, fully autonomous payment wallet, or protocol certification. The app is a single-operator local prototype. These limits are documented rather than represented as completed features.

## Try the project in five steps

1. Follow the [README setup instructions](../README.md#run-locally). Start the backend and frontend, then open `http://127.0.0.1:5173`.
2. Keep **Scripted rehearsal** and **Simulated payment** selected. The default mandate asks for a quiet keyboard and optional desk mat, with a ₹5,000 cap and approval above ₹3,000.
3. Start negotiation with the stock-failure switch enabled. Watch Arc 75 become unavailable in the simulated scenario, then observe the policy-compliant switch to Forma 75.
4. Approve the exact quote and complete the simulated payment. The fixed demo basket costs **₹3,862.16**, with **₹335.84** savings from the seeded catalog prices. These are demo amounts, not measured merchant uplift.
5. Select **Verify chain**, export the receipt, and retain its head separately. Use the [independent verifier](../scripts/verify_audit.py) to validate the export. Start another session and reject the quote to confirm checkout remains blocked.

## Where to review the requirements

| Requirement | Implementation and evidence |
| --- | --- |
| Buyer and seller workflow | [LangGraph commerce workflow](../backend/commerce.py), [agent provider](../backend/providers.py) |
| Bounded money actions | Integer paise, category allowlist, spend cap and fixed discount choices; [models](../backend/models.py), [policy checks](../backend/commerce.py) |
| Human approval | Approval binds the session, policy, quote and payment mode through a hash; rechecked at checkout/capture |
| Razorpay MCP runtime | [Official MCP SDK client](../backend/providers.py), runtime tool schema discovery and restricted tool calls |
| Checkout verification | Test keys only; checkout signature, order, amount, currency and captured-state verification in [commerce.py](../backend/commerce.py) |
| Explainable decisions | Streamed decision summaries and structured evidence in the [control room](../src/App.tsx); no private chain-of-thought disclosure |
| Graceful failure | Simulated stock loss and replacement; quota errors and uncertain payment outcomes stop visibly |
| Tamper-evident audit | [SQLite hash chain](../backend/store.py), independent [Python](../scripts/verify_audit.py) and [JavaScript](../e2e/verify.ts) verifiers |
| Repeated actions and crashes | Serialized payment transitions, atomic inventory/checkpoint writes, duplicate-request handling and reconciliation on restart |
| UI and accessibility | [Dashboard screenshot](control-room.png), responsive desktop/mobile layouts, focus indicators and automated contrast checks |

## Supporting material

- [README: installation, configuration, commands and limitations](../README.md)
- [Architecture and trust boundaries](architecture.md)
- [Validation record: 18 backend and 8 browser tests](validation.md)
- [GitHub Actions CI](https://github.com/ayush200i/agentic-commerce-trust/actions/workflows/ci.yml)
- [Silent technical rehearsal recording](rehearsal.webm) — scripted agents, simulated payments
- [Narration outline for a 2–4 minute final demo](demo-script.md)
- [Environment variable template](../.env.example) — no credentials included

## Complete the provider-backed demonstration

Supply an OpenAI API project with available credits and valid Razorpay test key ID/secret in the ignored local environment file. Restart the API, verify the MCP connection, then run an approved session with **OpenAI agents + Razorpay test via MCP**. Complete Razorpay Standard Checkout's test authorization and confirm the captured result both in the audit export and in Razorpay. Record the final narrated demo only after this succeeds.
