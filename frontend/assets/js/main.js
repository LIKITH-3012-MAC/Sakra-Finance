import { checkSession, logout } from "./auth.js";
import { setTheme } from "./theme.js";
import { initI18n } from "./i18n.js";
import { registerServiceWorker, initInstallPrompt } from "./pwa.js";

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
            <p class="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Secured Profile</p>
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
            <span data-i18n="sign_out">Sign Out</span>
          </button>
        </div>
      </div>
    `;

    document.getElementById("sidebar-logout")?.addEventListener("click", logout);
  }

  // 2. Render Header
  const headerContainer = document.getElementById("header-container");
  if (headerContainer) {
    const currentLangText = window.currentLanguage === "te" ? "🇮🇳 TE" : "🇬🇧 EN";

    headerContainer.innerHTML = `
      <header class="h-16 bg-slate-950/30 backdrop-blur-md border-b border-white/5 px-4 md:px-8 flex items-center justify-between shrink-0 relative z-10 select-none shadow-[0_4px_12px_rgba(0,0,0,0.25)]">
        <div class="flex items-center gap-2 md:gap-3">
          <span class="text-[9px] md:text-[10px] font-bold uppercase tracking-wider bg-blue-950/50 text-blue-400 px-2.5 py-1 rounded border border-blue-500/25 flex items-center gap-1.5 select-none font-sans">
            <span class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-ping"></span>
            <span data-i18n="secure_session">SECURE SESSION</span>
          </span>
          <span class="hidden sm:inline-flex text-[9px] md:text-[10px] font-bold uppercase tracking-wider bg-slate-900/50 text-slate-400 px-2.5 py-1 rounded border border-white/5 select-none font-sans">
            <span data-i18n="verified_ip">VERIFIED IP</span>
          </span>
        </div>
        
        <div class="flex items-center gap-3 md:gap-4 text-xs font-semibold text-slate-400 font-sans">
          
          <!-- Custom Premium Language Selector -->
          <div class="relative inline-block text-left" id="lang-switcher-container">
            <button id="lang-switcher-btn" class="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-900/50 hover:bg-slate-800/50 border border-white/5 text-[9px] uppercase font-bold tracking-wider text-slate-300 hover:text-slate-100 transition-colors select-none cursor-pointer">
              <i data-lucide="languages" class="w-3.5 h-3.5 text-slate-400"></i>
              <span id="current-lang-text">${currentLangText}</span>
              <i data-lucide="chevron-down" class="w-3 h-3 text-slate-500"></i>
            </button>
            <div id="lang-switcher-dropdown" class="absolute right-0 mt-2 w-32 bg-slate-950/95 border border-white/10 rounded-lg shadow-enterprise-md py-1 hidden z-50 flex flex-col backdrop-blur-md">
              <button data-lang="en" class="flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 text-slate-300 hover:text-white transition-colors cursor-pointer w-full text-[10px] font-bold uppercase tracking-wider">
                🇬🇧 English
              </button>
              <button data-lang="te" class="flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 text-slate-300 hover:text-white transition-colors cursor-pointer w-full text-[10px] font-bold uppercase tracking-wider">
                🇮🇳 తెలుగు
              </button>
            </div>
          </div>
          
          <span class="text-white/5">|</span>
          <div class="flex items-center gap-1.5 select-none text-[9px] font-bold text-emerald-400">
            <i data-lucide="shield-check" class="w-4 h-4 text-emerald-400"></i>
            <span class="hidden md:inline-block uppercase tracking-widest" data-i18n="audit_active">AUDIT ACTIVE</span>
          </div>
          <span class="text-white/5">|</span>
          <div class="flex items-center gap-1.5 text-slate-200">
            <i data-lucide="user" class="w-3.5 h-3.5 text-slate-500"></i>
            <span class="truncate max-w-[80px] sm:max-w-none">${user.username}</span>
          </div>
          <span class="md:hidden text-white/5">|</span>
          <button id="header-logout" class="md:hidden text-rose-400 hover:text-rose-600 transition-colors p-1 rounded bg-transparent border-none cursor-pointer">
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
      { name: "Dashboard", file: "dashboard.html", icon: "layout-dashboard", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
      { name: "Customers", file: "customers.html", icon: "users", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
      { name: "Daily Repayments", file: "payments.html", icon: "check-square", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"] },
      { name: "Notifications", file: "notifications.html", icon: "bell", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
      { name: "Sakra AI Copilot", file: "copilot.html", icon: "cpu", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] }
    ];
    const allowedLinks = links.filter(l => l.roles.includes(user.role));
    const mobileLinksHtml = allowedLinks.map(link => {
      const isActive = activePath === link.file;
      return `
        <a href="/${link.file}" class="flex flex-col items-center gap-1 transition-all duration-150 ${
          isActive ? "text-blue-400 font-bold" : "text-slate-500 hover:text-slate-300"
        }">
          <i data-lucide="${link.icon}" class="w-5 h-5"></i>
          <span class="text-[8px] uppercase tracking-wider font-semibold">${link.name.split(" ").pop()}</span>
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
              placeholder="Type a command or search action..."
              class="w-full bg-transparent outline-none border-none text-white text-sm"
            />
          </div>
          
          <div id="spotlight-items" class="max-h-[300px] overflow-y-auto p-2 flex flex-col gap-0.5">
            <!-- Dynamic command list -->
          </div>
          
          <div class="px-4 py-2.5 border-t border-slate-800 bg-slate-950/20 text-[10px] text-slate-500 flex items-center justify-between">
            <span>Search using command palette</span>
            <span>ESC to close</span>
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
    { name: "Navigate to Dashboard", action: () => window.location.href = "/dashboard.html", icon: "settings", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Navigate to Customers Directory", action: () => window.location.href = "/customers.html", icon: "users", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Record Daily Repayments", action: () => window.location.href = "/payments.html", icon: "settings", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN"] },
    { name: "Ask SAKRA AI Copilot", action: () => window.location.href = "/copilot.html", icon: "bot", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Open System Alerts", action: () => window.location.href = "/notifications.html", icon: "bell", roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"] },
    { name: "Security Audit Logs", action: () => window.location.href = "/reports.html", icon: "shield-alert", roles: ["SUPER_ADMIN"] },
    {
      name: "Switch Theme: Dark Luxury",
      action: () => {
        setTheme("dark");
        overlay.classList.add("hidden");
      },
      icon: "sparkles",
      roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"]
    },
    {
      name: "Switch Theme: Light Professional",
      action: () => {
        setTheme("light");
        overlay.classList.add("hidden");
      },
      icon: "sparkles",
      roles: ["SUPER_ADMIN", "ADMIN", "ASSISTANT_ADMIN", "VIEWER"]
    },
    {
      name: "Switch Theme: OLED Pitch Black",
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
    const filtered = allowedItems.filter(item => item.name.toLowerCase().includes(query));

    if (filtered.length === 0) {
      itemsContainer.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">No matching actions found.</p>`;
      return;
    }

    itemsContainer.innerHTML = filtered.map((item, idx) => `
      <button data-idx="${idx}" class="spotlight-btn w-full text-left px-4 py-3 rounded-xl hover:bg-slate-800/60 transition-all text-xs text-slate-300 flex items-center gap-3 hover:text-white cursor-pointer bg-transparent border-none">
        <i data-lucide="${item.icon}" class="w-4 h-4 text-indigo-400 shrink-0"></i>
        <span>${item.name}</span>
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

// Core execution workflow
async function executeMain() {
  const splashStart = Date.now();
  const loader = document.getElementById("global-page-loader");
  
  if (loader) {
    loader.className = ""; // Reset class list to rely on CSS
    loader.innerHTML = `
      <div class="sakra-splash-content">
        <div class="sakra-splash-logo-container">
          <svg class="sakra-splash-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 46" fill="none">
            <path fill="#863bff" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" style="fill:#863bff;fill:color(display-p3 .5252 .23 1);fill-opacity:1"/>
            <mask id="splash-mask-a" width="48" height="46" x="0" y="0" maskUnits="userSpaceOnUse" style="mask-type:alpha">
              <path fill="#000" d="M25.842 44.938c-.664.844-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.183c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.498 0-3.579-1.842-3.579H1.133c-.92 0-1.456-1.04-.92-1.787L9.91.473c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.578 1.842 3.578h11.377c.943 0 1.473 1.088.89 1.832L25.843 44.94z" style="fill:#000;fill-opacity:1"/>
            </mask>
            <g mask="url(#splash-mask-a)">
              <g filter="url(#splash-filt-b)">
                <ellipse cx="5.508" cy="14.704" fill="#ede6ff" rx="5.508" ry="14.704" style="fill:#ede6ff;fill:color(display-p3 .9275 .9033 1);fill-opacity:1" transform="matrix(.00324 1 1 -.00324 -4.47 31.516)"/>
              </g>
              <g filter="url(#splash-filt-c)">
                <ellipse cx="10.399" cy="29.851" fill="#ede6ff" rx="10.399" ry="29.851" style="fill:#ede6ff;fill:color(display-p3 .9275 .9033 1);fill-opacity:1" transform="matrix(.00324 1 1 -.00324 -39.328 7.883)"/>
              </g>
              <g filter="url(#splash-filt-d)">
                <ellipse cx="5.508" cy="30.487" fill="#7e14ff" rx="5.508" ry="30.487" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.814 -25.913 -14.639)scale(1 -1)"/>
              </g>
              <g filter="url(#splash-filt-e)">
                <ellipse cx="5.508" cy="30.599" fill="#7e14ff" rx="5.508" ry="30.599" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.814 -32.644 -3.334)scale(1 -1)"/>
              </g>
              <g filter="url(#splash-filt-f)">
                <ellipse cx="5.508" cy="30.599" fill="#7e14ff" rx="5.508" ry="30.599" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="matrix(.00324 1 1 -.00324 -34.34 30.47)"/>
              </g>
              <g filter="url(#splash-filt-g)">
                <ellipse cx="14.072" cy="22.078" fill="#ede6ff" rx="14.072" ry="22.078" style="fill:#ede6ff;fill:color(display-p3 .9275 .9033 1);fill-opacity:1" transform="rotate(93.35 24.506 48.493)scale(-1 1)"/>
              </g>
              <g filter="url(#splash-filt-h)">
                <ellipse cx="3.47" cy="21.501" fill="#7e14ff" rx="3.47" ry="21.501" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.009 28.708 47.59)scale(-1 1)"/>
              </g>
              <g filter="url(#splash-filt-i)">
                <ellipse cx="3.47" cy="21.501" fill="#7e14ff" rx="3.47" ry="21.501" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(89.009 28.708 47.59)scale(-1 1)"/>
              </g>
              <g filter="url(#splash-filt-j)">
                <ellipse cx=".387" cy="8.972" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(39.51 .387 8.972)"/>
              </g>
              <g filter="url(#splash-filt-k)">
                <ellipse cx="47.523" cy="-6.092" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 47.523 -6.092)"/>
              </g>
              <g filter="url(#splash-filt-l)">
                <ellipse cx="41.412" cy="6.333" fill="#47bfff" rx="5.971" ry="9.665" style="fill:#47bfff;fill:color(display-p3 .2799 .748 1);fill-opacity:1" transform="rotate(37.892 41.412 6.333)"/>
              </g>
              <g filter="url(#splash-filt-m)">
                <ellipse cx="-1.879" cy="38.332" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 -1.88 38.332)"/>
              </g>
              <g filter="url(#splash-filt-n)">
                <ellipse cx="-1.879" cy="38.332" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 -1.88 38.332)"/>
              </g>
              <g filter="url(#splash-filt-o)">
                <ellipse cx="35.651" cy="29.907" fill="#7e14ff" rx="4.407" ry="29.108" style="fill:#7e14ff;fill:color(display-p3 .4922 .0767 1);fill-opacity:1" transform="rotate(37.892 35.651 29.907)"/>
              </g>
              <g filter="url(#splash-filt-p)">
                <ellipse cx="38.418" cy="32.4" fill="#47bfff" rx="5.971" ry="15.297" style="fill:#47bfff;fill:color(display-p3 .2799 .748 1);fill-opacity:1" transform="rotate(37.892 38.418 32.4)"/>
              </g>
            </g>
            <defs>
              <filter id="splash-filt-b" width="60.045" height="41.654" x="-19.77" y="16.149" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="7.659"/>
              </filter>
              <filter id="splash-filt-c" width="90.34" height="51.437" x="-54.613" y="-7.533" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="7.659"/>
              </filter>
              <filter id="splash-filt-d" width="79.355" height="29.4" x="-49.64" y="2.03" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-e" width="79.579" height="29.4" x="-45.045" y="20.029" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-f" width="79.579" height="29.4" x="-43.513" y="21.178" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-g" width="74.749" height="58.852" x="15.756" y="-17.901" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="7.659"/>
              </filter>
              <filter id="splash-filt-h" width="61.377" height="25.362" x="23.548" y="2.284" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-i" width="61.377" height="25.362" x="23.548" y="2.284" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-j" width="56.045" height="63.649" x="-27.636" y="-22.853" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-k" width="54.814" height="64.646" x="20.116" y="-38.415" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-l" width="33.541" height="35.313" x="24.641" y="-11.323" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-m" width="54.814" height="64.646" x="-29.286" y="6.009" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-n" width="54.814" height="64.646" x="-29.286" y="6.009" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-o" width="54.814" height="64.646" x="8.244" y="-2.416" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
              <filter id="splash-filt-p" width="39.409" height="43.623" x="18.713" y="10.588" color-interpolation-filters="sRGB" filterUnits="userSpaceOnUse">
                <feFlood flood-opacity="0" result="BackgroundImageFix"/>
                <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
                <feGaussianBlur result="effect1_foregroundBlur" stdDeviation="4.596"/>
              </filter>
            </defs>
          </svg>
        </div>
        <div class="sakra-splash-text">
          <h1 class="sakra-splash-title">
            <span class="sakra-title-primary">SAKRA</span>
            <span class="sakra-title-secondary">FINANCE</span>
          </h1>
          <p class="sakra-splash-subtitle">Enterprise Finance Operating System</p>
        </div>
        <div class="sakra-splash-loading">
          <div class="sakra-loading-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <p id="sakra-splash-status" class="sakra-loading-status">Verifying Secure Gateway...</p>
        </div>
      </div>
    `;
  }

  // Update status function helper
  const setSplashStatus = (text) => {
    const statusEl = document.getElementById("sakra-splash-status");
    if (statusEl) statusEl.textContent = text;
  };

  // 1. Verify connection and check session
  setSplashStatus("Establishing secure node...");
  const user = await checkSession();

  // 2. Initialize translation dictionary
  setSplashStatus("Loading system languages...");
  await initI18n(user);

  // 3. Load configurations & check display mode
  setSplashStatus("Finalizing Secure Gateway...");

  // Enforce minimal splash screen hold time (900ms) for high-grade animation experience
  const elapsed = Date.now() - splashStart;
  if (elapsed < 900) {
    await new Promise((resolve) => setTimeout(resolve, 900 - elapsed));
  }

  const path = getPageFilename();
  const unauthenticatedPages = ["login.html", "activate.html", "forgot.html", "404.html", "500.html", "403.html"];
  const isUnauth = unauthenticatedPages.includes(path);

  if (isUnauth) {
    if (user && path === "login.html") {
      if (loader) loader.classList.add("hidden");
      window.location.href = "/dashboard.html";
      return;
    }
    if (loader) loader.classList.add("hidden");
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

  if (loader) {
    loader.classList.add("hidden");
  }

  // Setup layouts
  await initLayout(user);
}

// Global Auth Expired Event redirection handler
window.addEventListener("auth-expired", () => {
  window.location.href = "/login.html";
});

// Run bootstrap
executeMain();
