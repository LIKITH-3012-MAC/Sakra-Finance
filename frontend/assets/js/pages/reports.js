import api from "../api.js";

let currentPage = 1;
const limit = 25;
let actionFilter = "";
let totalLogs = 0;

const content = document.getElementById("reports-content");
const filterForm = document.getElementById("filter-form");
const filterInput = document.getElementById("action-filter-input");
const tableSpinner = document.getElementById("reports-spinner");
const emptyState = document.getElementById("reports-empty");
const tableContainer = document.getElementById("reports-table-container");
const tableBody = document.getElementById("reports-table-body");
const pageInfoText = document.getElementById("page-info-text");
const prevBtn = document.getElementById("prev-page-btn");
const nextBtn = document.getElementById("next-page-btn");

const actionColors = {
  USER_LOGIN: "bg-blue-50 text-blue-700 border-blue-100",
  USER_INVITE: "bg-blue-50 text-blue-700 border-blue-100",
  USER_LOGOUT: "bg-slate-50 text-slate-700 border-slate-100",
  USER_STATUS_CHANGE: "bg-amber-50 text-amber-700 border-amber-100",
  CUSTOMER_EDIT: "bg-amber-50 text-amber-700 border-amber-100",
  PAYMENT_EDIT: "bg-amber-50 text-amber-700 border-amber-100",
  CUSTOMER_CREATE: "bg-emerald-50 text-emerald-700 border-emerald-100",
  PAYMENT_RECORD: "bg-emerald-50 text-emerald-700 border-emerald-100",
  CUSTOMER_DELETE: "bg-rose-50 text-rose-700 border-rose-100"
};

async function init() {
  filterForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    actionFilter = filterInput.value || "";
    currentPage = 1;
    loadAuditLogs();
  });

  prevBtn?.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      loadAuditLogs();
    }
  });

  nextBtn?.addEventListener("click", () => {
    const totalPages = Math.ceil(totalLogs / limit);
    if (currentPage < totalPages) {
      currentPage++;
      loadAuditLogs();
    }
  });

  await loadAuditLogs();
  content?.classList.remove("hidden");
}

async function loadAuditLogs() {
  tableContainer.classList.add("hidden");
  emptyState.classList.add("hidden");
  tableSpinner.classList.remove("hidden");

  try {
    const params = { page: currentPage, limit };
    if (actionFilter.trim()) {
      params.action_filter = actionFilter.trim();
    }

    const res = await api.get("/audit", params);
    const payload = res.data || res;
    const logs = payload.logs || [];
    totalLogs = payload.total || 0;

    tableSpinner.classList.add("hidden");

    if (logs.length === 0) {
      emptyState.classList.remove("hidden");
      return;
    }

    // Render table rows
    tableBody.innerHTML = logs.map(log => {
      const badgeClass = actionColors[log.action] || "bg-slate-50 text-slate-700 border-slate-100";
      
      let detailsHtml = '<span class="text-text-muted">—</span>';
      const hasOld = !!log.old_values;
      const hasNew = !!log.new_values;

      if (hasOld || hasNew) {
        detailsHtml = `
          <details class="cursor-pointer group select-none">
            <summary class="text-primary hover:underline font-bold">View Details</summary>
            <div class="mt-2 p-3 rounded bg-slate-50 text-[11px] font-mono whitespace-pre-wrap max-h-40 overflow-y-auto border border-border-default text-left select-text">
              ${hasOld ? `
                <div class="mb-2">
                  <span class="font-bold text-danger">Old state:</span>
                  <pre class="mt-1">${JSON.stringify(log.old_values, null, 2)}</pre>
                </div>
              ` : ""}
              ${hasNew ? `
                <div>
                  <span class="font-bold text-success">New state:</span>
                  <pre class="mt-1">${JSON.stringify(log.new_values, null, 2)}</pre>
                </div>
              ` : ""}
            </div>
          </details>
        `;
      }

      return `
        <tr>
          <td class="text-xs text-text-muted whitespace-nowrap font-mono">
            ${window.formatDateTime ? window.formatDateTime(log.created_at) : new Date(log.created_at).toLocaleString()}
          </td>
          <td class="font-semibold text-text-primary text-xs">${log.actor_username}</td>
          <td>
            <span class="inline-block px-2.5 py-0.5 text-[10px] font-bold rounded border uppercase ${badgeClass}">
              ${log.action}
            </span>
          </td>
          <td class="text-xs text-text-secondary font-semibold">
            ${log.table_name} #${log.record_id}
          </td>
          <td class="text-xs text-text-muted font-mono">${log.ip_address}</td>
          <td>${detailsHtml}</td>
        </tr>
      `;
    }).join("");

    if (window.lucide) {
      window.lucide.createIcons();
    }

    // Update pagination values
    const totalPages = Math.ceil(totalLogs / limit);
    pageInfoText.innerText = `Page ${currentPage} of ${totalPages || 1} (${totalLogs} records)`;
    
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages || totalPages === 0;

    tableContainer.classList.remove("hidden");

  } catch (err) {
    console.error("Failed to load audit logs:", err);
    tableSpinner.classList.add("hidden");
    emptyState.classList.remove("hidden");
  }
}

// Start
setTimeout(init, 100);

window.addEventListener("language-changed", () => {
  loadAuditLogs();
});
