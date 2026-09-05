# Validation record

Local validation performed on 5 September 2026, Windows, Node 22.16.0 and Python 3.12.3.

| Check | Result |
| --- | --- |
| Python lint (`ruff check backend scripts tests`) | Passed |
| Backend (`python -m pytest -q`) | 18 passed |
| TypeScript and production frontend (`npm run build`) | Passed |
| Playwright (`npm run test:e2e`) | 8 passed: desktop and mobile |
| Automated WCAG A/AA checks | Passed on four pages and approval/completed states, desktop and mobile |
| JavaScript runtime errors during full rehearsal | None observed |
| Independent receipt verification | Passed in Python unit tests and browser-suite JavaScript verifier |
| MCP transport | Official Python SDK discovery, schema validation and tool calls passed against a local fixture |
| Playwright development MCP | Initialized; 24 tools discovered |
| GitHub | Private project repository created and cloned; feature branch used for the build |
| OpenAI authentication | Accepted by the models endpoint |
| OpenAI generation | Blocked: `credit_balance_exhausted` / `insufficient_quota`; the application correctly reports the error |
| Razorpay hosted MCP / test checkout | Not verified: test key ID and secret are not configured |

Provider fixtures are explicitly separate from real integration checks. No successful OpenAI agent generation or real Razorpay test capture is claimed. The single backend warning is a dependency deprecation in Starlette's test client, not a failed check.

## Covered failure and payment boundaries

- Mid-negotiation simulated stock loss and policy-compliant substitution.
- No eligible product, category restrictions, optional bundle removal when it exceeds the cap.
- Human approval, rejection, stale approval hash and a modified quote.
- Repeated and concurrent checkout/capture calls producing one order intent and one captured event.
- Signature mismatch, provider amount mismatch, uncertain order outcome and process restart.
- Live Razorpay key rejection and prevention of a simulated completion for a Razorpay session.
- Audit entry edits, reordering, deletion, and truncation against an independently retained head.
- Inventory and checkout-state rollback when the audit write fails; no partial reservation when stock runs out.
- Cross-origin browser write rejection and noninteger money input rejection.

## Remaining setup for the provider-backed demo

1. Give the OpenAI API project available credits, then run a session with OpenAI agents to verify generation.
2. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` locally using Razorpay test credentials. Restart the API and check MCP connectivity from Connections.
3. Run an approved Razorpay test checkout and verify the capture through MCP. Inspect the resulting audit receipt and the Razorpay dashboard.
4. Record the narrated hackathon video using that validated flow. The current WebM is a scripted, simulated technical rehearsal.

Hosted deployment and external audit anchoring remain stretch goals. The current app is a loopback-only, single-operator prototype.
