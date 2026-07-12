import api, { customFetch } from "../api.js";
import { formatCurrency, formatDate, formatInterestRate } from "../helpers.js";


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

  // Calculate coverage stats dynamically
  let latestCoverage = "—";
  let largestCoverage = "—";
  const actualPayments = aggregate_payments.filter(p => parseFloat(p.amount_paid) > 0 && p.equivalent_coverage != null);
  if (actualPayments.length > 0) {
    latestCoverage = `${actualPayments[0].equivalent_coverage} Days`;
    const maxCoverage = Math.max(...actualPayments.map(p => p.equivalent_coverage));
    largestCoverage = `${maxCoverage} Days`;
  }
  document.getElementById("stat-latest-coverage").innerText = latestCoverage;
  document.getElementById("stat-largest-coverage").innerText = largestCoverage;

  // Bind collection intelligence pending installments card listeners
  bindPendingKpiListeners(customer);

  // 3. Customer Details block
  document.getElementById("profile-photo-img").src = `/api/v1/customers/${customer.id}/photo?t=${new Date().getTime()}`;

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
          <td class="font-mono text-xs text-text-muted">#${loan.id}</td>
          <td class="text-right font-bold text-text-primary font-mono">${formatCurrency(loan.principal_amount)}</td>
          <td class="text-text-secondary font-semibold text-xs">${loan.interest_formula} @ ${formatInterestRate(loan.interest_rate)}</td>
          <td class="text-xs text-text-secondary font-mono">${loan.loan_start_date} → ${loan.loan_end_date}</td>
          <td class="text-center">
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
          <td class="text-text-muted font-mono text-xs">#${idx + 1}</td>
          <td class="font-semibold text-text-primary text-xs">${p.payment_date}</td>
          <td class="text-right font-mono text-xs text-text-secondary">${formatCurrency(p.expected_amount)}</td>
          <td class="text-right font-mono text-xs ${paidTextClass}">${formatCurrency(p.amount_paid)}</td>
          <td class="text-xs text-text-primary font-bold font-mono">${p.equivalent_coverage != null ? p.equivalent_coverage + ' Days' : '—'}</td>
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

  const closeViewer = () => {
    viewerModal?.classList.add("hidden");
    if (viewerContainer) viewerContainer.innerHTML = "";
    document.body.style.overflow = "";
  };
  closeViewerBtn?.addEventListener("click", closeViewer);
  viewerModal?.addEventListener("click", (e) => {
    if (e.target === viewerModal) closeViewer();
  });

  zoomInBtn?.addEventListener("click", () => {
    currentZoom += 0.15;
    if (currentZoom > 2.5) currentZoom = 2.5;
    viewerContainer.style.transform = `scale(${currentZoom})`;
  });

  zoomOutBtn?.addEventListener("click", () => {
    currentZoom -= 0.15;
    if (currentZoom < 0.4) currentZoom = 0.4;
    viewerContainer.style.transform = `scale(${currentZoom})`;
  });

  printBtn?.addEventListener("click", () => {
    if (!currentDocUrl) return;
    const printWindow = window.open(currentDocUrl, "_blank");
    printWindow?.focus();
    printWindow?.print();
  });

  downloadBtn?.addEventListener("click", () => {
    if (!currentDocUrl) return;
    const a = document.createElement("a");
    a.href = currentDocUrl;
    a.download = currentDocUrl.split("/").pop() || "document";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  });

  const openViewer = (title, endpoint, metaText) => {
    currentZoom = 1.0;
    viewerContainer.style.transform = "scale(1)";
    viewerTitle.innerText = title;
    viewerMeta.innerText = metaText;

    const viewerLoader = document.getElementById("viewer-loader");
    viewerLoader?.classList.remove("hidden");

    const token = localStorage.getItem("sakra_access_token") || sessionStorage.getItem("sakra_access_token") || localStorage.getItem("access_token") || sessionStorage.getItem("access_token");
    const apiBase = "/api/v1";
    const absoluteUrl = `${apiBase}${endpoint}`;

    fetch(absoluteUrl, {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${token}`
      }
    })
      .then(async (response) => {
        if (!response.ok) {
          if (response.status === 403) {
            throw new Error("Access Denied: VIEWER role is blocked from viewing identity documents.");
          }
          throw new Error("HTTP error " + response.status);
        }
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        currentDocUrl = objectUrl;

        viewerLoader?.classList.add("hidden");

        if (blob.type === "application/pdf") {
          viewerContainer.innerHTML = `<iframe src="${objectUrl}" class="w-full h-[550px] border-0 bg-white"></iframe>`;
        } else {
          viewerContainer.innerHTML = `<img src="${objectUrl}" class="max-w-full max-h-[550px] object-contain" />`;
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

  // Preview Buttons Bindings
  document.getElementById("view-aadhaar-btn")?.addEventListener("click", () => {
    if (!aMeta) return;
    openViewer("Aadhaar Card Preview", `/customers/${customer.id}/aadhaar`, `${aMeta.filename} (${(aMeta.file_size / (1024*1024)).toFixed(2)} MB)`);
  });

  document.getElementById("view-promissory-btn")?.addEventListener("click", () => {
    if (!pMeta) return;
    openViewer("Promissory Note Preview", `/customers/${customer.id}/promissory`, `${pMeta.filename} (${(pMeta.file_size / (1024*1024)).toFixed(2)} MB)`);
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

