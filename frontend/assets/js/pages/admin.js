import api, { customFetch } from "../api.js";
import { getCachedUser } from "../auth.js";

document.addEventListener("DOMContentLoaded", () => {
  const user = getCachedUser();
  if (!user || user.role !== "SUPER_ADMIN") {
    window.location.href = "/dashboard.html";
    return;
  }

  // Dashboard Stats Elements
  const statsMapping = {
    "stat-total-users": "total_users",
    "stat-online-users": "online_employees",
    "stat-offline-users": "offline_employees",
    "stat-active-sessions": "active_sessions",
    "stat-locked-accounts": "locked_accounts",
    "stat-failed-ins": "failed_logins", // fallback checking
    "stat-failed-logins": "failed_logins",
    "stat-pending-invitations": "pending_invitations",
    "stat-accepted-invitations": "accepted_invitations",
    "stat-expired-invitations": "expired_invitations",
    "stat-revoked-invitations": "revoked_invitations",
    "stat-today-logins": "today_logins",
    "stat-email-failures": "email_failures"
  };

  // Tables & Containers
  const employeesTableBody = document.getElementById("employees-table-body");
  const inviteTableBody = document.getElementById("invite-table-body");
  const sessionTableBody = document.getElementById("session-table-body");
  const mailLogsContainer = document.getElementById("mail-logs-container");

  // Tab state elements
  const tabEmployees = document.getElementById("tab-employees");
  const tabInvitations = document.getElementById("tab-invitations");
  const employeesTableContainer = document.getElementById("employees-table-container");
  const invitationsTableContainer = document.getElementById("invitations-table-container");

  // Search input
  const searchInput = document.getElementById("search-directory");

  // Modals
  const inviteModal = document.getElementById("invite-modal");
  const btnOpenInvite = document.getElementById("btn-open-invite");
  const btnCloseInvite = document.getElementById("btn-close-invite");
  const btnCancelInvite = document.getElementById("btn-cancel-invite");
  const inviteForm = document.getElementById("invite-form");
  const inviteErrorMsg = document.getElementById("invite-error-msg");

  const editModal = document.getElementById("edit-employee-modal");
  const btnCloseEdit = document.getElementById("btn-close-edit");
  const btnCancelEdit = document.getElementById("btn-cancel-edit");
  const editForm = document.getElementById("edit-employee-form");
  const editErrorMsg = document.getElementById("edit-error-msg");

  const copyModal = document.getElementById("copy-links-modal");
  const btnCloseCopyModal = document.getElementById("btn-close-copy-modal");
  const btnCloseCopyDone = document.getElementById("btn-close-copy-done");
  const copyInviteLinkInput = document.getElementById("copy-invite-link");
  const copyTempPasswordInput = document.getElementById("copy-temp-password");

  const btnCopyLink = document.getElementById("btn-copy-link");
  const btnCopyPassword = document.getElementById("btn-copy-password");

  // Active Tab Toggle
  let activeTab = "employees"; // employees or invitations

  tabEmployees.addEventListener("click", () => {
    activeTab = "employees";
    tabEmployees.className = "px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 border-blue-500 text-blue-400 bg-transparent cursor-pointer outline-none";
    tabInvitations.className = "px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 border-transparent text-text-muted bg-transparent cursor-pointer outline-none hover:text-text-primary";
    employeesTableContainer.classList.remove("hidden");
    invitationsTableContainer.classList.add("hidden");
    loadEmployees();
  });

  tabInvitations.addEventListener("click", () => {
    activeTab = "invitations";
    tabInvitations.className = "px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 border-blue-500 text-blue-400 bg-transparent cursor-pointer outline-none";
    tabEmployees.className = "px-4 py-2 text-xs font-bold uppercase tracking-wider border-b-2 border-transparent text-text-muted bg-transparent cursor-pointer outline-none hover:text-text-primary";
    invitationsTableContainer.classList.remove("hidden");
    employeesTableContainer.classList.add("hidden");
    loadInvitations();
  });

  // Search filter trigger
  let searchTimeout;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      if (activeTab === "employees") {
        loadEmployees();
      }
    }, 300);
  });

  // Open invite modal
  btnOpenInvite.addEventListener("click", () => {
    inviteErrorMsg.classList.add("hidden");
    inviteForm.reset();
    inviteModal.classList.remove("hidden");
  });

  const hideInviteModal = () => inviteModal.classList.add("hidden");
  btnCloseInvite.addEventListener("click", hideInviteModal);
  btnCancelInvite.addEventListener("click", hideInviteModal);

  // Open copy link helper modal
  const showCopyModal = (link, password) => {
    copyInviteLinkInput.value = link;
    copyTempPasswordInput.value = password;
    copyModal.classList.remove("hidden");
  };

  const hideCopyModal = () => copyModal.classList.add("hidden");
  btnCloseCopyModal.addEventListener("click", hideCopyModal);
  btnCloseCopyDone.addEventListener("click", hideCopyModal);

  btnCopyLink.addEventListener("click", () => {
    copyInviteLinkInput.select();
    navigator.clipboard.writeText(copyInviteLinkInput.value);
    btnCopyLink.innerText = "Copied!";
    setTimeout(() => btnCopyLink.innerText = "Copy", 1500);
  });

  btnCopyPassword.addEventListener("click", () => {
    copyTempPasswordInput.select();
    navigator.clipboard.writeText(copyTempPasswordInput.value);
    btnCopyPassword.innerText = "Copied!";
    setTimeout(() => btnCopyPassword.innerText = "Copy", 1500);
  });

  // Submit invite employee
  inviteForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    inviteErrorMsg.classList.add("hidden");

    const payload = {
      name: document.getElementById("invite-name").value.trim(),
      email: document.getElementById("invite-email").value.trim(),
      employee_code: document.getElementById("invite-code").value.trim(),
      branch: document.getElementById("invite-branch").value.trim(),
      department: document.getElementById("invite-dept").value.trim(),
      designation: document.getElementById("invite-designation").value.trim(),
      phone_number: document.getElementById("invite-phone").value.trim(),
      role: document.getElementById("invite-role").value,
      expiration_hours: parseFloat(document.getElementById("invite-expiry").value)
    };

    try {
      const submitBtn = document.getElementById("btn-submit-invite");
      submitBtn.disabled = true;
      submitBtn.innerText = "Sending Link...";

      const res = await customFetch("/admin/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      submitBtn.disabled = false;
      submitBtn.innerText = "Send Invitation Link";

      if (!res.success && res.message && res.message.includes("delivery failed")) {
         // Email failed, show code links
         hideInviteModal();
         showCopyModal(`${window.location.origin}/activate.html?token=n_a`, "Delivery failure - check mail queue status");
         loadDashboard();
         return;
      }

      if (!res.success) {
        throw new Error(res.message || "Failed to invite employee.");
      }

      hideInviteModal();
      // Generate mock parameters for copy preview link
      const mockToken = res.data?.invite_id || "placeholder_token";
      showCopyModal(`${window.location.origin}/activate.html?token=${mockToken}`, "Password dispatched via secure email gateway.");
      loadDashboard();
    } catch (err) {
      const submitBtn = document.getElementById("btn-submit-invite");
      submitBtn.disabled = false;
      submitBtn.innerText = "Send Invitation Link";
      inviteErrorMsg.innerText = err.detail || err.message || "Failed to invite.";
      inviteErrorMsg.classList.remove("hidden");
    }
  });

  // Edit employee modal close
  const hideEditModal = () => editModal.classList.add("hidden");
  btnCloseEdit.addEventListener("click", hideEditModal);
  btnCancelEdit.addEventListener("click", hideEditModal);

  // Submit edit employee details
  editForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    editErrorMsg.classList.add("hidden");

    const empId = document.getElementById("edit-emp-id").value;
    const payload = {
      full_name: document.getElementById("edit-full-name").value.trim(),
      phone_number: document.getElementById("edit-phone-number").value.trim(),
      branch: document.getElementById("edit-branch").value.trim(),
      department: document.getElementById("edit-department").value.trim(),
      designation: document.getElementById("edit-designation").value.trim(),
      role: document.getElementById("edit-role").value,
      status: document.getElementById("edit-status").value
    };

    // Compare fields
    const init = window.initialEditData || {};
    const hasChanged =
      payload.full_name !== init.full_name ||
      payload.phone_number !== init.phone_number ||
      payload.branch !== init.branch ||
      payload.department !== init.department ||
      payload.designation !== init.designation ||
      payload.role !== init.role ||
      payload.status !== init.status;

    if (!hasChanged) {
      editErrorMsg.innerText = "No changes detected.";
      editErrorMsg.classList.remove("hidden");
      return;
    }

    try {
      const submitBtn = document.getElementById("btn-submit-edit");
      const originalText = submitBtn.innerText;
      submitBtn.disabled = true;
      submitBtn.innerText = "Saving Changes...";

      const res = await customFetch(`/employees/${empId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      submitBtn.disabled = false;
      submitBtn.innerText = originalText;

      if (!res.success) {
        throw new Error(res.message || "Failed to update employee.");
      }

      hideEditModal();
      alert("Employee details updated successfully.");
      loadDashboard();
    } catch (err) {
      const submitBtn = document.getElementById("btn-submit-edit");
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerText = "Save Changes";
      }
      editErrorMsg.innerText = err.detail || err.message || "Failed to update.";
      editErrorMsg.classList.remove("hidden");
    }
  });

  // Terminate all sessions bulk action
  document.getElementById("btn-terminate-all").addEventListener("click", async () => {
    const confirmMsg = window.t ? window.t("admin_confirm_terminate_all") : "Are you sure you want to terminate all active sessions (except your own)? This will force all other employees to re-authenticate.";
    if (confirm(confirmMsg)) {
      const res = await customFetch("/admin/sessions/terminate-all", { method: "POST" });
      if (res.success) {
        alert(res.message);
        loadDashboard();
      }
    }
  });

  // Fetch stats and trigger updates
  async function loadDashboard() {
    try {
      // 1. Stats Metrics
      const statsRes = await customFetch("/admin/security-metrics");
      if (statsRes.success) {
        Object.keys(statsMapping).forEach(elId => {
          const el = document.getElementById(elId);
          if (el) {
            el.innerText = statsRes.data[statsMapping[elId]] ?? "0";
          }
        });
      }

      // 2. Load active tab table data
      if (activeTab === "employees") {
        loadEmployees();
      } else {
        loadInvitations();
      }

      // 3. Load active device sessions list
      loadSessions();

      // 4. Load Outbox mail audit list
      loadMailLogs();

    } catch (err) {
      console.error("Dashboard metrics failed to load:", err);
    }
  }

  // Load active employee directory list
  async function loadEmployees() {
    try {
      const querySearch = searchInput.value.trim();
      const url = querySearch ? `/admin/employees?search=${encodeURIComponent(querySearch)}` : "/admin/employees";
      const res = await customFetch(url);
      
      if (res.success) {
        if (res.data.length === 0) {
          employeesTableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-text-muted font-bold uppercase tracking-wider text-[9px]">No employees found match requirements</td></tr>`;
          return;
        }

        employeesTableBody.innerHTML = res.data.map(e => {
          const statusClass = e.status === "active" ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/20" : e.status === "INVITED" ? "bg-blue-950/40 text-blue-400 border-blue-500/20" : "bg-rose-950/40 text-rose-400 border-rose-500/20";
          return `
            <tr class="hover:bg-white/5 transition-all">
              <td class="py-4 px-6">
                <div class="font-bold text-text-primary">${e.full_name || e.username}</div>
                <div class="text-[10px] text-text-muted">${e.email}</div>
              </td>
              <td class="py-4 px-6">
                <div class="text-text-secondary">${e.employee_code || "—"}</div>
                <div class="text-[10px] text-text-muted">${e.branch || "—"}</div>
              </td>
              <td class="py-4 px-6 text-text-secondary">${e.department || "—"} <span class="text-white/5">/</span> ${e.designation || "—"}</td>
              <td class="py-4 px-6"><span class="px-2 py-0.5 rounded border border-white/5 bg-slate-900 text-text-muted font-bold text-[9px] uppercase tracking-wider">${e.role}</span></td>
              <td class="py-4 px-6"><span class="px-2 py-0.5 rounded border ${statusClass} font-bold text-[9px] uppercase tracking-wider">${e.status}</span></td>
              <td class="py-4 px-6 text-right space-x-2">
                <button class="btn-edit-emp px-2 py-1 bg-slate-900 hover:bg-slate-800 border border-white/5 rounded font-bold uppercase tracking-widest text-[8px] cursor-pointer" 
                  data-id="${e.id}"
                  data-fullname="${e.full_name || ''}"
                  data-phone="${e.phone_number || ''}"
                  data-branch="${e.branch || ''}"
                  data-dept="${e.department || ''}"
                  data-desg="${e.designation || ''}"
                  data-role="${e.role}"
                  data-status="${e.status}">
                  Edit
                </button>
                ${e.role !== "SUPER_ADMIN" ? `
                  <button class="btn-delete-emp px-2 py-1 bg-rose-950/30 text-rose-400 border border-rose-500/20 rounded font-bold uppercase tracking-widest text-[8px] hover:bg-rose-500/10 transition cursor-pointer" data-id="${e.id}">
                    Delete
                  </button>
                ` : ""}
              </td>
            </tr>
          `;
        }).join("");

        // Attach listeners for Edit buttons
        document.querySelectorAll(".btn-edit-emp").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            const empId = e.currentTarget.getAttribute("data-id");
            e.currentTarget.disabled = true;
            const originalText = e.currentTarget.innerText;
            e.currentTarget.innerText = "Loading...";

            try {
              const res = await customFetch(`/employees/${empId}`);
              e.currentTarget.disabled = false;
              e.currentTarget.innerText = originalText;

              if (res.success && res.data) {
                const emp = res.data;
                document.getElementById("edit-emp-id").value = emp.id;
                document.getElementById("edit-full-name").value = emp.full_name || "";
                document.getElementById("edit-phone-number").value = emp.phone_number || "";
                document.getElementById("edit-branch").value = emp.branch || "";
                document.getElementById("edit-department").value = emp.department || "";
                document.getElementById("edit-designation").value = emp.designation || "";
                document.getElementById("edit-role").value = emp.role;
                document.getElementById("edit-status").value = emp.status;

                // Cache initial state
                window.initialEditData = {
                  full_name: emp.full_name || "",
                  phone_number: emp.phone_number || "",
                  branch: emp.branch || "",
                  department: emp.department || "",
                  designation: emp.designation || "",
                  role: emp.role,
                  status: emp.status
                };

                editErrorMsg.classList.add("hidden");
                editModal.classList.remove("hidden");
              } else {
                alert(res.message || "Failed to load latest profile details.");
              }
            } catch (err) {
              e.currentTarget.disabled = false;
              e.currentTarget.innerText = originalText;
              alert(err.detail || err.message || "Failed to query profile details.");
            }
          });
        });

        // Attach listeners for Delete buttons
        document.querySelectorAll(".btn-delete-emp").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            const empId = e.currentTarget.getAttribute("data-id");
            const confirmMsg = window.t ? window.t("profile_confirm_delete") : "Are you sure you want to soft-delete this employee account? Access session keys will be revoked immediately.";
            if (confirm(confirmMsg)) {
              const res = await customFetch(`/admin/employees/${empId}`, { method: "DELETE" });
              if (res.success) {
                loadDashboard();
              }
            }
          });
        });
      }
    } catch (err) {
      console.error("Failed to load employees:", err);
    }
  }

  // Load pending/sent invitations list
  async function loadInvitations() {
    try {
      const res = await customFetch("/admin/invitations");
      if (res.success) {
        if (res.data.length === 0) {
          inviteTableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-text-muted font-bold uppercase tracking-wider text-[9px]">No invitations found</td></tr>`;
          return;
        }

        inviteTableBody.innerHTML = res.data.map(i => {
          const dateStr = window.formatDateTime ? window.formatDateTime(i.created_at) : new Date(i.created_at).toLocaleString();
          const statusClass = i.status === "PENDING" ? "bg-blue-950/40 text-blue-400 border-blue-500/20" : i.status === "USED" ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/20" : i.status === "EMAIL_FAILED" ? "bg-rose-950/40 text-rose-400 border-rose-500/20" : "bg-slate-800 text-text-muted border-slate-700";
          return `
            <tr class="hover:bg-white/5 transition-all">
              <td class="py-4 px-6">
                <div class="font-bold text-text-primary">${i.name}</div>
                <div class="text-[10px] text-text-muted">${dateStr}</div>
              </td>
              <td class="py-4 px-6">
                <div class="text-text-secondary">${i.email}</div>
                <div class="text-[10px] text-text-muted">Code: ${i.employee_code}</div>
              </td>
              <td class="py-4 px-6 text-text-secondary">${i.department} <span class="text-white/5">/</span> ${i.branch}</td>
              <td class="py-4 px-6"><span class="px-2 py-0.5 rounded border border-white/5 bg-slate-900 text-text-muted font-bold text-[9px] uppercase tracking-wider">${i.role}</span></td>
              <td class="py-4 px-6"><span class="px-2 py-0.5 rounded border ${statusClass} font-bold text-[9px] uppercase tracking-wider">${i.status}</span></td>
              <td class="py-4 px-6 text-right space-x-1">
                ${i.status === "PENDING" || i.status === "EMAIL_FAILED" ? `
                  <button class="btn-resend-invite px-2 py-1 bg-blue-950/20 text-blue-400 border border-blue-500/10 rounded font-bold uppercase tracking-widest text-[8px] hover:bg-blue-500/10 transition cursor-pointer" data-id="${i.id}">
                    Resend
                  </button>
                  <button class="btn-copy-raw-link px-2 py-1 bg-slate-900 border border-white/5 text-text-secondary rounded font-bold uppercase tracking-widest text-[8px] hover:text-white cursor-pointer" data-token="${i.id}">
                    Copy Link
                  </button>
                  <button class="btn-revoke-invite px-2 py-1 bg-rose-950/30 text-rose-400 border border-rose-500/20 rounded font-bold uppercase tracking-widest text-[8px] hover:bg-rose-500/10 transition cursor-pointer" data-id="${i.id}">
                    Revoke
                  </button>
                ` : ""}
                <button class="btn-delete-invite px-2 py-1 bg-slate-900 border border-white/5 text-text-muted rounded font-bold uppercase tracking-widest text-[8px] hover:text-rose-400 cursor-pointer" data-id="${i.id}">
                  Delete
                </button>
              </td>
            </tr>
          `;
        }).join("");

        // Attach actions
        document.querySelectorAll(".btn-resend-invite").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            const inviteId = e.currentTarget.getAttribute("data-id");
            e.currentTarget.disabled = true;
            e.currentTarget.innerText = "Retrying...";
            const res = await customFetch(`/admin/invitations/${inviteId}/resend`, { method: "POST" });
            e.currentTarget.disabled = false;
            e.currentTarget.innerText = "Resend";

            if (res.success) {
              alert("Invitation email successfully resent.");
              loadDashboard();
            } else {
              alert(res.message || "Failed to resend invitation.");
              loadDashboard();
            }
          });
        });

        document.querySelectorAll(".btn-copy-raw-link").forEach(btn => {
          btn.addEventListener("click", (e) => {
            const token = e.currentTarget.getAttribute("data-token");
            const link = `${window.location.origin}/activate.html?token=${token}`;
            navigator.clipboard.writeText(link);
            e.currentTarget.innerText = "Copied!";
            setTimeout(() => e.currentTarget.innerText = "Copy Link", 1500);
          });
        });

        document.querySelectorAll(".btn-revoke-invite").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            const inviteId = e.currentTarget.getAttribute("data-id");
            const confirmMsg = window.t ? window.t("admin_confirm_terminate") : "Revoke this invitation? The candidate will not be able to activate using their link.";
            if (confirm(confirmMsg)) {
              const res = await customFetch(`/admin/invitations/${inviteId}/revoke`, { method: "POST" });
              if (res.success) loadDashboard();
            }
          });
        });

        document.querySelectorAll(".btn-delete-invite").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            const inviteId = e.currentTarget.getAttribute("data-id");
            const confirmMsg = window.t ? window.t("profile_confirm_delete") : "Delete this invitation record completely?";
            if (confirm(confirmMsg)) {
              const res = await customFetch(`/admin/invitations/${inviteId}`, { method: "DELETE" });
              if (res.success) loadDashboard();
            }
          });
        });
      }
    } catch (err) {
      console.error("Failed to load invitations:", err);
    }
  }

  // Load active browser/device sessions list
  async function loadSessions() {
    try {
      const res = await customFetch("/admin/sessions");
      if (res.success) {
        if (res.data.length === 0) {
          sessionTableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-text-muted font-bold uppercase tracking-wider text-[9px]">No active device sessions</td></tr>`;
          return;
        }

        sessionTableBody.innerHTML = res.data.map(s => {
          const activeStr = window.formatDateTime ? window.formatDateTime(s.last_active) : new Date(s.last_active).toLocaleString();
          return `
            <tr class="hover:bg-white/5 transition-all">
              <td class="py-4 px-6">
                <div class="font-bold text-text-primary">${s.username}</div>
                <div class="text-[10px] text-text-muted">${s.email}</div>
              </td>
              <td class="py-4 px-6 text-text-secondary">${s.os} <span class="text-white/5">/</span> ${s.browser}</td>
              <td class="py-4 px-6 font-mono text-text-muted text-[10px]">${s.ip_address} <span class="text-slate-600">(${s.country || 'IN'})</span></td>
              <td class="py-4 px-6 text-text-muted text-[10px]">${activeStr}</td>
              <td class="py-4 px-6 text-right">
                <button class="btn-kill-session px-3 py-1 bg-slate-900 text-text-muted hover:bg-rose-950/30 hover:text-rose-400 border border-white/5 rounded font-bold uppercase tracking-widest text-[8px] cursor-pointer" data-sid="${s.session_id}">
                  Kill
                </button>
              </td>
            </tr>
          `;
        }).join("");

        // Terminate click action
        document.querySelectorAll(".btn-kill-session").forEach(btn => {
          btn.addEventListener("click", async (e) => {
            const sid = e.currentTarget.getAttribute("data-sid");
            const confirmMsg = window.t ? window.t("admin_confirm_terminate") : "Terminate access permissions for this device? User will be logged out immediately.";
            if (confirm(confirmMsg)) {
              const res = await customFetch(`/admin/sessions/${sid}/revoke`, { method: "POST" });
              if (res.success) loadDashboard();
            }
          });
        });
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  }

  // Load outbound email history audit outbox
  async function loadMailLogs() {
    try {
      const res = await customFetch("/admin/mail-logs");
      if (res.success) {
        if (res.data.length === 0) {
          mailLogsContainer.innerHTML = `<p class="text-center text-text-muted font-bold uppercase tracking-wider text-[9px] py-10">Outbox queue is empty</p>`;
          return;
        }

        mailLogsContainer.innerHTML = res.data.map(m => {
          const timeStr = new Date(m.created_at).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" });
          const statusColor = m.status === "SENT" ? "text-emerald-400" : "text-rose-500";
          return `
            <div class="p-3 border border-white/5 rounded bg-slate-950/40 space-y-1 hover:shadow-enterprise-sm transition-all duration-150">
              <div class="flex justify-between items-center text-[9px]">
                <span class="font-bold text-text-muted">${m.template}</span>
                <span class="${statusColor} font-bold">${m.status}</span>
              </div>
              <div class="text-xs font-bold text-text-primary truncate">${m.recipient}</div>
              <div class="text-[10px] text-text-muted truncate">${m.subject}</div>
              <div class="flex justify-between items-center text-[9px] text-slate-600 mt-1">
                <span class="font-mono truncate max-w-[120px]">${m.provider_message_id || 'no-id'}</span>
                <span>${timeStr}</span>
              </div>
            </div>
          `;
        }).join("");
      }
    } catch (err) {
      console.error("Failed to load mail logs:", err);
    }
  }

  // Initialize page components
  window.refreshPageData = async () => {
    await loadDashboard();
  };

  let autoRefreshInterval = null;
  function setupAutoRefresh() {
    const toggle = document.getElementById("auto-refresh-toggle");
    if (!toggle) return;

    const startAutoRefresh = () => {
      if (autoRefreshInterval) clearInterval(autoRefreshInterval);
      autoRefreshInterval = setInterval(async () => {
        console.log("Auto-refreshing admin IAM control...");
        await loadDashboard();
      }, 30000); // 30 seconds
    };

    const stopAutoRefresh = () => {
      if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
      }
    };

    const enabled = localStorage.getItem("admin-auto-refresh") === "true";
    toggle.checked = enabled;
    if (enabled) startAutoRefresh();

    toggle.addEventListener("change", (e) => {
      localStorage.setItem("admin-auto-refresh", e.target.checked);
      if (e.target.checked) {
        startAutoRefresh();
        if (window.showToast) window.showToast("IAM auto-refresh enabled (30s interval)", "success");
      } else {
        stopAutoRefresh();
        if (window.showToast) window.showToast("IAM auto-refresh disabled", "info");
      }
    });
  }

  loadDashboard();
  setupAutoRefresh();

  window.addEventListener("language-changed", () => {
    loadDashboard();
  });
});
