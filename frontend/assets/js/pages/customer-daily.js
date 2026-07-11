import api from "../api.js";
import { formatCurrency } from "../helpers.js";

const formatVal = (v) => {
  return window.formatCurrency ? window.formatCurrency(v) : formatCurrency(v);
};

async function loadDailyLedger() {
  const content = document.getElementById("daily-ledger-content");
  const todayDateText = document.getElementById("today-date-text");
  const todayAmountEl = document.getElementById("today-collections-amount");
  const todayCountEl = document.getElementById("today-collections-count");
  const tableBody = document.getElementById("ledger-table-body");
  const tableContainer = document.getElementById("ledger-table-container");
  const ledgerEmpty = document.getElementById("ledger-empty");

  try {
    const res = await api.get("/payments/today");
    const payload = res.data || res;

    // 1. Stats details
    const dateStr = payload.date || new Date().toISOString().split("T")[0];
    const rawTotal = payload.total_amount || 0;
    const count = payload.count || 0;
    const payments = payload.payments || [];

    if (todayDateText) {
      todayDateText.innerText = window.formatDate ? window.formatDate(new Date(dateStr)) : new Date(dateStr).toLocaleDateString("en-IN", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric"
      });
    }

    if (todayAmountEl) todayAmountEl.innerText = formatVal(parseFloat(rawTotal));
    if (todayCountEl) todayCountEl.innerText = count;

    // 2. Table loading
    if (payments.length === 0) {
      ledgerEmpty?.classList.remove("hidden");
      tableContainer?.classList.add("hidden");
    } else {
      ledgerEmpty?.classList.add("hidden");
      tableContainer?.classList.remove("hidden");

      tableBody.innerHTML = payments.map(p => `
        <tr>
          <td class="font-mono text-xs text-text-muted">#${p.id}</td>
          <td class="font-semibold text-text-primary">Loan Account #${p.loan_id}</td>
          <td class="text-xs text-text-muted font-mono">${new Date(p.created_at || p.payment_date).toLocaleTimeString(window.currentLanguage === "te" ? "te-IN" : "en-IN")}</td>
          <td class="text-right font-bold text-success font-mono">${formatVal(p.amount_paid)}</td>
          <td class="text-xs text-text-secondary font-semibold">${p.payment_mode || "CASH"}</td>
          <td class="text-xs text-text-secondary italic">${p.remarks || "—"}</td>
        </tr>
      `).join("");
    }

    if (window.lucide) {
      window.lucide.createIcons();
    }

    content?.classList.remove("hidden");

  } catch (err) {
    console.error("Failed to load daily collections ledger:", err);
    ledgerEmpty?.classList.remove("hidden");
    tableContainer?.classList.add("hidden");
    content?.classList.remove("hidden");
  }
}

// Start load
setTimeout(loadDailyLedger, 100);

window.addEventListener("language-changed", () => {
  loadDailyLedger();
});
