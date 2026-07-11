import api from "../api.js";
import { formatCurrency } from "../helpers.js";

const formatVal = (v) => {
  return window.formatCurrency ? window.formatCurrency(v) : formatCurrency(v);
};

let customers = [];
let filteredCustomers = [];
let selectedCustomer = null;
let selectedLoan = null;
let customerLoans = [];
let loanPayments = [];

const paymentsContent = document.getElementById("payments-content");
const searchInput = document.getElementById("customer-search-input");
const listContainer = document.getElementById("customer-list-card");
const loanSelectorCard = document.getElementById("loan-selector-card");
const loanListButtons = document.getElementById("loan-list-buttons");

const unselectedPlaceholder = document.getElementById("unselected-placeholder");
const activeWorkdesk = document.getElementById("active-workdesk");

const summaryRate = document.getElementById("summary-rate");
const summaryFormula = document.getElementById("summary-formula");
const summaryDates = document.getElementById("summary-dates");
const summaryStatusBadge = document.getElementById("summary-status-badge");

const formError = document.getElementById("form-error-msg");
const formSuccess = document.getElementById("form-success-msg");
const paymentForm = document.getElementById("record-payment-form");
const submitBtn = document.getElementById("form-submit-btn");

const paymentsBody = document.getElementById("loan-payments-table-body");
const paymentsEmpty = document.getElementById("loan-payments-empty");
const paymentsTable = document.getElementById("loan-payments-table-container");

const exportBtn = document.getElementById("export-csv-btn");

// Form payment date default today
const formDateInput = paymentForm?.querySelector('input[name="payment_date"]');
if (formDateInput) {
  formDateInput.value = new Date().toISOString().split("T")[0];
}

async function init() {
  try {
    const res = await api.get("/customers", { limit: 100 });
    const payload = res.data || res;
    customers = payload.customers || payload || [];
    filteredCustomers = [...customers];
    
    renderCustomerList();

    // Bind local filter events
    searchInput?.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      filteredCustomers = customers.filter(c => 
        (c.name || "").toLowerCase().includes(q) ||
        (c.phone_number || "").includes(q)
      );
      renderCustomerList();
    });

    // Form record payment
    paymentForm?.addEventListener("submit", handleRecordPayment);

    // Export CSV
    exportBtn?.addEventListener("click", handleExportCsv);

    paymentsContent?.classList.remove("hidden");
  } catch (err) {
    console.error("Failed to load customer list on counter:", err);
  }
}

function renderCustomerList() {
  if (filteredCustomers.length === 0) {
    listContainer.innerHTML = `<p class="text-center text-xs text-text-muted py-8 font-semibold">No customers found.</p>`;
    return;
  }

  listContainer.innerHTML = filteredCustomers.map(c => {
    const isSelected = selectedCustomer?.id === c.id;
    return `
      <button data-id="${c.id}" class="customer-select-btn w-full text-left px-4 py-3 rounded-md transition-all duration-100 flex items-center justify-between cursor-pointer border-none bg-transparent ${
        isSelected 
          ? "bg-primary text-white" 
          : "text-text-primary hover:bg-slate-100/50"
      }">
        <div>
          <p class="font-bold text-xs ${isSelected ? "text-white" : "text-text-primary"}">${c.name}</p>
          <p class="text-[10px] mt-0.5" style="opacity: ${isSelected ? 0.8 : 0.6};">${c.phone_number}</p>
        </div>
      </button>
    `;
  }).join("");

  // Attach button clicks
  listContainer.querySelectorAll(".customer-select-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.getAttribute("data-id"));
      const target = customers.find(c => c.id === id);
      if (target) {
        await selectCustomer(target);
      }
    });
  });
}

async function selectCustomer(c) {
  selectedCustomer = c;
  selectedLoan = null;
  customerLoans = [];
  loanPayments = [];
  
  formError.classList.add("hidden");
  formSuccess.classList.add("hidden");
  paymentForm?.reset();
  if (formDateInput) {
    formDateInput.value = new Date().toISOString().split("T")[0];
  }

  renderCustomerList(); // Refreshes active class style

  activeWorkdesk.classList.add("hidden");
  unselectedPlaceholder.classList.remove("hidden");
  loanSelectorCard.classList.add("hidden");

  try {
    const res = await api.get(`/customers/${c.id}`);
    const payload = res.data || res;
    customerLoans = payload.loans || [];

    if (customerLoans.length > 0) {
      loanSelectorCard.classList.remove("hidden");
      renderLoanSelector();

      // Auto-select first active/overdue loan
      const active = customerLoans.find(l => l.status === "ACTIVE" || l.status === "OVERDUE") || customerLoans[0];
      if (active) {
        await selectLoan(active);
      }
    } else {
      loanSelectorCard.classList.add("hidden");
    }
  } catch (err) {
    console.error("Failed to load customer loans:", err);
  }
}

function renderLoanSelector() {
  loanListButtons.innerHTML = customerLoans.map(loan => {
    const isSelected = selectedLoan?.id === loan.id;
    return `
      <button data-loan-id="${loan.id}" class="loan-select-btn text-left px-4 py-3 rounded-md transition-all text-xs cursor-pointer border bg-transparent w-full ${
        isSelected 
          ? "bg-blue-50/50 border-primary text-text-primary" 
          : "border-border-default hover:bg-slate-100/50 text-text-secondary"
      }">
        <p class="font-bold">Account #${loan.id}</p>
        <p class="text-[10px] text-text-muted mt-0.5">${formatVal(loan.principal_amount)} · Status: ${loan.status}</p>
      </button>
    `;
  }).join("");

  // Attach button clicks
  loanListButtons.querySelectorAll(".loan-select-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const loanId = parseInt(btn.getAttribute("data-loan-id"));
      const match = customerLoans.find(l => l.id === loanId);
      if (match) {
        await selectLoan(match);
      }
    });
  });
}

async function selectLoan(loan) {
  selectedLoan = loan;
  formError.classList.add("hidden");
  formSuccess.classList.add("hidden");

  renderLoanSelector(); // Refreshes active class style

  // Fill summary details
  summaryRate.innerText = window.formatInterestRate ? window.formatInterestRate(loan.interest_rate) : `${loan.interest_rate}%`;
  summaryFormula.innerText = loan.interest_formula;
  summaryDates.innerText = `${loan.loan_start_date} → ${loan.loan_end_date}`;

  const statusVariants = {
    ACTIVE: "bg-blue-50 text-blue-700 border-blue-100",
    COMPLETED: "bg-emerald-50 text-emerald-700 border-emerald-100",
    OVERDUE: "bg-rose-50 text-rose-700 border-rose-100",
    DEFAULTED: "bg-rose-50 text-rose-700 border-rose-100"
  };
  const variantClass = statusVariants[loan.status] || "bg-slate-50 text-slate-700 border-slate-100";
  summaryStatusBadge.innerHTML = `
    <span class="inline-block px-2.5 py-0.5 text-[10px] font-bold rounded border uppercase ${variantClass}">
      ${loan.status}
    </span>
  `;

  // Fetch payments list
  await refreshLoanPayments();

  unselectedPlaceholder.classList.add("hidden");
  activeWorkdesk.classList.remove("hidden");
}

async function refreshLoanPayments() {
  if (!selectedLoan) return;

  try {
    const res = await api.get(`/payments/loan/${selectedLoan.id}`);
    const payload = res.data || res;
    loanPayments = payload || [];

    if (loanPayments.length === 0) {
      paymentsEmpty.classList.remove("hidden");
      paymentsTable.classList.add("hidden");
    } else {
      paymentsEmpty.classList.add("hidden");
      paymentsTable.classList.remove("hidden");

      paymentsBody.innerHTML = loanPayments.map(p => {
        const norm = (p.payment_status || "PENDING").toUpperCase();
        let badgeClass = "bg-amber-50 text-amber-700 border-amber-100"; // PENDING
        if (norm === "PAID") {
          badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-100";
        } else if (norm === "PARTIALLY PAID") {
          badgeClass = "bg-blue-50 text-blue-700 border-blue-100";
        } else if (norm === "MISSED") {
          badgeClass = "bg-orange-50 text-orange-700 border-orange-100";
        } else if (norm === "OVERDUE") {
          badgeClass = "bg-rose-50 text-rose-700 border-rose-100";
        } else if (norm === "COMPLETED") {
          badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-100";
        }
        const statusBadge = `<span class="inline-block px-2 py-0.5 text-[10px] font-bold rounded border uppercase ${badgeClass}">${norm}</span>`;

        const paidTextClass = parseFloat(p.amount_paid) > 0 ? "text-success font-bold" : "text-text-muted";

        return `
          <tr>
            <td class="font-semibold text-text-primary text-xs">${p.payment_date}</td>
            <td class="text-right font-mono text-xs text-text-secondary">${formatVal(p.expected_amount)}</td>
            <td class="text-right font-mono text-xs ${paidTextClass}">${formatVal(p.amount_paid)}</td>
            <td class="text-xs text-text-secondary font-semibold">${p.payment_mode || "—"}</td>
            <td>${statusBadge}</td>
            <td class="text-xs text-text-secondary font-semibold">${p.recorded_by_name || "—"}</td>
            <td class="text-xs text-text-muted font-mono">${p.created_at || "—"}</td>
            <td class="text-xs text-text-secondary italic">${p.remarks || "—"}</td>
          </tr>
        `;
      }).join("");

    }

    if (window.lucide) {
      window.lucide.createIcons();
    }

  } catch (err) {
    console.error("Failed to load loan payments:", err);
  }
}

async function handleRecordPayment(e) {
  e.preventDefault();
  formError.classList.add("hidden");
  formSuccess.classList.add("hidden");

  if (!selectedLoan) {
    formError.innerText = "Select a loan first.";
    formError.classList.remove("hidden");
    return;
  }

  const formData = new FormData(paymentForm);
  const data = Object.fromEntries(formData.entries());

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin mr-1"></i> Recording...`;
  if (window.lucide) window.lucide.createIcons();

  try {
    const payload = {
      loan_id: selectedLoan.id,
      payment_date: data.payment_date,
      amount_paid: parseFloat(data.amount_paid),
      payment_mode: data.payment_mode,
      remarks: data.remarks || undefined
    };

    await api.post("/payments", payload);

    formSuccess.innerText = `₹${parseFloat(payload.amount_paid).toLocaleString("en-IN")} recorded successfully for ${payload.payment_date}.`;
    formSuccess.classList.remove("hidden");
    
    // Clear amount & remarks
    paymentForm.querySelector('input[name="amount_paid"]').value = "";
    paymentForm.querySelector('input[name="remarks"]').value = "";

    // Dynamic UI Refresh: reload customer list and details cards immediately
    const customerId = selectedCustomer.id;
    const loanId = selectedLoan.id;
    await init();
    const updatedCustomer = customers.find(c => c.id === customerId);
    if (updatedCustomer) {
      selectedCustomer = updatedCustomer;
      const resLoans = await api.get(`/customers/${customerId}`);
      const payloadLoans = resLoans.data || resLoans;
      customerLoans = payloadLoans.loans || [];
      renderLoanSelector();
      const updatedLoan = customerLoans.find(l => l.id === loanId);
      if (updatedLoan) {
        await selectLoan(updatedLoan);
      }
    } else {
      await refreshLoanPayments();
    }


  } catch (err) {
    const card = document.getElementById("payment-entry-card");
    if (card) {
      card.classList.remove("sa-shake");
      void card.offsetWidth;
      card.classList.add("sa-shake");
    }
    const msg = err.detail || err.message || "Failed to record payment.";
    formError.innerText = msg;
    formError.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span>Record Payment</span>`;
  }
}

async function handleExportCsv() {
  try {
    let params = "";
    if (selectedLoan) {
      params = `?loan_id=${selectedLoan.id}`;
    } else if (selectedCustomer) {
      params = `?customer_id=${selectedCustomer.id}`;
    }

    // Direct browser download by building custom headers with credentials inclusion
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"}/payments/export/csv${params}`, {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${localStorage.getItem("access_token")}`
      },
      credentials: "include"
    });

    if (!response.ok) {
      throw new Error("Export request failed");
    }

    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = window.URL.createObjectURL(blob);
    link.setAttribute("download", `payments_export_${new Date().toISOString().split("T")[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();

  } catch (err) {
    console.error("Export failed:", err);
  }
}

// Start load
setTimeout(init, 100);

window.addEventListener("language-changed", () => {
  renderCustomerList();
  if (selectedLoan) {
    selectLoan(selectedLoan);
  }
});
