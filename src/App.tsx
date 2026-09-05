import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  Check,
  CheckCheck,
  ChevronDown,
  Circle,
  CircleAlert,
  CircleCheck,
  ClipboardList,
  Fingerprint,
  Layers3,
  LockKeyhole,
  Package,
  Play,
  Plus,
  Radio,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Square,
  Terminal,
  X,
} from "lucide-react";

type Policy = {
  spend_cap: number;
  approval_threshold: number;
  categories: string[];
};
type Product = {
  id: string;
  name: string;
  price: number;
  category: string;
  stock: number;
  tags: string[];
  description: string;
};
type AuditEvent = {
  sequence: number;
  actor: string;
  action: string;
  summary: string;
  timestamp: string;
  hash: string;
  prev_hash: string;
  evidence: Record<string, unknown>;
};
type Quote = {
  amount: number;
  subtotal: number;
  savings: number;
  currency: string;
  discount_percent: number;
  lines: Product[];
};
type Session = {
  id: string;
  status: string;
  goal: string;
  agent_mode: string;
  payment_mode: string;
  policy: Policy;
  spend_so_far: number;
  quote: Quote | null;
  quote_hash: string;
  recovered: boolean;
  error: string | null;
  audit_head: string;
  events: AuditEvent[];
  verification: { valid: boolean; count: number; head: string };
  transaction: {
    order_id: string;
    payment_id: string | null;
    status: string;
  } | null;
  checks: { rule: string; passed: boolean; actual: unknown; limit: unknown }[];
};
type Health = {
  status: string;
  openai_configured: boolean;
  openai_model: string;
  razorpay_configured: boolean;
};
type History = {
  id: string;
  goal: string;
  status: string;
  spend_so_far: number;
  payment_mode: string;
  created_at: string;
};
const money = (paise: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: paise % 100 ? 2 : 0,
  }).format(paise / 100);
const statusText: Record<string, string> = {
  negotiating: "Agents negotiating",
  awaiting_approval: "Needs your approval",
  ready: "Ready for checkout",
  creating_order: "Creating order",
  awaiting_payment: "Awaiting payment",
  verifying_payment: "Verifying payment",
  completed: "Purchase complete",
  failed: "Stopped safely",
  rejected: "Quote rejected",
  reconciliation_required: "Reconciliation required",
};
const actorNames: Record<string, string> = {
  buyer: "Buyer agent",
  seller: "Seller agent",
  policy: "Policy engine",
  human: "You",
  system: "Control room",
  payment: "Payment gateway",
};
const labels: Record<string, string> = {
  session_started: "Mandate recorded",
  product_selected: "Product selected",
  offer_proposed: "Offer proposed",
  stock_failure: "Stock unavailable",
  replacement_selected: "Replacement selected",
  policy_evaluated: "Policy verified",
  quote_approved: "Quote approved",
  quote_rejected: "Quote rejected",
  order_requested: "Order requested",
  order_created: "Order created",
  payment_captured: "Payment captured",
  workflow_stopped: "Workflow stopped",
  bundle_removed: "Bundle adjusted",
};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    "/api" + path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Trust-Control": "local-operator",
          },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Check the input values and try again.",
    );
  return data;
}

function Seal({ large = false }: { large?: boolean }) {
  return (
    <span className={"seal " + (large ? "seal-large" : "")}>
      <ShieldCheck size={large ? 36 : 24} strokeWidth={1.3} />
    </span>
  );
}

function ProductDrawing({ kind }: { kind: string }) {
  if (kind === "accessories")
    return (
      <svg viewBox="0 0 280 150" aria-hidden="true">
        <path
          d="M38 57L214 32 257 97 75 124Z"
          fill="#9faaa3"
          stroke="#727f77"
        />
        <path
          d="M48 62L210 40 245 94 80 115Z"
          fill="none"
          stroke="#cdd4ce"
          strokeDasharray="2 3"
        />
      </svg>
    );
  if (kind === "audio")
    return (
      <svg viewBox="0 0 280 150" aria-hidden="true">
        <path
          d="M91 106V73a49 49 0 0198 0v33"
          fill="none"
          stroke="#748292"
          strokeWidth="16"
        />
        <rect x="78" y="76" width="29" height="50" rx="9" fill="#263750" />
        <rect x="173" y="76" width="29" height="50" rx="9" fill="#263750" />
      </svg>
    );
  return (
    <svg viewBox="0 0 280 150" aria-hidden="true">
      <g transform="translate(37 44) skewY(-8)">
        <rect x="0" y="5" width="210" height="81" rx="5" fill="#71818f" />
        <rect width="210" height="79" rx="5" fill="#d9deda" stroke="#9aa8ae" />
        {Array.from({ length: 4 }, (_, r) =>
          Array.from({ length: 13 }, (_, c) => (
            <rect
              key={`${r}-${c}`}
              x={7 + c * 15}
              y={7 + r * 14}
              width="12"
              height="11"
              rx="1.5"
              fill={c === 12 ? "#b5a368" : "#fafaf8"}
              stroke="#b4bdbc"
              strokeWidth=".6"
            />
          )),
        )}
        <rect x="59" y="64" width="88" height="8" rx="1" fill="#fafaf8" />
        <rect x="7" y="64" width="46" height="8" rx="1" fill="#c4ccca" />
        <rect x="153" y="64" width="49" height="8" rx="1" fill="#c4ccca" />
      </g>
    </svg>
  );
}

export default function App() {
  const [view, setView] = useState("control");
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [goal, setGoal] = useState(
    "Find a quiet mechanical keyboard for my desk, with a desk mat if the bundle fits my budget.",
  );
  const [cap, setCap] = useState("5000");
  const [threshold, setThreshold] = useState("3000");
  const [categories, setCategories] = useState(["keyboards", "accessories"]);
  const [agentMode, setAgentMode] = useState("rehearsal");
  const [paymentMode, setPaymentMode] = useState("simulated");
  const [inject, setInject] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);
  const [verified, setVerified] = useState(false);
  const [mcpStatus, setMcpStatus] = useState("");

  useEffect(() => {
    Promise.all([
      api<Health>("/health"),
      api<Product[]>("/catalog"),
      api<History[]>("/sessions"),
    ])
      .then(([h, c, s]) => {
        setHealth(h);
        setCatalog(c);
        setHistory(s);
      })
      .catch(() =>
        setError(
          "The backend is unavailable. Start the local API and refresh this page.",
        ),
      );
  }, []);
  useEffect(() => {
    if (!session?.id) return;
    const source = new EventSource(`/api/sessions/${session.id}/events`);
    source.onopen = () => setConnected(true);
    source.onmessage = (event) => {
      setSession(JSON.parse(event.data));
      setConnected(true);
    };
    source.onerror = () => setConnected(false);
    return () => source.close();
  }, [session?.id]);
  useEffect(() => {
    if (session?.status === "completed")
      api<Product[]>("/catalog")
        .then(setCatalog)
        .catch(() => {});
  }, [session?.status]);

  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    await action(async () => {
      const capValue = Number(cap),
        thresholdValue = Number(threshold);
      if (
        !Number.isFinite(capValue) ||
        !Number.isFinite(thresholdValue) ||
        capValue < 1 ||
        thresholdValue < 0 ||
        !categories.length
      )
        throw new Error(
          "Enter a valid cap and threshold, and permit at least one category.",
        );
      const s = await api<Session>("/sessions", {
        goal,
        policy: {
          spend_cap: Math.round(capValue * 100),
          approval_threshold: Math.round(thresholdValue * 100),
          categories,
        },
        agent_mode: agentMode,
        payment_mode: paymentMode,
        inject_stock_failure: inject,
      });
      setSession(s);
      setVerified(false);
    });
  }
  async function approve(approved: boolean) {
    if (!session) return;
    await action(async () =>
      setSession(
        await api<Session>(`/sessions/${session.id}/approval`, {
          approved,
          quote_hash: session.quote_hash,
        }),
      ),
    );
  }
  async function complete() {
    if (!session) return;
    await action(async () => {
      const s = await api<Session>(`/sessions/${session.id}/checkout`, {});
      setSession(s);
      if (s.status !== "awaiting_payment") return;
      if (s.payment_mode === "simulated") {
        setSession(
          await api<Session>(`/sessions/${s.id}/simulate-capture`, {}),
        );
        return;
      }
      const config = await api<Record<string, unknown>>(
        `/sessions/${s.id}/checkout-config`,
      );
      const loadScript = () =>
        new Promise<void>((resolve, reject) => {
          if ((window as any).Razorpay) return resolve();
          const script = document.createElement("script");
          script.src = "https://checkout.razorpay.com/v1/checkout.js";
          script.onload = () => resolve();
          script.onerror = () =>
            reject(
              new Error(
                "Razorpay Checkout could not load. The existing order is saved.",
              ),
            );
          document.head.appendChild(script);
        });
      await loadScript();
      const checkout = new (window as any).Razorpay({
        ...config,
        theme: { color: "#14213D" },
        handler: (response: unknown) => {
          void action(async () =>
            setSession(
              await api<Session>(`/sessions/${s.id}/confirm-payment`, response),
            ),
          );
        },
        modal: {
          ondismiss: () =>
            setError(
              "Checkout closed. Your order is saved; resume payment when ready.",
            ),
        },
      });
      checkout.on("payment.failed", () =>
        setError(
          "Razorpay reported a failed payment. Your order remains open; no captured payment has been confirmed.",
        ),
      );
      checkout.open();
    });
  }
  async function navigate(next: string) {
    setView(next);
    if (next === "receipts")
      api<History[]>("/sessions")
        .then(setHistory)
        .catch((e) => setError(e.message));
  }
  const amount = session?.quote?.amount || 0;
  const actualPolicy = session?.policy || {
    spend_cap: Number(cap) * 100,
    approval_threshold: Number(threshold) * 100,
    categories,
  };
  const inProgress =
    session &&
    ["negotiating", "creating_order", "verifying_payment"].includes(
      session.status,
    );
  const isComplete = session?.status === "completed";
  const events = session?.events || [];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            void navigate("control");
          }}
        >
          <Seal />
          <span>
            Counterseal
            <span className="brand-sub">Commerce, accounted for.</span>
          </span>
        </a>
        <div className="workspace-label">
          <span className="small-dot" /> Workspace 001 <LockKeyhole size={12} />
        </div>
        <nav aria-label="Main navigation">
          {[
            { id: "control", icon: Activity, label: "Control room" },
            { id: "catalog", icon: Package, label: "Merchant catalog" },
            { id: "receipts", icon: ClipboardList, label: "Session receipts" },
            { id: "connections", icon: Settings2, label: "Connections" },
          ].map((item) => (
            <button
              key={item.id}
              className={view === item.id ? "nav-item active" : "nav-item"}
              onClick={() => void navigate(item.id)}
            >
              <item.icon size={17} />
              {item.label}
              {view === item.id && <span className="nav-marker" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Fingerprint size={27} strokeWidth={1} />
          <p>
            Trust is a record.
            <br />
            Keep every decision.
          </p>
          <span>
            Policy-bound actions.
            <br />
            Verifiable receipts.
          </span>
        </div>
        <div className="sidebar-bottom">
          <span className="env-tag">
            <Circle size={7} fill="currentColor" /> Test environment
          </span>
          <span>Razorpay hackathon · Track 01</span>
          <div className="operator">
            <span className="avatar">AY</span>
            <div>
              Local operator<small>Approval authority</small>
            </div>
            <LockKeyhole size={13} />
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace 001</span>
            <span className="slash">/</span>
            <span>
              {view === "control"
                ? "Control room"
                : view === "catalog"
                  ? "Merchant catalog"
                  : view === "receipts"
                    ? "Session receipts"
                    : "Connections"}
            </span>
          </div>
          <span className="top-status">
            <span className={"small-dot " + (health ? "green" : "rust")} />
            {health ? "Local API online" : "Connecting to API"}
          </span>
        </header>
        <main id="main-content" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <div className="document-label">
                <span className="line-mark" /> Agentic commerce trust layer
              </div>
              <h1>
                {view === "control"
                  ? "Commerce under control."
                  : view === "catalog"
                    ? "The merchant’s shelf."
                    : view === "receipts"
                      ? "A record of every run."
                      : "Connected, with boundaries."}
              </h1>
              <p>
                {view === "control"
                  ? "Two agents. One mandate. Every action on the record."
                  : view === "catalog"
                    ? "A structured catalog the agents can discover and negotiate."
                    : view === "receipts"
                      ? "Reopen a session to inspect its decisions and export the audit trail."
                      : "Check the tools behind the negotiation and the payment."}
              </p>
            </div>
            <span className="edition">
              Counterseal / 01
              <br />
              <span>Hackathon edition</span>
            </span>
          </div>
          {error && (
            <div className="alert error" role="alert">
              <CircleAlert size={17} />
              <span>{error}</span>
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {view === "control" && (
            <>
              <div className="metrics">
                <div>
                  <span>Session status</span>
                  <strong
                    className={
                      "status-value " + (isComplete ? "green-text" : "")
                    }
                  >
                    <span
                      className={
                        "small-dot " + (isComplete ? "green" : "brass")
                      }
                    />
                    {session
                      ? statusText[session.status] || session.status
                      : "Ready for a mandate"}
                  </strong>
                  <small>
                    {session
                      ? "#" + session.id.slice(0, 8)
                      : "Your next purchase starts here"}
                  </small>
                </div>
                <div>
                  <span>Committed spend</span>
                  <strong>
                    {money(session?.spend_so_far || 0)}{" "}
                    <em>/ {money(actualPolicy.spend_cap || 0)}</em>
                  </strong>
                  <div className="spend-track">
                    <i
                      style={{
                        width: `${Math.min(100, ((session?.spend_so_far || 0) / (actualPolicy.spend_cap || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <span>Negotiated savings</span>
                  <strong>{money(session?.quote?.savings || 0)}</strong>
                  <small>
                    {session?.quote
                      ? `${session.quote.discount_percent}% below catalog price`
                      : "Calculated when agents agree"}
                  </small>
                </div>
                <div>
                  <span>Audit integrity</span>
                  <strong className="status-value">
                    <ShieldCheck size={18} />
                    {session
                      ? session.verification.valid
                        ? "Chain intact"
                        : "Verification failed"
                      : "Awaiting entries"}
                  </strong>
                  <small>{events.length} hash-linked entries</small>
                </div>
              </div>

              <div className="control-grid">
                <section className="negotiation panel">
                  <div className="panel-heading">
                    <h2>
                      <Terminal size={19} />
                      Negotiation desk
                    </h2>
                    <span className="live-label">
                      <Radio size={13} />
                      {session
                        ? connected
                          ? "Feed connected"
                          : "Reconnecting"
                        : "Standing by"}
                    </span>
                  </div>
                  {!session ? (
                    <div className="mandate-form">
                      <div className="section-number">
                        01 <span>Give the buyer a mandate</span>
                      </div>
                      <label htmlFor="goal">What should the buyer find?</label>
                      <textarea
                        id="goal"
                        value={goal}
                        onChange={(e) => setGoal(e.target.value)}
                        maxLength={600}
                      />
                      <div className="form-row">
                        <label>
                          Agent execution
                          <select
                            value={agentMode}
                            onChange={(e) => setAgentMode(e.target.value)}
                          >
                            <option value="rehearsal">
                              Scripted rehearsal
                            </option>
                            <option
                              value="openai"
                              disabled={!health?.openai_configured}
                            >
                              OpenAI agents
                            </option>
                          </select>
                        </label>
                        <label>
                          Payment provider
                          <select
                            value={paymentMode}
                            onChange={(e) => setPaymentMode(e.target.value)}
                          >
                            <option value="simulated">Simulated payment</option>
                            <option
                              value="razorpay"
                              disabled={!health?.razorpay_configured}
                            >
                              Razorpay test via MCP
                            </option>
                          </select>
                        </label>
                      </div>
                      <div className="failure-control">
                        <div>
                          <span className="failure-icon">
                            <RotateCcw size={16} />
                          </span>
                          <div>
                            <strong>Put recovery to the test</strong>
                            <small>
                              Simulate a stock change during negotiation.
                            </small>
                          </div>
                        </div>
                        <button
                          className={"switch " + (inject ? "on" : "")}
                          role="switch"
                          aria-checked={inject}
                          aria-label="Simulate stock failure"
                          onClick={() => setInject(!inject)}
                        >
                          <span />
                        </button>
                      </div>
                      <div className="start-row">
                        <button
                          className="primary"
                          disabled={busy || !health || goal.trim().length < 5}
                          onClick={() => void start()}
                        >
                          <Play size={14} fill="currentColor" />
                          {busy ? "Starting session…" : "Start negotiation"}
                        </button>
                        <span>
                          {agentMode === "rehearsal"
                            ? "Scripted decisions. No AI request."
                            : "Uses your OpenAI API credits."}
                        </span>
                      </div>
                      <div className="empty-transcript">
                        <div className="agent-pair">
                          <span>B</span>
                          <i />
                          <span>S</span>
                        </div>
                        <h3>A conversation with guardrails.</h3>
                        <p>
                          The buyer finds a fit. The seller makes an offer.
                          <br />
                          You approve what crosses the line.
                        </p>
                        <div>
                          <span>
                            <Check size={12} /> Bounded spend
                          </span>
                          <span>
                            <Check size={12} /> Visible decisions
                          </span>
                          <span>
                            <Check size={12} /> Verifiable record
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="session-mandate">
                        <span className="small-label">Purchase mandate</span>
                        <p>{session.goal}</p>
                        <div>
                          <span className="pill">
                            {session.agent_mode === "rehearsal"
                              ? "Scripted rehearsal"
                              : "OpenAI agents"}
                          </span>
                          <span className="pill">
                            {session.payment_mode === "simulated"
                              ? "Simulated payment"
                              : "Razorpay test"}
                          </span>
                          <span className="session-id">
                            #{session.id.slice(0, 8)}
                          </span>
                        </div>
                      </div>
                      <div
                        className="transcript"
                        aria-live="polite"
                        aria-relevant="additions text"
                      >
                        {events.map((event) => (
                          <article
                            className={
                              "message " +
                              (event.action === "stock_failure"
                                ? "failure-message"
                                : "")
                            }
                            key={event.sequence}
                          >
                            <span className={"actor-avatar " + event.actor}>
                              {event.actor === "buyer" ? (
                                "B"
                              ) : event.actor === "seller" ? (
                                "S"
                              ) : event.actor === "policy" ? (
                                <ShieldCheck size={15} />
                              ) : event.actor === "human" ? (
                                "Y"
                              ) : event.actor === "payment" ? (
                                <CheckCheck size={15} />
                              ) : (
                                <Circle size={13} />
                              )}
                            </span>
                            <div className="message-body">
                              <div className="message-heading">
                                <strong>
                                  {actorNames[event.actor] || event.actor}
                                </strong>
                                <time>
                                  {new Date(event.timestamp).toLocaleTimeString(
                                    "en-GB",
                                    {
                                      hour: "2-digit",
                                      minute: "2-digit",
                                      second: "2-digit",
                                    },
                                  )}
                                </time>
                              </div>
                              <p>{event.summary}</p>
                              {Object.keys(event.evidence).length > 0 && (
                                <details>
                                  <summary>
                                    Decision evidence <ChevronDown size={12} />
                                  </summary>
                                  <pre>
                                    {JSON.stringify(event.evidence, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </div>
                          </article>
                        ))}
                      </div>
                      {session.error && (
                        <div className="alert error" role="alert">
                          <CircleAlert size={17} />
                          <span>{session.error}</span>
                        </div>
                      )}
                      {session.quote && (
                        <div
                          className={
                            "quote-box " + (isComplete ? "captured" : "")
                          }
                        >
                          <div className="quote-title">
                            <span>
                              {isComplete
                                ? "Purchase receipt"
                                : "Negotiated quote"}
                            </span>
                            <span className="pill">
                              {session.quote.discount_percent}% discount
                            </span>
                          </div>
                          {session.quote.lines.map((p) => (
                            <div className="quote-line" key={p.id}>
                              <span>1 × {p.name}</span>
                              <span>{money(p.price)}</span>
                            </div>
                          ))}
                          <div className="quote-line discount">
                            <span>Seller discount</span>
                            <span>−{money(session.quote.savings)}</span>
                          </div>
                          <div className="quote-total">
                            <span>
                              Total <small>INR · demo catalog price</small>
                            </span>
                            <strong>{money(amount)}</strong>
                          </div>
                          {session.status === "awaiting_approval" && (
                            <div className="approval-box">
                              <div>
                                <LockKeyhole size={15} />
                                <span>
                                  Above your{" "}
                                  {money(session.policy.approval_threshold)}{" "}
                                  threshold. Approve this exact quote to unlock
                                  checkout.
                                </span>
                              </div>
                              <div className="button-row">
                                <button
                                  className="primary"
                                  disabled={busy}
                                  onClick={() => void approve(true)}
                                >
                                  <Check size={15} />
                                  Approve {money(amount)}
                                </button>
                                <button
                                  className="secondary"
                                  disabled={busy}
                                  onClick={() => void approve(false)}
                                >
                                  Reject quote
                                </button>
                              </div>
                            </div>
                          )}
                          {["ready", "awaiting_payment"].includes(
                            session.status,
                          ) && (
                            <button
                              className="primary payment-button"
                              disabled={busy}
                              onClick={() => void complete()}
                            >
                              <LockKeyhole size={15} />
                              {busy
                                ? "Processing…"
                                : session.status === "awaiting_payment"
                                  ? "Resume payment"
                                  : "Complete payment"}
                            </button>
                          )}
                          {isComplete && (
                            <div className="capture-receipt">
                              <Seal />
                              <div>
                                <strong>
                                  {session.payment_mode === "simulated"
                                    ? "Simulation complete"
                                    : "Test payment captured"}
                                </strong>
                                <small>{session.transaction?.payment_id}</small>
                              </div>
                              <Check size={18} />
                            </div>
                          )}
                        </div>
                      )}
                      {!inProgress && (
                        <div className="new-session">
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() => {
                              setSession(null);
                              setVerified(false);
                              setError("");
                            }}
                          >
                            <Plus size={14} />
                            New negotiation
                          </button>
                          <span>Existing sessions stay in receipts.</span>
                        </div>
                      )}
                    </>
                  )}
                </section>

                <div className="right-column">
                  <section className="policy-panel panel">
                    <div className="panel-heading">
                      <h2>
                        <ShieldCheck size={19} />
                        Policy boundaries
                      </h2>
                      <span className="pill navy-pill">
                        {session ? "Locked for session" : "Your mandate"}
                      </span>
                    </div>
                    <div className="policy-body">
                      <div className="policy-field">
                        <div>
                          <span className="rule-index">01</span>
                          <label htmlFor="cap">Maximum spend</label>
                        </div>
                        {session ? (
                          <strong>{money(actualPolicy.spend_cap)}</strong>
                        ) : (
                          <div className="money-input">
                            <span>₹</span>
                            <input
                              id="cap"
                              type="number"
                              min="1"
                              max="100000"
                              step="0.01"
                              value={cap}
                              onChange={(e) => setCap(e.target.value)}
                            />
                          </div>
                        )}
                      </div>
                      <div className="policy-field">
                        <div>
                          <span className="rule-index">02</span>
                          <label htmlFor="threshold">
                            Ask for approval above
                          </label>
                        </div>
                        {session ? (
                          <strong>
                            {money(actualPolicy.approval_threshold)}
                          </strong>
                        ) : (
                          <div className="money-input">
                            <span>₹</span>
                            <input
                              id="threshold"
                              type="number"
                              min="0"
                              max="100000"
                              step="0.01"
                              value={threshold}
                              onChange={(e) => setThreshold(e.target.value)}
                            />
                          </div>
                        )}
                      </div>
                      <div className="policy-category">
                        <div>
                          <span className="rule-index">03</span>
                          <span>Permitted categories</span>
                        </div>
                        <div className="category-options">
                          {["keyboards", "accessories", "audio"].map((c) => (
                            <label
                              className={
                                (session
                                  ? actualPolicy.categories
                                  : categories
                                ).includes(c)
                                  ? "category checked"
                                  : "category"
                              }
                              key={c}
                            >
                              <input
                                type="checkbox"
                                disabled={!!session}
                                checked={(session
                                  ? actualPolicy.categories
                                  : categories
                                ).includes(c)}
                                onChange={() =>
                                  setCategories((old) =>
                                    old.includes(c)
                                      ? old.filter((x) => x !== c)
                                      : [...old, c],
                                  )
                                }
                              />
                              {c}
                            </label>
                          ))}
                        </div>
                      </div>
                      <div className="policy-note">
                        <LockKeyhole size={13} />
                        <span>
                          {session
                            ? "Policy and quote bound to one approval."
                            : "Money actions run only after policy checks."}
                        </span>
                      </div>
                      {session && session.checks.length > 0 && (
                        <div className="policy-results">
                          {session.checks.map((c) => (
                            <span key={c.rule}>
                              <CircleCheck size={14} />
                              {c.rule} passed
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="audit-panel panel">
                    <div className="panel-heading">
                      <h2>
                        <Fingerprint size={19} />
                        Audit ledger
                      </h2>
                      <span className="entry-count">
                        {String(events.length).padStart(2, "0")} entries
                      </span>
                    </div>
                    <div className="ledger-caption">
                      <span>Event / proof</span>
                      <span>SHA-256</span>
                    </div>
                    {events.length === 0 ? (
                      <div className="empty-ledger">
                        <div className="receipt-lines">
                          {[1, 2, 3].map((n) => (
                            <div key={n}>
                              <span>0{n}</span>
                              <i />
                              <Square size={12} />
                            </div>
                          ))}
                        </div>
                        <p>The record begins with your mandate.</p>
                        <small>
                          Every entry includes the hash of the one before it.
                        </small>
                      </div>
                    ) : (
                      <div className="ledger-rows">
                        {events.map((event) => (
                          <details
                            className={
                              "ledger-row " +
                              (event.action === "payment_captured"
                                ? "stamp-row"
                                : "")
                            }
                            key={event.sequence}
                          >
                            <summary>
                              <span className="ledger-number">
                                {String(event.sequence).padStart(2, "0")}
                              </span>
                              <div>
                                <span>
                                  {labels[event.action] ||
                                    event.action.replaceAll("_", " ")}
                                </span>
                                <code>{event.hash.slice(0, 12)}…</code>
                              </div>
                              {event.action === "payment_captured" ? (
                                <span className="mini-stamp">
                                  <Check size={14} />
                                </span>
                              ) : (
                                <Check size={13} className="ledger-check" />
                              )}
                            </summary>
                            <div className="hash-detail">
                              <span>Entry hash</span>
                              <code>{event.hash}</code>
                              <span>Previous hash</span>
                              <code>{event.prev_hash}</code>
                            </div>
                          </details>
                        ))}
                      </div>
                    )}
                    <div className="ledger-footer">
                      <div>
                        <span
                          className={
                            "small-dot " +
                            (session?.verification.valid ? "green" : "slate")
                          }
                        />
                        {session?.verification.valid
                          ? "Hash chain verified"
                          : "No entries to verify"}
                        <span className="chain-link">
                          {events.length
                            ? `${events.length} / ${events.length}`
                            : "—"}
                        </span>
                      </div>
                      {session && (
                        <>
                          <div className="audit-actions">
                            <button
                              className="text-button"
                              onClick={() =>
                                void action(async () => {
                                  const fresh = await api<Session>(
                                    `/sessions/${session.id}`,
                                  );
                                  setSession(fresh);
                                  setVerified(true);
                                })
                              }
                            >
                              <ShieldCheck size={14} />
                              Verify chain
                            </button>
                            <a
                              href={`/api/sessions/${session.id}/audit`}
                              download
                            >
                              <ArrowDownToLine size={14} />
                              Export receipt
                            </a>
                          </div>
                          {verified && (
                            <span role="status" className="verification-result">
                              {session.verification.valid
                                ? `Verified ${events.length} entries against the stored head.`
                                : "Integrity check failed."}
                            </span>
                          )}
                        </>
                      )}
                      <small>
                        Hash-linked, not externally anchored. Save an exported
                        root independently for stronger verification.
                      </small>
                    </div>
                  </section>
                </div>
              </div>
              <div className="bottom-note">
                <span>
                  <Layers3 size={14} />
                  LangGraph orchestration · SQLite persistence · SHA-256 audit
                </span>
                <span>
                  {session?.payment_mode === "razorpay"
                    ? "Official Razorpay MCP · test mode"
                    : "Rehearsal payments are simulated"}
                </span>
              </div>
            </>
          )}

          {view === "catalog" && (
            <div className="catalog-grid">
              {catalog.map((product) => (
                <article className="catalog-product" key={product.id}>
                  <div className="product-visual">
                    <ProductDrawing kind={product.category} />
                    <span className="product-id">{product.id}</span>
                  </div>
                  <div className="product-copy">
                    <span className="small-label">{product.category}</span>
                    <h2>{product.name}</h2>
                    <p>{product.description}</p>
                    <div className="product-tags">
                      {product.tags.map((t) => (
                        <span key={t}>{t}</span>
                      ))}
                    </div>
                    <div className="product-price">
                      <strong>{money(product.price)}</strong>
                      <span>
                        <span className="small-dot green" />
                        {product.stock} in stock
                      </span>
                    </div>
                  </div>
                </article>
              ))}
              <div className="catalog-footnote">
                Seeded demo catalog. Rehearsal purchases reserve local stock; no
                merchant inventory is changed.
              </div>
            </div>
          )}

          {view === "receipts" && (
            <section className="panel history-panel">
              <div className="panel-heading">
                <h2>
                  <ClipboardList size={19} />
                  Session register
                </h2>
                <span>{history.length} sessions</span>
              </div>
              {history.length === 0 ? (
                <div className="empty-state">
                  <ClipboardList size={30} />
                  <h3>No receipts yet.</h3>
                  <p>Start a negotiation to create your first audit trail.</p>
                  <button
                    className="primary"
                    onClick={() => setView("control")}
                  >
                    Open control room
                  </button>
                </div>
              ) : (
                history.map((s) => (
                  <button
                    className="history-row"
                    key={s.id}
                    onClick={() =>
                      void action(async () => {
                        setSession(await api<Session>(`/sessions/${s.id}`));
                        setView("control");
                        setVerified(false);
                      })
                    }
                  >
                    <span className="history-id">
                      #{s.id.slice(0, 8)}
                      <small>
                        {new Date(s.created_at).toLocaleDateString("en-GB")}
                      </small>
                    </span>
                    <span className="history-goal">
                      {s.goal}
                      <small>
                        {s.payment_mode === "simulated"
                          ? "Simulated payment"
                          : "Razorpay test"}
                      </small>
                    </span>
                    <span className="history-status">
                      {statusText[s.status]}
                      <small>{money(s.spend_so_far)}</small>
                    </span>
                    <ChevronDown size={16} />
                  </button>
                ))
              )}
            </section>
          )}

          {view === "connections" && (
            <div className="connections-grid">
              <section className="connection-card">
                <div>
                  <Terminal size={24} />
                  <span className="pill">
                    {health?.openai_configured
                      ? "Key configured"
                      : "Not configured"}
                  </span>
                </div>
                <h2>OpenAI agents</h2>
                <p>
                  Buyer selection and seller offers use structured model
                  responses. Policy checks stay in the application.
                </p>
                <dl>
                  <dt>Model</dt>
                  <dd>{health?.openai_model || "gpt-4.1-mini"}</dd>
                  <dt>Credential location</dt>
                  <dd>Server-side environment</dd>
                </dl>
                <div className="connection-note">
                  A configured key does not guarantee API credits. A session
                  will report authentication, quota or network errors.
                </div>
                <a
                  href="https://platform.openai.com/settings/organization/billing"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open API billing
                </a>
              </section>
              <section className="connection-card">
                <div>
                  <Layers3 size={24} />
                  <span className="pill">
                    {health?.razorpay_configured
                      ? "Test keys configured"
                      : "Setup required"}
                  </span>
                </div>
                <h2>Razorpay MCP</h2>
                <p>
                  Orders, payment verification and capture go through Razorpay’s
                  official MCP server.
                </p>
                <dl>
                  <dt>Endpoint</dt>
                  <dd>mcp.razorpay.com/mcp</dd>
                  <dt>Environment</dt>
                  <dd>Test keys only</dd>
                </dl>
                <div className="connection-note">
                  Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env.local,
                  then restart the API. Live keys are rejected.
                </div>
                <button
                  className="secondary"
                  disabled={busy || !health?.razorpay_configured}
                  onClick={() =>
                    void action(async () => {
                      const r = await api<{ tools: string[] }>(
                        "/integrations/razorpay/check",
                        {},
                      );
                      setMcpStatus(
                        `Connected. ${r.tools.length} tools discovered.`,
                      );
                    })
                  }
                >
                  Check MCP connection
                </button>
                {mcpStatus && (
                  <p className="green-text" role="status">
                    {mcpStatus}
                  </p>
                )}
              </section>
              <section className="connection-card local-tools">
                <h2>Local trust infrastructure</h2>
                <div>
                  <span>
                    <CircleCheck size={17} />
                    LangGraph workflow
                  </span>
                  <span>
                    <CircleCheck size={17} />
                    SQLite session storage
                  </span>
                  <span>
                    <CircleCheck size={17} />
                    SHA-256 audit chain
                  </span>
                </div>
                <p>
                  This prototype runs for one local operator. Human approval is
                  a local UI action; no external identity signature or
                  blockchain anchor is claimed.
                </p>
              </section>
            </div>
          )}
        </main>
        <footer>
          <span>
            <Seal />
            Counterseal
          </span>
          <span>Built for explainable, bounded, gated commerce.</span>
          <span>v0.1 / Test only</span>
        </footer>
      </div>
    </div>
  );
}
