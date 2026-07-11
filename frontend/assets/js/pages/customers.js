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
        </div>
      </div>
    `;
  }).join("");

  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Row navigation trigger click setup (Desktop rows)
  tableBody.querySelectorAll("tr").forEach(row => {
    row.addEventListener("click", () => {
      const id = row.getAttribute("data-id");
      window.location.href = `/customer-profile.html?id=${id}`;
    });
  });

  // Card navigation trigger click setup (Mobile cards)
  mobileCardsContainer.querySelectorAll(".glass-card").forEach(card => {
    card.addEventListener("click", () => {
      const id = card.getAttribute("data-id");
      window.location.href = `/customer-profile.html?id=${id}`;
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
