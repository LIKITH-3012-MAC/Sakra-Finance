import { getCachedUser } from "../auth.js";
import { setTheme } from "../theme.js";
import { API_BASE_URL, SOCKET_TIMEOUT_MS } from "../config.js";

const content = document.getElementById("settings-content");
const usernameText = document.getElementById("settings-username");
const roleText = document.getElementById("settings-role");
const apiUrlText = document.getElementById("settings-api-url");
const timeoutText = document.getElementById("settings-timeout");

const darkBtn = document.getElementById("theme-dark-btn");
const lightBtn = document.getElementById("theme-light-btn");
const oledBtn = document.getElementById("theme-oled-btn");

const enBtn = document.getElementById("lang-en-btn");
const teBtn = document.getElementById("lang-te-btn");

function init() {
  const user = getCachedUser();
  if (!user) return; // Wait for main.js

  usernameText.innerText = user.username;
  roleText.innerText = user.role;
  apiUrlText.innerText = API_BASE_URL;
  timeoutText.innerText = `${SOCKET_TIMEOUT_MS} ms`;

  // Theme button triggers
  darkBtn?.addEventListener("click", () => {
    setTheme("dark");
    highlightActiveTheme();
  });

  lightBtn?.addEventListener("click", () => {
    setTheme("light");
    highlightActiveTheme();
  });

  oledBtn?.addEventListener("click", () => {
    setTheme("oled");
    highlightActiveTheme();
  });

  // Language button triggers
  enBtn?.addEventListener("click", async () => {
    if (window.setAppLanguage) {
      await window.setAppLanguage("en");
      highlightActiveLanguage();
    }
  });

  teBtn?.addEventListener("click", async () => {
    if (window.setAppLanguage) {
      await window.setAppLanguage("te");
      highlightActiveLanguage();
    }
  });

  // Listen to global changes to keep settings highlighted
  window.addEventListener("language-changed", () => {
    highlightActiveLanguage();
  });

  highlightActiveTheme();
  highlightActiveLanguage();
  content?.classList.remove("hidden");
}

function highlightActiveTheme() {
  const current = localStorage.getItem("theme") || "dark";
  
  [darkBtn, lightBtn, oledBtn].forEach(btn => {
    if (!btn) return;
    btn.classList.add("sakra-btn-secondary");
    btn.classList.remove("border-primary", "bg-blue-50/20");
  });

  let activeBtn = darkBtn;
  if (current === "light") activeBtn = lightBtn;
  if (current === "oled") activeBtn = oledBtn;

  if (activeBtn) {
    activeBtn.classList.remove("sakra-btn-secondary");
    activeBtn.classList.add("border-primary", "bg-blue-50/20");
  }
}

function highlightActiveLanguage() {
  const current = localStorage.getItem("language") || "en";

  [enBtn, teBtn].forEach(btn => {
    if (!btn) return;
    btn.classList.add("sakra-btn-secondary");
    btn.classList.remove("border-primary", "bg-blue-50/20");
  });

  const activeBtn = current === "te" ? teBtn : enBtn;
  if (activeBtn) {
    activeBtn.classList.remove("sakra-btn-secondary");
    activeBtn.classList.add("border-primary", "bg-blue-50/20");
  }
}

// Start load
setTimeout(init, 100);
