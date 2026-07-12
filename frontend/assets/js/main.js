import { checkSession, logout } from "./auth.js";
import { setTheme } from "./theme.js";
import { initI18n } from "./i18n.js";
import { registerServiceWorker, initInstallPrompt } from "./pwa.js";
import api from "./api.js";

// Initialize PWA
registerServiceWorker();
initInstallPrompt();

// Page role restrictions mapping
const PAGE_ROLES = {
  "reports.html": ["SUPER_ADMIN"],
  "admin.html": ["SUPER_ADMIN"],
  "payments.html": ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"],
  "customer-daily.html": ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"]
};

// Helper to get normalized page filename for clean URLs
function getPageFilename() {
  let path = window.location.pathname.split("/").pop();
  if (!path) {
    return "dashboard.html";
  }
  if (!path.includes(".")) {
    path = path + ".html";
  }
  return path;
}

// Check page permissions
function checkPagePermission(user) {
  const path = getPageFilename();
  if (PAGE_ROLES[path]) {
    if (!user || !PAGE_ROLES[path].includes(user.role)) {
      window.location.href = "/dashboard.html";
      return false;
    }
  }
  return true;
}

// Injects layouts and attaches listeners
async function initLayout(user) {
  // 1. Render Sidebar
  const sidebarContainer = document.getElementById("sidebar-container");
  if (sidebarContainer) {
    const activePath = getPageFilename();
    
    const links = [
      { name: "Dashboard", key: "nav_dashboard", file: "dashboard.html", icon: "layout-dashboard", roles: ["SUPER_ADMIN", "ADMIN", "FINANCE_MANAGER", "COLLECTION_OFFICER", "AUDITOR", "DATA_ENTRY", "VIEWER"] },
      { name: "Customers", key: "nav_customers", file: "customers.html", icon: "users", roles: ["SUPER_ADMIN", "ADMIN", "FINANCE_MANAGER", "COLLECTION_OFFICER", "DATA_ENTRY", "VIEWER"] },
      { name: "Daily Repayments", key: "nav_daily_repayments", file: "payments.html", icon: "check-square", roles: ["SUPER_ADMIN", "ADMIN", "FINANCE_MANAGER", "COLLECTION_OFFICER", "DATA_ENTRY"] },
      { name: "Notifications", key: "nav_notifications", file: "notifications.html", icon: "bell", roles: ["SUPER_ADMIN", "ADMIN", "FINANCE_MANAGER", "COLLECTION_OFFICER", "AUDITOR", "DATA_ENTRY", "VIEWER"] },
      { name: "Sakra AI Copilot", key: "nav_copilot", file: "copilot.html", icon: "cpu", roles: ["SUPER_ADMIN", "ADMIN", "FINANCE_MANAGER", "COLLECTION_OFFICER", "AUDITOR", "DATA_ENTRY", "VIEWER"] },
      { name: "Security Audit", key: "nav_security_audit", file: "reports.html", icon: "shield-alert", roles: ["SUPER_ADMIN", "ADMIN", "AUDITOR"] },
      { name: "Admin Control", key: "nav_admin_control", file: "admin.html", icon: "shield", roles: ["SUPER_ADMIN"] }
    ];

    const allowedLinks = links.filter(l => l.roles.includes(user.role));
    const navItemsHtml = allowedLinks.map(link => {
      const isActive = activePath === link.file;
      return `
        <a href="/${link.file}" class="flex items-center gap-3.5 px-4 py-3 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
          isActive 
            ? "bg-blue-900/15 text-blue-400 border border-blue-500/25 shadow-[0_0_15px_rgba(59,130,246,0.12)]" 
            : "text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent"
        }">
          <i data-lucide="${link.icon}" class="w-4 h-4 shrink-0 ${isActive ? "text-blue-400" : "text-slate-500"}"></i>
          <span data-i18n="${link.key}">${window.t(link.key)}</span>
        </a>
      `;
    }).join("");

    sidebarContainer.innerHTML = `
      <div class="hidden md:flex w-64 bg-slate-950/45 backdrop-blur-md text-slate-300 flex-col justify-between shrink-0 border-r border-white/5 relative z-20 h-screen select-none">
        <div class="flex flex-col">
          <!-- Portal Header -->
          <a href="/dashboard.html" class="p-6 border-b border-white/5 flex items-center justify-center select-none hover:opacity-90 active:scale-95 transition-all">
            <img src="/logo.png" alt="SAKRA FINANCE" class="h-10 w-auto object-contain" />
          </a>

          <!-- User Identity widget -->
          <div class="p-6 bg-slate-950/20 border-b border-white/5">
            <p class="text-[9px] text-slate-500 uppercase tracking-widest font-bold">${window.t ? window.t("secured_profile") : "Secured Profile"}</p>
            <p class="font-bold text-sm text-slate-200 mt-1 truncate">${user.username}</p>
            <span class="inline-block mt-2 px-2.5 py-0.5 text-[9px] uppercase tracking-wider font-bold rounded bg-blue-950/50 text-blue-400 border border-blue-500/20">
              ${user.role}
            </span>
          </div>

          <!-- Navigation items -->
          <nav class="p-4 flex flex-col gap-1.5">
            ${navItemsHtml}
          </nav>
        </div>

        <!-- Footer & Log out -->
        <div class="p-4 border-t border-white/5 flex flex-col gap-4">
          <button id="sidebar-logout" class="w-full flex items-center gap-3.5 px-4 py-3 rounded-lg text-xs font-semibold uppercase tracking-wider text-rose-400/80 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-all duration-150 cursor-pointer">
            <i data-lucide="log-out" class="w-4 h-4 shrink-0"></i>
            <span data-i18n="sign_out">${window.t ? window.t("sign_out") : "Sign Out"}</span>
          </button>
        </div>
      </div>
    `;

    // Mobile Sidebar Drawer (visible on < md)
    let mobileDrawerOverlay = document.getElementById("mobile-sidebar-overlay");
    let mobileDrawer = document.getElementById("mobile-sidebar-drawer");

    if (!mobileDrawerOverlay) {
      mobileDrawerOverlay = document.createElement("div");
      mobileDrawerOverlay.id = "mobile-sidebar-overlay";
      document.body.appendChild(mobileDrawerOverlay);
    }

    if (!mobileDrawer) {
      mobileDrawer = document.createElement("div");
      mobileDrawer.id = "mobile-sidebar-drawer";
      document.body.appendChild(mobileDrawer);
    }

    mobileDrawer.innerHTML = `
      <div class="flex flex-col h-full">
        <div class="flex flex-col">
          <a href="/dashboard.html" class="p-5 border-b border-white/5 flex items-center justify-center select-none">
            <img src="/logo.png" alt="SAKRA FINANCE" class="h-8 w-auto object-contain" />
          </a>
          <div class="p-4 bg-slate-950/20 border-b border-white/5">
            <p class="text-[9px] text-slate-500 uppercase tracking-widest font-bold">${window.t ? window.t("secured_profile") : "Secured Profile"}</p>
            <p class="font-bold text-sm text-slate-200 mt-1 truncate">${user.username}</p>
            <span class="inline-block mt-2 px-2.5 py-0.5 text-[9px] uppercase tracking-wider font-bold rounded bg-blue-950/50 text-blue-400 border border-blue-500/20">
              ${user.role}
            </span>
          </div>
          <nav class="p-3 flex flex-col gap-1">
            ${navItemsHtml}
          </nav>
        </div>
        <div class="mt-auto p-3 border-t border-white/5">
          <button id="mobile-drawer-logout" class="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-xs font-semibold uppercase tracking-wider text-rose-400/80 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-all cursor-pointer min-h-[44px]">
            <i data-lucide="log-out" class="w-4 h-4 shrink-0"></i>
            <span data-i18n="sign_out">${window.t ? window.t("sign_out") : "Sign Out"}</span>
          </button>
        </div>
      </div>
    `;

    // Close drawer on overlay click
    mobileDrawerOverlay.addEventListener("click", () => {
      mobileDrawer.classList.remove("active");
      mobileDrawerOverlay.classList.remove("active");
    });

    // Close drawer on nav link click
    mobileDrawer.querySelectorAll("a").forEach(link => {
      link.addEventListener("click", () => {
        mobileDrawer.classList.remove("active");
        mobileDrawerOverlay.classList.remove("active");
      });
    });

    document.getElementById("mobile-drawer-logout")?.addEventListener("click", logout);
    document.getElementById("sidebar-logout")?.addEventListener("click", logout);
  }

  // 2. Render Header
  const headerContainer = document.getElementById("header-container");
  if (headerContainer) {
    const currentLangText = window.currentLanguage === "te" ? "🇮🇳 TE" : "🇬🇧 EN";

    headerContainer.innerHTML = `
      <header class="h-14 md:h-16 bg-slate-950/30 backdrop-blur-md border-b border-white/5 px-3 md:px-8 flex items-center justify-between shrink-0 relative z-10 select-none shadow-[0_4px_12px_rgba(0,0,0,0.25)]">
        <div class="flex items-center gap-2 md:gap-3">
          <!-- Mobile Hamburger Menu -->
          <button id="mobile-hamburger-btn" class="md:hidden flex items-center justify-center w-10 h-10 rounded-lg bg-slate-900/50 hover:bg-slate-800/50 border border-white/5 text-slate-300 hover:text-white transition-all cursor-pointer" aria-label="Open menu">
            <i data-lucide="menu" class="w-5 h-5"></i>
          </button>
          <span class="text-[9px] md:text-[10px] font-bold uppercase tracking-wider bg-blue-950/50 text-blue-400 px-2.5 py-1 rounded border border-blue-500/25 flex items-center gap-1.5 select-none font-sans">
            <span class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-ping"></span>
            <span data-i18n="secure_session" class="hidden sm:inline">${window.t ? window.t("secure_session") : "SECURE SESSION"}</span>
            <span class="sm:hidden">LIVE</span>
          </span>
          <span class="hidden lg:inline-flex text-[9px] md:text-[10px] font-bold uppercase tracking-wider bg-slate-900/50 text-slate-400 px-2.5 py-1 rounded border border-white/5 select-none font-sans header-hide-mobile">
            <span data-i18n="verified_ip">${window.t ? window.t("verified_ip") : "VERIFIED IP"}</span>
          </span>
        </div>
        
        <div class="flex items-center gap-2 md:gap-4 text-xs font-semibold text-slate-400 font-sans">
          
          <!-- Custom Premium Language Selector -->
          <div class="relative inline-block text-left" id="lang-switcher-container">
            <button id="lang-switcher-btn" class="flex items-center gap-1.5 px-2 md:px-2.5 py-1.5 rounded bg-slate-900/50 hover:bg-slate-800/50 border border-white/5 text-[9px] uppercase font-bold tracking-wider text-slate-300 hover:text-slate-100 transition-colors select-none cursor-pointer min-w-[40px] min-h-[36px] justify-center">
              <i data-lucide="languages" class="w-3.5 h-3.5 text-slate-400"></i>
              <span id="current-lang-text" class="hidden sm:inline">${currentLangText}</span>
              <i data-lucide="chevron-down" class="w-3 h-3 text-slate-500 hidden sm:inline"></i>
            </button>
            <div id="lang-switcher-dropdown" class="absolute right-0 mt-2 w-32 bg-slate-950/95 border border-white/10 rounded-lg shadow-enterprise-md py-1 hidden z-50 flex flex-col backdrop-blur-md">
              <button data-lang="en" class="flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 text-slate-300 hover:text-white transition-colors cursor-pointer w-full text-[10px] font-bold uppercase tracking-wider min-h-[40px]">
                🇬🇧 English
              </button>
              <button data-lang="te" class="flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 text-slate-300 hover:text-white transition-colors cursor-pointer w-full text-[10px] font-bold uppercase tracking-wider min-h-[40px]">
                🇮🇳 తెలుగు
              </button>
            </div>
          </div>
          
          <span class="text-white/5 hidden md:inline">|</span>
          <!-- Premium Sync Refresh Button -->
          <button id="global-refresh-btn" class="flex items-center gap-1.5 px-2 md:px-2.5 py-1.5 rounded bg-slate-900/50 hover:bg-slate-800/50 border border-white/5 text-[9px] uppercase font-bold tracking-wider text-slate-300 hover:text-slate-100 transition-colors select-none cursor-pointer min-w-[36px] min-h-[36px] justify-center">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5 text-slate-400" id="global-refresh-icon"></i>
            <span data-i18n="btn_refresh" class="hidden md:inline">REFRESH</span>
          </button>
          
          <span class="text-white/5 hidden md:inline">|</span>
          <!-- Premium Notifications Bell Icon -->
          <div class="relative inline-block" id="header-notifications-bell-container">
            <button id="header-notifications-bell" class="relative flex items-center p-2 rounded bg-slate-900/50 hover:bg-slate-800/50 border border-white/5 text-slate-300 hover:text-slate-100 transition-all select-none cursor-pointer min-w-[36px] min-h-[36px] justify-center">
              <i data-lucide="bell" class="w-4 h-4"></i>
              <span id="notifications-badge" class="absolute -top-1.5 -right-1.5 bg-rose-500 text-white text-[8px] font-bold px-1 py-0.5 rounded-full scale-0 transition-transform shadow-[0_0_8px_rgba(239,68,68,0.5)]">0</span>
            </button>
          </div>
          
          <span class="text-white/5 hidden lg:inline">|</span>
          <div class="hidden lg:flex items-center gap-1.5 select-none text-[9px] font-bold text-emerald-400">
            <i data-lucide="shield-check" class="w-4 h-4 text-emerald-400"></i>
            <span class="uppercase tracking-widest" data-i18n="audit_active">${window.t ? window.t("audit_active") : "AUDIT ACTIVE"}</span>
          </div>
          <span class="text-white/5 hidden lg:inline">|</span>
          <div class="hidden lg:flex items-center gap-1.5 text-slate-200">
            <i data-lucide="user" class="w-3.5 h-3.5 text-slate-500"></i>
            <span class="truncate max-w-[80px] sm:max-w-none">${user.username}</span>
          </div>
          <span class="md:hidden text-white/5">|</span>
          <button id="header-logout" class="md:hidden text-rose-400 hover:text-rose-600 transition-colors p-1 rounded bg-transparent border-none cursor-pointer min-w-[36px] min-h-[36px] flex items-center justify-center">
            <i data-lucide="log-out" class="w-4 h-4"></i>
          </button>
        </div>
      </header>
    `;

    document.getElementById("header-logout")?.addEventListener("click", logout);

    // Language switcher toggle & execution
    const langBtn = document.getElementById("lang-switcher-btn");
    const langDropdown = document.getElementById("lang-switcher-dropdown");
    if (langBtn && langDropdown) {
      langBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        langDropdown.classList.toggle("hidden");
      });
      document.addEventListener("click", () => {
        langDropdown.classList.add("hidden");
      });
      langDropdown.querySelectorAll("[data-lang]").forEach(btn => {
        btn.addEventListener("click", async (e) => {
          const selectedLang = btn.getAttribute("data-lang");
          await window.setAppLanguage(selectedLang);
          const textEl = document.getElementById("current-lang-text");
          if (textEl) {
            textEl.textContent = selectedLang === "te" ? "🇮🇳 TE" : "🇬🇧 EN";
          }
        });
      });
    }

    // Global Refresh mechanism
    const refreshBtn = document.getElementById("global-refresh-btn");
    const refreshIcon = document.getElementById("global-refresh-icon");
    if (refreshBtn && refreshIcon) {
      refreshBtn.addEventListener("click", async () => {
        refreshBtn.disabled = true;
        refreshIcon.classList.add("animate-spin");
        const startTime = Date.now();
        try {
          if (window.refreshPageData) {
            await window.refreshPageData();
            window.showToast("Data synchronized with live database successfully.", "success");
          } else {
            // default fallback
            window.location.reload();
          }
        } catch (err) {
          console.error("Refresh synchronization failed:", err);
          window.showToast("Unable to synchronize data. Please check connection.", "error");
        } finally {
          const elapsed = Date.now() - startTime;
          if (elapsed < 400) {
            await new Promise(r => setTimeout(r, 400 - elapsed));
          }
          refreshBtn.disabled = false;
          refreshIcon.classList.remove("animate-spin");
          if (window.lucide) window.lucide.createIcons();
        }
      });
    }

  // 4. Render Mobile Bottom Navigation (for screens < 768px)
    let mobileNav = document.getElementById("mobile-bottom-nav");
    if (!mobileNav) {
      mobileNav = document.createElement("div");
      mobileNav.id = "mobile-bottom-nav";
      mobileNav.className = "md:hidden fixed bottom-0 left-0 right-0 h-16 bg-slate-950/90 backdrop-blur-md border-t border-white/5 z-50 flex justify-around items-center px-2 shadow-deep select-none";
      document.body.appendChild(mobileNav);
    }
    const activePath = getPageFilename();
    const links = [
      { name: "Dashboard", key: "nav_dashboard", file: "dashboard.html", icon: "layout-dashboard", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
      { name: "Customers", key: "nav_customers", file: "customers.html", icon: "users", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
      { name: "Daily Repayments", key: "nav_daily_repayments", file: "payments.html", icon: "check-square", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"] },
      { name: "Notifications", key: "nav_notifications", file: "notifications.html", icon: "bell", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
      { name: "Sakra AI Copilot", key: "nav_copilot", file: "copilot.html", icon: "cpu", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] }
    ];
    const allowedLinks = links.filter(l => l.roles.includes(user.role));
    const mobileLinksHtml = allowedLinks.map(link => {
      const isActive = activePath === link.file;
      return `
        <a href="/${link.file}" class="relative flex flex-col items-center gap-1 transition-all duration-150 ${
          isActive ? "text-blue-400 font-bold" : "text-slate-500 hover:text-slate-300"
        }">
          <i data-lucide="${link.icon}" class="w-5 h-5"></i>
          ${link.file === "notifications.html" ? `<span id="mobile-notifications-badge" class="absolute top-0 right-3 bg-rose-500 text-white text-[7px] font-bold px-1 rounded-full scale-0 transition-transform shadow-[0_0_8px_rgba(239,68,68,0.5)]">0</span>` : ""}
          <span class="text-[8px] uppercase tracking-wider font-semibold" data-i18n="${link.key}">${window.t ? window.t(link.key) : link.name}</span>
        </a>
      `;
    }).join("");
    mobileNav.innerHTML = mobileLinksHtml;
  }

  // 3. Render Command Palette
  const paletteContainer = document.getElementById("command-palette-container");
  if (paletteContainer) {
    paletteContainer.innerHTML = `
      <div id="spotlight-overlay" class="spotlight-overlay hidden">
        <div class="spotlight-box">
          <div class="p-4 border-b border-slate-800 flex items-center gap-3">
            <i data-lucide="search" class="w-5 h-5 text-slate-400"></i>
            <input
              id="spotlight-search"
              type="text"
              data-i18n-placeholder="cmd_search_placeholder"
              placeholder="${window.t ? window.t("cmd_search_placeholder") : "Type a command or search action..."}"
              class="w-full bg-transparent outline-none border-none text-white text-sm"
            />
          </div>
          
          <div id="spotlight-items" class="max-h-[300px] overflow-y-auto p-2 flex flex-col gap-0.5">
            <!-- Dynamic command list -->
          </div>
          
          <div class="px-4 py-2.5 border-t border-slate-800 bg-slate-950/20 text-[10px] text-slate-500 flex items-center justify-between">
            <span data-i18n="cmd_search_help">${window.t ? window.t("cmd_search_help") : "Search using command palette"}</span>
            <span data-i18n="cmd_search_esc">${window.t ? window.t("cmd_search_esc") : "ESC to close"}</span>
          </div>
        </div>
      </div>
    `;

    setupCommandPalette(user);
  }

  // Re-instantiate icons
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// Spotlight commands management
function setupCommandPalette(user) {
  const overlay = document.getElementById("spotlight-overlay");
  const input = document.getElementById("spotlight-search");
  const itemsContainer = document.getElementById("spotlight-items");

  if (!overlay || !input || !itemsContainer) return;

  const items = [
    { name: "Navigate to Dashboard", key: "cmd_nav_dashboard", action: () => window.location.href = "/dashboard.html", icon: "settings", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Navigate to Customers Directory", key: "cmd_nav_customers", action: () => window.location.href = "/customers.html", icon: "users", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Record Daily Repayments", key: "cmd_record_repayments", action: () => window.location.href = "/payments.html", icon: "settings", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"] },
    { name: "Ask SAKRA AI Copilot", key: "cmd_ask_copilot", action: () => window.location.href = "/copilot.html", icon: "bot", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Open System Alerts", key: "cmd_open_alerts", action: () => window.location.href = "/notifications.html", icon: "bell", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Security Audit Logs", key: "cmd_security_logs", action: () => window.location.href = "/reports.html", icon: "shield-alert", roles: ["SUPER_ADMIN"] },
    {
      name: "Switch Theme: Dark Luxury",
      key: "cmd_theme_dark",
      action: () => {
        setTheme("dark");
        overlay.classList.add("hidden");
      },
      icon: "sparkles",
      roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"]
    },
    {
      name: "Switch Theme: Light Professional",
      key: "cmd_theme_light",
      action: () => {
        setTheme("light");
        overlay.classList.add("hidden");
      },
      icon: "sparkles",
      roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"]
    },
    {
      name: "Switch Theme: OLED Pitch Black",
      key: "cmd_theme_oled",
      action: () => {
        setTheme("oled");
        overlay.classList.add("hidden");
      },
      icon: "sparkles",
      roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"]
    }
  ];

  const allowedItems = items.filter(i => i.roles.includes(user.role));

  function renderItems(filterText = "") {
    const query = filterText.toLowerCase().trim();
    const filtered = allowedItems.filter(item => {
      const translatedName = (window.t ? window.t(item.key) : item.name).toLowerCase();
      return translatedName.includes(query) || item.name.toLowerCase().includes(query);
    });

    if (filtered.length === 0) {
      itemsContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">${window.t ? window.t("cmd_no_results") : "No matching actions found."}</p>`;
      return;
    }

    itemsContainer.innerHTML = filtered.map((item, idx) => `
      <button data-idx="${idx}" class="spotlight-btn w-full text-left px-4 py-3 rounded-xl hover:bg-slate-800/60 transition-all text-xs text-slate-300 flex items-center gap-3 hover:text-white cursor-pointer bg-transparent border-none">
        <i data-lucide="${item.icon}" class="w-4 h-4 text-indigo-400 shrink-0"></i>
        <span>${window.t ? window.t(item.key) : item.name}</span>
      </button>
    `).join("");

    if (window.lucide) {
      window.lucide.createIcons();
    }

    // Attach click listeners
    const buttons = itemsContainer.querySelectorAll(".spotlight-btn");
    buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = btn.getAttribute("data-idx");
        const match = filtered[idx];
        if (match) {
          match.action();
          overlay.classList.add("hidden");
        }
      });
    });
  }

  // Toggle overlay keypress shortcuts
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      overlay.classList.add("hidden");
    }
  });

  input.addEventListener("input", (e) => {
    renderItems(e.target.value);
  });

  overlay.addEventListener("click", () => {
    overlay.classList.add("hidden");
  });

  overlay.firstElementChild.addEventListener("click", (e) => {
    e.stopPropagation();
  });
}

// ═══════════════════════════════════════════════════════════════
//  CINEMATIC INTRO EXPERIENCE V3.0
// ═══════════════════════════════════════════════════════════════

const CI_LOGO_PATH = "M 24 5 L 42 32 L 24 38 L 6 32 Z M 24 15 L 13 29 L 24 33 L 35 29 Z";

function buildCinematicHTML() {
  return `
    <!-- Volumetric depth -->
    <div class="ci-depth">
      <div class="ci-orb ci-orb-1"></div>
      <div class="ci-orb ci-orb-2"></div>
    </div>

    <!-- Glass reflection -->
    <div class="ci-glass"></div>

    <!-- Content stage -->
    <div class="ci-stage">
      <!-- Logo -->
      <div class="ci-logo-wrap">
        <svg class="ci-logo-svg" viewBox="0 0 48 46" fill="none" xmlns="http://www.w3.org/2000/svg">
          <!-- Stroke outline (draws progressively) -->
          <path class="ci-stroke" d="${CI_LOGO_PATH}"/>
          <!-- Branded fill (revealed after stroke) -->
          <g class="ci-fill">
            <!-- Outer metallic/gradient frame -->
            <path d="${CI_LOGO_PATH}" fill="url(#ci-metal-grad)" fill-rule="evenodd"/>
            <!-- Central glowing blue orb -->
            <circle cx="24" cy="24" r="3.2" fill="url(#ci-orb-grad)" filter="url(#ci-orb-glow)"/>
          </g>
          <defs>
            <!-- Metallic frame gradient -->
            <linearGradient id="ci-metal-grad" x1="6" y1="5" x2="42" y2="38" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#00f0ff"/>
              <stop offset="25%" stop-color="#e2e8f0"/>
              <stop offset="50%" stop-color="#1d4ed8"/>
              <stop offset="75%" stop-color="#ffffff"/>
              <stop offset="100%" stop-color="#00f0ff"/>
            </linearGradient>
            <!-- Orb gradient -->
            <radialGradient id="ci-orb-grad" cx="24" cy="24" r="3.2" fx="23" fy="23" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#ffffff"/>
              <stop offset="40%" stop-color="#00f0ff"/>
              <stop offset="70%" stop-color="#1d4ed8"/>
              <stop offset="100%" stop-color="#040815"/>
            </radialGradient>
            <!-- Orb blur/glow -->
            <filter id="ci-orb-glow" x="15" y="15" width="18" height="18" filterUnits="userSpaceOnUse">
              <feGaussianBlur stdDeviation="0.75" result="blur"/>
            </filter>
          </defs>
        </svg>
        <div class="ci-pulse"></div>
        <div class="ci-sweep"></div>
      </div>

      <!-- Welcome text -->
      <div class="ci-welcome" aria-hidden="true">
        <span>W</span><span>E</span><span>L</span><span>C</span><span>O</span><span>M</span><span>E</span><span style="width:0.6em;letter-spacing:0"></span><span>T</span><span>O</span>
      </div>

      <!-- Brand -->
      <div class="ci-brand">
        <span class="ci-brand-sakra">SAKRA</span>
        <span class="ci-brand-finance">FINANCE</span>
      </div>

      <!-- Subtitle -->
      <p class="ci-subtitle">Enterprise Finance Operating System</p>
    </div>

    <!-- Background glow expansion -->
    <div class="ci-expand"></div>
  `;
}

/** Schedule a single class-add at a specific ms offset from startTime */
function scheduleActivation(el, cls, startTime, atMs) {
  const now = Date.now();
  const delay = Math.max(0, atMs - (now - startTime));
  setTimeout(() => el && el.classList.add(cls), delay);
}

/** Orchestrate the full cinematic timeline */
function orchestrateCinematic(loader, startTime) {
  // 0.6s — SVG stroke begins drawing
  const strokePath = loader.querySelector('.ci-stroke');
  if (strokePath) {
    const len = strokePath.getTotalLength();
    strokePath.style.strokeDasharray = len;
    strokePath.style.strokeDashoffset = len;
    scheduleActivation(strokePath, 'ci-active', startTime, 600);
  }

  // 1.0s — Fill reveals after stroke completes
  const fillPath = loader.querySelector('.ci-fill');
  scheduleActivation(fillPath, 'ci-active', startTime, 1000);

  // 1.1s — Cyan pulse
  const pulse = loader.querySelector('.ci-pulse');
  scheduleActivation(pulse, 'ci-active', startTime, 1100);

  // 1.3s — "WELCOME TO" letter-by-letter reveal
  const letters = loader.querySelectorAll('.ci-welcome span');
  letters.forEach((span, i) => {
    if (span.style.width) return; // skip spacer
    const delay = 1300 + (i * 40);
    const d = Math.max(0, delay - (Date.now() - startTime));
    setTimeout(() => {
      span.style.animation = `ci-letter 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards`;
    }, d);
  });

  // 1.6s — SAKRA/FINANCE convergence
  const sakra = loader.querySelector('.ci-brand-sakra');
  const finance = loader.querySelector('.ci-brand-finance');
  scheduleActivation(sakra, 'ci-active', startTime, 1600);
  scheduleActivation(finance, 'ci-active', startTime, 1600);

  // 1.9s — Subtitle
  const subtitle = loader.querySelector('.ci-subtitle');
  scheduleActivation(subtitle, 'ci-active', startTime, 1900);

  // 2.1s — Light sweep
  const sweep = loader.querySelector('.ci-sweep');
  scheduleActivation(sweep, 'ci-active', startTime, 2100);

  // 2.3s — Background glow expansion
  const expand = loader.querySelector('.ci-expand');
  scheduleActivation(expand, 'ci-active', startTime, 2300);
}

/** Dissolve the intro overlay smoothly */
function dissolveIntro(loader) {
  return new Promise((resolve) => {
    loader.classList.add('ci-dissolve');
    const onEnd = () => {
      loader.removeEventListener('transitionend', onEnd);
      loader.style.display = 'none';
      resolve();
    };
    loader.addEventListener('transitionend', onEnd);
    // Safety fallback in case transitionend doesn't fire
    setTimeout(() => {
      loader.style.display = 'none';
      resolve();
    }, 600);
  });
}

// Core execution workflow
async function executeMain() {
  const bootStart = Date.now();
  const loader = document.getElementById("global-page-loader");
  const isFirstLoad = !sessionStorage.getItem('sakra-intro-played');

  if (loader) {
    loader.className = ""; // Reset — CSS styles via #global-page-loader
    if (isFirstLoad) {
      loader.innerHTML = buildCinematicHTML();
      orchestrateCinematic(loader, bootStart);
      sessionStorage.setItem('sakra-intro-played', '1');
    }
    // Subsequent loads: loader is empty = pure black screen, dissolves quickly
  }

  // ── Boot checks run IN PARALLEL with the animation ──────────
  const user = await checkSession();
  await initI18n(user);

  // ── Enforce minimum animation duration ──────────────────────
  const elapsed = Date.now() - bootStart;
  const minDuration = isFirstLoad ? 2800 : 350;
  if (elapsed < minDuration) {
    await new Promise((r) => setTimeout(r, minDuration - elapsed));
  }

  // ── Route to correct page ───────────────────────────────────
  const path = getPageFilename();
  const unauthenticatedPages = ["login.html", "activate.html", "forgot.html", "404.html", "500.html", "403.html"];
  const isUnauth = unauthenticatedPages.includes(path);

  if (isUnauth) {
    if (user && path === "login.html") {
      if (loader) loader.classList.add("hidden");
      window.location.href = "/dashboard.html";
      return;
    }
    if (loader) {
      if (isFirstLoad) {
        await dissolveIntro(loader);
      } else {
        loader.classList.add("hidden");
      }
    }
    window.translatePage();
    return;
  }

  if (!user) {
    if (loader) loader.classList.add("hidden");
    window.location.href = "/login.html";
    return;
  }

  // Validate permission scope
  if (!checkPagePermission(user)) {
    if (loader) loader.classList.add("hidden");
    return;
  }

  // ── Dissolve into dashboard ─────────────────────────────────
  if (loader) {
    if (isFirstLoad) {
      await dissolveIntro(loader);
    } else {
      loader.classList.add("hidden");
    }
  }

  // Setup layouts
  window.currentUserSession = user;
  await initLayout(user);
  await initNotificationCenter(user);
}

// Global Language Changed Redraw Listener
window.addEventListener("language-changed", () => {
  if (window.currentUserSession) {
    initLayout(window.currentUserSession);
  }
});

// Global Auth Expired Event redirection handler
window.addEventListener("auth-expired", () => {
  window.location.href = "/login.html";
});

// ── Responsive Typography & Auto-Fit for Financial Numbers ───
window.autoFitFinancialNumbers = function() {
  const elements = document.querySelectorAll('.text-financial-number');
  elements.forEach(el => {
    // Reset inline font size so clamp/container-query styles can compute baseline
    el.style.fontSize = '';
    
    const parent = el.parentElement;
    if (!parent) return;

    const parentStyle = window.getComputedStyle(parent);
    const paddingLeft = parseFloat(parentStyle.paddingLeft || 0);
    const paddingRight = parseFloat(parentStyle.paddingRight || 0);
    
    // Safety boundary margins (8px)
    const availableWidth = parent.clientWidth - (paddingLeft + paddingRight) - 8;
    if (availableWidth <= 0) return;

    let currentSize = parseFloat(window.getComputedStyle(el).fontSize);
    const minSize = 9; // Minimum readable size

    while (el.scrollWidth > availableWidth && currentSize > minSize) {
      currentSize -= 0.5;
      el.style.fontSize = `${currentSize}px`;
    }
  });
};

// Handle resize event
window.addEventListener("resize", () => {
  window.autoFitFinancialNumbers();
});

// Setup mutation observer to fit text automatically when numbers load dynamically
const autoFitObserver = new MutationObserver(() => {
  autoFitObserver.disconnect();
  window.autoFitFinancialNumbers();
  autoFitObserver.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
});

// Start observing on load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    window.autoFitFinancialNumbers();
    autoFitObserver.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });
  });
} else {
  window.autoFitFinancialNumbers();
  autoFitObserver.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
}

// Premium glassmorphic toast notification system
window.showToast = function(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "fixed top-6 right-6 z-[9999] flex flex-col gap-3 pointer-events-none max-w-sm w-full";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `glass-card p-4 rounded-xl border border-white/10 shadow-enterprise-lg flex items-start gap-3 pointer-events-auto transform translate-x-12 opacity-0 transition-all duration-300 bg-slate-900/90 backdrop-blur-md`;
  
  let iconName = "info";
  let iconColor = "text-blue-400";
  if (type === "success") {
    iconName = "check-circle-2";
    iconColor = "text-emerald-400";
  } else if (type === "error") {
    iconName = "alert-triangle";
    iconColor = "text-rose-400";
  } else if (type === "warning") {
    iconName = "alert-circle";
    iconColor = "text-amber-400";
  }

  toast.innerHTML = `
    <div class="${iconColor} shrink-0 mt-0.5">
      <i data-lucide="${iconName}" class="w-4 h-4"></i>
    </div>
    <div class="flex-1">
      <p class="text-xs font-semibold text-text-primary leading-relaxed">${message}</p>
    </div>
    <button class="text-text-muted hover:text-text-primary shrink-0 transition-colors close-btn cursor-pointer">
      <i data-lucide="x" class="w-3.5 h-3.5"></i>
    </button>
  `;

  container.appendChild(toast);
  
  if (window.lucide) window.lucide.createIcons({ node: toast });

  // Slide/Fade In
  requestAnimationFrame(() => {
    toast.classList.remove("translate-x-12", "opacity-0");
  });

  const dismiss = () => {
    toast.classList.add("translate-x-12", "opacity-0");
    setTimeout(() => {
      toast.remove();
      if (container.children.length === 0) {
        container.remove();
      }
    }, 300);
  };

  toast.querySelector(".close-btn").addEventListener("click", dismiss);

  // Auto-dismiss after 4 seconds
  setTimeout(dismiss, 4000);
};

let notificationSseSource = null;

async function initNotificationCenter(user) {
  // Check if drawer element already exists
  let drawer = document.getElementById("notifications-drawer");
  if (!drawer) {
    drawer = document.createElement("div");
    drawer.id = "notifications-drawer";
    drawer.className = "fixed top-0 right-0 bottom-0 w-full sm:w-[420px] bg-slate-950/95 backdrop-blur-lg border-l border-white/10 z-[1000] shadow-2xl transform translate-x-full transition-transform duration-300 flex flex-col";
    document.body.appendChild(drawer);
  }

  // Load sound preference
  let soundEnabled = localStorage.getItem("sakra-notif-sound") !== "off";

  // HTML structure
  drawer.innerHTML = `
    <!-- Header -->
    <div class="p-4 border-b border-white/5 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <i data-lucide="bell" class="w-4 h-4 text-blue-400"></i>
        <h3 class="text-xs uppercase font-bold tracking-wider text-slate-200">Alert Center</h3>
      </div>
      <div class="flex items-center gap-3">
        <!-- Sound toggle button -->
        <button id="drawer-sound-toggle" class="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-white/5 transition-colors cursor-pointer">
          <i data-lucide="${soundEnabled ? "volume-2" : "volume-x"}" class="w-3.5 h-3.5" id="sound-icon"></i>
        </button>
        <button id="close-notifications-drawer" class="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-white/5 transition-colors cursor-pointer">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>
    </div>

    <!-- Search & Bulk Actions -->
    <div class="p-4 border-b border-white/5 flex flex-col gap-3">
      <div class="flex items-center gap-2 bg-slate-900/50 rounded border border-white/5 px-3 py-1.5">
        <i data-lucide="search" class="w-3.5 h-3.5 text-slate-400"></i>
        <input id="drawer-search" type="text" placeholder="Search alerts..." class="bg-transparent border-none outline-none text-[11px] text-white w-full" />
      </div>
      <div class="flex items-center justify-between text-[10px] text-slate-400">
        <button id="drawer-mark-all-read" class="hover:text-blue-400 transition-colors flex items-center gap-1 cursor-pointer">
          <i data-lucide="check-check" class="w-3 h-3"></i> Mark all read
        </button>
        <button id="drawer-clear-read" class="hover:text-rose-400 transition-colors flex items-center gap-1 cursor-pointer">
          <i data-lucide="trash-2" class="w-3 h-3"></i> Clear read
        </button>
      </div>
    </div>

    <!-- Filter chips -->
    <div class="px-4 py-2 bg-slate-950/40 border-b border-white/5 overflow-x-auto flex gap-1.5 select-none scrollbar-none">
      <button data-filter="all" class="filter-chip active text-[9px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border border-white/5 transition-all cursor-pointer">All</button>
      <button data-filter="unread" class="filter-chip text-[9px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border border-white/5 transition-all cursor-pointer">Unread</button>
      <button data-filter="PAYMENT" class="filter-chip text-[9px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border border-white/5 transition-all cursor-pointer">Payments</button>
      <button data-filter="CUSTOMER" class="filter-chip text-[9px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border border-white/5 transition-all cursor-pointer">Customers</button>
      <button data-filter="LOAN" class="filter-chip text-[9px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border border-white/5 transition-all cursor-pointer">Loans</button>
      <button data-filter="SECURITY" class="filter-chip text-[9px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border border-white/5 transition-all cursor-pointer">Security</button>
      <button data-filter="AI" class="filter-chip text-[9px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border border-white/5 transition-all cursor-pointer">AI</button>
    </div>

    <!-- Notifications List -->
    <div id="drawer-list" class="flex-1 overflow-y-auto p-4 flex flex-col gap-4"></div>
  `;

  if (window.lucide) window.lucide.createIcons({ node: drawer });

  // Notifications state
  let notificationsList = [];
  let currentFilter = "all";
  let searchQuery = "";

  // Sound cue audio
  const notifAudio = new Audio("https://assets.mixkit.co/active_storage/sfx/2869/2869-84.wav");
  notifAudio.volume = 0.4;

  // Toggle drawer listeners
  const bellBtn = document.getElementById("header-notifications-bell");
  const closeBtn = document.getElementById("close-notifications-drawer");

  const openDrawer = () => {
    drawer.classList.add("active");
    renderList();
  };

  const closeDrawer = () => {
    drawer.classList.remove("active");
  };

  bellBtn?.addEventListener("click", openDrawer);
  closeBtn?.addEventListener("click", closeDrawer);

  // sound toggle listener
  const soundToggle = document.getElementById("drawer-sound-toggle");
  const soundIcon = document.getElementById("sound-icon");
  soundToggle?.addEventListener("click", () => {
    soundEnabled = !soundEnabled;
    localStorage.setItem("sakra-notif-sound", soundEnabled ? "on" : "off");
    if (soundIcon) {
      soundIcon.setAttribute("data-lucide", soundEnabled ? "volume-2" : "volume-x");
      if (window.lucide) window.lucide.createIcons({ node: soundToggle });
    }
  });

  // Filter chips selection
  const chips = drawer.querySelectorAll(".filter-chip");
  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentFilter = chip.getAttribute("data-filter");
      renderList();
    });
  });

  // Search input
  const searchInput = document.getElementById("drawer-search");
  searchInput?.addEventListener("input", (e) => {
    searchQuery = e.target.value.toLowerCase().trim();
    renderList();
  });

  // Bulk actions
  const markAllReadBtn = document.getElementById("drawer-mark-all-read");
  const clearReadBtn = document.getElementById("drawer-clear-read");

  markAllReadBtn?.addEventListener("click", async () => {
    try {
      await api.post("/notifications/read-all");
      notificationsList.forEach(n => n.is_read = true);
      updateBadges();
      renderList();
      window.showToast("All notifications marked as read.", "success");
    } catch (err) {
      console.error(err);
    }
  });

  clearReadBtn?.addEventListener("click", () => {
    notificationsList = notificationsList.filter(n => !n.is_read);
    updateBadges();
    renderList();
    window.showToast("Read notifications cleared from view.", "success");
  });

  // Retrieve details
  const fetchNotifications = async () => {
    try {
      const res = await api.get("/notifications/");
      const payload = res.data || res;
      notificationsList = payload.notifications || [];
      updateBadges();
      renderList();
    } catch (err) {
      console.error("Failed to load notifications:", err);
    }
  };

  const updateBadges = () => {
    const unreadCount = notificationsList.filter(n => !n.is_read).length;
    const badge = document.getElementById("notifications-badge");
    const mobileBadge = document.getElementById("mobile-notifications-badge");

    if (badge) {
      badge.textContent = unreadCount;
      if (unreadCount > 0) {
        badge.classList.remove("scale-0");
        badge.classList.add("scale-100");
      } else {
        badge.classList.remove("scale-100");
        badge.classList.add("scale-0");
      }
    }
    if (mobileBadge) {
      mobileBadge.textContent = unreadCount;
      if (unreadCount > 0) {
        mobileBadge.classList.remove("scale-0");
        mobileBadge.classList.add("scale-100");
      } else {
        mobileBadge.classList.remove("scale-100");
        mobileBadge.classList.add("scale-0");
      }
    }
  };

  const renderList = () => {
    const listContainer = document.getElementById("drawer-list");
    if (!listContainer) return;

    // Filter items
    let filtered = notificationsList;
    if (currentFilter === "unread") {
      filtered = notificationsList.filter(n => !n.is_read);
    } else if (currentFilter !== "all") {
      filtered = notificationsList.filter(n => n.notification_type.startsWith(currentFilter));
    }

    if (searchQuery) {
      filtered = filtered.filter(n => 
        (n.message || "").toLowerCase().includes(searchQuery) ||
        (n.notification_type || "").toLowerCase().includes(searchQuery)
      );
    }

    if (filtered.length === 0) {
      listContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-12 text-slate-500 text-center">
          <i data-lucide="bell-off" class="w-8 h-8 text-slate-600 mb-2"></i>
          <p class="text-xs">No alerts found</p>
        </div>
      `;
      if (window.lucide) window.lucide.createIcons({ node: listContainer });
      return;
    }

    // Grouping by Date: Today, Yesterday, Last 7 Days, Older
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);

    const groups = {
      Today: [],
      Yesterday: [],
      "Last 7 Days": [],
      Older: []
    };

    filtered.forEach(n => {
      const dt = new Date(n.sent_at);
      if (dt >= today) {
        groups.Today.push(n);
      } else if (dt >= yesterday) {
        groups.Yesterday.push(n);
      } else if (dt >= lastWeek) {
        groups["Last 7 Days"].push(n);
      } else {
        groups.Older.push(n);
      }
    });

    let html = "";
    Object.keys(groups).forEach(groupName => {
      const groupItems = groups[groupName];
      if (groupItems.length === 0) return;

      html += `
        <div class="flex flex-col gap-2">
          <h4 class="text-[9px] uppercase tracking-widest font-bold text-slate-500 mt-2">${groupName}</h4>
          <div class="flex flex-col gap-2">
      `;

      groupItems.forEach(n => {
        let severity = "info";
        let colorClass = "severity-info";
        let icon = "info";
        let bgStyle = "bg-slate-900/40";
        
        const type = n.notification_type;
        if (type.includes("LARGE") || type.includes("HIGH") || type.includes("ALERT") || type.includes("WARNING")) {
          severity = "high";
          colorClass = "severity-high";
          icon = "alert-circle";
          bgStyle = "bg-amber-950/10 border-amber-500/10";
        } else if (type === "OVERDUE" || type.includes("FAILURE") || type.includes("DISABLED") || type.includes("CRITICAL")) {
          severity = "critical";
          colorClass = "severity-critical";
          icon = "alert-triangle";
          bgStyle = "bg-rose-950/10 border-rose-500/10";
        } else if (type.includes("REGISTERED") || type.includes("SUCCESS") || type.includes("COMPLETED")) {
          severity = "success";
          colorClass = "severity-success";
          icon = "check-circle-2";
          bgStyle = "bg-emerald-950/10 border-emerald-500/10";
        } else if (type.includes("UPDATED") || type.includes("MODIFIED")) {
          severity = "medium";
          colorClass = "severity-medium";
          icon = "edit-3";
          bgStyle = "bg-blue-950/10 border-blue-500/10";
        }

        const dateStr = new Date(n.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        html += `
          <div data-notif-id="${n.id}" class="notification-item ${colorClass} ${bgStyle} p-3 rounded-lg border border-white/5 flex flex-col gap-1.5 transition-all hover:bg-slate-900/60 cursor-pointer ${n.is_read ? "opacity-60" : "font-semibold shadow-sm"}">
            <div class="flex items-center justify-between gap-2">
              <span class="text-[9px] uppercase tracking-wider font-bold ${
                severity === "critical" ? "text-rose-400" :
                severity === "high" ? "text-amber-400" :
                severity === "success" ? "text-emerald-400" :
                severity === "medium" ? "text-blue-400" : "text-slate-400"
              }">${n.notification_type.replace(/_/g, " ")}</span>
              <span class="text-[8px] text-slate-500 font-sans font-normal">${dateStr}</span>
            </div>
            <p class="text-[11px] text-slate-300 leading-relaxed">${n.message}</p>
            <div class="flex items-center justify-end text-[9px] text-blue-400 gap-1 hover:text-blue-300 transition-all font-sans font-bold">
              <span>View details</span>
              <i data-lucide="chevron-right" class="w-3 h-3"></i>
            </div>
          </div>
        `;
      });

      html += `
          </div>
        </div>
      `;
    });

    listContainer.innerHTML = html;
    if (window.lucide) window.lucide.createIcons({ node: listContainer });

    // Item click listeners
    listContainer.querySelectorAll(".notification-item").forEach(item => {
      item.addEventListener("click", async () => {
        const id = parseInt(item.getAttribute("data-notif-id"));
        const notif = notificationsList.find(n => n.id === id);
        if (notif) {
          // Mark as read
          if (!notif.is_read) {
            notif.is_read = true;
            try {
              await api.patch(`/notifications/${notif.id}/read`);
            } catch (e) {
              console.error(e);
            }
            updateBadges();
            renderList();
          }

          // Close drawer
          closeDrawer();

          // Redirect
          if (notif.notification_type.startsWith("CUSTOMER")) {
            window.location.href = `/customer-profile.html?id=${notif.customer_id}`;
          } else if (notif.notification_type.startsWith("PAYMENT") || notif.notification_type === "OVERDUE") {
            window.location.href = `/payments.html?customer_id=${notif.customer_id}`;
          } else if (notif.notification_type.startsWith("LOAN")) {
            window.location.href = `/customer-profile.html?id=${notif.customer_id}#loans`;
          } else if (notif.notification_type.startsWith("SECURITY")) {
            window.location.href = `/reports.html`;
          } else if (notif.notification_type.startsWith("AI")) {
            window.location.href = `/copilot.html`;
          }
        }
      });
    });
  };

  // Perform initial fetch
  await fetchNotifications();

  // ── Establish Real-Time SSE Stream ──────────────────────────
  if (notificationSseSource) {
    notificationSseSource.close();
  }

  const token = localStorage.getItem("access_token");
  if (!token) return;

  notificationSseSource = new EventSource(`/api/v1/notifications/stream?token=${token}`);

  notificationSseSource.onmessage = (event) => {
    try {
      const newNotif = JSON.parse(event.data);
      // Prepend to list
      notificationsList.unshift(newNotif);
      updateBadges();
      renderList();

      // Dispatch window event for other listeners (like notifications.js)
      window.dispatchEvent(new CustomEvent("new-notification", { detail: newNotif }));

      // Show temporary toast alert
      window.showToast(newNotif.message, newNotif.notification_type.includes("CRITICAL") || newNotif.notification_type === "OVERDUE" ? "error" : "success");

      // Play soft sound cue if enabled
      if (soundEnabled) {
        notifAudio.play().catch(e => console.warn("Audio play prevented:", e));
      }
    } catch (err) {
      console.error("Failed to parse SSE event:", err);
    }
  };

  notificationSseSource.onerror = (err) => {
    console.debug("Notification stream disconnected. Retrying...");
  };
}

// Run bootstrap
executeMain();
