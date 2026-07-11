import api from "../api.js";
import { getCachedUser } from "../auth.js";

let messages = [];
const sessionId = `session_${Math.random().toString(36).substring(7)}`;

const content = document.getElementById("copilot-content");
const messagesContainer = document.getElementById("chat-messages-container");
const inputForm = document.getElementById("chat-input-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("chat-send-btn");
const historyLoader = document.getElementById("chat-history-loader");

const suggestions = [
  { title: "Dashboard Summary", query: "Give me a high level overview of our portfolio collections, active loans, and overdue counts." },
  { title: "Risk Guidelines", query: "What are the rules for calculating customer credit score and overdue loans?" },
  { title: "Days Crossed", query: "Identify customers who crossed the 100 days repayment threshold and display their outstanding amounts." }
];

async function init() {
  const user = getCachedUser();
  if (!user) return; // Wait for main.js session resolution

  // Populate identities in Header
  const userEl = document.getElementById("copilot-username");
  if (userEl) userEl.innerText = user.username;
  
  const roleEl = document.getElementById("copilot-role");
  if (roleEl) roleEl.innerText = user.role;
  
  const roleElMobile = document.getElementById("copilot-role-mobile");
  if (roleElMobile) roleElMobile.innerText = user.role;

  // Initialize lang switcher texts
  const currentLang = window.currentLanguage || "en";
  const textEn = document.getElementById("current-lang-text");
  if (textEn) textEn.innerText = currentLang === "te" ? "🇮🇳 TE" : "🇬🇧 EN";
  
  const textMo = document.getElementById("current-lang-text-mobile");
  if (textMo) textMo.innerText = currentLang === "te" ? "TE" : "EN";

  // Bind clear history triggers
  document.getElementById("clear-history-btn")?.addEventListener("click", handleClearHistory);
  document.getElementById("clear-history-btn-mobile")?.addEventListener("click", handleClearHistory);

  // Bind message submit
  inputForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    handleSend();
  });

  // Setup dynamic switcher drops and date loop
  setupLanguageSwitcher();
  updateDateTime();
  setInterval(updateDateTime, 1000);

  // Register language changed event listener to redraw
  window.addEventListener("language-changed", () => {
    renderMessages();
  });

  await loadHistory(user);
  content?.classList.remove("hidden");
}

function updateDateTime() {
  const dtEl = document.getElementById("copilot-datetime");
  if (dtEl) {
    const locale = window.currentLanguage === "te" ? "te-IN" : "en-IN";
    dtEl.innerText = new Date().toLocaleString(locale, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
      timeZone: "Asia/Kolkata"
    }) + " IST";
  }
}

function setupLanguageSwitcher() {
  const setupToggle = (btnId, dropdownId, textId) => {
    const btn = document.getElementById(btnId);
    const dropdown = document.getElementById(dropdownId);
    if (!btn || !dropdown) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      dropdown.classList.toggle("hidden");
    });

    dropdown.querySelectorAll("[data-lang]").forEach(item => {
      item.addEventListener("click", async () => {
        const lang = item.getAttribute("data-lang");
        await window.setAppLanguage(lang);
        
        const textEn = document.getElementById("current-lang-text");
        if (textEn) textEn.innerText = lang === "te" ? "🇮🇳 TE" : "🇬🇧 EN";
        
        const textMo = document.getElementById("current-lang-text-mobile");
        if (textMo) textMo.innerText = lang === "te" ? "TE" : "EN";

        dropdown.classList.add("hidden");
      });
    });
  };

  setupToggle("lang-switcher-btn", "lang-switcher-dropdown", "current-lang-text");
  setupToggle("lang-switcher-btn-mobile", "lang-switcher-dropdown-mobile", "current-lang-text-mobile");

  document.addEventListener("click", () => {
    document.getElementById("lang-switcher-dropdown")?.classList.add("hidden");
    document.getElementById("lang-switcher-dropdown-mobile")?.classList.add("hidden");
  });
}

async function loadHistory(user) {
  if (historyLoader) historyLoader.style.display = "flex";
  
  const defaultGreeting = {
    role: "assistant",
    content: `Hello ${user.username || "Admin"}! I am **SAKRA AI COPILOT** 🤖. I am your secure, permission-aware financial intelligence assistant. How can I help you analyze portfolios today?`
  };

  try {
    const res = await api.get("/copilot/chat/history");
    const payload = res.data || res;
    const loadedMsgs = payload.messages || payload || [];

    if (loadedMsgs.length > 0) {
      messages = loadedMsgs;
    } else {
      messages = [defaultGreeting];
    }
  } catch (err) {
    console.error("Failed to load chat history:", err);
    messages = [defaultGreeting];
  } finally {
    if (historyLoader) historyLoader.style.display = "none";
    renderMessages();
  }
}

function parseMarkdown(text) {
  if (!text) return "";
  
  // Handle code blocks
  let processed = text;
  processed = processed.replace(/```([\s\S]*?)```/g, (match, p1) => {
    return `<pre class="bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-xs my-3 overflow-x-auto border border-white/10 select-text">${p1.trim()}</pre>`;
  });

  // Handle inline code `code`
  processed = processed.replace(/`([^`]+)`/g, "<code class='bg-slate-100 text-primary px-1.5 py-0.5 rounded font-mono text-xs border border-slate-200'>$1</code>");

  // Handle tables
  const lines = processed.split("\n");
  let insideTable = false;
  let tableRows = [];
  let finalLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("|") && line.endsWith("|")) {
      if (!insideTable) {
        insideTable = true;
        tableRows = [];
      }
      const cols = line.split("|").map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
      tableRows.push(cols);
    } else {
      if (insideTable) {
        insideTable = false;
        let tableHtml = `<div class="overflow-x-auto my-4 border border-slate-200/60 rounded-xl"><table class="sakra-table w-full">`;
        tableRows.forEach((row, rowIdx) => {
          const isHeader = rowIdx === 0 || (rowIdx === 1 && row.every(cell => cell.startsWith("-")));
          if (row.every(cell => cell.startsWith("-"))) {
            return;
          }
          tableHtml += `<tr>`;
          row.forEach(cell => {
            const isNumeric = /^[₹\d,\.\-\+%]+$/.test(cell.replace(/[\s]/g, ""));
            const tdClass = isNumeric ? "font-mono text-right tabular-nums text-text-primary text-xs" : "text-left text-xs text-text-secondary font-semibold";
            if (rowIdx === 0) {
              tableHtml += `<th class="${tdClass} uppercase tracking-wider text-[9px] font-bold bg-slate-50">${cell}</th>`;
            } else {
              tableHtml += `<td class="p-3 border-t border-slate-100 ${tdClass}">${cell}</td>`;
            }
          });
          tableHtml += `</tr>`;
        });
        tableHtml += `</table></div>`;
        finalLines.push(tableHtml);
      }
      
      // List items
      if (line.startsWith("-") || line.startsWith("*")) {
        finalLines.push(`<li class="ml-5 list-disc mt-1.5 text-text-secondary font-semibold text-[15px] md:text-[17px] leading-relaxed">${line.substring(1).trim()}</li>`);
      } else if (/^\d+\.\s/.test(line)) {
        const dotIndex = line.indexOf(".");
        finalLines.push(`<li class="ml-5 list-decimal mt-1.5 text-text-secondary font-semibold text-[15px] md:text-[17px] leading-relaxed">${line.substring(dotIndex + 1).trim()}</li>`);
      } else if (line.length > 0) {
        let formattedLine = line.replace(/\*\*(.*?)\*\*/g, "<strong class='text-text-primary font-bold'>$1</strong>");
        formattedLine = formattedLine.replace(/(₹\s?\d+[\d,]*(\.\d+)?|\b\d+[\d,]*(\.\d+)?\b)/g, "<span class='font-mono font-bold text-primary tabular-nums'>$1</span>");
        
        finalLines.push(`<p class="mt-3 text-[15px] md:text-[17px] leading-[1.7] text-text-secondary font-medium font-sans">${formattedLine}</p>`);
      }
    }
  }

  if (insideTable) {
    let tableHtml = `<div class="overflow-x-auto my-4 border border-slate-200/60 rounded-xl"><table class="sakra-table w-full">`;
    tableRows.forEach((row, rowIdx) => {
      if (row.every(cell => cell.startsWith("-"))) return;
      tableHtml += `<tr>`;
      row.forEach(cell => {
        const isNumeric = /^[₹\d,\.\-\+%]+$/.test(cell.replace(/[\s]/g, ""));
        const tdClass = isNumeric ? "font-mono text-right tabular-nums text-text-primary text-xs" : "text-left text-xs text-text-secondary font-semibold";
        if (rowIdx === 0) {
          tableHtml += `<th class="${tdClass} uppercase tracking-wider text-[9px] font-bold bg-slate-50">${cell}</th>`;
        } else {
          tableHtml += `<td class="p-3 border-t border-slate-100 ${tdClass}">${cell}</td>`;
        }
      });
      tableHtml += `</tr>`;
    });
    tableHtml += `</table></div>`;
    finalLines.push(tableHtml);
  }

  return finalLines.join("");
}

function renderMessages(loadingAi = false) {
  const loader = document.getElementById("chat-history-loader");
  if (loader) loader.classList.add("hidden");

  // If there is only one message (greeting) and it is from the assistant, render the welcome dashboard
  if (messages.length === 1 && messages[0].role === "assistant") {
    const welcomeGreeting = messages[0].content;
    
    messagesContainer.innerHTML = `
      <div class="w-full max-w-[650px] mx-auto flex flex-col items-center justify-center py-8 md:py-16 text-center select-none font-sans px-4">
        <div class="w-14 h-14 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center p-3 mb-6 shadow-enterprise-md animate-pulse">
          <img src="/logo.png" alt="Sakra AI" class="w-full h-full object-contain" />
        </div>
        <h3 class="text-xl font-bold text-text-primary tracking-tight font-sans" data-i18n="copilot_title">Sakra AI Copilot</h3>
        <p class="text-xs text-text-secondary mt-1 font-semibold" data-i18n="copilot_subtitle">Enterprise Financial Intelligence</p>
        
        <div class="text-sm text-text-secondary mt-6 leading-relaxed font-medium bg-white/50 border border-slate-200/60 rounded-2xl p-5 text-left w-full shadow-enterprise-sm leading-relaxed border break-words">
          ${parseMarkdown(welcomeGreeting)}
        </div>

        <div class="w-full flex flex-col gap-3 mt-8 text-left">
          <span class="text-[9px] font-bold uppercase tracking-wider text-text-muted select-none" data-i18n="copilot_suggest_title">Suggested Tasks:</span>
          <div class="grid grid-cols-1 gap-2.5">
            ${suggestions.map((s, idx) => {
              const translatedTitle = window.t ? window.t(`copilot_suggest_${idx === 0 ? "repay" : idx === 1 ? "defaulters" : "interest"}`) || s.title : s.title;
              return `
                <button data-idx="${idx}" class="suggestion-btn flex items-center justify-between p-3.5 rounded-xl border border-slate-200 hover:border-primary/50 bg-white hover:bg-slate-50 transition-all text-xs font-semibold select-none cursor-pointer group text-text-secondary shadow-enterprise-sm">
                  <span>${translatedTitle}</span>
                  <i data-lucide="arrow-right" class="w-4 h-4 text-text-muted group-hover:text-primary transition-transform group-hover:translate-x-0.5"></i>
                </button>
              `;
            }).join("")}
          </div>
        </div>

        <div class="mt-8 bg-blue-50 border border-blue-100 rounded-2xl p-4 flex gap-3 text-left w-full shadow-enterprise-sm">
          <i data-lucide="shield-check" class="w-5 h-5 text-primary shrink-0 mt-0.5"></i>
          <div>
            <h4 class="text-[10px] font-bold uppercase tracking-wider text-blue-700 font-sans">SAFETY GUARANTEE</h4>
            <p class="text-[10px] text-text-secondary leading-relaxed font-bold mt-1">
              This AI interface enforces strict banking regulations. The agent uses secure API endpoints and has no direct data-modifying permissions.
            </p>
          </div>
        </div>
      </div>
    `;

    // Attach click events to suggestion buttons
    messagesContainer.querySelectorAll(".suggestion-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-idx"));
        handleSend(suggestions[idx].query);
      });
    });

  } else {
    // Render ChatGPT style messages
    messagesContainer.innerHTML = messages.map(msg => {
      const isAssistant = msg.role === "assistant";
      
      if (isAssistant) {
        return `
          <div class="flex gap-4 w-full items-start self-start">
            <div class="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/25 flex items-center justify-center text-primary shrink-0 shadow-enterprise-sm">
              <i data-lucide="bot" class="w-5 h-5"></i>
            </div>
            <div class="flex-1 glass-card bg-white/40 border border-slate-200/60 p-4 md:p-5 rounded-2xl shadow-enterprise-sm max-w-[85%] overflow-hidden">
              ${parseMarkdown(msg.content)}
            </div>
          </div>
        `;
      } else {
        return `
          <div class="flex gap-4 w-full justify-end self-end">
            <div class="bg-primary text-white p-3.5 md:p-4 rounded-2xl shadow-enterprise-md max-w-[90%] md:max-w-[70%] text-xs md:text-sm font-sans font-semibold leading-relaxed border-0 break-words select-text">
              ${parseMarkdown(msg.content)}
            </div>
            <div class="w-10 h-10 rounded-xl bg-slate-100 border border-border-default flex items-center justify-center text-text-secondary shrink-0 shadow-enterprise-sm">
              <i data-lucide="user" class="w-5 h-5"></i>
            </div>
          </div>
        `;
      }
    }).join("");
  }

  if (loadingAi) {
    messagesContainer.innerHTML += `
      <div class="flex gap-4 w-full items-start self-start" id="ai-loading-indicator">
        <div class="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/25 flex items-center justify-center text-primary shrink-0 shadow-enterprise-sm">
          <i data-lucide="bot" class="w-5 h-5"></i>
        </div>
        <div class="glass-card bg-white/40 border border-slate-200/60 p-4 rounded-2xl shadow-enterprise-sm flex items-center gap-1.5 select-none py-4">
          <span class="w-2 h-2 bg-primary/80 rounded-full typing-dot animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 bg-primary/80 rounded-full typing-dot animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 bg-primary/80 rounded-full typing-dot animate-bounce" style="animation-delay: 300ms"></span>
        </div>
      </div>
    `;
  }

  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Scroll viewport to bottom
  setTimeout(() => {
    const viewport = document.getElementById("chat-viewport");
    if (viewport) viewport.scrollTop = viewport.scrollHeight;
  }, 50);
}

async function handleSend(textToSend = null) {
  const query = textToSend || chatInput.value;
  if (!query.trim()) return;

  if (!textToSend) {
    chatInput.value = "";
  }

  // Add User message
  messages.push({ role: "user", content: query });
  renderMessages(true);

  // Disable form inputs
  chatInput.disabled = true;
  sendBtn.disabled = true;

  try {
    const res = await api.post("/copilot/chat", {
      query,
      session_id: sessionId
    });
    
    const payload = res.data || res;
    const assistantText = payload.response || "No response received.";
    messages.push({ role: "assistant", content: assistantText });

  } catch (err) {
    console.error("AI chat error:", err);
    messages.push({
      role: "assistant",
      content: "❌ **Failed to retrieve response.** The AI gateway encountered an error. Please verify the server connection."
    });
  } finally {
    chatInput.disabled = false;
    sendBtn.disabled = false;
    renderMessages(false);
    chatInput.focus();
  }
}

async function handleClearHistory() {
  try {
    await api.delete("/copilot/chat/history");
    const user = getCachedUser();
    messages = [{
      role: "assistant",
      content: `Chat session refreshed. How can I help you today, ${user?.username}?`
    }];
    renderMessages();
  } catch (err) {
    console.error("Failed to clear history:", err);
  }
}

// Start
setTimeout(init, 100);
