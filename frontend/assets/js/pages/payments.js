import api from "../api.js";
import { formatCurrency } from "../helpers.js";
import { API_BASE_URL } from "../config.js";

const formatVal = (v) => {
  return window.formatCurrency ? window.formatCurrency(v) : formatCurrency(v);
};

let customers = [];
let filteredCustomers = [];
let selectedCustomer = null;
let selectedLoan = null;
let customerLoans = [];
let loanPayments = [];
let pendingSubmitData = null;
let customerDetailsCache = {};
let aggregatePayments = [];

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

// Double confirmation warning modal selectors
const doubleConfirmModal = document.getElementById("double-confirm-modal");
const confirmCustomerName = document.getElementById("confirm-customer-name");
const confirmCustomerId = document.getElementById("confirm-customer-id");
const confirmLoanId = document.getElementById("confirm-loan-id");
const confirmAmount = document.getElementById("confirm-amount");
const confirmCancelBtn = document.getElementById("confirm-cancel-btn");
const confirmApproveBtn = document.getElementById("confirm-approve-btn");

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

    // Bind local filter events matching multiple fields (Name, Phone, Customer ID, Loan ID, Aadhaar)
    searchInput?.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      filteredCustomers = customers.filter(c => {
        const nameMatch = (c.name || "").toLowerCase().includes(q);
        const phoneMatch = (c.phone_number || "").includes(q);
        const idMatch = String(c.id).includes(q) || `#${c.id}`.includes(q);
        const aadharMatch = (c.aadhar_masked || "").toLowerCase().includes(q);
        const loanMatch = (c.loans || []).some(l => 
          String(l.id).includes(q) || 
          `#${l.id}`.toLowerCase().includes(q)
        );
        return nameMatch || phoneMatch || idMatch || aadharMatch || loanMatch;
      });
      renderCustomerList();
    });

    // Form record payment
    paymentForm?.addEventListener("submit", handleRecordPayment);

    // Export CSV
    exportBtn?.addEventListener("click", handleExportCsv);

    // Modal click listeners
    confirmCancelBtn?.addEventListener("click", () => {
      doubleConfirmModal.classList.remove("active");
      doubleConfirmModal.classList.add("hidden");
      pendingSubmitData = null;
    });

    confirmApproveBtn?.addEventListener("click", async () => {
      doubleConfirmModal.classList.remove("active");
      doubleConfirmModal.classList.add("hidden");
      if (pendingSubmitData) {
        const payload = pendingSubmitData;
        pendingSubmitData = null;
        await executeRecordPayment(payload);
      }
    });

    const backBtn = document.getElementById("mobile-back-to-list-btn");
    if (backBtn) {
      backBtn.addEventListener("click", () => {
        document.querySelector(".payments-customer-panel")?.classList.remove("mobile-hidden");
        document.querySelector(".payments-workspace-panel")?.classList.add("mobile-hidden");
      });
    }

    // Auto-select customer from URL query param if present
    const urlParams = new URLSearchParams(window.location.search);
    const paramCustId = urlParams.get("customer_id");
    if (paramCustId) {
      const match = customers.find(c => String(c.id) === String(paramCustId));
      if (match) {
        selectCustomer(match);
      }
    }

    paymentsContent?.classList.remove("hidden");
  } catch (err) {
    console.error("Failed to load customer list on counter:", err);
  }
}

function renderCustomerList() {
  if (customers.length === 0) {
    listContainer.innerHTML = `<p class="text-center text-xs text-text-muted py-8 font-semibold">${window.t("payments_no_customer_available")}</p>`;
    
    // Set unselected placeholder texts to empty state dynamically
    const titleEl = document.querySelector("#unselected-placeholder h3");
    const descEl = document.querySelector("#unselected-placeholder p");
    if (titleEl) {
      titleEl.setAttribute("data-i18n", "payments_no_customer_available_title");
      titleEl.innerText = window.t("payments_no_customer_available_title");
    }
    if (descEl) {
      descEl.setAttribute("data-i18n", "payments_no_customer_available");
      descEl.innerText = window.t("payments_no_customer_available");
    }
    return;
  }

  if (filteredCustomers.length === 0) {
    listContainer.innerHTML = `<p class="text-center text-xs text-text-muted py-8 font-semibold">${window.t("customers_no_records")}</p>`;
    return;
  }

  listContainer.innerHTML = filteredCustomers.map(c => {
    const isSelected = selectedCustomer?.id === c.id;
    return `
      <button data-id="${c.id}" class="customer-select-btn w-full text-left px-4 py-3 rounded-md flex items-center justify-between cursor-pointer border bg-transparent ${
        isSelected 
          ? "active" 
          : "text-text-primary hover:bg-white/5"
      }" style="margin-bottom: 4px;">
        <div class="flex-1 min-w-0 pr-2">
          <p class="font-extrabold text-xs text-white truncate">${c.name}</p>
          <p class="text-[10px] text-text-secondary mt-0.5 font-mono truncate">${c.phone_number} • ID #${c.id}</p>
        </div>
        ${isSelected ? `<i data-lucide="check" class="w-3.5 h-3.5 text-blue-400 shrink-0"></i>` : ""}
      </button>
    `;
  }).join("");

  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Attach button clicks and hovers for instant latency prefetching
  listContainer.querySelectorAll(".customer-select-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.getAttribute("data-id"));
      const target = customers.find(c => c.id === id);
      if (target) {
        await selectCustomer(target);
      }
    });

    btn.addEventListener("mouseenter", () => {
      const id = parseInt(btn.getAttribute("data-id"));
      prefetchCustomer(id);
    });
  });
}

async function prefetchCustomer(id) {
  if (customerDetailsCache[id]) return;
  try {
    const res = await api.get(`/customers/${id}`);
    customerDetailsCache[id] = res.data || res;
  } catch (err) {
    console.warn(`Failed to prefetch customer details for ${id}:`, err);
  }
}

async function selectCustomer(c) {
  const startTime = performance.now();
  selectedCustomer = c;
  selectedLoan = null;
  customerLoans = [];
  loanPayments = [];
  
  // Mobile UI drill-down: toggle classes
  document.querySelector(".payments-customer-panel")?.classList.add("mobile-hidden");
  document.querySelector(".payments-workspace-panel")?.classList.remove("mobile-hidden");
  
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
    // Check client-side cache first
    let payload = customerDetailsCache[c.id];
    let cached = false;
    if (payload) {
      cached = true;
    } else {
      const res = await api.get(`/customers/${c.id}`);
      payload = res.data || res;
      customerDetailsCache[c.id] = payload;
    }

    const apiTime = performance.now();
    
    // Store full detailed customer profile
    const details = payload.customer || c;
    selectedCustomer = details;
    aggregatePayments = payload.aggregate_payments || [];

    // Update breadcrumbs
    const breadcrumbName = document.getElementById("breadcrumb-customer-name");
    if (breadcrumbName) {
      breadcrumbName.innerText = details.name;
    }

    // Populate Current Customer sticky header card text fields
    document.getElementById("cc-customer-name").innerText = details.name;
    document.getElementById("cc-id-tag").innerText = `ID #${details.id}`;
    document.getElementById("cc-customer-phone").innerText = details.phone_number;

    const createdVal = details.created_at || details.created_date || "";
    const dateStr = createdVal ? new Date(createdVal).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    }) : "—";
    document.getElementById("cc-customer-created").innerText = dateStr;

    // Handle avatar display and initials fallback
    const photoImg = document.getElementById("cc-photo");
    const initialsBox = document.getElementById("cc-initials-fallback");
    if (details.has_profile_photo) {
      photoImg.src = `${API_BASE_URL}/customers/${details.id}/photo?t=${new Date().getTime()}`;
      photoImg.classList.remove("hidden");
      initialsBox.classList.add("hidden");
    } else {
      photoImg.classList.add("hidden");
      initialsBox.classList.remove("hidden");
      
      const nameParts = (details.name || "").trim().split(" ");
      let initials = "";
      if (nameParts.length > 0) {
        initials += nameParts[0][0] || "";
        if (nameParts.length > 1) {
          initials += nameParts[nameParts.length - 1][0] || "";
        }
      }
      initialsBox.innerText = initials.toUpperCase() || "C";
    }

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

    const endTime = performance.now();
    console.log(`%c[PERFORMANCE PROFILE] Customer Selection`, "color: #3b82f6; font-weight: bold;");
    console.log(`- Fetch Type: ${cached ? "Memory Cache (Prefetched)" : "Network API Call"}`);
    console.log(`- API Latency: ${(apiTime - startTime).toFixed(2)} ms`);
    console.log(`- UI Rendering: ${(endTime - apiTime).toFixed(2)} ms`);
    console.log(`- Total Selection Latency: ${(endTime - startTime).toFixed(2)} ms`);
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
          ? "bg-blue-500/10 border-blue-500/30 text-white shadow-md shadow-blue-500/5" 
          : "border-white/5 hover:bg-white/5 text-text-secondary"
      }">
        <p class="font-bold text-white">Account #${loan.id}</p>
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

  // Fill sticky Current Customer Card loan properties
  document.getElementById("cc-loan-status").innerText = loan.status;

  // Determine risk level based on loan status & credit score
  const score = loan.credit_score || 700;
  let riskLevel = "MEDIUM RISK";
  let riskClass = "bg-amber-500/10 border-amber-500/20 text-amber-400";
  if (score >= 750) {
    riskLevel = "LOW RISK";
    riskClass = "bg-emerald-500/10 border-emerald-500/20 text-emerald-400";
  } else if (score < 650 || loan.status === "OVERDUE") {
    riskLevel = "HIGH RISK";
    riskClass = "bg-rose-500/10 border-rose-500/20 text-rose-400";
  }
  const riskEl = document.getElementById("cc-risk-level");
  riskEl.innerText = riskLevel;
  riskEl.className = `px-2.5 py-0.5 text-[9px] font-bold tracking-wider rounded border uppercase ${riskClass}`;

  // Avatar active status indicator color
  const statusDot = document.getElementById("cc-status-dot");
  if (loan.status === "ACTIVE") {
    statusDot.className = "absolute bottom-0.5 right-0.5 w-4 h-4 rounded-full border-2 border-[#040815] bg-emerald-500";
  } else if (loan.status === "OVERDUE" || loan.status === "DEFAULTED") {
    statusDot.className = "absolute bottom-0.5 right-0.5 w-4 h-4 rounded-full border-2 border-[#040815] bg-rose-500";
  } else {
    statusDot.className = "absolute bottom-0.5 right-0.5 w-4 h-4 rounded-full border-2 border-[#040815] bg-slate-500";
  }

  // outstanding and KPI micro-cards
  const bs = loan.balance_summary || {};
  const outstanding = parseFloat(bs.remaining_balance || loan.remaining_balance || 0);
  document.getElementById("cc-outstanding-bal").innerText = formatVal(outstanding);
  
  const interestVal = parseFloat(bs.interest || loan.interest_amount || 0);
  const totalRepayableVal = parseFloat(bs.total_due || loan.total_repayable_amount || 0);

  document.getElementById("kpi-principal").innerText = formatVal(loan.principal_amount);
  document.getElementById("kpi-interest").innerText = formatVal(interestVal);
  document.getElementById("kpi-total-repayable").innerText = formatVal(totalRepayableVal);
  document.getElementById("kpi-paid").innerText = formatVal(bs.total_paid || 0);
  document.getElementById("kpi-remaining").innerText = formatVal(outstanding);
  
  const overdueDays = parseInt(bs.overdue_days || 0);
  document.getElementById("kpi-overdue-days").innerText = overdueDays > 0 ? `${overdueDays} Days` : "None";
  
  const nextDue = bs.next_due_date || "—";
  document.getElementById("kpi-next-due").innerText = nextDue;

  // Completion Progress bar calculations
  const completion = parseFloat(bs.completion_percent || 0);
  document.getElementById("progress-percent").innerText = `${completion.toFixed(1)}%`;
  document.getElementById("progress-bar-fill").style.width = `${completion}%`;

  document.getElementById("kpi-rate").innerText = window.formatInterestRate ? window.formatInterestRate(loan.interest_rate) : `${loan.interest_rate}%`;
  document.getElementById("kpi-formula").innerText = loan.interest_formula;

  // Safety Confirmation Block details
  document.getElementById("safety-customer-name").innerText = selectedCustomer.name;
  document.getElementById("safety-customer-id").innerText = `ID #${selectedCustomer.id}`;
  document.getElementById("safety-loan-id").innerText = `Account #${loan.id}`;

  // Fetch payments list
  await refreshLoanPayments();

  // Add workdesk animation class to prevent layout shifts
  activeWorkdesk.classList.remove("sa-workdesk-transition");
  void activeWorkdesk.offsetWidth;
  activeWorkdesk.classList.add("sa-workdesk-transition");

  unselectedPlaceholder.classList.add("hidden");
  activeWorkdesk.classList.remove("hidden");
}

async function refreshLoanPayments() {
  if (!selectedLoan) return;

  const cardsContainer = document.getElementById("loan-payments-cards-container");

  try {
    loanPayments = (aggregatePayments || []).filter(p => p.loan_id === selectedLoan.id);
    loanPayments.sort((a, b) => new Date(a.payment_date) - new Date(b.payment_date));

    if (loanPayments.length === 0) {
      paymentsEmpty.classList.remove("hidden");
      paymentsTable.classList.add("hidden");
      if (cardsContainer) cardsContainer.classList.add("hidden");
    } else {
      paymentsEmpty.classList.add("hidden");
      paymentsTable.classList.remove("hidden");
      if (cardsContainer) cardsContainer.classList.remove("hidden");

      const CHUNK_SIZE = 25;
      const initialChunk = loanPayments.slice(0, CHUNK_SIZE);
      const remainingChunk = loanPayments.slice(CHUNK_SIZE);

      const renderRowHtml = (p) => {
        const norm = (p.payment_status || "PENDING").toUpperCase();
        let badgeClass = "bg-amber-500/10 text-amber-400 border-amber-500/20"; // PENDING
        if (norm === "PAID") {
          badgeClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 status-pill-emerald";
        } else if (norm === "PARTIALLY PAID") {
          badgeClass = "bg-blue-500/10 text-blue-400 border-blue-500/20";
        } else if (norm === "MISSED") {
          badgeClass = "bg-orange-500/10 text-orange-400 border-orange-500/20";
        } else if (norm === "OVERDUE") {
          badgeClass = "bg-rose-500/10 text-rose-400 border-rose-500/20 status-pill-rose animate-pulse";
        } else if (norm === "COMPLETED") {
          badgeClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 status-pill-emerald";
        }
        const statusBadge = `<span class="inline-block px-2.5 py-0.5 text-[10px] font-bold rounded-full border uppercase ${badgeClass}">${norm}</span>`;
        const paidTextClass = parseFloat(p.amount_paid) > 0 ? "text-emerald-400 font-extrabold" : "text-text-muted";

        return `
          <tr class="h-10 hover:bg-white/5 transition-all">
            <td data-label="Date" class="font-semibold text-text-primary text-xs py-2.5 px-4 font-mono">${p.payment_date}</td>
            <td data-label="Expected" class="text-right font-mono text-xs text-text-secondary py-2.5 px-4">${formatVal(p.expected_amount)}</td>
            <td data-label="Paid" class="text-right font-mono text-xs ${paidTextClass} py-2.5 px-4">${formatVal(p.amount_paid)}</td>
            <td data-label="Coverage" class="text-xs text-text-primary font-bold font-mono py-2.5 px-4">${p.equivalent_coverage != null ? Number(p.equivalent_coverage).toFixed(2) + ' Days' : '—'}</td>
            <td data-label="Method" class="text-xs text-text-secondary font-semibold py-2.5 px-4">${p.payment_mode || "—"}</td>
            <td data-label="Status" class="py-2.5 px-4">${statusBadge}</td>
            <td data-label="Recorded By" class="text-xs text-text-secondary font-semibold py-2.5 px-4">${p.recorded_by_name || "—"}</td>
            <td data-label="Time" class="text-xs text-text-muted font-mono py-2.5 px-4">${p.created_at || "—"}</td>
            <td data-label="Notes" class="text-xs text-text-secondary italic py-2.5 px-4 max-w-[150px] truncate hover:whitespace-normal" title="${p.remarks || ''}">${p.remarks || "—"}</td>
          </tr>
        `;
      };

      paymentsBody.innerHTML = initialChunk.map(renderRowHtml).join("");

      if (remainingChunk.length > 0) {
        requestAnimationFrame(() => {
          const div = document.createElement("tbody");
          div.innerHTML = remainingChunk.map(renderRowHtml).join("");
          while (div.firstChild) {
            paymentsBody.appendChild(div.firstChild);
          }
          if (window.lucide) {
            window.lucide.createIcons();
          }
        });
      }

      // Render mobile cards
      if (cardsContainer) {
        const renderCardHtml = (p) => {
          const norm = (p.payment_status || "PENDING").toUpperCase();
          let badgeClass = "bg-amber-500/10 text-amber-400 border-amber-500/20";
          if (norm === "PAID") {
            badgeClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 status-pill-emerald";
          } else if (norm === "PARTIALLY PAID") {
            badgeClass = "bg-blue-500/10 text-blue-400 border-blue-500/20";
          } else if (norm === "MISSED") {
            badgeClass = "bg-orange-500/10 text-orange-400 border-orange-500/20";
          } else if (norm === "OVERDUE") {
            badgeClass = "bg-rose-500/10 text-rose-400 border-rose-500/20 status-pill-rose animate-pulse";
          } else if (norm === "COMPLETED") {
            badgeClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 status-pill-emerald";
          }
          const statusBadge = `<span class="inline-block px-2 py-0.5 text-[9px] font-bold rounded border uppercase ${badgeClass}">${norm}</span>`;
          const paidTextClass = parseFloat(p.amount_paid) > 0 ? "text-emerald-400 font-extrabold" : "text-text-muted";

          return `
            <div class="sakra-payment-card border border-white/5 rounded-lg bg-slate-950/40 overflow-hidden flex flex-col transition-all">
              <div class="sakra-payment-card-header flex items-center justify-between p-4 cursor-pointer select-none min-h-[48px]">
                <div class="flex items-center gap-2">
                  <i data-lucide="calendar" class="w-3.5 h-3.5 text-blue-400"></i>
                  <span class="font-mono font-bold text-xs text-white">${p.payment_date}</span>
                </div>
                <div class="flex items-center gap-2">
                  ${statusBadge}
                  <i data-lucide="chevron-down" class="w-4 h-4 text-text-muted transition-transform duration-200 chevron-icon"></i>
                </div>
              </div>

              <div class="grid grid-cols-3 gap-2 px-4 pb-4 border-b border-white/5 bg-slate-950/20 py-2.5">
                <div class="flex flex-col">
                  <span class="text-[8px] text-text-muted uppercase tracking-wider font-bold">Expected</span>
                  <span class="font-mono font-bold text-[11px] text-text-secondary">${formatVal(p.expected_amount)}</span>
                </div>
                <div class="flex flex-col">
                  <span class="text-[8px] text-text-muted uppercase tracking-wider font-bold">Paid</span>
                  <span class="font-mono font-extrabold text-[11px] ${paidTextClass}">${formatVal(p.amount_paid)}</span>
                </div>
                <div class="flex flex-col">
                  <span class="text-[8px] text-text-muted uppercase tracking-wider font-bold">Coverage</span>
                  <span class="font-mono font-bold text-[11px] text-blue-400">${p.equivalent_coverage != null ? Number(p.equivalent_coverage).toFixed(2) + ' Days' : '—'}</span>
                </div>
              </div>

              <div class="sakra-payment-card-details hidden p-4 bg-slate-950/70 space-y-2 text-[10px] border-t border-white/5">
                <div class="flex justify-between items-center py-1 border-b border-white/5">
                  <span class="text-text-muted">Payment Method</span>
                  <span class="text-white font-bold">${p.payment_mode || "—"}</span>
                </div>
                <div class="flex justify-between items-center py-1 border-b border-white/5">
                  <span class="text-text-muted">Recorded By</span>
                  <span class="text-white font-semibold">${p.recorded_by_name || "—"}</span>
                </div>
                <div class="flex justify-between items-center py-1 border-b border-white/5">
                  <span class="text-text-muted">Timestamp</span>
                  <span class="text-text-secondary font-mono">${p.created_at || "—"}</span>
                </div>
                <div class="flex flex-col gap-1 py-1">
                  <span class="text-text-muted">Remarks</span>
                  <span class="text-text-secondary italic leading-normal">${p.remarks || "—"}</span>
                </div>
              </div>
            </div>
          `;
        };

        cardsContainer.innerHTML = loanPayments.map(renderCardHtml).join("");

        // Bind accordion click expand/collapse behavior
        cardsContainer.querySelectorAll(".sakra-payment-card").forEach(card => {
          const header = card.querySelector(".sakra-payment-card-header");
          const details = card.querySelector(".sakra-payment-card-details");
          header.addEventListener("click", () => {
            if (card.classList.contains("expanded")) {
              card.classList.remove("expanded");
              details.classList.add("hidden");
            } else {
              card.classList.add("expanded");
              details.classList.remove("hidden");
            }
          });
        });
      }
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
  const amount = parseFloat(data.amount_paid);

  if (isNaN(amount) || amount <= 0) {
    formError.innerText = "Enter a valid positive payment amount.";
    formError.classList.remove("hidden");
    return;
  }

  const payload = {
    loan_id: selectedLoan.id,
    payment_date: data.payment_date,
    amount_paid: amount,
    payment_mode: data.payment_mode,
    remarks: data.remarks || undefined
  };

  // Intercept high-value payments exceeding ₹50,000 for double confirmation modal
  if (amount > 50000) {
    pendingSubmitData = payload;

    confirmCustomerName.innerText = selectedCustomer.name;
    confirmCustomerId.innerText = `ID #${selectedCustomer.id}`;
    confirmLoanId.innerText = `Account #${selectedLoan.id}`;
    confirmAmount.innerText = formatVal(amount);

    doubleConfirmModal.classList.remove("hidden");
    doubleConfirmModal.classList.add("active");
    if (window.lucide) {
      window.lucide.createIcons();
    }
    return;
  }

  await executeRecordPayment(payload);
}

async function executeRecordPayment(payload) {
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin mr-1"></i> Recording...`;
  if (window.lucide) window.lucide.createIcons();

  try {
    await api.post("/payments", payload);

    formSuccess.innerText = `₹${parseFloat(payload.amount_paid).toLocaleString("en-IN")} recorded successfully for ${payload.payment_date}.`;
    formSuccess.classList.remove("hidden");
    
    // Clear amount & remarks
    paymentForm.querySelector('input[name="amount_paid"]').value = "";
    paymentForm.querySelector('input[name="remarks"]').value = "";

    // Invalidate client-side details cache for this customer
    const customerId = selectedCustomer.id;
    const loanId = selectedLoan.id;
    delete customerDetailsCache[customerId];

    // Dynamic UI Refresh: reload customer list and details cards asynchronously in background
    init().then(async () => {
      const updatedCustomer = customers.find(c => c.id === customerId);
      if (updatedCustomer) {
        selectedCustomer = updatedCustomer;
        const resLoans = await api.get(`/customers/${customerId}`);
        const payloadLoans = resLoans.data || resLoans;
        customerDetailsCache[customerId] = payloadLoans; // Re-populate cache
        aggregatePayments = payloadLoans.aggregate_payments || []; // Update local payments list
        customerLoans = payloadLoans.loans || [];
        renderLoanSelector();
        const updatedLoan = customerLoans.find(l => l.id === loanId);
        if (updatedLoan) {
          await selectLoan(updatedLoan);
        }
      } else {
        await refreshLoanPayments();
      }
    });

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
    const response = await fetch(`${API_BASE_URL}/payments/export/csv${params}`, {
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

window.refreshPageData = async () => {
  await init();
};

window.addEventListener("language-changed", () => {
  renderCustomerList();
  if (selectedLoan) {
    selectLoan(selectedLoan);
  }
});

