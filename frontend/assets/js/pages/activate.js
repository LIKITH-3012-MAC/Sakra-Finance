/**
 * Account Activation Controller
 * Validates invitation tokens, enforces password policies, and activates employee accounts.
 */

document.addEventListener("DOMContentLoaded", async () => {
  const loadingState = document.getElementById("loading-state");
  const errorState = document.getElementById("error-state");
  const errorDetail = document.getElementById("error-detail");
  const activateCard = document.getElementById("activate-card");
  const activateForm = document.getElementById("activate-form");
  const activateError = document.getElementById("activate-error");
  const activateBtn = document.getElementById("activate-btn");

  // Invitation info display
  const inviteNameEl = document.getElementById("invite-name");
  const inviteRoleEl = document.getElementById("invite-role");
  const inviteDeptEl = document.getElementById("invite-dept");

  // Password strength elements
  const newPasswordInput = document.getElementById("new-password");
  const strengthBar = document.getElementById("strength-bar");
  const strengthLabel = document.getElementById("strength-label");

  // Extract token from URL
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");

  if (!token) {
    showError("No activation token was provided in the URL.");
    return;
  }

  // Step 1: Validate the invitation token against the backend
  try {
    const res = await fetch(`/api/v1/auth/invite-validate?token=${encodeURIComponent(token)}`);
    const data = await res.json();

    if (!res.ok || !data.success) {
      showError(data.detail || data.message || "Invalid or expired invitation token.");
      return;
    }

    // Token is valid — show the activation form
    inviteNameEl.innerText = data.data.name;
    inviteRoleEl.innerText = data.data.role;
    inviteDeptEl.innerText = data.data.department;

    loadingState.classList.add("hidden");
    activateCard.classList.remove("hidden");

    // Initialize Lucide icons for newly rendered elements
    if (window.lucide) window.lucide.createIcons();

  } catch (err) {
    showError("Could not connect to the SAKRA authentication server.");
    return;
  }

  // Step 2: Password strength meter (real-time)
  newPasswordInput.addEventListener("input", () => {
    const val = newPasswordInput.value;
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

  // Step 3: Form submission — activate the account
  activateForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    activateError.classList.add("hidden");

    const tempPassword = document.getElementById("temp-password").value;
    const newPassword = newPasswordInput.value;
    const confirmPassword = document.getElementById("confirm-password").value;

    // Client-side validation
    if (newPassword !== confirmPassword) {
      showFormError("New password and confirmation do not match.");
      return;
    }

    if (newPassword.length < 12) {
      showFormError("Password must be at least 12 characters long.");
      return;
    }

    // Disable submit
    activateBtn.disabled = true;
    activateBtn.innerHTML = `
      <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
      ${window.t ? window.t("please_wait") : "Activating..."}
    `;

    try {
      const res = await fetch("/api/v1/auth/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: token,
          temporary_password: tempPassword,
          new_password: newPassword,
        }),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        showFormError(data.detail || data.message || "Activation failed.");
        activateBtn.disabled = false;
        activateBtn.innerHTML = `<i data-lucide="check-circle" class="w-4 h-4"></i> ${window.t ? window.t("activate_btn_submit") : "Activate Account"}`;
        if (window.lucide) window.lucide.createIcons();
        return;
      }

      // Store tokens and redirect to dashboard (fixed local storage keys)
      const accessToken = data.data?.token?.access_token;
      const userData = data.data?.user;

      if (accessToken) {
        localStorage.setItem("access_token", accessToken);
      }
      if (userData) {
        localStorage.setItem("user", JSON.stringify(userData));
        if (userData.preferred_language && window.setAppLanguage) {
          await window.setAppLanguage(userData.preferred_language);
        }
      }

      // Redirect to dashboard
      window.location.href = "/dashboard.html";

    } catch (err) {
      showFormError("Network error. Please check your connection and try again.");
      activateBtn.disabled = false;
      activateBtn.innerHTML = `<i data-lucide="check-circle" class="w-4 h-4"></i> ${window.t ? window.t("activate_btn_submit") : "Activate Account"}`;
      if (window.lucide) window.lucide.createIcons();
    }
  });

  function showError(message) {
    loadingState.classList.add("hidden");
    errorDetail.innerText = message;
    errorState.classList.remove("hidden");
    if (window.lucide) window.lucide.createIcons();
  }

  function showFormError(message) {
    activateError.innerText = message;
    activateError.classList.remove("hidden");
  }
});
