import api from "../api.js";
import { applyTheme } from "../theme.js";
import { initParticles } from "../particles.js";

// Initialize particles and themes
initParticles("particlesCanvas");
applyTheme();

// Form elements
const card = document.getElementById("forgot-card");
const emailForm = document.getElementById("forgot-form-email");
const otpForm = document.getElementById("forgot-form-otp");
const resetForm = document.getElementById("forgot-form-reset");
const statusMsg = document.getElementById("status-message");

// Inputs
const emailInput = document.getElementById("email");
const otpInput = document.getElementById("otp");
const newPassInput = document.getElementById("new-password");
const confirmPassInput = document.getElementById("confirm-password");

// Buttons
const sendOtpBtn = document.getElementById("send-otp-btn");
const verifyOtpBtn = document.getElementById("verify-otp-btn");
const resetBtn = document.getElementById("reset-password-btn");

// Password strength meter
const strengthBar = document.getElementById("strength-bar");
const strengthLabel = document.getElementById("strength-label");

// State
let flowEmail = "";
let resetToken = "";

// Show message helper
function showMessage(msg, isError = false) {
  statusMsg.classList.remove("hidden", "bg-rose-950/30", "border-rose-900/50", "text-rose-300", "bg-emerald-950/30", "border-emerald-900/50", "text-emerald-300");
  statusMsg.innerText = msg;
  if (isError) {
    statusMsg.classList.add("bg-rose-950/30", "border-rose-900/50", "text-rose-300", "border");
  } else {
    statusMsg.classList.add("bg-emerald-950/30", "border-emerald-900/50", "text-emerald-300", "border");
  }
}

// Shake card helper
function shakeCard() {
  if (card) {
    card.classList.remove("sa-shake");
    void card.offsetWidth; // Trigger reflow
    card.classList.add("sa-shake");
  }
}

// Password strength calculator
newPassInput.addEventListener("input", () => {
  const val = newPassInput.value;
  let score = 0;
  if (val.length >= 8) score++;
  if (val.length >= 12) score++;
  if (/[A-Z]/.test(val)) score++;
  if (/[a-z]/.test(val)) score++;
  if (/\d/.test(val)) score++;
  if (/[!@#$%^&*(),.?":{}|<>]/.test(val)) score++;

  const percentage = Math.min(Math.round((score / 6) * 100), 100);
  strengthBar.style.width = percentage + "%";

  if (score <= 2) {
    strengthBar.className = "h-full rounded-full bg-rose-500 transition-all duration-300";
    strengthLabel.innerText = window.t ? window.t("activate_strength_weak") : "Weak";
    strengthLabel.className = "text-[9px] text-rose-400 font-bold uppercase tracking-wider mt-0.5";
  } else if (score <= 4) {
    strengthBar.className = "h-full rounded-full bg-amber-500 transition-all duration-300";
    strengthLabel.innerText = window.t ? window.t("activate_strength_medium") : "Medium";
    strengthLabel.className = "text-[9px] text-amber-400 font-bold uppercase tracking-wider mt-0.5";
  } else {
    strengthBar.className = "h-full rounded-full bg-emerald-500 transition-all duration-300";
    strengthLabel.innerText = window.t ? window.t("activate_strength_strong") : "Strong";
    strengthLabel.className = "text-[9px] text-emerald-400 font-bold uppercase tracking-wider mt-0.5";
  }
});

// Stage 1 submit: Send OTP
emailForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = emailInput.value.trim();
  if (!email) return;

  sendOtpBtn.disabled = true;
  const originalHtml = sendOtpBtn.innerHTML;
  sendOtpBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline mr-1"></i> Sending...`;
  if (window.lucide) window.lucide.createIcons();

  try {
    const res = await api.post("/auth/forgot-password", { email });
    flowEmail = email;
    showMessage(window.t ? window.t("forgot_success_otp_sent") : "Verification code sent to email.");
    emailForm.classList.add("hidden");
    otpForm.classList.remove("hidden");
    if (window.lucide) window.lucide.createIcons();
  } catch (err) {
    shakeCard();
    showMessage(err.detail || err.message || "Failed to dispatch verification code.", true);
    sendOtpBtn.disabled = false;
    sendOtpBtn.innerHTML = originalHtml;
    if (window.lucide) window.lucide.createIcons();
  }
});

// Stage 2 submit: Verify OTP
otpForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const otp = otpInput.value.trim();
  if (!otp) return;

  verifyOtpBtn.disabled = true;
  const originalHtml = verifyOtpBtn.innerHTML;
  verifyOtpBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline mr-1"></i> Verifying...`;
  if (window.lucide) window.lucide.createIcons();

  try {
    const res = await api.post("/auth/verify-otp", { email: flowEmail, otp });
    resetToken = res.data.reset_token;
    showMessage(window.t ? window.t("forgot_success_otp_verified") : "OTP verified successfully. Create new credentials.");
    otpForm.classList.add("hidden");
    resetForm.classList.remove("hidden");
    if (window.lucide) window.lucide.createIcons();
  } catch (err) {
    shakeCard();
    showMessage(err.detail || err.message || "Incorrect verification code.", true);
    verifyOtpBtn.disabled = false;
    verifyOtpBtn.innerHTML = originalHtml;
    if (window.lucide) window.lucide.createIcons();
  }
});

// Stage 3 submit: Reset Password
resetForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = newPassInput.value;
  const confirm = confirmPassInput.value;

  if (password !== confirm) {
    shakeCard();
    showMessage("Passwords do not match.", true);
    return;
  }
  if (password.length < 12) {
    shakeCard();
    showMessage("Password must be at least 12 characters.", true);
    return;
  }

  resetBtn.disabled = true;
  const originalHtml = resetBtn.innerHTML;
  resetBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline mr-1"></i> Resetting...`;
  if (window.lucide) window.lucide.createIcons();

  try {
    await api.post("/auth/reset-password", {
      email: flowEmail,
      token: resetToken,
      new_password: password
    });
    showMessage(window.t ? window.t("forgot_success_reset") : "Password reset successfully. Redirecting to login...");
    resetForm.classList.add("hidden");
    setTimeout(() => {
      window.location.href = "/login.html";
    }, 2000);
  } catch (err) {
    shakeCard();
    showMessage(err.detail || err.message || "Failed to update password.", true);
    resetBtn.disabled = false;
    resetBtn.innerHTML = originalHtml;
    if (window.lucide) window.lucide.createIcons();
  }
});

// Initialize icons on load
if (window.lucide) {
  window.lucide.createIcons();
}
