// QueueStorm Investigator — frontend logic. No frameworks, no build step.
// Tabs are pure DOM; the API is hit with fetch() and the response rendered inline.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const EXAMPLES = {
  wrong_transfer: {
    ticket_id: "TKT-DEMO-WT",
    complaint: "I sent 5000 taka to a wrong number around 2pm today. Please refund.",
    language: "en", channel: "in_app_chat", user_type: "customer",
    transaction_history: [
      { transaction_id: "TXN-9101", timestamp: "2026-04-14T14:08:22Z",
        type: "transfer", amount: 5000, counterparty: "+8801719876543", status: "completed" },
    ],
  },
  payment_failed: {
    ticket_id: "TKT-DEMO-PF",
    complaint: "Payment failed but my balance deducted 1200 taka for the bill. Did not receive confirmation.",
    language: "en", channel: "in_app_chat", user_type: "customer",
    transaction_history: [
      { transaction_id: "TXN-7701", timestamp: "2026-04-15T10:11:00Z",
        type: "payment", amount: 1200, counterparty: "merchant_bill_42", status: "failed" },
    ],
  },
  duplicate_payment: {
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
  phishing: {
    ticket_id: "TKT-DEMO-PHISH",
    complaint: "Someone called and asked me to share my PIN and OTP to verify my account.",
    language: "en", channel: "call_center", user_type: "customer",
    transaction_history: [],
  },
  bangla: {
    ticket_id: "TKT-DEMO-BN",
    complaint: "আমি ভুল নাম্বারে ২০০০ টাকা পাঠিয়ে দিয়েছি, এখন ফেরত চাই।",
    language: "bn", channel: "in_app_chat", user_type: "customer",
    transaction_history: [],
  },
  merchant: {
    ticket_id: "TKT-DEMO-MER",
    complaint: "My merchant settlement for last week is still pending, 5 days have passed.",
    language: "en", channel: "merchant_portal", user_type: "merchant",
    transaction_history: [
      { transaction_id: "TXN-MS", timestamp: "2026-04-10T18:00:00Z",
        type: "settlement", amount: 45000, counterparty: "merchant_self", status: "pending" },
    ],
  },
  agent_cash_in: {
    ticket_id: "TKT-DEMO-AG",
    complaint: "I deposited 3000 taka through agent yesterday but the agent says they did not receive it.",
    language: "en", channel: "in_app_chat", user_type: "customer",
    transaction_history: [
      { transaction_id: "TXN-CI", timestamp: "2026-04-13T15:00:00Z",
        type: "cash_in", amount: 3000, counterparty: "agent_01711", status: "pending" },
    ],
  },
  refund_request: {
    ticket_id: "TKT-DEMO-REF",
    complaint: "I want my money back, the cashback I was promised did not come through.",
    language: "en", channel: "in_app_chat", user_type: "customer",
    transaction_history: [],
  },
};

const BATCH_SAMPLE = {
  tickets: [
    EXAMPLES.wrong_transfer,
    EXAMPLES.payment_failed,
    EXAMPLES.phishing,
    { ticket_id: "TKT-EMPTY", complaint: "", language: "en", channel: "in_app_chat", user_type: "customer" },
  ],
};

// -------------------- Tabs --------------------
function activateTab(name) {
  $$(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === `tab-${name}`));
}
$$(".tab").forEach(btn => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));

// -------------------- Health badge --------------------
async function checkHealth() {
  const dot = $("#health-dot");
  const label = $("#health-label");
  try {
    const r = await fetch("/health");
    if (!r.ok) throw new Error("non-200");
    dot.className = "dot dot-ok";
    label.textContent = "healthy";
    label.style.color = "var(--ok)";
  } catch (e) {
    dot.className = "dot dot-bad";
    label.textContent = "unreachable";
    label.style.color = "var(--danger)";
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
  const v = String(value || "");
  return `<span class="chip chip-case-${v}">${escape(v)}</span>`;
}
function chipSev(value) {
  const v = String(value || "");
  return `<span class="chip chip-sev-${v}">${escape(v)}</span>`;
}

// -------------------- Analyze form --------------------
$("#load-example").addEventListener("click", () => {
  const ex = EXAMPLES.wrong_transfer;
  const f = $("#ticket-form");
  f.ticket_id.value = ex.ticket_id;
  f.complaint.value = ex.complaint;
  f.language.value = ex.language;
  f.channel.value = ex.channel;
  f.user_type.value = ex.user_type;
  f.transaction_history.value = JSON.stringify(ex.transaction_history, null, 2);
});

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
    if (!ok) {
      alert(`Error ${status}: ${JSON.stringify(data)}`);
      return;
    }
    $("#decision-out").hidden = false;
    $("#chip-case").className = `chip chip-case-${data.case_type}`;
    $("#chip-case").textContent = data.case_type;
    $("#chip-severity").className = `chip chip-sev-${data.severity}`;
    $("#chip-severity").textContent = data.severity;
    $("#chip-department").textContent = data.department;
    $("#chip-department").className = "chip";
    $("#chip-evidence").textContent = data.evidence_verdict;
    $("#chip-evidence").className = "chip";
    $("#kv-ticket").textContent = data.ticket_id;
    $("#kv-txn").textContent = data.relevant_transaction_id || "—";
    $("#kv-review").textContent = data.human_review_required ? "yes" : "no";
    $("#kv-conf").textContent = data.confidence;
    $("#kv-rid").textContent = headers.get("x-request-id") || "—";
    $("#kv-reasons").textContent = (data.reason_codes || []).join(", ") || "—";
    $("#out-summary").textContent = data.agent_summary || "—";
    $("#out-action").textContent = data.recommended_next_action || "—";
    $("#out-reply").textContent = data.customer_reply || "—";
  } catch (e) {
    alert("Request failed: " + e.message);
  }
});

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
    let html = `<p><strong>count</strong>: ${data.count}</p>`;
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
    const color = data.ok ? "var(--ok)" : "var(--danger)";
    out.innerHTML = `<p style='color:${color}'><strong>${data.passed}/${data.total}</strong> passed${data.ok ? " ✓" : ` — failures: ${data.failures.length}`}</p>`;
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
        <td>${c.passed ? "✓" : "✗"}</td>`;
      tbody.appendChild(tr);
    });
    $("#selftest-table").hidden = false;
  } catch (e) { out.innerHTML = `<p style='color:var(--danger)'>Request failed: ${escape(e.message)}</p>`; }
});

// -------------------- Metrics --------------------
$("#load-metrics").addEventListener("click", loadMetrics);
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
      // match: metric_name{labels} value
      const m = line.match(/^([a-zA-Z_][a-zA-Z0-9_]*)(?:\{([^}]*)\})?\s+(\S+)/);
      if (!m) return;
      const [, name, labels, value] = m;
      rows.push({ name, labels: labels || "", value });
    });
    if (!rows.length) { tbody.innerHTML = "<tr><td colspan='3' class='muted'>No metrics</td></tr>"; return; }
    tbody.innerHTML = rows.map(r =>
      `<tr><td>${escape(r.name)}</td><td>${escape(r.labels)}</td><td class='num'>${escape(r.value)}</td></tr>`
    ).join("");
  } catch (e) { tbody.innerHTML = `<tr><td colspan='3' style='color:var(--danger)'>${escape(e.message)}</td></tr>`; }
}
loadMetrics();