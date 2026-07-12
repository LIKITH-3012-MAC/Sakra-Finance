import api, { customFetch } from "../api.js";
import { formatCurrency, formatDate, formatInterestRate } from "../helpers.js";
import { API_BASE_URL } from "../config.js";


async function customFetchBlob(url, options = {}) {
  const absoluteUrl = url.startsWith("http") ? url : `${API_BASE_URL}${url}`;
  options.headers = options.headers || {};
  
  const token = localStorage.getItem("access_token") || localStorage.getItem("sakra_access_token");
  if (token) {
    options.headers["Authorization"] = `Bearer ${token}`;
  }
  options.credentials = "include";

  const response = await fetch(absoluteUrl, options);
  if (response.status === 401) {
    const rToken = localStorage.getItem("refresh_token");
    if (rToken) {
      const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rToken }),
        credentials: "include"
      });
      if (refreshResponse.ok) {
        const refreshPayload = await refreshResponse.json();
        const newAccessToken = refreshPayload.data.token.access_token;
        localStorage.setItem("access_token", newAccessToken);
        options.headers["Authorization"] = `Bearer ${newAccessToken}`;
        return customFetchBlob(url, options);
      }
    }
  }
  
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error("Access Denied: VIEWER role is blocked from viewing identity documents.");
    }
    throw new Error("HTTP error " + response.status);
  }
  return response.blob();
}

async function loadSecureImage(imgElement, url, fallbackSvg) {
  if (!imgElement) return;
  try {
    const blob = await customFetchBlob(url);
    const objectUrl = URL.createObjectURL(blob);
    imgElement.src = objectUrl;
  } catch (err) {
    if (fallbackSvg) imgElement.src = fallbackSvg;
  }
}

let profileId = null;

async function init() {
  const params = new URLSearchParams(window.location.search);
  profileId = params.get("id");

  if (!profileId) {
    window.location.href = "/customers.html";
    return;
  }

  try {
    const res = await api.get(`/customers/${profileId}`);
    const data = res.data || res;
    window.currentProfileData = data;
    
    renderProfile(data);

    // Show content
    document.getElementById("profile-content").classList.remove("hidden");
  } catch (err) {
    console.error("Failed to load customer profile:", err);
    const mainEl = document.querySelector("main");
    if (mainEl) {
      mainEl.innerHTML = `
        <div class="glass-card text-center py-20 flex flex-col items-center justify-center max-w-lg mx-auto mt-16 p-8 border border-white/5 rounded-xl bg-slate-950/40 backdrop-blur-md shadow-deep">
          <i data-lucide="alert-circle" class="w-12 h-12 text-rose-400 mb-4 animate-pulse"></i>
          <h3 class="text-xs font-bold text-slate-100 uppercase tracking-widest">Customer ID #${profileId || "—"} Was Not Found</h3>
          <p class="text-[11px] text-slate-400 mt-2 font-medium">The requested record does not exist or has been archived from Aiven MySQL.</p>
          <div class="flex gap-4 mt-8">
            <a href="/customers.html" class="sakra-btn-tactile bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 text-[9px] uppercase tracking-widest font-bold rounded border-0 cursor-pointer flex items-center gap-1.5">
              <i data-lucide="arrow-left" class="w-3.5 h-3.5"></i> Return to Registry
            </a>
            <a href="/customers.html" class="sakra-btn-tactile bg-slate-800 hover:bg-slate-700 text-slate-200 px-5 py-2.5 text-[9px] uppercase tracking-widest font-bold rounded border-0 cursor-pointer flex items-center gap-1.5">
              <i data-lucide="search" class="w-3.5 h-3.5"></i> Search Another
            </a>
          </div>
        </div>
      `;
      if (window.lucide) window.lucide.createIcons();
    }
  }
}

function renderProfile(data) {
  const { customer, loans = [], aggregate_payments = [], credit_score, summary = {} } = data;

  // 1. Identity Header
  document.getElementById("profile-name").innerText = customer.name;
  document.getElementById("profile-phone").innerText = customer.phone_number;
  document.getElementById("profile-aadhar").innerText = customer.aadhar_masked || "—";
  document.getElementById("profile-id").innerText = `#${customer.id}`;
  document.getElementById("profile-version").innerText = customer.version_id ?? "1";

  // 2. Financial Stats (Derived 100% from backend source of truth summary object)
  const activeLoansCount = loans.filter(l => l.status === "ACTIVE" || l.status === "OVERDUE").length;

  document.getElementById("stat-principal").innerText = formatCurrency(summary.total_principal || 0);
  document.getElementById("stat-interest").innerText = formatCurrency(summary.total_interest || 0);
  document.getElementById("stat-repayable").innerText = formatCurrency(summary.total_repayable || 0);
  document.getElementById("stat-paid").innerText = formatCurrency(summary.total_paid || 0);
  document.getElementById("stat-outstanding").innerText = formatCurrency(summary.remaining_balance || 0);
  document.getElementById("stat-pending-installments").innerText = customer.pending_installments_count || 0;
  document.getElementById("stat-loans-count").innerText = activeLoansCount;

  // Customer-level Equivalent Coverage KPI (Total Collected ÷ Daily Installment)
  const equivCoverage = summary.equivalent_coverage;
  const totalPaid = summary.total_paid || 0;
  const dailyInstallment = summary.total_daily_installment || 0;
  const coverageEl = document.getElementById("stat-equivalent-coverage");
  if (equivCoverage != null && equivCoverage > 0) {
    coverageEl.innerText = `${Number(equivCoverage).toFixed(2)} Days`;
  } else {
    coverageEl.innerText = "—";
  }
  // Populate tooltip formula breakdown
  const tooltipCollected = document.getElementById("tooltip-collected");
  const tooltipDaily = document.getElementById("tooltip-daily-installment");
  const tooltipCalc = document.getElementById("tooltip-coverage-calc");
  if (tooltipCollected) tooltipCollected.innerText = formatCurrency(totalPaid);
  if (tooltipDaily) tooltipDaily.innerText = formatCurrency(dailyInstallment);
  if (tooltipCalc) tooltipCalc.innerText = equivCoverage != null ? `${Number(equivCoverage).toFixed(2)} Days` : "—";

  // Bind collection intelligence pending installments card listeners
  bindPendingKpiListeners(customer);

  // 3. Customer Details block
  const profilePhotoImg = document.getElementById("profile-photo-img");
  const fallbackSvg = `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23cbd5e1' style='background:%23f1f5f9;'><path fill-rule='evenodd' d='M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A9.75 9.75 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z' clip-rule='evenodd' /></svg>`;
  loadSecureImage(profilePhotoImg, `/customers/${customer.id}/photo`, fallbackSvg);

  const dobEl = document.getElementById("details-dob");
  const dobRow = document.getElementById("details-dob-row");
  if (customer.date_of_birth) {
    dobEl.innerText = customer.date_of_birth;
  } else {
    dobRow.classList.add("hidden");
  }

  const genderEl = document.getElementById("details-gender");
  const genderRow = document.getElementById("details-gender-row");
  if (customer.gender) {
    genderEl.innerText = customer.gender;
  } else {
    genderRow.classList.add("hidden");
  }

  const occupationEl = document.getElementById("details-occupation");
  const occupationRow = document.getElementById("details-occupation-row");
  if (customer.occupation) {
    occupationEl.innerText = customer.occupation;
  } else {
    occupationRow.classList.add("hidden");
  }

  const addressEl = document.getElementById("details-address");
  const addressRow = document.getElementById("details-address-row");
  if (customer.address) {
    addressEl.innerText = customer.address;
  } else {
    addressRow.classList.add("hidden");
  }

  const promissoryEl = document.getElementById("details-promissory");
  const promissoryRow = document.getElementById("details-promissory-row");
  if (customer.promissory_note) {
    promissoryEl.innerText = customer.promissory_note;
  } else {
    promissoryRow.classList.add("hidden");
  }

  const remarksEl = document.getElementById("details-remarks");
  const remarksRow = document.getElementById("details-remarks-row");
  if (customer.remarks) {
    remarksEl.innerText = customer.remarks;
  } else {
    remarksRow.classList.add("hidden");
  }

  document.getElementById("details-registered").innerText = `Registered: ${formatDate(customer.created_at)}`;


  // 4. Credit Score circle gauge
  const scoreVal = credit_score || 700;
  const scoreText = document.getElementById("score-val-text");
  const scoreCircle = document.getElementById("score-gauge-circle");
  const scoreBadgeContainer = document.getElementById("score-badge-container");

  scoreText.innerText = scoreVal;

  // Calculate score color and variants
  let scoreColor = "#2563EB"; // primary
  let scoreVariant = "primary";
  let scoreTextRating = "Good";

  if (scoreVal >= 750) {
    scoreColor = "#059669"; // success
    scoreVariant = "success";
    scoreTextRating = "Excellent";
  } else if (scoreVal >= 650) {
    scoreColor = "#2563EB"; // primary
    scoreVariant = "primary";
    scoreTextRating = "Good";
  } else if (scoreVal >= 500) {
    scoreColor = "#D97706"; // warning
    scoreVariant = "warning";
    scoreTextRating = "Fair";
  } else {
    scoreColor = "#DC2626"; // danger
    scoreVariant = "danger";
    scoreTextRating = "Poor";
  }

  // Draw circle
  scoreText.style.color = scoreColor;
  scoreCircle.setAttribute("stroke", scoreColor);
  const scorePercent = Math.min(1, Math.max(0, (scoreVal - 300) / 550));
  const circumference = 339.292; // 2 * pi * 54
  const offset = circumference * (1 - scorePercent);
  scoreCircle.setAttribute("stroke-dashoffset", offset);

  // Render Badge
  const badgeClasses = {
    success: "bg-emerald-50 text-emerald-700 border-emerald-100",
    primary: "bg-blue-50 text-blue-700 border-blue-100",
    warning: "bg-amber-50 text-amber-700 border-amber-100",
    danger: "bg-rose-50 text-rose-700 border-rose-100"
  };
  scoreBadgeContainer.innerHTML = `
    <span class="inline-block px-2 py-0.5 text-[10px] uppercase tracking-wider font-bold rounded border ${badgeClasses[scoreVariant]}">
      ${scoreTextRating}
    </span>
  `;

  // 5. Payment Distribution Chart.js Scatter Plot
  renderScatterPlot(loans, aggregate_payments, customer);

  // 6. Loans Table
  const loansBody = document.getElementById("loans-table-body");
  const loansEmpty = document.getElementById("loans-empty");
  const loansTable = document.getElementById("loans-table-container");

  if (loans.length === 0) {
    loansEmpty.classList.remove("hidden");
    loansTable.classList.add("hidden");
  } else {
    loansEmpty.classList.add("hidden");
    loansTable.classList.remove("hidden");

    const statusVariants = {
      ACTIVE: "bg-blue-50 text-blue-700 border-blue-100",
      COMPLETED: "bg-emerald-50 text-emerald-700 border-emerald-100",
      OVERDUE: "bg-rose-50 text-rose-700 border-rose-100",
      DEFAULTED: "bg-rose-50 text-rose-700 border-rose-100"
    };

    loansBody.innerHTML = loans.map(loan => {
      const variantClass = statusVariants[loan.status] || "bg-slate-50 text-slate-700 border-slate-100";
      return `
        <tr>
          <td data-label="Loan ID" class="font-mono text-xs text-text-muted">#${loan.id}</td>
          <td data-label="Principal" class="text-right font-bold text-text-primary font-mono">${formatCurrency(loan.principal_amount)}</td>
          <td data-label="Formula" class="text-text-secondary font-semibold text-xs">${loan.interest_formula} @ ${formatInterestRate(loan.interest_rate)}</td>
          <td data-label="Period" class="text-xs text-text-secondary font-mono">${loan.loan_start_date} → ${loan.loan_end_date}</td>
          <td data-label="Status" class="text-center">
            <span class="inline-block px-2.5 py-0.5 text-[10px] font-bold rounded border uppercase ${variantClass}">
              ${loan.status}
            </span>
          </td>
        </tr>
      `;
    }).join("");
  }

  // 7. Payments History Table
  const paymentsBody = document.getElementById("payments-table-body");
  const paymentsEmpty = document.getElementById("payments-empty");
  const paymentsTable = document.getElementById("payments-table-container");

  if (aggregate_payments.length === 0) {
    paymentsEmpty.classList.remove("hidden");
    paymentsTable.classList.add("hidden");
  } else {
    paymentsEmpty.classList.add("hidden");
    paymentsTable.classList.remove("hidden");

    paymentsBody.innerHTML = aggregate_payments.map((p, idx) => {
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
          <td data-label="#" class="text-text-muted font-mono text-xs">#${idx + 1}</td>
          <td data-label="Date" class="font-semibold text-text-primary text-xs">${p.payment_date}</td>
          <td data-label="Expected" class="text-right font-mono text-xs text-text-secondary">${formatCurrency(p.expected_amount)}</td>
          <td data-label="Paid" class="text-right font-mono text-xs ${paidTextClass}">${formatCurrency(p.amount_paid)}</td>
          <td data-label="Coverage" class="text-xs text-text-primary font-bold font-mono">${p.equivalent_coverage != null ? Number(p.equivalent_coverage).toFixed(2) + ' Days' : '—'}</td>
          <td data-label="Mode" class="text-xs text-text-secondary font-semibold">${p.payment_mode || "—"}</td>
          <td data-label="Status">${statusBadge}</td>
          <td data-label="Recorded By" class="text-xs text-text-secondary font-semibold">${p.recorded_by_name || "—"}</td>
          <td data-label="Time" class="text-xs text-text-muted font-mono">${p.created_at || "—"}</td>
          <td data-label="Notes" class="text-xs text-text-secondary italic">${p.remarks || "—"}</td>
          <td data-label="Actions" class="text-center select-none font-sans">
            <div class="flex items-center justify-center gap-2">
              ${p.id ? `
                <button class="edit-payment-btn p-1 text-blue-400 hover:text-blue-300 hover:bg-blue-950/30 rounded transition-colors border-0 bg-transparent cursor-pointer" data-id="${p.id}" data-date="${p.payment_date}" data-amount="${p.amount_paid}" data-mode="${p.payment_mode}" data-remarks="${p.remarks || ''}" data-version="${p.version_id || 1}" title="Edit Payment">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-edit-2"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                </button>
                <button class="delete-payment-btn p-1 text-rose-400 hover:text-rose-300 hover:bg-rose-950/30 rounded transition-colors border-0 bg-transparent cursor-pointer" data-id="${p.id}" data-amount="${p.amount_paid}" data-date="${p.payment_date}" title="Delete Payment">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash-2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
                </button>
              ` : `
                <button class="record-payment-btn p-1 px-2 text-[9px] font-extrabold uppercase tracking-wider text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/30 rounded border border-emerald-500/20 bg-transparent cursor-pointer transition-colors" data-loan-id="${p.loan_id}" data-date="${p.payment_date}" title="Record Payment">
                  Record
                </button>
              `}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  // 8. Collection Intelligence Dashboard
  const activeLoans = loans.filter(l => l.status === "ACTIVE" || l.status === "OVERDUE");
  const dashboardEl = document.getElementById("collection-intelligence-dashboard");
  if (activeLoans.length > 0) {
    dashboardEl.classList.remove("hidden");
    dashboardEl.innerHTML = activeLoans.map(loan => {
      // 1. Calendar Progress
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const startDate = new Date(loan.loan_start_date);
      startDate.setHours(0, 0, 0, 0);

      const diffTime = today.getTime() - startDate.getTime();
      const diffDays = Math.max(0, Math.floor(diffTime / (1000 * 60 * 60 * 24)));
      const daysPassed = Math.min(diffDays, loan.duration_days);

      // 2. Expected Collection Till Today
      const dailyInstallment = parseFloat(loan.daily_installment || 0);
      const expectedCollection = daysPassed * dailyInstallment;

      // 3. Actual Collection
      const totalPaid = parseFloat(loan.balance_summary?.total_paid || 0);

      // 4. Equivalent Paid Days (total_paid / daily_installment)
      const equivalentPaidDays = dailyInstallment > 0 ? (totalPaid / dailyInstallment) : 0;

      // 5. Compare Them (behind_days = days_passed - equivalent_paid_days)
      const behindDays = daysPassed - equivalentPaidDays;
      let progressTextOnly = "";
      let progressBadgeClass = "";
      let progressDotClass = "";
      let progressAnimateClass = "";
      if (behindDays > 0) {
        progressTextOnly = `${behindDays.toFixed(2)} Days Behind`;
        progressBadgeClass = "bg-rose-500/15 text-rose-400 border border-rose-500/30";
        progressDotClass = "bg-rose-500";
        progressAnimateClass = "animate-pulse";
      } else if (behindDays < 0) {
        progressTextOnly = `${Math.abs(behindDays).toFixed(2)} Days Ahead`;
        progressBadgeClass = "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30";
        progressDotClass = "bg-emerald-500";
        progressAnimateClass = "";
      } else {
        progressTextOnly = "On Schedule";
        progressBadgeClass = "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30";
        progressDotClass = "bg-emerald-500";
        progressAnimateClass = "";
      }

      // 6. Pending Collection Till Today (expected - total_paid, min 0)
      const pendingToday = Math.max(0, expectedCollection - totalPaid);

      // 7. Remaining Balance
      const remainingBalance = parseFloat(loan.remaining_balance || 0);

      return `
        <div class="glass-card p-6 bg-slate-950/40 border border-white/5 shadow-deep rounded-xl flex flex-col gap-5 text-slate-200">
          <div class="flex items-center justify-between border-b border-white/5 pb-3 select-none">
            <div class="flex items-center gap-2">
              <i data-lucide="activity" class="w-5 h-5 text-blue-400 animate-pulse animate-duration-1000"></i>
              <span class="text-xs font-bold text-white uppercase tracking-widest font-sans">Collection Intelligence — Loan #${loan.id}</span>
            </div>
            <span class="px-2.5 py-0.5 text-[9px] font-bold rounded border uppercase bg-blue-950/50 text-blue-400 border-blue-500/20 font-mono">
              Daily Installment: ${formatCurrency(dailyInstallment)}
            </span>
          </div>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Loan Duration</p>
              <p class="text-lg md:text-xl font-bold mt-2 font-sans text-white" data-animate="duration" data-val="${loan.duration_days}">0 Days</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Days Passed</p>
              <p class="text-lg md:text-xl font-bold mt-2 font-sans text-white" data-animate="days-passed" data-val="${daysPassed}">0 Days</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Expected Collection Till Today</p>
              <p class="text-lg md:text-xl font-bold mt-2 font-sans text-white" data-animate="expected" data-val="${expectedCollection}">₹0.00</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Actual Collection</p>
              <p class="text-lg md:text-xl font-bold mt-2 font-sans text-success" data-animate="actual" data-val="${totalPaid}">₹0.00</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm col-span-1">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Equivalent Installments Covered</p>
              <p class="text-lg md:text-xl font-bold mt-2 font-sans text-blue-400" data-animate="equivalent" data-val="${equivalentPaidDays}">0.00 Days</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm col-span-1 flex flex-col justify-between">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Collection Progress</p>
              <div class="mt-2.5 flex justify-center items-center">
                <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-extrabold uppercase tracking-wider ${progressBadgeClass}">
                  <span class="w-1.5 h-1.5 rounded-full ${progressDotClass} ${progressAnimateClass}"></span>
                  <span>${progressTextOnly}</span>
                </span>
              </div>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Pending Collection Till Today</p>
              <p class="text-lg md:text-xl font-bold mt-2 font-sans text-rose-400" data-animate="pending" data-val="${pendingToday}">₹0.00</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Remaining Loan Balance</p>
              <p class="text-lg md:text-xl font-bold mt-2 font-sans text-rose-500" data-animate="balance" data-val="${remainingBalance}">₹0.00</p>
            </div>
          </div>
        </div>
      `;
    }).join("");
    
    // Animate numbers
    setTimeout(animateKPIs, 50);
  } else {
    dashboardEl.classList.add("hidden");
    dashboardEl.innerHTML = "";
  }

  // Bind actions for payment table action buttons
  bindPaymentActions();

  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Mobile accordion initialization
  if (window.innerWidth < 768) {
    initializeMobileAccordions(data);
  }
}

function renderScatterPlot(loans, payments, customer) {
  const canvas = document.getElementById("scatterChartCanvas");
  const emptyMsg = document.getElementById("scatter-chart-empty");
  
  if (!payments || payments.length === 0) {
    canvas.classList.add("hidden");
    emptyMsg.classList.remove("hidden");
    return;
  }

  canvas.classList.remove("hidden");
  emptyMsg.classList.add("hidden");

  // Calculate day offsets since first loan start date
  const firstLoanStart = loans.length > 0 ? new Date(loans[0].loan_start_date) : new Date();
  
  const chartData = payments.filter(p => parseFloat(p.amount_paid || 0) > 0).map(p => {
    const payDate = new Date(p.payment_date);
    const dayIndex = Math.max(0, Math.round((payDate - firstLoanStart) / (1000 * 60 * 60 * 24)));
    return {
      x: dayIndex,
      y: parseFloat(p.amount_paid || 0),
      date: p.payment_date
    };
  });


  const ctx = canvas.getContext("2d");
  
  // Render Chart
  new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [{
        label: "Payment Logs",
        data: chartData,
        backgroundColor: "rgba(37, 99, 235, 0.7)",
        borderColor: "rgb(37, 99, 235)",
        borderWidth: 1,
        pointRadius: 6,
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const item = context.raw;
              return [
                `Day: ${item.x}`,
                `Date: ${item.date}`,
                `Amount: ₹${item.y.toLocaleString("en-IN")}`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "Days offset since loan start",
            font: { size: 10, weight: "bold" }
          },
          grid: {
            color: "#f1f5f9"
          },
          ticks: {
            font: { size: 10, family: "JetBrains Mono" }
          }
        },
        y: {
          title: {
            display: true,
            text: "Amount Paid (₹)",
            font: { size: 10, weight: "bold" }
          },
          grid: {
            color: "#f1f5f9"
          },
          ticks: {
            font: { size: 10, family: "JetBrains Mono" }
          }
        }
      }
    }
  });

  // ── Document Metadata and Operations Setup ──

  const docsMeta = customer.documents_metadata || {};
  
  // Aadhaar Meta
  const aMeta = docsMeta["AADHAAR"];
  const aStatus = document.getElementById("aadhaar-status-badge");
  if (aMeta) {
    if (aStatus) {
      aStatus.innerText = window.t ? window.t("profile_doc_uploaded") : "UPLOADED";
      aStatus.className = "inline-block px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wide bg-emerald-50 text-emerald-700 border-emerald-100 border";
    }
    document.getElementById("aadhaar-meta-filename").innerText = aMeta.filename;
    document.getElementById("aadhaar-meta-size").innerText = `${(aMeta.file_size / (1024 * 1024)).toFixed(2)} MB`;
    document.getElementById("aadhaar-meta-date").innerText = formatDate(aMeta.uploaded_at);
    document.getElementById("aadhaar-meta-by").innerText = aMeta.uploaded_by_name;
  } else {
    if (aStatus) {
      aStatus.innerText = window.t ? window.t("profile_doc_missing") : "MISSING";
      aStatus.className = "inline-block px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wide bg-rose-50 text-rose-700 border-rose-100 border";
    }
    document.getElementById("aadhaar-meta-filename").innerText = window.t ? window.t("profile_doc_no_file") : "No file uploaded";
    document.getElementById("aadhaar-meta-size").innerText = "—";
    document.getElementById("aadhaar-meta-date").innerText = "—";
    document.getElementById("aadhaar-meta-by").innerText = "—";
  }

  // Promissory Meta
  const pMeta = docsMeta["PROMISSORY_NOTE"];
  const pStatus = document.getElementById("promissory-status-badge");
  if (pMeta) {
    if (pStatus) {
      pStatus.innerText = window.t ? window.t("profile_doc_uploaded") : "UPLOADED";
      pStatus.className = "inline-block px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wide bg-emerald-50 text-emerald-700 border-emerald-100 border";
    }
    document.getElementById("promissory-meta-filename").innerText = pMeta.filename;
    document.getElementById("promissory-meta-size").innerText = `${(pMeta.file_size / (1024 * 1024)).toFixed(2)} MB`;
    document.getElementById("promissory-meta-date").innerText = formatDate(pMeta.uploaded_at);
    document.getElementById("promissory-meta-by").innerText = pMeta.uploaded_by_name;
  } else {
    if (pStatus) {
      pStatus.innerText = window.t ? window.t("profile_doc_missing") : "MISSING";
      pStatus.className = "inline-block px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wide bg-rose-50 text-rose-700 border-rose-100 border";
    }
    document.getElementById("promissory-meta-filename").innerText = window.t ? window.t("profile_doc_no_file") : "No file uploaded";
    document.getElementById("promissory-meta-size").innerText = "—";
    document.getElementById("promissory-meta-date").innerText = "—";
    document.getElementById("promissory-meta-by").innerText = "—";
  }

  // Photo Container Event for replacement
  const photoContainer = document.getElementById("profile-photo-container");
  const replacePhotoInput = document.getElementById("replace-photo-input");

  photoContainer?.addEventListener("click", () => replacePhotoInput?.click());
  replacePhotoInput?.addEventListener("change", async () => {
    const file = replacePhotoInput.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      photoContainer.style.opacity = "0.5";
      await customFetch(`/customers/${customer.id}/documents/PROFILE_PHOTO`, {
        method: "POST",
        body: formData
      });
      window.location.reload();
    } catch (err) {
      alert("Failed to replace profile photo: " + (err.message || err.detail || JSON.stringify(err)));
      photoContainer.style.opacity = "";
    }
  });

  // Document Viewer Setup
  const viewerModal = document.getElementById("document-viewer-modal");
  const viewerContainer = document.getElementById("viewer-content-container");
  const viewerTitle = document.getElementById("viewer-title");
  const viewerMeta = document.getElementById("viewer-file-meta");
  const closeViewerBtn = document.getElementById("close-viewer-btn");
  const downloadBtn = document.getElementById("viewer-download-btn");
  const printBtn = document.getElementById("viewer-print");
  const zoomInBtn = document.getElementById("viewer-zoom-in");
  const zoomOutBtn = document.getElementById("viewer-zoom-out");

  let currentZoom = 1.0;
  let currentDocUrl = "";
  let activeDocType = "";
  
  // Available doc types for swiping
  const docTypesList = ["PROFILE_PHOTO", "AADHAAR", "PROMISSORY_NOTE"];

  const getAvailableDocs = () => {
    return docTypesList.filter(type => docsMeta[type] || (type === "PROFILE_PHOTO" && customer.has_profile_photo));
  };

  const closeViewer = () => {
    viewerModal?.classList.add("hidden");
    if (viewerContainer) viewerContainer.innerHTML = "";
    document.body.style.overflow = "";
  };
  closeViewerBtn?.addEventListener("click", closeViewer);
  viewerModal?.addEventListener("click", (e) => {
    if (e.target === viewerModal) closeViewer();
  });

  const updateZoom = () => {
    if (viewerContainer) {
      viewerContainer.style.transform = `scale(${currentZoom})`;
    }
  };

  zoomInBtn?.addEventListener("click", () => {
    currentZoom += 0.15;
    if (currentZoom > 3.0) currentZoom = 3.0;
    updateZoom();
  });

  zoomOutBtn?.addEventListener("click", () => {
    currentZoom -= 0.15;
    if (currentZoom < 0.4) currentZoom = 0.4;
    updateZoom();
  });

  printBtn?.addEventListener("click", () => {
    if (!currentDocUrl) return;
    const printWindow = window.open(currentDocUrl, "_blank");
    printWindow?.focus();
    printWindow?.print();
  });

  document.getElementById("viewer-open-new-tab")?.addEventListener("click", () => {
    if (!currentDocUrl) return;
    window.open(currentDocUrl, "_blank");
  });

  downloadBtn?.addEventListener("click", () => {
    if (!currentDocUrl) return;
    const a = document.createElement("a");
    a.href = currentDocUrl;
    a.download = `${customer.name}_${activeDocType.toLowerCase()}`.replace(/\s+/g, "_");
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  });

  const openViewer = (docType) => {
    activeDocType = docType;
    currentZoom = 1.0;
    updateZoom();

    let title = docType.replace(/_/g, " ");
    let endpoint = `/customers/${customer.id}/aadhaar`;
    if (docType === "PROFILE_PHOTO") endpoint = `/customers/${customer.id}/photo`;
    else if (docType === "PROMISSORY_NOTE") endpoint = `/customers/${customer.id}/promissory`;

    const meta = docsMeta[docType] || {};
    let metaText = meta.filename ? `${meta.filename} (${(meta.file_size / (1024 * 1024)).toFixed(2)} MB)` : "Live Photo Stream";

    viewerTitle.innerText = `${customer.name} — ${title}`;
    viewerMeta.innerText = metaText;

    const viewerLoader = document.getElementById("viewer-loader");
    viewerLoader?.classList.remove("hidden");

    customFetchBlob(endpoint)
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob);
        currentDocUrl = objectUrl;

        viewerLoader?.classList.add("hidden");

        if (blob.type === "application/pdf") {
          viewerContainer.innerHTML = `<iframe src="${objectUrl}" class="w-full h-[550px] border-0 bg-white"></iframe>`;
        } else {
          viewerContainer.innerHTML = `<img src="${objectUrl}" class="max-w-full max-h-[550px] object-contain select-none" id="viewer-img" />`;
          initZoomGestures();
        }

        viewerModal?.classList.remove("hidden");
        document.body.style.overflow = "hidden";
        if (window.lucide) window.lucide.createIcons();
      })
      .catch((err) => {
        viewerLoader?.classList.add("hidden");
        alert(err.message || "Failed to load document preview securely.");
      });
  };

  // Expose to window for accordion / card clicks
  window.showDocumentViewer = (docIdOrType, filename, contentType) => {
    let docType = docIdOrType;
    if (!docTypesList.includes(docType)) {
      docType = "AADHAAR";
    }
    openViewer(docType);
  };

  // Swipe gesture detection to navigate between available docs
  let viewTouchStartX = 0;
  let viewTouchEndX = 0;

  viewerModal.addEventListener("touchstart", (e) => {
    viewTouchStartX = e.changedTouches[0].screenX;
  }, { passive: true });

  viewerModal.addEventListener("touchend", (e) => {
    viewTouchEndX = e.changedTouches[0].screenX;
    const diffX = viewTouchStartX - viewTouchEndX;
    const available = getAvailableDocs();

    if (Math.abs(diffX) > 100 && available.length > 1) {
      let currentIndex = available.indexOf(activeDocType);
      if (diffX > 0) {
        // Swipe left -> view next doc
        currentIndex = (currentIndex + 1) % available.length;
      } else {
        // Swipe right -> view prev doc
        currentIndex = (currentIndex - 1 + available.length) % available.length;
      }
      openViewer(available[currentIndex]);
    }
  }, { passive: true });

  // Double tap & Pinch zoom on the image
  function initZoomGestures() {
    const img = document.getElementById("viewer-img");
    if (!img) return;

    let lastTap = 0;
    img.addEventListener("touchend", (e) => {
      const currentTime = new Date().getTime();
      const tapLength = currentTime - lastTap;
      if (tapLength < 300 && tapLength > 0) {
        // Double tap!
        e.preventDefault();
        currentZoom = currentZoom === 1.0 ? 2.0 : 1.0;
        updateZoom();
      }
      lastTap = currentTime;
    });

    let initialPinchDist = 0;
    img.addEventListener("touchstart", (e) => {
      if (e.touches.length === 2) {
        initialPinchDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
      }
    }, { passive: true });

    img.addEventListener("touchmove", (e) => {
      if (e.touches.length === 2 && initialPinchDist > 0) {
        const dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        const scaleChange = dist / initialPinchDist;
        currentZoom = Math.min(3.0, Math.max(0.5, currentZoom * scaleChange));
        updateZoom();
        initialPinchDist = dist;
      }
    }, { passive: true });
  }

  // Preview Buttons Bindings
  document.getElementById("view-aadhaar-btn")?.addEventListener("click", () => {
    if (!aMeta) {
      alert("No document uploaded.");
      return;
    }
    openViewer("AADHAAR");
  });

  document.getElementById("view-promissory-btn")?.addEventListener("click", () => {
    if (!pMeta) {
      alert("No document uploaded.");
      return;
    }
    openViewer("PROMISSORY_NOTE");
  });

  // Document Replacement inputs setup
  const replaceAadhaarInput = document.getElementById("replace-aadhaar-input");
  const replacePromissoryInput = document.getElementById("replace-promissory-input");

  document.getElementById("replace-aadhaar-btn")?.addEventListener("click", () => replaceAadhaarInput?.click());
  document.getElementById("replace-promissory-btn")?.addEventListener("click", () => replacePromissoryInput?.click());

  const handleFileReplacement = async (input, docType) => {
    const file = input.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      await customFetch(`/customers/${customer.id}/documents/${docType}`, {
        method: "POST",
        body: formData
      });
      window.location.reload();
    } catch (err) {
      alert(`Failed to replace document: ${err.message || err.detail || JSON.stringify(err)}`);
    }
  };

  replaceAadhaarInput?.addEventListener("change", () => handleFileReplacement(replaceAadhaarInput, "AADHAAR"));
  replacePromissoryInput?.addEventListener("change", () => handleFileReplacement(replacePromissoryInput, "PROMISSORY_NOTE"));

  // Document Deletion Setup
  const handleFileDeletion = async (docType) => {
    const confirmMsg = window.t ? window.t("profile_confirm_delete") : `Are you sure you want to permanently delete this ${docType} document from the database?`;
    if (!confirm(confirmMsg)) return;
    try {
      await api.delete(`/customers/${customer.id}/documents/${docType}`);
      window.location.reload();
    } catch (err) {
      alert(`Failed to delete document: ${err.message || err.detail || JSON.stringify(err)}`);
    }
  };

  document.getElementById("delete-aadhaar-btn")?.addEventListener("click", () => handleFileDeletion("AADHAAR"));
  document.getElementById("delete-promissory-btn")?.addEventListener("click", () => handleFileDeletion("PROMISSORY_NOTE"));
}



// Start
setTimeout(init, 100);

window.refreshPageData = async () => {
  await init();
};

window.addEventListener("language-changed", () => {
  if (window.currentProfileData) {
    renderProfile(window.currentProfileData);
  }
});


function bindPendingKpiListeners(customer) {
  const card = document.getElementById("kpi-pending-card");
  if (!card) return;

  // Make sure we have a tooltip element for hover preview
  let tooltip = document.getElementById("profile-pending-tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.id = "profile-pending-tooltip";
    tooltip.className = "sakra-dark-tooltip transition-all duration-150 transform scale-95 opacity-0 fixed hidden z-50 pointer-events-none";
    document.body.appendChild(tooltip);
  }

  // Make sure we have the inspection panel overlay
  let overlay = document.getElementById("pending-inspection-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "pending-inspection-overlay";
    document.body.appendChild(overlay);
  }

  function openInspectionPanel() {
    // Lock body scroll
    document.body.classList.add("overflow-hidden");

    const isMobile = window.innerWidth < 768;

    // Set overlay layout based on mobile/desktop
    if (isMobile) {
      overlay.className = "fixed inset-0 z-55 bg-[#020617]/70 backdrop-blur-sm flex items-end justify-center hidden opacity-0 transition-opacity duration-200";
    } else {
      overlay.className = "fixed inset-0 z-55 bg-[#020617]/70 backdrop-blur-sm flex items-center justify-center hidden opacity-0 transition-opacity duration-200";
    }

    const meta = {
      pending_installments_count: customer.pending_installments_count || 0,
      oldest_pending_date: customer.oldest_pending_date,
      latest_pending_date: customer.latest_pending_date,
      pending_amount: customer.pending_amount || 0,
      pending_dates: customer.pending_dates || []
    };

    let itemsHtml = "";
    if (meta.pending_dates && meta.pending_dates.length > 0) {
      itemsHtml = meta.pending_dates.map((d, index) => {
        const divider = index > 0 ? `<div class="border-t border-white/5 my-3.5"></div>` : "";
        
        // Calculate days overdue
        const today = new Date();
        const scheduleDate = new Date(d.date);
        const diffTime = today.getTime() - scheduleDate.getTime();
        const daysOverdue = Math.max(0, Math.floor(diffTime / (1000 * 60 * 60 * 24)));

        return `
          ${divider}
          <div class="flex items-center justify-between text-xs py-1">
            <div class="flex flex-col gap-1">
              <span class="text-[11px] font-bold text-white font-mono tracking-wide">${d.date}</span>
              <span class="text-[10px] text-text-muted">Overdue: <span class="font-mono font-bold text-blue-400">${daysOverdue} Days</span></span>
            </div>
            <div class="flex flex-col items-end gap-1.5 font-sans">
              <span class="font-mono font-bold text-white">${formatCurrency(d.expected_amount)}</span>
              <span class="px-2 py-0.5 rounded text-[8px] font-bold tracking-wide uppercase border ${
                d.status === 'OVERDUE' 
                  ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' 
                  : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
              }">${d.status}</span>
            </div>
          </div>
        `;
      }).join("");
    } else {
      itemsHtml = `<p class="text-center text-xs text-text-muted py-8 select-none">No pending installments recorded.</p>`;
    }

    const panelClass = isMobile
      ? "relative bg-slate-900 border-t border-blue-500/30 shadow-[0_-4px_30px_rgba(59,130,246,0.2)] rounded-t-2xl w-full max-w-md overflow-hidden transform translate-y-full transition-all duration-200 flex flex-col max-h-[85vh]"
      : "relative bg-slate-900 border border-blue-500/30 shadow-[0_0_30px_rgba(59,130,246,0.25)] rounded-2xl w-full max-w-md overflow-hidden transform scale-98 transition-all duration-200 flex flex-col max-h-[80vh]";

    const dragHandle = isMobile
      ? `<div class="w-12 h-1.5 bg-slate-700/80 rounded-full mx-auto my-3 shrink-0"></div>`
      : "";

    overlay.innerHTML = `
      <div class="${panelClass}" id="pending-inspection-panel">
        ${dragHandle}
        <!-- Sticky Header -->
        <div class="px-5 py-4 border-b border-white/10 flex justify-between items-center shrink-0 bg-slate-950/40 select-none">
          <div class="flex flex-col">
            <span class="text-[10px] font-bold text-blue-400 uppercase tracking-widest">Pending Installments</span>
            <span class="text-sm font-bold text-white mt-0.5">${customer.name} (ID: ${customer.id})</span>
          </div>
          <button id="close-inspection-panel" class="text-text-muted hover:text-white p-1.5 rounded-lg hover:bg-white/5 transition-colors focus:outline-none focus:ring-1 focus:ring-blue-500" aria-label="Close panel">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-x"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>

        <!-- Scrollable Content Area -->
        <div id="inspection-panel-body" class="overflow-y-auto p-5 flex-1 overscroll-contain select-text">
          <div class="space-y-1">
            ${itemsHtml}
          </div>
        </div>

        <!-- Sticky Footer Summary -->
        <div class="px-5 py-4 border-t border-white/10 shrink-0 bg-slate-950/60 select-none">
          <div class="grid grid-cols-3 gap-2 text-center">
            <div>
              <span class="text-[9px] font-bold text-text-muted uppercase tracking-wider block font-sans">Total Missed</span>
              <span class="text-xs font-bold text-white mt-1 block">${meta.pending_installments_count} Installments</span>
            </div>
            <div>
              <span class="text-[9px] font-bold text-text-muted uppercase tracking-wider block font-sans">Total Pending</span>
              <span class="text-xs font-bold text-rose-500 mt-1 block">${formatCurrency(meta.pending_amount)}</span>
            </div>
            <div>
              <span class="text-[9px] font-bold text-text-muted uppercase tracking-wider block font-sans">Oldest Date</span>
              <span class="text-[10px] font-bold text-amber-500 mt-1 block font-mono">${meta.oldest_pending_date || '—'}</span>
            </div>
          </div>
        </div>
      </div>
    `;

    // Event listeners for close
    const closeBtn = overlay.querySelector("#close-inspection-panel");
    const panel = overlay.querySelector("#pending-inspection-panel");
    const body = overlay.querySelector("#inspection-panel-body");

    // Prevent page scroll when pointer is inside body
    if (body) {
      body.addEventListener("wheel", (e) => {
        const scrollTop = body.scrollTop;
        const scrollHeight = body.scrollHeight;
        const height = body.clientHeight;
        const delta = e.deltaY;

        if ((delta > 0 && scrollTop + height >= scrollHeight) || (delta < 0 && scrollTop <= 0)) {
          e.preventDefault();
        }
      }, { passive: false });
    }

    function closePanel() {
      // Release body scroll
      document.body.classList.remove("overflow-hidden");

      overlay.classList.add("opacity-0");
      if (isMobile) {
        panel.classList.add("translate-y-full");
      } else {
        panel.classList.add("scale-98");
      }

      document.removeEventListener("keydown", handleEsc);

      setTimeout(() => {
        overlay.classList.add("hidden");
      }, 200);
    }

    function handleEsc(e) {
      if (e.key === "Escape") {
        closePanel();
      }
    }

    closeBtn.addEventListener("click", closePanel);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        closePanel();
      }
    });

    document.addEventListener("keydown", handleEsc);

    // Show overlay
    overlay.classList.remove("hidden");
    setTimeout(() => {
      overlay.classList.add("opacity-100");
      overlay.classList.remove("opacity-0");
      if (isMobile) {
        panel.classList.remove("translate-y-full");
        panel.classList.add("translate-y-0");
      } else {
        panel.classList.remove("scale-98");
        panel.classList.add("scale-100");
      }
      closeBtn.focus();
    }, 10);
  }

  // Hover listeners (Desktop preview hover)
  card.addEventListener("mouseenter", (e) => {
    if (window.innerWidth < 768) return; // Skip on mobile
    
    tooltip.innerHTML = `
      <div class="text-[10px] font-bold text-white tracking-wider flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-900 border border-blue-500/25 shadow-lg rounded-lg">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-blue-400 animate-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
        <span>Click to inspect details</span>
      </div>
    `;

    tooltip.classList.remove("hidden");
    const rect = card.getBoundingClientRect();
    const tooltipHeight = tooltip.offsetHeight;
    const tooltipWidth = tooltip.offsetWidth;
    
    let top = rect.top - tooltipHeight - 8;
    let left = rect.left + (rect.width / 2) - (tooltipWidth / 2);

    if (top < 10) {
      top = rect.bottom + 8;
    }
    if (left < 10) {
      left = 10;
    }
    if (left + tooltipWidth > window.innerWidth - 10) {
      left = window.innerWidth - tooltipWidth - 10;
    }

    tooltip.style.top = `${top + window.scrollY}px`;
    tooltip.style.left = `${left + window.scrollX}px`;

    tooltip.classList.remove("scale-95", "opacity-0");
    tooltip.classList.add("scale-100", "opacity-100");
  });

  card.addEventListener("mouseleave", () => {
    tooltip.classList.remove("scale-100", "opacity-100");
    tooltip.classList.add("scale-95", "opacity-0");
    setTimeout(() => {
      if (tooltip.classList.contains("opacity-0")) {
        tooltip.classList.add("hidden");
      }
    }, 150);
  });

  // Tap/Click listener to open inspection panel
  card.addEventListener("click", (e) => {
    e.stopPropagation();
    tooltip.classList.add("hidden");
    tooltip.classList.remove("scale-100", "opacity-100");
    openInspectionPanel();
  });
}


function animateKPIs() {
  const elements = document.querySelectorAll("[data-animate]");
  elements.forEach(el => {
    const targetVal = parseFloat(el.getAttribute("data-val") || 0);
    const type = el.getAttribute("data-animate");
    
    // Store the previous value in a custom attribute to avoid restarting from 0 if refreshed
    const prevVal = parseFloat(el.getAttribute("data-prev") || 0);
    el.setAttribute("data-prev", targetVal);
    
    if (prevVal === targetVal) {
      if (type === "duration" || type === "days-passed") {
        el.innerText = `${Math.round(targetVal)} Days`;
      } else if (type === "equivalent") {
        el.innerText = `${targetVal.toFixed(2)} Days`;
      } else {
        el.innerText = formatCurrency(targetVal);
      }
      return;
    }
    
    let duration = 600; // ms
    let startTimestamp = null;
    
    const step = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const current = prevVal + progress * (targetVal - prevVal);
      
      if (type === "duration" || type === "days-passed") {
        el.innerText = `${Math.round(current)} Days`;
      } else if (type === "equivalent") {
        el.innerText = `${current.toFixed(2)} Days`;
      } else {
        el.innerText = formatCurrency(current);
      }
      
      if (progress < 1) {
        window.requestAnimationFrame(step);
      }
    };
    window.requestAnimationFrame(step);
  });
}

function bindPaymentActions() {
  // Record Buttons
  document.querySelectorAll(".record-payment-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const loanId = btn.getAttribute("data-loan-id");
      const date = btn.getAttribute("data-date");
      
      document.getElementById("rp-loan-id").value = loanId;
      document.getElementById("rp-payment-date").value = date;
      document.getElementById("rp-amount-paid").value = "";
      document.getElementById("rp-remarks").value = "";
      
      document.getElementById("rp-error").classList.add("hidden");
      document.getElementById("rp-success").classList.add("hidden");
      
      document.getElementById("record-payment-modal").classList.remove("hidden");
      document.body.style.overflow = "hidden";
    });
  });
  
  // Edit Buttons
  document.querySelectorAll(".edit-payment-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const date = btn.getAttribute("data-date");
      const amount = btn.getAttribute("data-amount");
      const mode = btn.getAttribute("data-mode");
      const remarks = btn.getAttribute("data-remarks");
      const version = btn.getAttribute("data-version");
      
      document.getElementById("ep-payment-id").value = id;
      document.getElementById("ep-version-id").value = version;
      document.getElementById("ep-payment-date").value = date;
      document.getElementById("ep-amount-paid").value = amount;
      document.getElementById("ep-payment-mode").value = mode;
      document.getElementById("ep-remarks").value = remarks;
      
      document.getElementById("ep-error").classList.add("hidden");
      document.getElementById("ep-success").classList.add("hidden");
      
      document.getElementById("edit-payment-modal").classList.remove("hidden");
      document.body.style.overflow = "hidden";
    });
  });
  
  // Delete Buttons
  document.querySelectorAll(".delete-payment-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      const amount = btn.getAttribute("data-amount");
      const date = btn.getAttribute("data-date");
      
      if (!confirm(`Are you sure you want to permanently delete the payment of ₹${parseFloat(amount).toLocaleString('en-IN')} for ${date}?`)) {
        return;
      }
      
      try {
        await api.delete(`/payments/${id}`);
        await window.refreshPageData();
      } catch (err) {
        alert("Failed to delete payment: " + (err.message || err.detail || JSON.stringify(err)));
      }
    });
  });
}

// Modal close triggers
document.getElementById("close-record-payment-modal")?.addEventListener("click", () => {
  document.getElementById("record-payment-modal").classList.add("hidden");
  document.body.style.overflow = "";
});
document.getElementById("close-edit-payment-modal")?.addEventListener("click", () => {
  document.getElementById("edit-payment-modal").classList.add("hidden");
  document.body.style.overflow = "";
});

// Forms submit triggers
document.getElementById("record-payment-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const submitBtn = document.getElementById("submit-record-payment");
  const errorEl = document.getElementById("rp-error");
  const successEl = document.getElementById("rp-success");
  
  errorEl.classList.add("hidden");
  successEl.classList.add("hidden");
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span>Recording...</span>`;
  
  const payload = {
    loan_id: parseInt(form.querySelector('[name="loan_id"]').value),
    payment_date: form.querySelector('[name="payment_date"]').value,
    amount_paid: parseFloat(form.querySelector('[name="amount_paid"]').value),
    payment_mode: form.querySelector('[name="payment_mode"]').value,
    remarks: form.querySelector('[name="remarks"]').value || undefined
  };
  
  try {
    await api.post("/payments", payload);
    successEl.innerText = "Payment recorded successfully!";
    successEl.classList.remove("hidden");
    
    setTimeout(async () => {
      document.getElementById("record-payment-modal").classList.add("hidden");
      document.body.style.overflow = "";
      await window.refreshPageData();
    }, 800);
  } catch (err) {
    errorEl.innerText = err.message || err.detail || "Failed to record payment.";
    errorEl.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span>Record Payment</span>`;
  }
});

document.getElementById("edit-payment-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const submitBtn = document.getElementById("submit-edit-payment");
  const errorEl = document.getElementById("ep-error");
  const successEl = document.getElementById("ep-success");
  
  errorEl.classList.add("hidden");
  successEl.classList.add("hidden");
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span>Saving...</span>`;
  
  const paymentId = form.querySelector('[name="payment_id"]').value;
  const payload = {
    amount_paid: parseFloat(form.querySelector('[name="amount_paid"]').value),
    payment_mode: form.querySelector('[name="payment_mode"]').value,
    remarks: form.querySelector('[name="remarks"]').value || undefined,
    version_id: parseInt(form.querySelector('[name="version_id"]').value)
  };
  
  try {
    await api.put(`/payments/${paymentId}`, payload);
    successEl.innerText = "Payment updated successfully!";
    successEl.classList.remove("hidden");
    
    setTimeout(async () => {
      document.getElementById("edit-payment-modal").classList.add("hidden");
      document.body.style.overflow = "";
      await window.refreshPageData();
    }, 800);
  } catch (err) {
    errorEl.innerText = err.message || err.detail || "Failed to modify payment.";
    errorEl.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span>Save Changes</span>`;
  }
});


function initializeMobileAccordions(data) {
  if (window.innerWidth >= 768) return;

  const { customer, loans = [], aggregate_payments = [], credit_score } = data;
  const activeLoan = loans.find(l => l.status === "ACTIVE" || l.status === "OVERDUE") || loans[0];

  const parentContainer = document.getElementById("profile-content");
  if (!parentContainer) return;

  // Elements to hide on mobile
  const chartSplit = parentContainer.querySelector(".grid.grid-cols-1.lg\\:grid-cols-3");
  if (chartSplit) chartSplit.style.display = "none";

  const kycCard = parentContainer.querySelector(".glass-card.bg-white\\/60.p-6.flex.flex-col.gap-4");
  if (kycCard) kycCard.style.display = "none";

  const loansTable = parentContainer.querySelector(".sakra-table-wrapper.bg-white\\/60");
  if (loansTable) loansTable.style.display = "none";

  const paymentsTable = parentContainer.querySelector(".sakra-table-wrapper.bg-white\\/60.backdrop-blur-md");
  if (paymentsTable) paymentsTable.style.display = "none";

  const collectionDash = document.getElementById("collection-intelligence-dashboard");
  if (collectionDash) collectionDash.style.display = "none";

  let accordionContainer = document.getElementById("mobile-profile-accordions");
  if (!accordionContainer) {
    accordionContainer = document.createElement("div");
    accordionContainer.id = "mobile-profile-accordions";
    accordionContainer.className = "flex flex-col gap-3 mt-6";
    const statsGrid = parentContainer.querySelector(".profile-stats-grid");
    if (statsGrid) {
      statsGrid.parentNode.insertBefore(accordionContainer, statsGrid.nextSibling);
    } else {
      parentContainer.appendChild(accordionContainer);
    }
  }

  // 1. Overview Accordion
  const detailsHtml = `
    <div class="flex flex-col gap-3">
      <div class="flex justify-between items-center text-xs py-1.5 border-b border-white/5">
        <span class="text-text-muted">DOB:</span>
        <span class="text-text-primary font-mono font-bold">${customer.date_of_birth || "—"}</span>
      </div>
      <div class="flex justify-between items-center text-xs py-1.5 border-b border-white/5">
        <span class="text-text-muted">Gender:</span>
        <span class="text-text-primary font-bold">${customer.gender || "—"}</span>
      </div>
      <div class="flex justify-between items-center text-xs py-1.5 border-b border-white/5">
        <span class="text-text-muted">Occupation:</span>
        <span class="text-text-primary font-bold">${customer.occupation || "—"}</span>
      </div>
      <div class="flex flex-col text-xs py-1.5 border-b border-white/5 gap-1">
        <span class="text-text-muted">Address:</span>
        <span class="text-text-secondary leading-normal">${customer.address || "—"}</span>
      </div>
      <div class="flex flex-col text-xs py-1.5 border-b border-white/5 gap-1">
        <span class="text-text-muted">Note Memos:</span>
        <span class="text-text-secondary leading-normal italic">${customer.promissory_note || "—"}</span>
      </div>
      <div class="flex justify-between items-center text-xs py-1.5">
        <span class="text-text-muted">Credit Score:</span>
        <span class="font-mono font-extrabold text-blue-400">${credit_score || 700}</span>
      </div>
    </div>
  `;

  // 2. Collection Intelligence & Analytics Accordion
  const analyticsHtml = `
    <div class="flex flex-col gap-4">
      <div class="bg-slate-950/40 p-3 rounded-lg border border-white/5">
        <h4 class="text-[9px] uppercase tracking-wider text-text-muted mb-2 font-bold">Payment Distribution</h4>
        <canvas id="mobileScatterChartCanvas" style="max-height: 160px; width: 100%;"></canvas>
      </div>
      <div class="flex flex-col gap-2">
        <h4 class="text-[9px] uppercase tracking-wider text-text-muted font-bold">Collection Intelligence</h4>
        <div id="mobile-collection-dashboard-body"></div>
      </div>
    </div>
  `;

  // 3. Loan Details Accordion
  const loansHtml = `
    <div class="flex flex-col gap-3">
      ${loans.map(loan => {
        const variantClass = loan.status === "ACTIVE" ? "bg-blue-500/10 text-blue-400 border-blue-500/20" :
                             loan.status === "COMPLETED" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                             "bg-rose-500/10 text-rose-400 border-rose-500/20";
        return `
          <div class="bg-slate-950/30 p-3.5 rounded-lg border border-white/5 flex flex-col gap-2 font-mono text-xs">
            <div class="flex justify-between items-center">
              <span class="text-white font-bold">Loan #${loan.id}</span>
              <span class="px-2 py-0.5 rounded text-[9px] font-bold border uppercase ${variantClass}">${loan.status}</span>
            </div>
            <div class="h-px bg-white/5"></div>
            <div class="grid grid-cols-2 gap-2 text-[10px]">
              <div>
                <span class="text-[8px] text-text-muted block uppercase">Principal</span>
                <span class="font-bold text-text-secondary">${formatCurrency(loan.principal_amount)}</span>
              </div>
              <div>
                <span class="text-[8px] text-text-muted block uppercase">Formula</span>
                <span class="text-text-secondary">${loan.interest_formula} @ ${formatInterestRate(loan.interest_rate)}</span>
              </div>
              <div class="col-span-2">
                <span class="text-[8px] text-text-muted block uppercase">Period</span>
                <span class="text-text-secondary">${loan.loan_start_date} → ${loan.loan_end_date || '—'}</span>
              </div>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;

  // 4. Documents Accordion
  const docsMeta = data.documents_metadata || {};
  const docStatusHtml = `
    <div class="flex flex-col gap-2.5">
      ${["PROFILE_PHOTO", "AADHAAR", "PROMISSORY_NOTE"].map(docType => {
        const doc = docsMeta[docType];
        const title = docType.replace(/_/g, " ");
        if (doc) {
          return `
            <div class="bg-slate-950/30 p-3 rounded-lg border border-white/5 flex justify-between items-center text-xs">
              <div class="flex items-center gap-2">
                <i data-lucide="file-check" class="w-4 h-4 text-emerald-400"></i>
                <div class="flex flex-col">
                  <span class="font-bold text-text-primary text-[11px] uppercase">${title}</span>
                  <span class="text-[8px] text-text-muted font-mono mt-0.5">${doc.filename}</span>
                </div>
              </div>
              <button class="sakra-btn-tactile bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white px-2.5 py-1 rounded text-[9px] font-bold uppercase border border-blue-500/20 cursor-pointer preview-doc-btn" data-doc-type="${docType}">
                Preview
              </button>
            </div>
          `;
        } else {
          return `
            <div class="bg-slate-950/30 p-3 rounded-lg border border-white/5 flex justify-between items-center text-xs opacity-75">
              <div class="flex items-center gap-2">
                <i data-lucide="file-warning" class="w-4 h-4 text-amber-500"></i>
                <div class="flex flex-col">
                  <span class="font-bold text-text-primary text-[11px] uppercase">${title}</span>
                  <span class="text-[8px] text-amber-500/80 font-semibold mt-0.5">Missing Document</span>
                </div>
              </div>
            </div>
          `;
        }
      }).join("")}
    </div>
  `;

  // 5. Repayment History Accordion
  const repaymentsHtml = `
    <div class="flex flex-col gap-3">
      ${aggregate_payments.map((p, idx) => {
        const norm = (p.payment_status || "PENDING").toUpperCase();
        let badgeClass = "bg-amber-500/10 text-amber-400 border border-amber-500/20";
        if (norm === "PAID") badgeClass = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
        else if (norm === "OVERDUE") badgeClass = "bg-rose-500/10 text-rose-400 border border-rose-500/20";
        
        return `
          <div class="bg-slate-950/30 p-3 rounded-lg border border-white/5 flex flex-col gap-2 font-mono text-xs">
            <div class="flex justify-between items-center">
              <span class="text-text-secondary font-bold">Transaction #${idx + 1} (${p.payment_date})</span>
              <span class="px-1.5 py-0.5 rounded text-[8px] font-bold border ${badgeClass}">${norm}</span>
            </div>
            <div class="grid grid-cols-2 gap-2 text-[10px] text-text-muted">
              <div>
                <span>Expected:</span> <span class="text-white">${formatCurrency(p.expected_amount)}</span>
              </div>
              <div>
                <span>Paid:</span> <span class="text-success font-bold">${formatCurrency(p.amount_paid)}</span>
              </div>
              <div>
                <span>Coverage:</span> <span class="text-blue-400">${p.equivalent_coverage != null ? Number(p.equivalent_coverage).toFixed(2) + ' Days' : '—'}</span>
              </div>
              <div>
                <span>Mode:</span> <span class="text-white">${p.payment_mode || "CASH"}</span>
              </div>
            </div>
            ${p.remarks ? `<p class="text-[9px] text-text-muted italic border-t border-white/5 pt-1.5 mt-1">Note: ${p.remarks}</p>` : ""}
          </div>
        `;
      }).join("")}
      ${aggregate_payments.length === 0 ? '<p class="text-center text-xs text-text-muted py-6">No payments recorded</p>' : ''}
    </div>
  `;

  // 6. Loan Schedule Accordion
  const schedules = activeLoan?.schedules || [];
  const scheduleHtml = `
    <div class="flex flex-col gap-2 max-h-80 overflow-y-auto pr-1">
      ${schedules.map(s => {
        let badgeClass = s.remaining_amount <= 0 ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-amber-500/10 text-amber-400 border-amber-500/20";
        let statusText = s.remaining_amount <= 0 ? "PAID" : "UNPAID";
        return `
          <div class="bg-slate-950/20 p-2.5 rounded-lg border border-white/5 flex justify-between items-center text-[11px] font-mono">
            <div class="flex flex-col">
              <span class="font-bold text-white">EMI #${s.installment_number}</span>
              <span class="text-[9px] text-text-muted mt-0.5">Due: ${s.due_date}</span>
            </div>
            <div class="flex items-center gap-3">
              <div class="flex flex-col text-right">
                <span class="text-white font-bold">${formatCurrency(s.expected_amount)}</span>
                <span class="text-[9px] text-rose-400">Bal: ${formatCurrency(s.remaining_amount)}</span>
              </div>
              <span class="px-1.5 py-0.5 rounded text-[8px] font-bold border ${badgeClass}">${statusText}</span>
            </div>
          </div>
        `;
      }).join("")}
      ${schedules.length === 0 ? '<p class="text-center text-xs text-text-muted py-6">No schedules active</p>' : ''}
    </div>
  `;

  // 7. Security Logs Accordion
  const securityHtml = `
    <div class="flex flex-col gap-2 font-mono text-[10px] text-text-secondary">
      <div class="p-2.5 bg-slate-950/20 border border-white/5 rounded-lg flex flex-col gap-1">
        <span class="text-blue-400 font-bold uppercase text-[9px] tracking-wider">Account Creation</span>
        <span>Registered by operator on ${formatDate(customer.created_at)}</span>
      </div>
      <div class="p-2.5 bg-slate-950/20 border border-white/5 rounded-lg flex flex-col gap-1 mt-1">
        <span class="text-amber-400 font-bold uppercase text-[9px] tracking-wider">Profile Revision Trace</span>
        <span>Database Version ID: #${customer.version_id}</span>
        <span>Last updated: ${customer.updated_at ? formatDate(customer.updated_at) : 'No updates recorded'}</span>
      </div>
    </div>
  `;

  const accordions = [
    { id: "overview", title: "Overview", icon: "user", content: detailsHtml },
    { id: "analytics", title: "Collection Analytics", icon: "line-chart", content: analyticsHtml },
    { id: "loans", title: "Loan Details", icon: "credit-card", content: loansHtml },
    { id: "documents", title: "Documents", icon: "file-text", content: docStatusHtml },
    { id: "history", title: "Repayment History", icon: "history", content: repaymentsHtml },
    { id: "schedule", title: "Loan Schedule", icon: "calendar", content: scheduleHtml },
    { id: "audit", title: "Security Logs", icon: "shield", content: securityHtml }
  ];

  accordionContainer.innerHTML = accordions.map(a => {
    const savedState = localStorage.getItem(`sakra-profile-accordion-${a.id}`);
    const isActive = savedState === "open";
    const activeClass = isActive ? "active" : "";
    return `
      <div class="sakra-profile-accordion ${activeClass}" data-accordion-id="${a.id}">
        <div class="sakra-profile-accordion-header">
          <div class="flex items-center gap-2">
            <i data-lucide="${a.icon}" class="w-3.5 h-3.5 text-blue-400"></i>
            <span>${a.title}</span>
          </div>
          <i data-lucide="chevron-down" class="w-4 h-4 sakra-profile-accordion-chevron"></i>
        </div>
        <div class="sakra-profile-accordion-content">
          <div class="sakra-profile-accordion-inner">
            ${a.content}
          </div>
        </div>
      </div>
    `;
  }).join("");

  accordionContainer.querySelectorAll(".sakra-profile-accordion").forEach(acc => {
    const header = acc.querySelector(".sakra-profile-accordion-header");
    header.addEventListener("click", () => {
      const aId = acc.getAttribute("data-accordion-id");
      if (acc.classList.contains("active")) {
        acc.classList.remove("active");
        localStorage.setItem(`sakra-profile-accordion-${aId}`, "closed");
      } else {
        acc.classList.add("active");
        localStorage.setItem(`sakra-profile-accordion-${aId}`, "open");
      }
    });
  });

  const mobileCanvas = document.getElementById("mobileScatterChartCanvas");
  if (mobileCanvas) {
    renderScatterPlotOnMobile(loans, aggregate_payments, customer, mobileCanvas);
  }

  const mobileIntelBody = document.getElementById("mobile-collection-dashboard-body");
  if (mobileIntelBody && collectionDash) {
    mobileIntelBody.innerHTML = collectionDash.innerHTML;
  }

  accordionContainer.querySelectorAll(".preview-doc-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const docType = btn.getAttribute("data-doc-type");
      const doc = docsMeta[docType];
      if (doc && window.showDocumentViewer) {
        window.showDocumentViewer(doc.id, doc.filename, doc.content_type);
      }
    });
  });

  if (window.lucide) {
    window.lucide.createIcons({ node: accordionContainer });
  }
}

function renderScatterPlotOnMobile(loans, payments, customer, canvas) {
  if (!payments || payments.length === 0) return;
  const firstLoanStart = loans.length > 0 ? new Date(loans[0].loan_start_date) : new Date();
  
  const chartData = payments.filter(p => parseFloat(p.amount_paid || 0) > 0).map(p => {
    const payDate = new Date(p.payment_date);
    const dayIndex = Math.max(0, Math.round((payDate - firstLoanStart) / (1000 * 60 * 60 * 24)));
    return {
      x: dayIndex,
      y: parseFloat(p.amount_paid || 0),
      date: p.payment_date
    };
  });

  const ctx = canvas.getContext("2d");
  new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [{
        label: "Payment Logs",
        data: chartData,
        backgroundColor: "rgba(37, 99, 235, 0.7)",
        borderColor: "rgb(37, 99, 235)",
        borderWidth: 1,
        pointRadius: 5,
        pointHoverRadius: 7
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(context) {
              const item = context.raw;
              return [
                `Day: ${item.x}`,
                `Date: ${item.date}`,
                `Amount: ₹${item.y.toLocaleString("en-IN")}`
              ];
            }
          }
        }
      },
      scales: {
        x: { ticks: { font: { size: 8 } } },
        y: { ticks: { font: { size: 8 } } }
      }
    }
  });
}


