import api from "../api.js";

let showAll = false;
let notifications = [];

const content = document.getElementById("notifications-content");
const unreadText = document.getElementById("unread-count-text");
const toggleFilterBtn = document.getElementById("toggle-filter-btn");
const markAllBtn = document.getElementById("mark-all-btn");
const listContainer = document.getElementById("notifications-list");
const emptyState = document.getElementById("notifications-empty");

async function init() {
  toggleFilterBtn?.addEventListener("click", () => {
    showAll = !showAll;
    toggleFilterBtn.innerText = showAll 
      ? (window.t ? window.t("notifications_unread_only") : "Show Unread Only") 
      : (window.t ? window.t("notifications_filter_all") : "Show All");
    loadNotifications();
  });

  markAllBtn?.addEventListener("click", handleMarkAllRead);

  await loadNotifications();
  content?.classList.remove("hidden");
}

async function loadNotifications() {
  try {
    const res = await api.get("/notifications", { unread_only: !showAll });
    const payload = res.data || res;
    notifications = payload.notifications || payload || [];

    const unreadCount = notifications.filter(n => !n.is_read).length;
    unreadText.innerText = unreadCount > 0 
      ? `${unreadCount} ${window.t ? window.t("notifications_unread_count") : "unread alerts pending"}`
      : (window.t ? window.t("notifications_all_caught_up") : "All caught up.");

    // Show/Hide Mark All Read btn
    if (unreadCount > 0) {
      markAllBtn?.classList.remove("hidden");
    } else {
      markAllBtn?.classList.add("hidden");
    }

    renderNotificationsList();

  } catch (err) {
    console.error("Failed to load notifications:", err);
  }
}

function renderNotificationsList() {
  if (notifications.length === 0) {
    emptyState.classList.remove("hidden");
    listContainer.innerHTML = "";
    return;
  }

  emptyState.classList.add("hidden");
  
  listContainer.innerHTML = notifications.map(n => {
    const isOverdue = n.notification_type === "OVERDUE_ALERT";
    const borderLeftColor = n.is_read ? "#e2e8f0" : (isOverdue ? "#dc2626" : "#2563eb");
    const bgClass = n.is_read ? "opacity-60 bg-white/60" : "bg-white";
    const borderLeftStyle = `border-left: 4px solid ${borderLeftColor};`;
    const title = isOverdue 
      ? (window.t ? window.t("admin_confirm_terminate") : "Overdue Alert") 
      : (window.t ? window.t("nav_notifications") : "System Notification");

    return `
      <div
        class="sakra-card-default flex items-start justify-between gap-4 transition-all duration-150 relative ${bgClass}"
        style="${borderLeftStyle}"
      >
        <div class="flex items-start gap-4">
          <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 border ${
            isOverdue 
              ? "bg-rose-50 text-danger border-rose-100" 
              : "bg-blue-50 text-primary border-blue-100"
          }">
            <i data-lucide="${isOverdue ? "shield-alert" : "bell"}" class="w-5 h-5"></i>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="font-bold text-xs uppercase tracking-wider text-text-primary">
                ${title}
              </span>
              ${!n.is_read ? `<span class="inline-block px-1.5 py-0.5 text-[8px] font-bold rounded uppercase bg-blue-50 text-blue-700 border border-blue-100">${window.t ? window.t("notifications_badge_new") : "New"}</span>` : ""}
            </div>
            <p class="text-sm text-text-secondary mt-1.5 font-semibold line-clamp-2 leading-relaxed">${n.message}</p>
            <p class="text-[10px] text-text-muted mt-2 font-mono">${window.formatDateTime ? window.formatDateTime(n.sent_at) : new Date(n.sent_at).toLocaleString()}</p>
          </div>
        </div>

        ${!n.is_read ? `
          <button
            data-id="${n.id}"
            class="dismiss-btn neu-button neu-button-secondary shrink-0 text-[10px] px-3.5 py-1.5 cursor-pointer font-sans"
          >
            ${window.t ? window.t("notifications_btn_dismiss") : "Dismiss"}
          </button>
        ` : ""}
      </div>
    `;
  }).join("");

  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Bind individual dismiss click listeners
  listContainer.querySelectorAll(".dismiss-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.getAttribute("data-id"));
      await handleDismissNotification(id);
    });
  });
}

async function handleDismissNotification(id) {
  try {
    await api.patch(`/notifications/${id}/read`);
    // Optimistic status update
    notifications = notifications.map(n => n.id === id ? { ...n, is_read: true } : n);
    
    // Recalculate unread count
    const unreadCount = notifications.filter(n => !n.is_read).length;
    unreadText.innerText = unreadCount > 0 
      ? `${unreadCount} ${window.t ? window.t("notifications_unread_count") : "unread alerts pending"}`
      : (window.t ? window.t("notifications_all_caught_up") : "All caught up.");
    if (unreadCount === 0) markAllBtn?.classList.add("hidden");

    renderNotificationsList();
  } catch (err) {
    console.error("Failed to dismiss notification:", err);
  }
}

async function handleMarkAllRead() {
  try {
    await api.post("/notifications/read-all");
    notifications = notifications.map(n => ({ ...n, is_read: true }));
    
    unreadText.innerText = window.t ? window.t("notifications_all_caught_up") : "All caught up.";
    markAllBtn?.classList.add("hidden");
    
    renderNotificationsList();
  } catch (err) {
    console.error("Failed to mark all as read:", err);
  }
}

// Start load
setTimeout(init, 100);

window.addEventListener("language-changed", () => {
  loadNotifications();
});
