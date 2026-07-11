import { login } from "../auth.js";
import { applyTheme } from "../theme.js";
import { initParticles } from "../particles.js";

// Initialize Particles background
initParticles("particlesCanvas");
applyTheme();

const form = document.getElementById("login-form");
const loginCard = document.getElementById("login-card");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const errorContainer = document.getElementById("error-message");
const capslockWarning = document.getElementById("capslock-warning");
const togglePasswordBtn = document.getElementById("toggle-password");
const submitBtn = document.getElementById("submit-btn");

// Caps Lock Detection
window.addEventListener("keyup", (e) => {
  if (e.getModifierState && e.getModifierState("CapsLock")) {
    capslockWarning?.classList.remove("hidden");
  } else {
    capslockWarning?.classList.add("hidden");
  }
});

// Toggle Password Field Visibility
togglePasswordBtn?.addEventListener("click", () => {
  const isPassword = passwordInput.type === "password";
  passwordInput.type = isPassword ? "text" : "password";
  const icon = togglePasswordBtn.querySelector("i");
  if (icon && window.lucide) {
    icon.setAttribute("data-lucide", isPassword ? "eye-off" : "eye");
    window.lucide.createIcons();
  }
});

// Submit Logic
const getLoadingTexts = () => [
  window.t ? window.t("login_loading_identity") : "Verifying system identity...",
  window.t ? window.t("login_loading_permissions") : "Checking gateway permissions...",
  window.t ? window.t("login_loading_session") : "Establishing secure session..."
];

form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (errorContainer) {
    errorContainer.classList.add("hidden");
    errorContainer.innerText = "";
  }

  const username = usernameInput.value;
  const password = passwordInput.value;

  if (!username || !password) {
    shakeCard();
    if (errorContainer) {
      errorContainer.innerText = window.t ? window.t("login_err_required") : "System credentials are required to request clear gateway access.";
      errorContainer.classList.remove("hidden");
    }
    return;
  }

  // Set Loading state
  submitBtn.disabled = true;
  let loaderIndex = 0;
  const list = getLoadingTexts();
  submitBtn.innerHTML = `
    <div class="flex items-center justify-center gap-2.5 font-sans">
      <i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i>
      <span id="loading-msg">${list[0]}</span>
    </div>
  `;
  if (window.lucide) window.lucide.createIcons();

  const msgSpan = document.getElementById("loading-msg");
  const interval = setInterval(() => {
    loaderIndex = (loaderIndex + 1) % list.length;
    if (msgSpan) {
      msgSpan.innerText = list[loaderIndex];
    }
  }, 900);

  try {
    const user = await login(username, password);
    clearInterval(interval);
    
    // Switch language to preferred user settings if defined
    if (user && user.preferred_language && window.setAppLanguage) {
      await window.setAppLanguage(user.preferred_language);
    }
    
    window.location.href = "/dashboard.html";
  } catch (err) {
    clearInterval(interval);
    shakeCard();
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span>${window.t ? window.t("login_btn_signin") : "Sign In To SAKRA"}</span>`;
    if (errorContainer) {
      errorContainer.innerText = err.detail || err.message || (window.t ? window.t("error_500_desc") : "Authentication failed.");
      errorContainer.classList.remove("hidden");
    }
  }
});

function shakeCard() {
  if (loginCard) {
    loginCard.classList.remove("sa-shake");
    // Trigger reflow to restart animation
    void loginCard.offsetWidth;
    loginCard.classList.add("sa-shake");
  }
}

// Setup Initial Icons
if (window.lucide) {
  window.lucide.createIcons();
}
