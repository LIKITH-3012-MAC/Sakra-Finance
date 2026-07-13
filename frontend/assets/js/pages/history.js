import api from "../api.js";
import { formatCurrency, formatPhone } from "../helpers.js";
import { renderActivityTimeline } from "./loan-closure.js";

async function loadHistoryPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const customerId = urlParams.get("id");
  if (!customerId) {
    alert("No customer ID provided in URL parameters.");
    window.location.href = "/customers.html";
    return;
  }

  const loader = document.getElementById("global-page-loader");
  const content = document.getElementById("history-content");

  try {
    // 1. Fetch customer details
    const res = await api.get(`/customers/${customerId}`);
    const customer = res.data || res;

    // 2. Map core identity
    document.getElementById("history-name").innerText = customer.name;
    document.getElementById("history-phone").innerText = formatPhone(customer.phone_number);
    document.getElementById("history-aadhar").innerText = customer.aadhar_masked || "—";
    document.getElementById("history-customer-id").innerText = `#${customer.id}`;

    // Avatar Initials fallback
    const initials = customer.name.split(" ").map(n => n[0]).join("").substring(0, 2);
    document.getElementById("history-avatar-fallback").innerText = initials;

    // Load active or primary loan details
    const activeLoan = customer.loans?.find(l => l.status === "ACTIVE") || customer.loans?.[0];
    if (activeLoan) {
      document.getElementById("history-loan-id").innerText = `#${activeLoan.id}`;
      
      const principal = parseFloat(activeLoan.principal_amount || 0);
      const interest = parseFloat(activeLoan.interest_amount || 0);
      const totalPaid = parseFloat(activeLoan.balance_summary?.total_paid || 0);
      const totalRepayable = parseFloat(activeLoan.total_repayable_amount || 0);

      document.getElementById("history-stat-principal").innerText = formatCurrency(principal);
      document.getElementById("history-stat-interest").innerText = formatCurrency(interest);
      document.getElementById("history-stat-collected").innerText = formatCurrency(totalPaid);

      // Status pill mapping
      const statusEl = document.getElementById("history-stat-status");
      statusEl.innerText = activeLoan.status;
      if (activeLoan.status === "CLOSED" || activeLoan.balance_summary?.remaining_balance <= 0) {
        statusEl.className = "text-xs font-extrabold inline-flex items-center w-fit px-2.5 py-0.5 rounded border uppercase mt-1 status-pill-closed";
      } else if (activeLoan.status === "OVERDUE") {
        statusEl.className = "text-xs font-extrabold inline-flex items-center w-fit px-2.5 py-0.5 rounded border uppercase mt-1 bg-rose-500/10 text-rose-400 border-rose-500/20";
      } else {
        statusEl.className = "text-xs font-extrabold inline-flex items-center w-fit px-2.5 py-0.5 rounded border uppercase mt-1 bg-blue-500/10 text-blue-400 border-blue-500/20";
      }

      // Analytics snapshots
      const dailyInstallment = parseFloat(activeLoan.daily_installment || 0);
      const equivCoverage = dailyInstallment > 0 ? (totalPaid / dailyInstallment) : 0;
      document.getElementById("history-anal-coverage").innerText = `${equivCoverage.toFixed(1)} Days`;

      // Delinquency days
      const today = new Date();
      today.setHours(0,0,0,0);
      const start = new Date(activeLoan.loan_start_date);
      start.setHours(0,0,0,0);
      const elapsedDays = Math.max(0, Math.floor((today - start) / (1000 * 60 * 60 * 24)));
      const behindDays = elapsedDays - equivCoverage;
      
      const behindEl = document.getElementById("history-anal-behind");
      if (behindDays > 0) {
        behindEl.innerText = `${behindDays.toFixed(1)} Days Behind`;
        behindEl.className = "text-rose-400 font-bold";
      } else if (behindDays < 0) {
        behindEl.innerText = `${Math.abs(behindDays).toFixed(1)} Days Ahead`;
        behindEl.className = "text-emerald-400 font-bold";
      } else {
        behindEl.innerText = "On Schedule";
        behindEl.className = "text-emerald-400 font-bold";
      }
    } else {
      document.getElementById("history-loan-id").innerText = "No Loans";
      document.getElementById("history-stat-status").innerText = "REGISTERED";
      document.getElementById("history-stat-status").className = "text-xs font-extrabold inline-flex items-center w-fit px-2.5 py-0.5 rounded border border-white/10 uppercase mt-1";
    }

    // 3. Map bio metadata
    document.getElementById("history-bio-job").innerText = customer.occupation || "Unspecified";
    
    // Gender / Age
    const gender = customer.gender ? customer.gender.toUpperCase() : "—";
    let age = "—";
    if (customer.dob) {
      const birth = new Date(customer.dob);
      const diff = Date.now() - birth.getTime();
      const ageDate = new Date(diff);
      age = Math.abs(ageDate.getUTCFullYear() - 1970);
    }
    document.getElementById("history-bio-gender-age").innerText = `${gender} / ${age} Years`;
    document.getElementById("history-bio-address").innerText = customer.address || "No address on record";

    // Latest credit score
    document.getElementById("history-anal-credit").innerText = customer.aggregate?.credit_score || "700 (Default)";

    // 4. Render Activity timeline events
    await renderActivityTimeline(customerId, "history-timeline-container");

    // Reveal UI
    loader.classList.add("hidden");
    content.classList.remove("hidden");
  } catch (err) {
    loader.classList.add("hidden");
    alert("Failed to load history details: " + (err.message || err));
  }
}

// Start
document.addEventListener("DOMContentLoaded", loadHistoryPage);
