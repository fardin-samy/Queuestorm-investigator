// QueueStorm Investigator — frontend logic. No frameworks, no build step.

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// ---------- Example tickets (each entry powers a clickable card in the sidebar) ----------
const EXAMPLES = {
  wrong_transfer: {
    label: "Wrong transfer",
    icon: "↗️",
    hint: "Customer sent money to the wrong number",
    body: {
      ticket_id: "TKT-DEMO-WT",
      complaint: "I sent 5000 taka to a wrong number around 2pm today. Please refund.",
      language: "en", channel: "in_app_chat", user_type: "customer",
      transaction_history: [
        { transaction_id: "TXN-9101", timestamp: "2026-04-14T14:08:22Z",
          type: "transfer", amount: 5000, counterparty: "+8801719876543", status: "completed" },
      ],
    },
  },
  payment_failed: {
    label: "Payment failed",
    icon: "💳",
    hint: "Balance deducted, merchant not credited",
    body: {
      ticket_id: "TKT-DEMO-PF",
      complaint: "Payment failed but my balance deducted 1200 taka for the bill. Did not receive confirmation.",
      language: "en", channel: "in_app_chat", user_type: "customer",
      transaction_history: [
        { transaction_id: "TXN-7701", timestamp: "2026-04-15T10:11:00Z",
          type: "payment", amount: 1200, counterparty: "merchant_bill_42", status: "failed" },
      ],
    },
  },
  duplicate_payment: {
    label: "Duplicate payment",
    icon: "🔁",
    hint: "Charged twice for the same order",
    body: {
      ticket_id: "TKT-DEMO-DUP",
      complaint: "I was charged twice for the same payment of 800 taka. Please check.",
      language: "en", channel: "in_app_chat", user_type: "customer",
      transaction_history: [
        { transaction_id: "TXN-D1", timestamp: "2026-04-14T11:00:00Z",
          type: "payment", amount: 800, counterparty: "merchant_x", status: "completed" },
        { transaction_id: "TXN-D2", timestamp: "2026-04-14T11:00:42Z",
          type: "payment", amount: 800, counterparty: "merchant_x", status: "completed" },
      ],
    },
  },
  phishing: {
    label: "Phishing attempt",
    icon: "🎣",
    hint: "Asks for PIN / OTP — should be blocked",
    body: {
      ticket_id: "TKT-DEMO-PHISH",
      complaint: "Someone called and asked me to share my PIN and OTP to verify my account.",
      language: "en", channel: "call_center", user_type: "customer",
      transaction_history: [],
    },
  },
  bangla: {
    label: "Bangla refund",
    icon: "বাং",
    hint: "Mixed Bangla complaint",
    body: {
      ticket_id: "TKT-DEMO-BN",
      complaint: "আমি ভুল নাম্বারে ২০০০ টাকা পাঠিয়ে দিয়েছি, এখন ফেরত চাই।",
      language: "bn", channel: "in_app_chat", user_type: "customer",
      transaction_history: [],
    },
  },
  merchant: {
    label: "Merchant settlement",
    icon: "🏪",
    hint: "Settlement stuck for days",
    body: {
      ticket_id: "TKT-DEMO-MER",
      complaint: "My merchant settlement for last week is still pending, 5 days have passed.",
      language: "en", channel: "merchant_portal", user_type: "merchant",
      transaction_history: [
        { transaction_id: "TXN-MS", timestamp: "2026-04-10T18:00:00Z",
          type: "settlement", amount: 45000, counterparty: "merchant_self", status: "pending" },
      ],
    },
  },
  agent_cash_in: {
    label: "Agent cash-in",
    icon: "🏧",
    hint: "Cash-in dispute with agent",
    body: {
      ticket_id: "TKT-DEMO-AG",
      complaint: "I deposited 3000 taka through agent yesterday but the agent says they did not receive it.",
      language: "en", channel: "in_app_chat", user_type: "customer",
      transaction_history: [
        { transaction_id: "TXN-CI", timestamp: "2026-04-13T15:00:00Z",
          type: "cash_in", amount: 3000, counterparty: "agent_01711", status: "pending" },
      ],
    },
  },
  refund_request: {
    label: "Refund request",
    icon: "💸",
    hint: "Promised cashback not received",
    body: {
      ticket_id: "TKT-DEMO-REF",
      complaint: "I want my money back, the cashback I was promised did not come through.",
      language: "en", channel: "in_app_chat", user_type: "customer",
      transaction_history: [],
    },
  },
};

const EXAMPLE_ORDER = [
  "wrong_transfer", "payment_failed", "duplicate_payment", "phishing",
  "bangla", "merchant", "agent_cash_in", "refund_request",
];

const BATCH_SAMPLE = {
  tickets: [
    EXAMPLES.wrong_transfer.body,
    EXAMPLES.payment_failed.body,
    EXAMPLES.phishing.body,
    { ticket_id: "TKT-EMPTY", complaint: "", language: "en", channel: "in_app_chat", user_type: "customer" },
  ],
};

// Case-type color tokens (mirrors the left-border palette in styles.css)
const CASE_COLOR = {
  wrong_transfer:    "var(--case-wrong_transfer)",
  payment_failed:    "var(--case-payment_failed)",
  duplicate_payment: "var(--case-duplicate_payment)",
  phishing:          "var(--case-phishing)",
  refund_request:    "var(--case-refund_request)",
  cash_in_dispute:   "var(--case-cash_in_dispute)",
  merchant_settlement: "var(--case-merchant)",
  positive_feedback: "var(--case-positive)",
  unknown:           "var(--case-unknown)",
};

// -------------------- Tabs --------------------
function activateTab(name) {
  $$(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === `tab-${name}`));
}
$$(".tab").forEach(btn => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));

// -------------------- Health badge --------------------
async function checkHealth() {
  const pill = $("#status-pill");
  const label = $("#health-label");
  pill.classList.remove("ok", "bad", "loading");
  try {
    const r = await fetch("/health");
    if (!r.ok) throw new Error("non-200");
    pill.classList.add("ok");
    label.textContent = "service healthy";
  } catch (e) {
    pill.classList.add("bad");
    label.textContent = "service unreachable";
  }
}
checkHealth();
setInterval(checkHealth, 15000);

// -------------------- Helpers --------------------
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  let data; try { data = JSON.parse(text); } catch { data = { _raw: text }; }
  return { status: r.status, ok: r.ok, data, headers: r.headers };
}

function escape(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function chipCase(value) {
  return `<span class="chip chip-case-${escape(value)}">${escape(value)}</span>`;
}
function chipSev(value) {
  return `<span class="chip chip-sev-${escape(value)}">${escape(value)}</span>`;
}

// -------------------- Example-card sidebar --------------------
function renderExamples() {
  const host = $("#examples");
  host.innerHTML = "";
  EXAMPLE_ORDER.forEach(key => {
    const ex = EXAMPLES[key];
    const card = document.createElement("button");
    card.type = "button";
    card.className = "example";
    card.style.setProperty("--example-color", CASE_COLOR[key] || CASE_COLOR.unknown);
    card.innerHTML = `
      <div class="icon">${ex.icon}</div>
      <div class="name">${escape(ex.label)}</div>
      <div class="hint">${escape(ex.hint)}</div>`;
    card.addEventListener("click", () => loadExample(key));
    host.appendChild(card);
  });
}
renderExamples();

function loadExample(key) {
  const ex = EXAMPLES[key];
  if (!ex) return;
  const f = $("#ticket-form");
  f.ticket_id.value = ex.body.ticket_id || "";
  f.complaint.value = ex.body.complaint || "";
  f.language.value = ex.body.language || "en";
  f.channel.value = ex.body.channel || "in_app_chat";
  f.user_type.value = ex.body.user_type || "customer";
  f.transaction_history.value = ex.body.transaction_history
    ? JSON.stringify(ex.body.transaction_history, null, 2) : "";
  f.complaint.focus();
  f.scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#clear-form").addEventListener("click", () => {
  const f = $("#ticket-form");
  f.reset();
  f.ticket_id.value = "";
  f.complaint.value = "";
  f.transaction_history.value = "";
  $("#decision-empty").hidden = false;
  $("#decision-out").hidden = true;
});

// -------------------- Analyze form --------------------
$("#ticket-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  let history = [];
  const histRaw = f.transaction_history.value.trim();
  if (histRaw) {
    try { history = JSON.parse(histRaw); }
    catch (e) { return alert("Transaction history JSON is invalid: " + e.message); }
  }
  const body = {
    ticket_id: f.ticket_id.value.trim(),
    complaint: f.complaint.value,
    language: f.language.value,
    channel: f.channel.value,
    user_type: f.user_type.value,
    transaction_history: history,
  };
  $("#decision-empty").hidden = true;
  $("#decision-out").hidden = true;
  try {
    const { status, ok, data, headers } = await postJSON("/analyze-ticket", body);
    if (!ok) { alert(`Error ${status}: ${JSON.stringify(data)}`); return; }

    // Chips
    setChip("chip-case",      "chip-case",      data.case_type);
    setChipText("chip-case-text", data.case_type);
    setChip("chip-severity",  "chip-sev",       data.severity);
    setChipText("chip-sev-text", data.severity);
    setChip("chip-department","chip-dept",      data.department);
    setChipText("chip-dept-text", data.department);
    const evClass = data.evidence_verdict === "consistent"    ? "chip-ev-consistent"
                  : data.evidence_verdict === "inconsistent"  ? "chip-ev-inconsistent"
                  : data.evidence_verdict === "insufficient_data" ? "chip-ev-insufficient"
                  : "chip-ev-na";
    setChip("chip-evidence",  evClass,          data.evidence_verdict);
    setChipText("chip-ev-text", data.evidence_verdict);
    setChip("chip-review",    data.human_review_required ? "chip-review-yes" : "chip-review-no",
            data.human_review_required ? "review: yes" : "review: no");
    setChipText("chip-review-text", data.human_review_required ? "review: yes" : "review: no");

    // Stat tiles
    $("#kv-conf").textContent = data.confidence ?? "—";
    $("#stat-sev").textContent = data.severity || "—";
    $("#stat-evt").textContent = data.evidence_verdict || "—";
    $("#stat-rev").textContent = data.human_review_required ? "required" : "no";

    // KV
    $("#kv-ticket").textContent  = data.ticket_id || "—";
    $("#kv-txn").textContent     = data.relevant_transaction_id || "—";
    $("#kv-rid").textContent     = headers.get("x-request-id") || "—";
    $("#kv-reasons").textContent = (data.reason_codes || []).join(", ") || "—";

    // Output blocks
    $("#out-summary").textContent = data.agent_summary || "—";
    $("#out-action").textContent  = data.recommended_next_action || "—";
    $("#out-reply").textContent   = data.customer_reply || "—";

    $("#decision-out").hidden = false;
  } catch (e) { alert("Request failed: " + e.message); }
});

function setChip(id, klass, value) {
  const el = document.getElementById(id);
  // Reset classes except the base 'chip'
  el.className = "chip " + klass;
  el.setAttribute("data-value", value || "");
}
function setChipText(textId, value) {
  document.getElementById(textId).textContent = value || "—";
}

// -------------------- Batch --------------------
$("#batch-load-sample").addEventListener("click", () => {
  $("#batch-json").value = JSON.stringify(BATCH_SAMPLE, null, 2);
});

$("#batch-submit").addEventListener("click", async () => {
  const raw = $("#batch-json").value.trim();
  let body; try { body = JSON.parse(raw); } catch (e) { return alert("Invalid JSON: " + e.message); }
  const out = $("#batch-out");
  out.innerHTML = "<p class='muted'>Running…</p>";
  try {
    const { status, ok, data } = await postJSON("/analyze-tickets", body);
    if (!ok) { out.innerHTML = `<p style='color:var(--danger)'>Error ${status}: ${escape(JSON.stringify(data))}</p>`; return; }
    let html = `<div class="stats" style="margin-top:14px;">
      <div class="stat acc"><div class="label">Count</div><div class="value">${data.count}</div></div>
      <div class="stat evt"><div class="label">Successful</div><div class="value">${data.results.filter(r => r.status === 200).length}</div></div>
      <div class="stat rev"><div class="label">Per-ticket errors</div><div class="value">${data.results.filter(r => r.status !== 200).length}</div></div>
    </div>`;
    html += `<table><thead><tr><th>#</th><th>Ticket</th><th>Status</th><th>Case type</th><th>Department</th></tr></thead><tbody>`;
    data.results.forEach((r, i) => {
      const ct = r.body && r.body.case_type;
      const dp = r.body && r.body.department;
      const err = r.body && r.body.error;
      const color = r.status === 200 ? "var(--ok)" : "var(--danger)";
      html += `<tr>
        <td>${i + 1}</td>
        <td>${escape(r.ticket_id)}</td>
        <td style='color:${color}'>${r.status}${err ? " — " + escape(err) : ""}</td>
        <td>${ct ? chipCase(ct) : ""}</td>
        <td>${escape(dp || "")}</td>
      </tr>`;
    });
    html += "</tbody></table>";
    out.innerHTML = html;
  } catch (e) { out.innerHTML = `<p style='color:var(--danger)'>Request failed: ${escape(e.message)}</p>`; }
});

// -------------------- Self-test --------------------
$("#run-selftest").addEventListener("click", async () => {
  const out = $("#selftest-summary");
  out.innerHTML = "<p class='muted'>Running 10 hostile cases…</p>";
  $("#selftest-table").hidden = true;
  try {
    const r = await fetch("/selftest");
    const data = await r.json();
    const klass = data.ok ? "verdict ok" : "verdict bad";
    const icon  = data.ok ? "✅" : "⚠️";
    out.innerHTML = `<div class="${klass}">${icon} <span class="num">${data.passed}/${data.total}</span> passed${data.ok ? "" : ` — ${data.failures.length} failure(s)`}</div>`;
    const tbody = $("#selftest-table tbody");
    tbody.innerHTML = "";
    data.cases.forEach(c => {
      const tr = document.createElement("tr");
      tr.className = c.passed ? "passed" : "failed";
      tr.innerHTML = `
        <td>${escape(c.ticket_id)}</td>
        <td>${c.status}</td>
        <td>${c.case_type ? chipCase(c.case_type) : ""}</td>
        <td>${c.severity ? chipSev(c.severity) : ""}</td>
        <td>${escape(c.department || "")}</td>
        <td>${escape(c.evidence_verdict || "")}</td>
        <td>${c.human_review_required ? "yes" : "no"}</td>
        <td class="${c.passed ? "ok" : "bad"}">${c.passed ? "✓" : "✗"}</td>`;
      tbody.appendChild(tr);
    });
    $("#selftest-table").hidden = false;
  } catch (e) { out.innerHTML = `<p style='color:var(--danger)'>Request failed: ${escape(e.message)}</p>`; }
});

// -------------------- Metrics --------------------
$("#load-metrics").addEventListener("click", loadMetrics);
$("#toggle-metrics-raw").addEventListener("click", () => {
  const pre = $("#metrics-raw");
  const btn = $("#toggle-metrics-raw");
  pre.hidden = !pre.hidden;
  btn.textContent = pre.hidden ? "Show raw" : "Hide raw";
});

async function loadMetrics() {
  const tbody = $("#metrics-table tbody");
  tbody.innerHTML = "<tr><td colspan='3' class='muted'>Loading…</td></tr>";
  try {
    const r = await fetch("/metrics");
    const text = await r.text();
    $("#metrics-raw").textContent = text;
    const rows = [];
    text.split("\n").forEach(line => {
      if (!line || line.startsWith("#")) return;
      const m = line.match(/^([a-zA-Z_][a-zA-Z0-9_]*)(?:\{([^}]*)\})?\s+(\S+)/);
      if (!m) return;
      rows.push({ name: m[1], labels: m[2] || "", value: m[3] });
    });
    if (!rows.length) { tbody.innerHTML = "<tr><td colspan='3' class='muted'>No metrics</td></tr>"; return; }
    tbody.innerHTML = rows.map(r =>
      `<tr><td>${escape(r.name)}</td><td>${escape(r.labels)}</td><td class='num'>${escape(r.value)}</td></tr>`
    ).join("");
  } catch (e) { tbody.innerHTML = `<tr><td colspan='3' style='color:var(--danger)'>${escape(e.message)}</td></tr>`; }
}
loadMetrics();