import api from "../api.js";
import { getCachedUser } from "../auth.js";

// Setup Clock
function updateClock() {
  const dateEl = document.getElementById("dashboard-date");
  const timeEl = document.getElementById("dashboard-time");
  if (!dateEl || !timeEl) return;

  const now = new Date();
  
  if (window.formatDate) {
    dateEl.innerText = window.formatDate(now);
  } else {
    dateEl.innerText = now.toLocaleDateString("en-IN", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric"
    });
  }

  timeEl.innerText = now.toLocaleTimeString(window.currentLanguage === "te" ? "te-IN" : "en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
    timeZone: "Asia/Kolkata"
  }) + " IST";
}

setInterval(updateClock, 1000);
updateClock();

// Helper to format currency
const formatVal = (v) => {
  return window.formatCurrency ? window.formatCurrency(v) : new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  }).format(v || 0);
};

// Numeric counters rollup animation
function animateValue(elementId, start, end, duration, formatFn = null) {
  const obj = document.getElementById(elementId);
  if (!obj) return;
  
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const val = progress * (end - start) + start;
    obj.innerText = formatFn ? formatFn(val) : Math.floor(val);
    if (progress < 1) {
      window.requestAnimationFrame(step);
    }
  };
  window.requestAnimationFrame(step);
}

// Fetch Data
async function loadDashboard() {
  const user = getCachedUser();
  if (!user) return; // Wait for session check in main.js

  // Render SUPER_ADMIN exclusive links
  if (user.role === "SUPER_ADMIN") {
    document.getElementById("action-audit-trail")?.classList.remove("hidden");
  }

  try {
    const [analyticsRes, notifRes] = await Promise.allSettled([
      api.get("/analytics/dashboard"),
      api.get("/notifications", { unread_only: true })
    ]);

    let stats = null;
    let alerts = [];

    if (analyticsRes.status === "fulfilled") {
      stats = analyticsRes.value.data || analyticsRes.value;
    }
    
    if (notifRes.status === "fulfilled") {
      const payload = notifRes.value.data || notifRes.value;
      alerts = (payload.notifications || payload || []).slice(0, 5);
    }

    renderStats(stats);
    renderAlerts(alerts);

    // Show dashboard
    document.getElementById("dashboard-content")?.classList.remove("hidden");

  } catch (err) {
    console.error("Dashboard metrics load error:", err);
  }
}

function renderStats(stats) {
  if (!stats) return;

  const targetCustomers = stats.total_customers ?? 0;
  const targetPrincipal = parseFloat(stats.active_principal ?? 0);
  const targetCollected = parseFloat(stats.total_collected ?? 0);
  const targetOverdue = stats.overdue_count ?? 0;

  const disbursed = parseFloat(stats.disbursed_principal || 0);
  const targetRealization = disbursed > 0 ? Math.min(Math.round((targetCollected / disbursed) * 100), 100) : 0;

  // Run rollups
  animateValue("metric-customers", 0, targetCustomers, 700);
  animateValue("metric-principal", 0, targetPrincipal, 850, formatVal);
  animateValue("metric-collected", 0, targetCollected, 850, formatVal);
  animateValue("metric-realization", 0, targetRealization, 600, (v) => `${Math.floor(v)}%`);
  animateValue("metric-overdue", 0, targetOverdue, 700);

  // Populate dynamic slide-open hover details
  const customersHoverEl = document.getElementById("metric-customers-hover");
  if (customersHoverEl) {
    customersHoverEl.innerText = `${targetCustomers} ${window.t ? window.t("dashboard_registered_profiles") : "active registered profiles"}`;
  }

  const principalHoverEl = document.getElementById("metric-principal-hover");
  if (principalHoverEl) principalHoverEl.innerText = formatVal(targetPrincipal);

  const collectedHoverEl = document.getElementById("metric-collected-hover");
  if (collectedHoverEl) collectedHoverEl.innerText = formatVal(targetCollected);

  const realizationHoverEl = document.getElementById("metric-realization-hover");
  if (realizationHoverEl) {
    realizationHoverEl.innerText = `${window.t ? window.t("customers_col_principal") : "Principal"}: ${formatVal(disbursed)}`;
  }

  const overdueHoverEl = document.getElementById("metric-overdue-hover");
  if (overdueHoverEl) {
    overdueHoverEl.innerText = `${targetOverdue} ${window.t ? window.t("dashboard_overdue_desc") : "accounts require action"}`;
  }
}

function renderAlerts(alerts) {
  const container = document.getElementById("alerts-stream-list");
  if (!container) return;

  if (alerts.length === 0) {
    container.innerHTML = `
      <div class="glass-card text-center py-8 bg-white/60">
        <i data-lucide="check-circle-2" class="w-8 h-8 text-success mx-auto mb-2"></i>
        <p class="text-xs text-text-secondary font-bold" data-i18n="success">Portfolios healthy</p>
        <p class="text-[10px] text-text-muted mt-0.5" data-i18n="notifications_no_alerts">No critical overdue warnings active.</p>
      </div>
    `;
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  container.innerHTML = alerts.map(alert => {
    const isOverdue = alert.notification_type === "OVERDUE_ALERT";
    const title = isOverdue 
      ? (window.t ? window.t("admin_confirm_terminate") : "Overdue Alert") 
      : (window.t ? window.t("nav_notifications") : "System Notification");
    return `
      <a href="/notifications.html" class="glass-card p-4 group flex items-start gap-3 hover:border-border-focus bg-white/50 cursor-pointer block">
        <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border ${
          isOverdue 
            ? "bg-rose-50 text-danger border-rose-100" 
            : "bg-blue-50 text-primary border-blue-100"
        }">
          <i data-lucide="${isOverdue ? "shield-alert" : "bell"}" class="w-4 h-4"></i>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[10px] font-bold uppercase tracking-wider text-text-primary truncate">
            ${title}
          </p>
          <p class="text-xs text-text-secondary mt-1 font-semibold line-clamp-2 leading-relaxed">
            ${alert.message}
          </p>
        </div>
      </a>
    `;
  }).join("");

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// Initial load check
setTimeout(loadDashboard, 100);

// Redraw stats on language change
window.addEventListener("language-changed", () => {
  loadDashboard();
});
