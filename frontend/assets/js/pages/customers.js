import api, { customFetch } from "../api.js";
import { getCachedUser } from "../auth.js";
import { formatCurrency } from "../helpers.js";


let customerRegistry = [];
let searchQuery = "";
let activeFilter = "all";
let activeSort = "created_at";
let activeSortDir = "desc";
let currentPage = 1;
const pageSize = 10;

const customersContent = document.getElementById("customers-content");
const addCustomerBtn = document.getElementById("add-customer-btn");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const tableBody = document.getElementById("customers-table-body");
const tableSpinner = document.getElementById("table-loading-spinner");
const emptyState = document.getElementById("empty-state");
const errorState = document.getElementById("error-state");
const tableContainer = document.getElementById("table-container");
const pageInfo = document.getElementById("page-info");
const prevBtn = document.getElementById("prev-page-btn");
const nextBtn = document.getElementById("next-page-btn");
const retryLoadBtn = document.getElementById("retry-load-btn");
const emptyStateAddBtn = document.getElementById("empty-state-add-btn");
const mobileCardsContainer = document.getElementById("customers-cards-mobile");
const sortSelect = document.getElementById("sort-select");
const sortDirSelect = document.getElementById("sort-dir-select");

// Modal Elements
const addModal = document.getElementById("add-customer-modal");
const closeModalBtn = document.getElementById("close-modal-btn");
const cancelModalBtn = document.getElementById("cancel-modal-btn");
const addForm = document.getElementById("add-customer-form");
const modalError = document.getElementById("modal-error-message");
const modalSubmitBtn = document.getElementById("modal-submit-btn");

// Set Disbursal Date default to today
const dateInput = addForm?.querySelector('input[name="loan_start_date"]');
if (dateInput) {
  dateInput.value = new Date().toISOString().split("T")[0];
}

function openModal() {
  addForm?.reset();
  if (dateInput) dateInput.value = new Date().toISOString().split("T")[0];
  modalError?.classList.add("hidden");
  
  // Lock body scrolling
  document.body.style.overflow = "hidden";
  
  addModal?.classList.remove("hidden");
  // Force browser reflow to trigger transition
  addModal?.offsetHeight;
  addModal?.classList.add("active");
  
  // Focus first input automatically after scale animation
  setTimeout(() => {
    const firstInput = addForm?.querySelector("input[name='name']");
    firstInput?.focus();
  }, 150);
}

function closeModal() {
  addModal?.classList.remove("active");
  document.body.style.overflow = "";
  
  // Wait for transition before hiding completely
  setTimeout(() => {
    if (addModal && !addModal.classList.contains("active")) {
      addModal.classList.add("hidden");
    }
  }, 280);
}

async function init() {
  const user = getCachedUser();
  if (!user) return; // Wait for main.js session resolution

  // Show register account option if authorized
  if (["SUPER_ADMIN", "ADMIN"].includes(user.role)) {
    addCustomerBtn?.classList.remove("hidden");
  }

  // Bind Modal Events
  addCustomerBtn?.addEventListener("click", openModal);
  closeModalBtn?.addEventListener("click", closeModal);
  cancelModalBtn?.addEventListener("click", closeModal);
  emptyStateAddBtn?.addEventListener("click", openModal);

  // Modal Overlay click closing (only direct clicks on backdrop)
  addModal?.addEventListener("click", (e) => {
    if (e.target === addModal) {
      closeModal();
    }
  });

  // ESC key closing binding
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && addModal && !addModal.classList.contains("hidden")) {
      closeModal();
    }
  });

  // ── Profile Photo Upload Setup ──
  const photoInput = document.getElementById("profile-photo-input");
  const photoPreviewImg = document.getElementById("photo-preview-img");
  const photoPlaceholder = document.getElementById("photo-placeholder");
  const removePhotoBtn = document.getElementById("remove-photo-btn");
  const uploadPhotoBtn = document.getElementById("upload-photo-btn");

  const triggerPhotoUpload = () => photoInput?.click();
  document.getElementById("photo-preview-container")?.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    triggerPhotoUpload();
  });
  uploadPhotoBtn?.addEventListener("click", triggerPhotoUpload);

  photoInput?.addEventListener("change", () => {
    const file = photoInput.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        alert("Profile photo exceeds 5MB limit.");
        photoInput.value = "";
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        if (photoPreviewImg) {
          photoPreviewImg.src = e.target.result;
          photoPreviewImg.classList.remove("hidden");
        }
        photoPlaceholder?.classList.add("hidden");
        removePhotoBtn?.classList.remove("hidden");
      };
      reader.readAsDataURL(file);
    }
  });

  removePhotoBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (photoInput) photoInput.value = "";
    if (photoPreviewImg) {
      photoPreviewImg.src = "";
      photoPreviewImg.classList.add("hidden");
    }
    photoPlaceholder?.classList.remove("hidden");
    removePhotoBtn?.classList.add("hidden");
  });

  // ── Aadhaar Dropzone Setup ──
  const aadhaarDropzone = document.getElementById("aadhaar-dropzone");
  const aadhaarInput = document.getElementById("aadhaar-file-input");
  const aadhaarPrompt = document.getElementById("aadhaar-upload-prompt");
  const aadhaarDetails = document.getElementById("aadhaar-file-details");
  const aadhaarName = document.getElementById("aadhaar-file-name");
  const aadhaarSize = document.getElementById("aadhaar-file-size");
  const clearAadhaarBtn = document.getElementById("clear-aadhaar-btn");

  aadhaarDropzone?.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    aadhaarInput?.click();
  });

  aadhaarInput?.addEventListener("change", () => {
    const file = aadhaarInput.files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        alert("Aadhaar file exceeds 10MB limit.");
        aadhaarInput.value = "";
        return;
      }
      if (aadhaarName) aadhaarName.innerText = file.name;
      if (aadhaarSize) aadhaarSize.innerText = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
      aadhaarPrompt?.classList.add("hidden");
      aadhaarDetails?.classList.remove("hidden");
    }
  });

  clearAadhaarBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (aadhaarInput) aadhaarInput.value = "";
    aadhaarDetails?.classList.add("hidden");
    aadhaarPrompt?.classList.remove("hidden");
  });

  // ── Promissory dropzone Setup ──
  const promissoryDropzone = document.getElementById("promissory-dropzone");
  const promissoryInput = document.getElementById("promissory-file-input");
  const promissoryPrompt = document.getElementById("promissory-upload-prompt");
  const promissoryDetails = document.getElementById("promissory-file-details");
  const promissoryName = document.getElementById("promissory-file-name");
  const promissorySize = document.getElementById("promissory-file-size");
  const clearPromissoryBtn = document.getElementById("clear-promissory-btn");

  promissoryDropzone?.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    promissoryInput?.click();
  });

  promissoryInput?.addEventListener("change", () => {
    const file = promissoryInput.files[0];
    if (file) {
      if (file.size > 20 * 1024 * 1024) {
        alert("Promissory Note file exceeds 20MB limit.");
        promissoryInput.value = "";
        return;
      }
      if (promissoryName) promissoryName.innerText = file.name;
      if (promissorySize) promissorySize.innerText = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
      promissoryPrompt?.classList.add("hidden");
      promissoryDetails?.classList.remove("hidden");
    }
  });

  clearPromissoryBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    if (promissoryInput) promissoryInput.value = "";
    promissoryDetails?.classList.add("hidden");
    promissoryPrompt?.classList.remove("hidden");
  });


  // Accessibility Focus Trap
  addModal?.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    
    const focusable = addModal.querySelectorAll("input, select, button");
    if (focusable.length === 0) return;
    
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    
    if (e.shiftKey) {
      if (document.activeElement === first) {
        last.focus();
        e.preventDefault();
      }
    } else {
      if (document.activeElement === last) {
        first.focus();
        e.preventDefault();
      }
    }
  });

  // Bind Search, Filter, Sort Inputs
  searchForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    searchQuery = searchInput.value || "";
    currentPage = 1;
    renderRegistry();
  });

  searchInput?.addEventListener("input", () => {
    searchQuery = searchInput.value || "";
    currentPage = 1;
    renderRegistry();
  });

  sortSelect?.addEventListener("change", () => {
    activeSort = sortSelect.value;
    renderRegistry();
  });

  sortDirSelect?.addEventListener("change", () => {
    activeSortDir = sortDirSelect.value;
    renderRegistry();
  });

  const sortPendingHeader = document.getElementById("sort-pending");
  sortPendingHeader?.addEventListener("click", () => {
    if (activeSort === "pending_installments") {
      activeSortDir = activeSortDir === "asc" ? "desc" : "asc";
    } else {
      activeSort = "pending_installments";
      activeSortDir = "desc";
    }
    if (sortSelect) sortSelect.value = "pending_installments";
    if (sortDirSelect) sortDirSelect.value = activeSortDir;
    renderRegistry();
  });

  // Filter Buttons binding
  document.querySelectorAll(".sakra-filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sakra-filter-btn").forEach(b => {
        b.className = "sakra-filter-btn px-3 py-1.5 rounded border text-[9px] uppercase tracking-wider border-border-default hover:bg-slate-50 text-text-secondary cursor-pointer bg-white";
      });
      btn.className = "sakra-filter-btn px-3 py-1.5 rounded border text-[9px] uppercase tracking-wider bg-blue-50 text-blue-600 border-blue-200 cursor-pointer";
      
      activeFilter = btn.getAttribute("data-filter");
      currentPage = 1;
      renderRegistry();
    });
  });

  retryLoadBtn?.addEventListener("click", () => {
    loadCustomers();
  });

  prevBtn?.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      renderRegistry();
    }
  });

  nextBtn?.addEventListener("click", () => {
    const filtered = getFilteredAndSorted();
    const totalPages = Math.ceil(filtered.length / pageSize);
    if (currentPage < totalPages) {
      currentPage++;
      renderRegistry();
    }
  });

  addForm?.addEventListener("submit", handleAddCustomerSubmit);

  // Initial load
  await loadCustomers();
  customersContent?.classList.remove("hidden");
}

async function loadCustomers() {
  tableContainer.classList.add("hidden");
  emptyState.classList.add("hidden");
  errorState.classList.add("hidden");
  tableSpinner.classList.remove("hidden");

  try {
    // Fetch all records for full client-side telemetry operations
    const res = await api.get("/customers", { limit: 100 });
    const payload = res.data || res;
    customerRegistry = payload.customers || [];

    tableSpinner.classList.add("hidden");
    renderRegistry();
  } catch (err) {
    console.error("Failed to load customer registry:", err);
    tableSpinner.classList.add("hidden");
    errorState.classList.remove("hidden");
  }
}


function getFilteredAndSorted() {
  let filtered = [...customerRegistry];

  // 1. Search Query Match
  if (searchQuery.trim()) {
    const term = searchQuery.toLowerCase().trim();
    filtered = filtered.filter(c => {
      const nameMatch = c.name?.toLowerCase().includes(term);
      const phoneMatch = c.phone_number?.toLowerCase().includes(term);
      const idMatch = c.id?.toString() === term;
      const aadharMatch = c.aadhar_masked?.includes(term);
      
      const activeLoan = c.loans?.find(l => l.status === "ACTIVE") || c.loans?.[0];
      const loanIdMatch = activeLoan ? activeLoan.id?.toString() === term : false;
      
      return nameMatch || phoneMatch || idMatch || aadharMatch || loanIdMatch;
    });
  }

  // 2. Status/Risk Filters Match
  if (activeFilter !== "all") {
    filtered = filtered.filter(c => {
      const activeLoan = c.loans?.find(l => l.status === "ACTIVE") || c.loans?.[0];
      const remaining = activeLoan ? parseFloat(activeLoan.balance_summary.remaining_balance) : 0;
      const score = c.aggregate?.credit_score || 700;
      const createdDate = new Date(c.created_at);
      const today = new Date();

      if (activeFilter === "active") {
        return activeLoan && activeLoan.status === "ACTIVE" && remaining > 0;
      }
      if (activeFilter === "completed") {
        return activeLoan && (activeLoan.status === "PAID" || remaining <= 0);
      }
      if (activeFilter === "overdue") {
        if (!activeLoan) return false;
        return activeLoan.status === "OVERDUE" || (new Date(activeLoan.loan_end_date) < today && remaining > 0);
      }
      if (activeFilter === "high_risk") {
        return score < 650;
      }
      if (activeFilter === "low_risk") {
        return score >= 750;
      }
      return true;
    });
  }

  // 3. Sorting
  filtered.sort((a, b) => {
    const activeLoanA = a.loans?.find(l => l.status === "ACTIVE") || a.loans?.[0];
    const activeLoanB = b.loans?.find(l => l.status === "ACTIVE") || b.loans?.[0];

    let valA, valB;

    if (activeSort === "name") {
      valA = a.name || "";
      valB = b.name || "";
    } else if (activeSort === "pending_installments") {
      valA = a.pending_installments_count || 0;
      valB = b.pending_installments_count || 0;
    } else if (activeSort === "principal") {
      valA = activeLoanA ? parseFloat(activeLoanA.principal_amount) : 0;
      valB = activeLoanB ? parseFloat(activeLoanB.principal_amount) : 0;
    } else if (activeSort === "remaining") {
      valA = activeLoanA ? parseFloat(activeLoanA.balance_summary.remaining_balance) : 0;
      valB = activeLoanB ? parseFloat(activeLoanB.balance_summary.remaining_balance) : 0;
    } else if (activeSort === "credit_score") {
      valA = a.aggregate?.credit_score || 700;
      valB = b.aggregate?.credit_score || 700;
    } else if (activeSort === "due_date") {
      valA = activeLoanA ? new Date(activeLoanA.loan_end_date) : new Date(0);
      valB = activeLoanB ? new Date(activeLoanB.loan_end_date) : new Date(0);
    } else if (activeSort === "status") {
      valA = activeLoanA ? activeLoanA.status : "";
      valB = activeLoanB ? activeLoanB.status : "";
    } else { // created_at
      valA = new Date(a.created_at);
      valB = new Date(b.created_at);
    }

    if (typeof valA === "string") {
      return activeSortDir === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return activeSortDir === "asc" ? valA - valB : valB - valA;
  });

  return filtered;
}

function renderRegistry() {
  const filtered = getFilteredAndSorted();
  const totalFiltered = filtered.length;

  document.getElementById("total-accounts-text").innerText = `${totalFiltered} account${totalFiltered !== 1 ? "s" : ""} active in view`;

  if (totalFiltered === 0) {
    tableContainer.classList.add("hidden");
    emptyState.classList.remove("hidden");
    return;
  }

  emptyState.classList.add("hidden");
  errorState.classList.add("hidden");
  tableContainer.classList.remove("hidden");

  // Pagination bounds
  const totalPages = Math.ceil(totalFiltered / pageSize) || 1;
  if (currentPage > totalPages) currentPage = totalPages;

  pageInfo.innerText = `Page ${currentPage} of ${totalPages} (${totalFiltered} total)`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;

  const paginated = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const today = new Date();

  // 1. Render Desktop Rows
  tableBody.innerHTML = paginated.map(c => {
    const activeLoan = c.loans?.find(l => l.status === "ACTIVE") || c.loans?.[0];
    const principal = activeLoan ? parseFloat(activeLoan.principal_amount) : 0;
    const remaining = activeLoan ? parseFloat(activeLoan.balance_summary.remaining_balance) : 0;
    const paid = activeLoan ? parseFloat(activeLoan.balance_summary.total_paid) : 0;
    const creditScore = c.aggregate?.credit_score || 700;
    const interestRate = activeLoan ? activeLoan.interest_rate : 0;
    const formula = activeLoan ? activeLoan.interest_formula : "—";
    
    // Risk calculations
    let riskLevel = "MEDIUM RISK";
    let riskClass = "text-amber-600";
    if (creditScore >= 750) {
      riskLevel = "LOW RISK";
      riskClass = "text-emerald-600";
    } else if (creditScore < 650) {
      riskLevel = "HIGH RISK";
      riskClass = "text-rose-600";
    }

    // Days Overdue or Remaining
    let timelineText = "No active timeline";
    let daysOverdue = 0;
    if (activeLoan) {
      const dueDate = new Date(activeLoan.loan_end_date);
      const diffTime = dueDate.getTime() - today.getTime();
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      if (remaining <= 0) {
        timelineText = "Timeline completed";
      } else if (diffDays < 0) {
        daysOverdue = Math.abs(diffDays);
        timelineText = `${daysOverdue} days overdue`;
      } else {
        timelineText = `${diffDays} days remaining`;
      }
    }

    // Dynamic Status Badge
    let statusText = "ACTIVE";
    let badgeClass = "bg-blue-50 text-blue-700 border-blue-100";
    if (activeLoan) {
      statusText = activeLoan.status;
      if (statusText === "PAID" || remaining <= 0) {
        statusText = "PAID";
        badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-100";
      } else if (statusText === "OVERDUE" || daysOverdue > 0) {
        statusText = "OVERDUE";
        badgeClass = "bg-rose-50 text-rose-700 border-rose-100";
      } else if (statusText === "PENDING") {
        badgeClass = "bg-amber-50 text-amber-700 border-amber-100";
      }
    }

    const pendingCount = c.pending_installments_count || 0;
    let pendingBadgeClass = "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";
    let pendingDot = "🟢";
    let pendingLabel = "Perfect 0";
    if (pendingCount >= 15) {
      pendingBadgeClass = "bg-rose-500/20 text-rose-600 border-rose-500/30 animate-pulse";
      pendingDot = "🔴";
      pendingLabel = `${pendingCount}`;
    } else if (pendingCount >= 8) {
      pendingBadgeClass = "bg-rose-500/10 text-rose-600 border-rose-500/25";
      pendingDot = "🔴";
      pendingLabel = `${pendingCount}`;
    } else if (pendingCount >= 4) {
      pendingBadgeClass = "bg-orange-500/10 text-orange-600 border-orange-500/25";
      pendingDot = "🟠";
      pendingLabel = `${pendingCount}`;
    } else if (pendingCount >= 1) {
      pendingBadgeClass = "bg-amber-500/10 text-amber-600 border-amber-500/25";
      pendingDot = "🟡";
      pendingLabel = `${pendingCount}`;
    }

    const pendingBadge = `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold border cursor-pointer select-none transition-all hover:scale-105 active:scale-95 pending-trigger-badge ${pendingBadgeClass}" 
            data-id="${c.id}">
        <span>${pendingDot}</span>
        <span class="${pendingCount >= 15 ? 'animate-pulse font-extrabold text-rose-600' : ''}">${pendingLabel}</span>
      </span>
    `;

    const statusBadge = `
      <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-bold border ${badgeClass}">
        ${statusText}
      </span>
    `;

    return `
      <tr class="cursor-pointer hover:bg-slate-50" data-id="${c.id}">
        <td class="text-center">
          <img src="/api/v1/customers/${c.id}/photo" class="w-8 h-8 rounded-full border border-border-default/45 shadow-sm object-cover mx-auto select-none" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' fill=\'%23cbd5e1\' style=\'background:%23f1f5f9;\'><path fill-rule=\'evenodd\' d=\'M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A9.75 9.75 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z\' clip-rule=\'evenodd\' /></svg>'" />
        </td>
        <td class="font-mono text-xs text-text-muted">#${c.id}</td>
        <td class="font-semibold text-text-primary text-xs">${c.name}</td>
        <td class="font-mono text-xs text-text-secondary">${c.phone_number}</td>
        <td class="text-right font-mono text-xs font-semibold text-text-secondary">${formatCurrency(principal)}</td>
        <td class="text-right font-mono text-xs font-bold text-text-primary">${formatCurrency(remaining)}</td>
        <td class="text-center">
          ${pendingBadge}
        </td>
        <td class="text-center">
          ${statusBadge}
        </td>
      </tr>
    `;
  }).join("");


  // 2. Render Mobile Cards
  mobileCardsContainer.innerHTML = paginated.map(c => {
    const activeLoan = c.loans?.find(l => l.status === "ACTIVE") || c.loans?.[0];
    const principal = activeLoan ? parseFloat(activeLoan.principal_amount) : 0;
    const remaining = activeLoan ? parseFloat(activeLoan.balance_summary.remaining_balance) : 0;
    const paid = activeLoan ? parseFloat(activeLoan.balance_summary.total_paid) : 0;
    const creditScore = c.aggregate?.credit_score || 700;
    
    // Risk Level
    let riskLevel = "MEDIUM RISK";
    let riskClass = "text-amber-600";
    if (creditScore >= 750) {
      riskLevel = "LOW RISK";
      riskClass = "text-emerald-600";
    } else if (creditScore < 650) {
      riskLevel = "HIGH RISK";
      riskClass = "text-rose-600";
    }

    // Status
    let statusText = "ACTIVE";
    let badgeClass = "bg-blue-50 text-blue-700 border-blue-100";
    if (activeLoan) {
      statusText = activeLoan.status;
      if (statusText === "PAID" || remaining <= 0) {
        statusText = "PAID";
        badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-100";
      } else if (statusText === "OVERDUE") {
        badgeClass = "bg-rose-50 text-rose-700 border-rose-100";
      }
    }

    const statusBadge = `
      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold border ${badgeClass}">
        ${statusText}
      </span>
    `;

    const pendingCount = c.pending_installments_count || 0;
    let pendingBadgeClass = "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";
    let pendingDot = "🟢";
    let pendingLabel = "Perfect 0";
    if (pendingCount >= 15) {
      pendingBadgeClass = "bg-rose-500/20 text-rose-600 border-rose-500/30 animate-pulse";
      pendingDot = "🔴";
      pendingLabel = `${pendingCount}`;
    } else if (pendingCount >= 8) {
      pendingBadgeClass = "bg-rose-500/10 text-rose-600 border-rose-500/25";
      pendingDot = "🔴";
      pendingLabel = `${pendingCount}`;
    } else if (pendingCount >= 4) {
      pendingBadgeClass = "bg-orange-500/10 text-orange-600 border-orange-500/25";
      pendingDot = "🟠";
      pendingLabel = `${pendingCount}`;
    } else if (pendingCount >= 1) {
      pendingBadgeClass = "bg-amber-500/10 text-amber-600 border-amber-500/25";
      pendingDot = "🟡";
      pendingLabel = `${pendingCount}`;
    }

    const pendingBadge = `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold border cursor-pointer select-none pending-trigger-badge ${pendingBadgeClass}" 
            data-id="${c.id}">
        <span>${pendingDot}</span>
        <span class="${pendingCount >= 15 ? 'animate-pulse font-extrabold text-rose-600' : ''}">${pendingLabel}</span>
      </span>
    `;

    return `
      <div class="glass-card p-5 border border-border-default/45 flex flex-col gap-4 cursor-pointer hover:border-primary/50 transition-all duration-150" data-id="${c.id}">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-[9px] font-mono text-text-muted">UID: #${c.id}</span>
            <h4 class="text-sm font-bold text-text-primary mt-0.5">${c.name}</h4>
            <p class="text-[10px] text-text-muted font-mono mt-0.5">${c.phone_number}</p>
          </div>
          <div>
            ${statusBadge}
          </div>
        </div>
        <div class="h-px bg-border-default/30"></div>
        <div class="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span class="text-[9px] uppercase tracking-wider text-text-muted block">Remaining</span>
            <span class="font-bold text-text-primary font-mono">${formatCurrency(remaining)}</span>
          </div>
          <div>
            <span class="text-[9px] uppercase tracking-wider text-text-muted block">Principal</span>
            <span class="font-semibold text-text-secondary font-mono">${formatCurrency(principal)}</span>
          </div>
          <div>
            <span class="text-[9px] uppercase tracking-wider text-text-muted block">Risk / Score</span>
            <span class="font-bold font-mono ${riskClass}">${creditScore} (${riskLevel})</span>
          </div>
          <div>
            <span class="text-[9px] uppercase tracking-wider text-text-muted block">Disbursed Due</span>
            <span class="font-mono text-text-secondary">${activeLoan ? activeLoan.loan_end_date : "—"}</span>
          </div>
          <div>
            <span class="text-[9px] uppercase tracking-wider text-text-muted block">Pending Installments</span>
            <span class="inline-block mt-0.5">${pendingBadge}</span>
          </div>
        </div>
      </div>
    `;
  }).join("");

  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Row selection setup (Desktop rows)
  tableBody.querySelectorAll("tr").forEach(row => {
    row.addEventListener("click", (e) => {
      if (e.target.closest(".pending-trigger-badge")) {
        e.stopPropagation();
        return;
      }
      const id = row.getAttribute("data-id");
      tableBody.querySelectorAll("tr").forEach(r => r.classList.remove("bg-blue-50/40", "border-l-4", "border-primary"));
      row.classList.add("bg-blue-50/40", "border-l-4", "border-primary");
      selectCustomer(id);
    });
  });

  // Card selection setup (Mobile cards)
  mobileCardsContainer.querySelectorAll(".glass-card").forEach(card => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".pending-trigger-badge")) {
        e.stopPropagation();
        return;
      }
      const id = card.getAttribute("data-id");
      mobileCardsContainer.querySelectorAll(".glass-card").forEach(c => c.classList.remove("border-primary"));
      card.classList.add("border-primary");
      selectCustomer(id);
    });
  });

  // Pending badges interactivity (Hover / Tap)
  initPendingBadgeListeners();
}

function initPendingBadgeListeners() {
  const badges = document.querySelectorAll(".pending-trigger-badge");
  
  // Make sure we have a tooltip element for hover preview
  let tooltip = document.getElementById("pending-installments-tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.id = "pending-installments-tooltip";
    tooltip.className = "sakra-dark-tooltip transition-all duration-150 transform scale-95 opacity-0 fixed hidden z-50 pointer-events-none";
    document.body.appendChild(tooltip);
  }

  // Make sure we have the inspection panel elements
  let overlay = document.getElementById("pending-inspection-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "pending-inspection-overlay";
    document.body.appendChild(overlay);
  }

  function openInspectionPanel(customer) {
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

  // Bind trigger elements
  badges.forEach(badge => {
    badge.addEventListener("click", (e) => {
      e.stopPropagation();
      // Hide preview tooltip immediately
      tooltip.classList.add("hidden");
      tooltip.classList.remove("scale-100", "opacity-100");

      const id = badge.getAttribute("data-id");
      const customer = customerRegistry.find(c => c.id == id);
      if (!customer) return;

      openInspectionPanel(customer);
    });

    badge.addEventListener("mouseenter", (e) => {
      if (window.innerWidth < 768) return; // Skip on mobile
      const id = badge.getAttribute("data-id");
      const customer = customerRegistry.find(c => c.id == id);
      if (!customer) return;

      tooltip.innerHTML = `
        <div class="text-[10px] font-bold text-white tracking-wider flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-900 border border-blue-500/25 shadow-lg rounded-lg">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-blue-400 animate-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
          <span>Click to inspect details</span>
        </div>
      `;

      tooltip.classList.remove("hidden");
      const rect = badge.getBoundingClientRect();
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

    badge.addEventListener("mouseleave", () => {
      tooltip.classList.remove("scale-100", "opacity-100");
      tooltip.classList.add("scale-95", "opacity-0");
      setTimeout(() => {
        if (tooltip.classList.contains("opacity-0")) {
          tooltip.classList.add("hidden");
        }
      }, 150);
    });
  });
}

async function handleAddCustomerSubmit(e) {
  e.preventDefault();
  modalError.classList.add("hidden");
  modalError.innerText = "";

  const formData = new FormData(addForm);
  const data = Object.fromEntries(formData.entries());

  // Validate Aadhaar is 12 digits
  const aadhar = data.aadhar_number;
  if (!aadhar || aadhar.length !== 12 || isNaN(aadhar)) {
    modalError.innerText = "Aadhaar Identity must be exactly 12 numeric digits.";
    modalError.classList.remove("hidden");
    return;
  }

  // Validate required fields
  if (!data.name?.trim()) {
    modalError.innerText = "Customer name is required.";
    modalError.classList.remove("hidden");
    return;
  }
  if (!data.phone_number?.trim()) {
    modalError.innerText = "Phone number is required.";
    modalError.classList.remove("hidden");
    return;
  }
  if (!data.principal_amount || parseFloat(data.principal_amount) <= 0) {
    modalError.innerText = "Principal amount must be a positive number.";
    modalError.classList.remove("hidden");
    return;
  }

  // Validate interest rate
  let rawRate = data.interest_rate;
  if (typeof rawRate === "string") {
    rawRate = rawRate.trim();
  }
  if (!rawRate) {
    modalError.innerText = "Interest rate is required.";
    modalError.classList.remove("hidden");
    return;
  }
  const rateRegex = /^\d+(\.\d{1,4})?$/;
  if (!rateRegex.test(rawRate)) {
    modalError.innerText = "Interest rate must be a positive number with up to 4 decimal places (e.g. 10, 10.5, 12.75, 0.50).";
    modalError.classList.remove("hidden");
    return;
  }
  const parsedRate = parseFloat(rawRate);
  if (parsedRate < 0 || parsedRate > 100) {
    modalError.innerText = "Interest rate must be between 0% and 100%.";
    modalError.classList.remove("hidden");
    return;
  }

  // Validate file uploads selection
  const photoInput = document.getElementById("profile-photo-input");
  const aadhaarInput = document.getElementById("aadhaar-file-input");
  const promissoryFileInput = document.getElementById("promissory-file-input");

  if (!aadhaarInput?.files || !aadhaarInput.files[0]) {
    modalError.innerText = "Aadhaar Card document file upload is required.";
    modalError.classList.remove("hidden");
    return;
  }
  if (!promissoryFileInput?.files || !promissoryFileInput.files[0]) {
    modalError.innerText = "Promissory Note document file upload is required.";
    modalError.classList.remove("hidden");
    return;
  }

  modalSubmitBtn.disabled = true;
  modalSubmitBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin mr-1"></i> Onboarding Account...`;
  if (window.lucide) window.lucide.createIcons();

  // Setup Progress Bar
  const progressContainer = document.getElementById("upload-progress-container");
  const progressText = document.getElementById("upload-progress-text");
  const progressBar = document.getElementById("upload-progress-bar");

  if (progressContainer) {
    progressContainer.classList.remove("hidden");
    progressText.innerText = "15%";
    progressBar.style.width = "15%";
  }

  let progress = 15;
  const progressInterval = setInterval(() => {
    if (progress < 90) {
      progress += Math.floor(Math.random() * 8) + 4;
      if (progress > 90) progress = 90;
      if (progressText) progressText.innerText = `${progress}%`;
      if (progressBar) progressBar.style.width = `${progress}%`;
    }
  }, 120);

  try {
    // STEP 1: Upload Documents and Create Customer Profile
    const submitFormData = new FormData();
    submitFormData.append("name", data.name.trim());
    submitFormData.append("phone_number", data.phone_number.trim());
    submitFormData.append("aadhar_number", data.aadhar_number.trim());
    submitFormData.append("address", data.address?.trim() || "");
    submitFormData.append("promissory_note", data.promissory_note?.trim() || "");
    submitFormData.append("date_of_birth", data.date_of_birth || "");
    submitFormData.append("gender", data.gender || "");
    submitFormData.append("occupation", data.occupation?.trim() || "");
    submitFormData.append("remarks", data.remarks?.trim() || "");

    if (photoInput?.files && photoInput.files[0]) {
      submitFormData.append("profile_photo", photoInput.files[0]);
    }
    submitFormData.append("aadhaar", aadhaarInput.files[0]);
    submitFormData.append("promissory_file", promissoryFileInput.files[0]);

    let customerRes;
    try {
      customerRes = await customFetch("/customers/", {
        method: "POST",
        body: submitFormData
      });
    } catch (custErr) {
      const msg = custErr?.message || custErr?.detail || custErr?.errors?.detail || "Customer onboarding failed. Please verify files and details.";
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }

    clearInterval(progressInterval);
    if (progressText) progressText.innerText = "100%";
    if (progressBar) progressBar.style.width = "100%";

    const customerId = customerRes?.data?.id || customerRes?.id;
    if (!customerId) {
      throw new Error("Customer profile created but no ID returned.");
    }

    // STEP 2: Create Associated Loan Record
    const loanPayload = {
      customer_id: customerId,
      principal_amount: parseFloat(data.principal_amount),
      interest_rate: String(data.interest_rate).trim(),
      loan_start_date: data.loan_start_date || new Date().toISOString().split("T")[0],
      interest_formula: data.interest_formula || "FLAT",
      duration_days: parseInt(data.duration_days) || 100
    };

    try {
      await api.post("/loans/", loanPayload);
    } catch (loanErr) {
      console.warn("Customer onboarding complete but loan registry failed:", loanErr);
    }

    // Reset dropzones
    const photoPreviewImg = document.getElementById("photo-preview-img");
    if (photoPreviewImg) {
      photoPreviewImg.src = "";
      photoPreviewImg.classList.add("hidden");
    }
    document.getElementById("photo-placeholder")?.classList.remove("hidden");
    document.getElementById("remove-photo-btn")?.classList.add("hidden");

    document.getElementById("aadhaar-file-details")?.classList.add("hidden");
    document.getElementById("aadhaar-upload-prompt")?.classList.remove("hidden");

    document.getElementById("promissory-file-details")?.classList.add("hidden");
    document.getElementById("promissory-upload-prompt")?.classList.remove("hidden");

    if (progressContainer) progressContainer.classList.add("hidden");

    closeModal();
    addForm.reset();
    await loadCustomers();
  } catch (err) {
    clearInterval(progressInterval);
    if (progressContainer) progressContainer.classList.add("hidden");
    const msg = err?.message || err?.detail || "Registration failed. Please verify all inputs and try again.";
    modalError.innerText = typeof msg === "string" ? msg : JSON.stringify(msg);
    modalError.classList.remove("hidden");
  } finally {
    modalSubmitBtn.disabled = false;
    modalSubmitBtn.innerHTML = `<span>Complete Onboarding</span>`;
    if (window.lucide) window.lucide.createIcons();
  }
}


// Start
setTimeout(init, 100);

window.addEventListener("language-changed", () => {
  renderRegistry();
});

let selectedCustomerId = null;
let customerAnalyticsCache = {};

let activeCharts = {
  repaymentTimeline: null,
  paymentPattern: null,
  outstandingBalance: null,
  paymentConsistency: null,
  cumulativeCollection: null
};

function destroyExistingCharts() {
  Object.keys(activeCharts).forEach(key => {
    if (activeCharts[key]) {
      activeCharts[key].destroy();
      activeCharts[key] = null;
    }
  });
}

async function selectCustomer(id) {
  if (selectedCustomerId === id) return;
  selectedCustomerId = id;

  const emptyState = document.getElementById("analytics-empty-state");
  const activePanel = document.getElementById("analytics-active-panel");

  // Fade out old charts if they are visible
  if (!activePanel.classList.contains("hidden")) {
    activePanel.classList.remove("opacity-100");
    activePanel.classList.add("opacity-0");
    await new Promise(resolve => setTimeout(resolve, 150));
  }

  // Check cache first
  let data;
  if (customerAnalyticsCache[id]) {
    data = customerAnalyticsCache[id];
  } else {
    try {
      const res = await api.get(`/customers/${id}`);
      data = res.data || res;
      customerAnalyticsCache[id] = data;
    } catch (err) {
      console.error("Failed to fetch customer details for analytics:", err);
      alert("Error loading customer analytics data.");
      return;
    }
  }

  // Populate Profile Header
  const { customer, loans = [], aggregate_payments = [], credit_score, summary = {} } = data;
  const activeLoan = loans.find(l => l.status === "ACTIVE" || l.status === "OVERDUE") || loans[0];

  const profileBtn = document.getElementById("view-profile-btn");
  if (profileBtn) {
    profileBtn.href = `/customer-profile.html?id=${customer.id}`;
  }

  document.getElementById("detail-profile-photo").src = `/api/v1/customers/${customer.id}/photo?t=${new Date().getTime()}`;
  document.getElementById("detail-profile-name").innerText = customer.name;
  document.getElementById("detail-profile-phone").innerText = customer.phone_number;
  document.getElementById("detail-profile-aadhar").innerText = customer.aadhar_masked || "—";
  document.getElementById("detail-profile-id").innerText = `#${customer.id}`;
  document.getElementById("detail-profile-dob-gender").innerText = `${customer.date_of_birth || "—"} / ${customer.gender || "—"}`;
  document.getElementById("detail-profile-occupation").innerText = customer.occupation || "—";
  document.getElementById("detail-profile-address").innerText = customer.address || "—";

  // KPIs
  const principal = activeLoan ? parseFloat(activeLoan.principal_amount) : 0;
  const interest = activeLoan ? parseFloat(activeLoan.interest_amount) : 0;
  const repayable = activeLoan ? parseFloat(activeLoan.total_repayable_amount) : 0;
  const paid = activeLoan ? parseFloat(activeLoan.balance_summary.total_paid) : 0;
  const remaining = activeLoan ? parseFloat(activeLoan.balance_summary.remaining_balance) : 0;
  const completion = repayable > 0 ? (paid / repayable) * 100 : 0;
  const cScore = credit_score || 700;

  // Risk Rating
  let riskLevel = "MEDIUM";
  if (cScore >= 750) riskLevel = "LOW RISK";
  else if (cScore < 650) riskLevel = "HIGH RISK";

  // Timeline & Payments Info
  let daysRemaining = 0;
  let nextPaymentText = "—";
  if (activeLoan) {
    const today = new Date();
    const dueDate = new Date(activeLoan.loan_end_date);
    const diffTime = dueDate.getTime() - today.getTime();
    daysRemaining = Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
    
    // Find next unpaid schedule
    const sortedSchedules = [...(activeLoan.schedules || [])].sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
    const nextUnpaid = sortedSchedules.find(s => s.status !== "PAID");
    if (nextUnpaid) {
      nextPaymentText = `${nextUnpaid.due_date} (₹${parseFloat(nextUnpaid.installment_amount).toLocaleString("en-IN")})`;
    }
  }

  const sortedPayments = [...(aggregate_payments || [])].sort((a, b) => new Date(a.payment_date) - new Date(b.payment_date));
  const lastPayment = sortedPayments[sortedPayments.length - 1];
  const lastPaymentText = lastPayment ? `${lastPayment.payment_date} (₹${parseFloat(lastPayment.amount_paid).toLocaleString("en-IN")})` : "—";

  document.getElementById("kpi-principal").innerText = formatCurrency(principal);
  document.getElementById("kpi-interest").innerText = formatCurrency(interest);
  document.getElementById("kpi-repayable").innerText = formatCurrency(repayable);
  document.getElementById("kpi-collected").innerText = formatCurrency(paid);

  // Equivalent Coverage KPI (Total Collected ÷ Daily Installment)
  const equivCov = summary.equivalent_coverage;
  const totalDailyInst = summary.total_daily_installment || 0;
  const kpiCovEl = document.getElementById("kpi-equivalent-coverage");
  if (kpiCovEl) {
    kpiCovEl.innerText = (equivCov != null && equivCov > 0) ? `${Number(equivCov).toFixed(2)} Days` : "—";
  }
  const kpiTTCollected = document.getElementById("kpi-tooltip-collected");
  const kpiTTDaily = document.getElementById("kpi-tooltip-daily");
  const kpiTTResult = document.getElementById("kpi-tooltip-result");
  if (kpiTTCollected) kpiTTCollected.innerText = formatCurrency(paid);
  if (kpiTTDaily) kpiTTDaily.innerText = formatCurrency(totalDailyInst);
  if (kpiTTResult) kpiTTResult.innerText = (equivCov != null && equivCov > 0) ? `${Number(equivCov).toFixed(2)} Days` : "—";

  document.getElementById("kpi-remaining").innerText = formatCurrency(remaining);
  document.getElementById("kpi-completion").innerText = `${completion.toFixed(2)}%`;
  document.getElementById("kpi-credit-score").innerText = cScore;
  document.getElementById("kpi-risk-score").innerText = riskLevel;
  document.getElementById("kpi-expected-emi").innerText = activeLoan ? formatCurrency(parseFloat(activeLoan.daily_installment)) : "₹0.00";
  document.getElementById("kpi-days-remaining").innerText = activeLoan ? `${daysRemaining} days` : "—";
  document.getElementById("kpi-last-payment").innerText = lastPaymentText;
  document.getElementById("kpi-next-payment").innerText = nextPaymentText;

  // Render Charts
  destroyExistingCharts();
  renderRepaymentTimeline(sortedPayments, repayable);
  renderPaymentPattern(loans, sortedPayments);
  renderOutstandingTrend(loans, sortedPayments, repayable);
  renderPaymentConsistency(activeLoan, sortedPayments);
  renderCumulativeCollection(sortedPayments);

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
      let progressText = "";
      let progressClass = "";
      if (behindDays > 0) {
        progressText = `🔴 ${behindDays.toFixed(2)} Days Behind`;
        progressClass = "text-rose-400 font-bold";
      } else if (behindDays < 0) {
        progressText = `🟢 ${Math.abs(behindDays).toFixed(2)} Days Ahead`;
        progressClass = "text-emerald-400 font-bold";
      } else {
        progressText = `🟢 On Schedule`;
        progressClass = "text-emerald-400 font-bold";
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
              <span class="text-xs font-bold text-white uppercase tracking-widest">Collection Intelligence — Loan #${loan.id}</span>
            </div>
            <span class="px-2.5 py-0.5 text-[9px] font-bold rounded border uppercase bg-blue-950/50 text-blue-400 border-blue-500/20 font-mono">
              Daily Installment: ${formatCurrency(dailyInstallment)}
            </span>
          </div>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Loan Duration</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number text-white" data-animate="duration" data-val="${loan.duration_days}">0 Days</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Days Passed</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number text-white" data-animate="days-passed" data-val="${daysPassed}">0 Days</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Expected Collection Till Today</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number text-white" data-animate="expected" data-val="${expectedCollection}">₹0.00</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Actual Collection</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number text-success" data-animate="actual" data-val="${totalPaid}">₹0.00</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm col-span-1">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Equivalent Installments Covered</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number text-blue-400" data-animate="equivalent" data-val="${equivalentPaidDays}">0.00 Days</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm col-span-1">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Collection Progress</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number ${progressClass}">${progressText}</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Pending Collection Till Today</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number text-rose-400" data-animate="pending" data-val="${pendingToday}">₹0.00</p>
            </div>
            <div class="glass-card text-center py-4 bg-white/5 border border-white/10 rounded-lg shadow-sm">
              <p class="text-[9px] font-bold uppercase tracking-widest text-text-muted">Remaining Loan Balance</p>
              <p class="text-xl font-bold mt-2 font-mono text-financial-number text-rose-500" data-animate="balance" data-val="${remainingBalance}">₹0.00</p>
            </div>
          </div>
        </div>
      `;
    }).join("");
    
    setTimeout(animateKPIs, 50);
  } else {
    dashboardEl.classList.add("hidden");
    dashboardEl.innerHTML = "";
  }

  // Update Icons inside summary
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Animate Entrance
  emptyState.classList.add("hidden");
  activePanel.classList.remove("hidden");
  
  // Force reflow and add opacity class for transitions
  activePanel.offsetHeight;
  activePanel.classList.remove("opacity-0");
  activePanel.classList.add("opacity-100");

  // Scroll smoothly to analytics section
  document.getElementById("customer-analytics-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderRepaymentTimeline(payments, totalRepayable) {
  const ctx = document.getElementById("chart-repayment-timeline").getContext("2d");
  
  let running = totalRepayable;
  const data = payments.map(p => {
    running -= parseFloat(p.amount_paid);
    return {
      x: p.payment_date,
      y: parseFloat(p.amount_paid),
      mode: p.payment_mode || "CASH",
      running: running
    };
  });

  activeCharts.repaymentTimeline = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map(d => d.x),
      datasets: [{
        label: "Repayments",
        data: data,
        borderColor: "rgb(59, 130, 246)",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        fill: false
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
              const raw = context.raw;
              return [
                `Amount: ₹${raw.y.toLocaleString("en-IN")}`,
                `Mode: ${raw.mode}`,
                `Running Balance: ₹${Math.max(0, raw.running).toLocaleString("en-IN")}`
              ];
            }
          }
        }
      },
      scales: {
        x: { grid: { color: "rgba(0, 0, 0, 0.05)" }, ticks: { font: { size: 9 } } },
        y: { grid: { color: "rgba(0, 0, 0, 0.05)" }, ticks: { font: { size: 9 } } }
      }
    }
  });
}

function renderPaymentPattern(loans, payments) {
  const ctx = document.getElementById("chart-payment-pattern").getContext("2d");
  
  const firstLoanStart = loans.length > 0 ? new Date(loans[0].loan_start_date) : new Date();

  const data = payments.map(p => {
    const payDate = new Date(p.payment_date);
    const dayIndex = Math.max(0, Math.round((payDate - firstLoanStart) / (1000 * 60 * 60 * 24)));
    
    let color = "rgb(16, 185, 129)"; // Green
    if (p.payment_status === "PARTIAL") {
      color = "rgb(245, 158, 11)"; // Yellow
    } else if (p.payment_status === "LATE") {
      color = "rgb(239, 68, 68)"; // Red
    }

    return {
      x: dayIndex,
      y: parseFloat(p.amount_paid),
      id: p.id,
      mode: p.payment_mode,
      color: color,
      date: p.payment_date
    };
  });

  activeCharts.paymentPattern = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [{
        data: data,
        pointBackgroundColor: data.map(d => d.color),
        pointBorderColor: data.map(d => d.color),
        pointRadius: 6,
        pointHoverRadius: 8
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
              const raw = context.raw;
              return [
                `Payment ID: #${raw.id}`,
                `Date: ${raw.date} (Day ${raw.x})`,
                `Amount: ₹${raw.y.toLocaleString("en-IN")}`,
                `Mode: ${raw.mode}`
              ];
            }
          }
        }
      },
      scales: {
        x: { 
          title: { display: true, text: "Days offset since loan start", font: { size: 9 } },
          grid: { color: "rgba(0, 0, 0, 0.05)" }, 
          ticks: { font: { size: 9 } } 
        },
        y: { 
          title: { display: true, text: "Amount Paid (₹)", font: { size: 9 } },
          grid: { color: "rgba(0, 0, 0, 0.05)" }, 
          ticks: { font: { size: 9 } } 
        }
      }
    }
  });
}

function renderOutstandingTrend(loans, payments, totalRepayable) {
  const ctx = document.getElementById("chart-outstanding-balance").getContext("2d");

  const trendData = [{ x: loans[0]?.loan_start_date || new Date().toISOString().split("T")[0], y: totalRepayable }];
  let currentBal = totalRepayable;
  payments.forEach(p => {
    currentBal = Math.max(0, currentBal - parseFloat(p.amount_paid));
    trendData.push({ x: p.payment_date, y: currentBal });
  });

  activeCharts.outstandingBalance = new Chart(ctx, {
    type: "line",
    data: {
      labels: trendData.map(d => d.x),
      datasets: [{
        label: "Outstanding Balance",
        data: trendData,
        borderColor: "rgb(6, 182, 212)",
        backgroundColor: "rgba(6, 182, 212, 0.1)",
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        fill: true
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
              return `Outstanding: ₹${context.raw.y.toLocaleString("en-IN")}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { color: "rgba(0, 0, 0, 0.05)" }, ticks: { font: { size: 9 } } },
        y: { grid: { color: "rgba(0, 0, 0, 0.05)" }, ticks: { font: { size: 9 } } }
      }
    }
  });
}

function renderPaymentConsistency(loan, payments) {
  const ctx = document.getElementById("chart-payment-consistency").getContext("2d");

  const expectedEmi = loan ? parseFloat(loan.daily_installment || 0) : 0;
  
  const data = payments.map(p => {
    const amt = parseFloat(p.amount_paid);
    let comparison = "On-time";
    if (amt > expectedEmi) comparison = "Extra payment";
    else if (amt < expectedEmi) comparison = "Missed/Partial payment";
    
    return {
      x: p.payment_date,
      y: amt,
      expected: expectedEmi,
      comparison: comparison
    };
  });

  activeCharts.paymentConsistency = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Actual Payments",
          data: data,
          pointBackgroundColor: "rgb(59, 130, 246)",
          pointBorderColor: "rgb(59, 130, 246)",
          pointRadius: 5,
          pointHoverRadius: 7
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(context) {
              const raw = context.raw;
              return [
                `Date: ${raw.x}`,
                `Paid: ₹${raw.y.toLocaleString("en-IN")}`,
                `Expected EMI: ₹${raw.expected.toLocaleString("en-IN")}`,
                `Status: ${raw.comparison}`
              ];
            }
          }
        }
      },
      scales: {
        x: { grid: { color: "rgba(0, 0, 0, 0.05)" }, ticks: { font: { size: 9 } } },
        y: { 
          grid: { color: "rgba(0, 0, 0, 0.05)" }, 
          ticks: { font: { size: 9 } }
        }
      }
    }
  });
}

function renderCumulativeCollection(payments) {
  const ctx = document.getElementById("chart-cumulative-collection").getContext("2d");

  const cumulativeData = [];
  let cumulativeSum = 0;
  payments.forEach(p => {
    cumulativeSum += parseFloat(p.amount_paid);
    cumulativeData.push({ x: p.payment_date, y: cumulativeSum });
  });

  activeCharts.cumulativeCollection = new Chart(ctx, {
    type: "line",
    data: {
      labels: cumulativeData.map(d => d.x),
      datasets: [{
        label: "Cumulative Collected",
        data: cumulativeData,
        borderColor: "rgb(37, 99, 235)",
        tension: 0.3,
        pointRadius: 4,
        pointHoverRadius: 6,
        fill: true,
        backgroundColor: function(context) {
          const chart = context.chart;
          const {ctx, chartArea} = chart;
          if (!chartArea) return null;
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, "rgba(59, 130, 246, 0.25)");
          gradient.addColorStop(1, "rgba(59, 130, 246, 0)");
          return gradient;
        }
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
              return `Cumulative Paid: ₹${context.raw.y.toLocaleString("en-IN")}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { color: "rgba(0, 0, 0, 0.05)" }, ticks: { font: { size: 9 } } },
        y: { grid: { color: "rgba(0, 0, 0, 0.05)" }, ticks: { font: { size: 9 } } }
      }
    }
  });
}

window.refreshPageData = async () => {
  await loadCustomers();
  if (selectedCustomerId) {
    const activeId = selectedCustomerId;
    selectedCustomerId = null;
    await selectCustomer(activeId);
  }
};

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

