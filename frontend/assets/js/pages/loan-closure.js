import api from "../api.js";
import { formatCurrency } from "../helpers.js";

export class LoanClosureWizard {
  constructor(loanId, onComplete = null) {
    this.loanId = loanId;
    this.onComplete = onComplete;
    this.currentStep = 1;
    this.summaryData = null;
    this.enteredAmount = 0;
    this.passkey = "";
    this.modalEl = null;
  }

  async init() {
    try {
      this.showGlobalLoader();
      const res = await api.get(`/loan-closure/${this.loanId}/summary`);
      this.summaryData = res.data || res;
      this.enteredAmount = this.summaryData.remaining_balance;
      this.hideGlobalLoader();
      this.renderModal();
      this.showStep(1);
    } catch (err) {
      this.hideGlobalLoader();
      alert("Failed to load loan closure summary: " + (err.message || err));
    }
  }

  showGlobalLoader() {
    const loader = document.getElementById("global-page-loader");
    if (loader) loader.classList.remove("hidden");
  }

  hideGlobalLoader() {
    const loader = document.getElementById("global-page-loader");
    if (loader) loader.classList.add("hidden");
  }

  renderModal() {
    // Remove existing if any
    const existing = document.getElementById("loan-closure-wizard-overlay");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "loan-closure-wizard-overlay";
    overlay.className = "wizard-overlay";
    overlay.innerHTML = `
      <div class="wizard-modal glass-card">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-white/5 flex items-center justify-between">
          <h3 class="text-xs font-bold uppercase tracking-widest text-text-primary flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
            <span>Enterprise Settlement Wizard</span>
          </h3>
          <button type="button" class="text-text-muted hover:text-text-primary cursor-pointer border-0 bg-transparent" id="wizard-close-btn">
            <i data-lucide="x" class="w-4 h-4"></i>
          </button>
        </div>

        <!-- Body -->
        <div class="p-6 overflow-y-auto max-h-[75vh]" id="wizard-body-content">
          <!-- STEP 1: Settlement Summary -->
          <div class="wizard-step" data-step="1">
            <h4 class="text-sm font-bold text-text-primary mb-4 uppercase tracking-wider">Step 1: Ledger Account Summary</h4>
            <div class="grid grid-cols-2 gap-4 text-xs font-medium text-text-secondary bg-slate-950/40 p-4 border border-white/5 rounded-lg mb-4">
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Customer</span>
                <span class="text-text-primary font-bold">${this.summaryData.customer_name}</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Customer ID / Loan ID</span>
                <span class="text-text-primary font-mono font-bold">#${this.summaryData.customer_id} / #${this.summaryData.loan_id}</span>
              </div>
              <div class="h-px bg-white/5 col-span-2"></div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Principal</span>
                <span class="font-mono">${formatCurrency(this.summaryData.principal)}</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Interest</span>
                <span class="font-mono">${formatCurrency(this.summaryData.interest)}</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Total Repayable</span>
                <span class="font-mono text-text-primary font-bold">${formatCurrency(this.summaryData.total_repayable)}</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Collected Till Now</span>
                <span class="font-mono text-emerald-400 font-bold">${formatCurrency(this.summaryData.collected_till_now)}</span>
              </div>
              <div class="h-px bg-white/5 col-span-2"></div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Remaining Balance</span>
                <span class="font-mono text-rose-400 font-extrabold text-sm">${formatCurrency(this.summaryData.remaining_balance)}</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Expected Daily EMI</span>
                <span class="font-mono">${formatCurrency(this.summaryData.expected_daily_installment)}</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Equivalent Coverage</span>
                <span class="font-mono text-blue-400 font-bold">${this.summaryData.equivalent_paid_days} Days</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Ledger Delinquency</span>
                <span class="font-mono font-bold ${this.summaryData.days_behind_ahead > 0 ? 'text-rose-400' : 'text-emerald-400'}">
                  ${this.summaryData.days_behind_ahead > 0 ? `${this.summaryData.days_behind_ahead} Days Behind` : `${Math.abs(this.summaryData.days_behind_ahead)} Days Ahead`}
                </span>
              </div>
              <div class="h-px bg-white/5 col-span-2"></div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Credit Score</span>
                <span class="font-mono font-bold text-text-primary">${this.summaryData.credit_score}</span>
              </div>
              <div>
                <span class="text-[9px] uppercase tracking-wider text-text-muted block">Risk Level</span>
                <span class="font-bold text-text-primary">${this.summaryData.risk_score}</span>
              </div>
            </div>
          </div>

          <!-- STEP 2: Settlement Confirmation -->
          <div class="wizard-step" data-step="2">
            <h4 class="text-sm font-bold text-text-primary mb-4 uppercase tracking-wider text-center">Step 2: Settlement Confirmation</h4>
            <div class="flex flex-col items-center justify-center py-6 text-center">
              <span class="text-[10px] uppercase font-bold text-text-muted tracking-widest">REMAINING OUTSTANDING BALANCE</span>
              <span class="text-3xl font-extrabold text-rose-400 mt-2 font-mono">${formatCurrency(this.summaryData.remaining_balance)}</span>
              
              <div class="mt-8 p-4 bg-white/5 border border-white/5 rounded-lg w-full max-w-sm">
                <p class="text-xs text-text-secondary leading-relaxed font-semibold">
                  Has the customer paid the ENTIRE remaining balance to fully clear the ledger account?
                </p>
              </div>
            </div>
          </div>

          <!-- STEP 3: Cash Verification -->
          <div class="wizard-step" data-step="3">
            <h4 class="text-sm font-bold text-text-primary mb-4 uppercase tracking-wider">Step 3: Cash Verification</h4>
            <div class="flex flex-col gap-4 max-w-sm mx-auto">
              <div class="flex flex-col gap-1.5">
                <label class="text-[10px] font-bold uppercase tracking-wider text-text-muted">Final Amount Received (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  id="wizard-amount-input"
                  class="sakra-input-tactile font-mono text-center text-lg font-bold"
                  value="${this.summaryData.remaining_balance}"
                />
                <span class="text-[9px] text-text-muted text-center mt-1">Verify physical currency count before input.</span>
              </div>
            </div>
          </div>

          <!-- STEP 4: Validation Engine -->
          <div class="wizard-step" data-step="4">
            <h4 class="text-sm font-bold text-text-primary mb-4 uppercase tracking-wider">Step 4: Amount Validation Engine</h4>
            <div class="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-400 flex flex-col gap-3">
              <div class="flex items-center gap-2 font-bold uppercase tracking-wider">
                <i data-lucide="alert-triangle" class="w-5 h-5"></i>
                <span>Settlement Mismatch Detected</span>
              </div>
              <p class="leading-relaxed font-semibold">
                The entered amount does not match the ledger remaining balance. Please verify before continuing.
              </p>
              <div class="grid grid-cols-2 gap-3 mt-2 border-t border-white/5 pt-3 font-mono font-bold text-[11px]">
                <div>
                  <span class="text-[9px] uppercase tracking-wider text-text-muted block">Remaining Balance</span>
                  <span class="text-text-primary">${formatCurrency(this.summaryData.remaining_balance)}</span>
                </div>
                <div>
                  <span class="text-[9px] uppercase tracking-wider text-text-muted block">Entered Amount</span>
                  <span class="text-amber-300" id="wizard-step4-entered-text">₹0.00</span>
                </div>
              </div>
            </div>
          </div>

          <!-- STEP 5: Manager Authorization -->
          <div class="wizard-step" data-step="5">
            <h4 class="text-sm font-bold text-text-primary mb-4 uppercase tracking-wider text-center">Step 5: Manager Authorization</h4>
            <div class="flex flex-col gap-4 max-w-sm mx-auto py-4">
              <div class="flex flex-col gap-1.5 text-center">
                <label class="text-[10px] font-bold uppercase tracking-wider text-text-muted">Enter Loan Closure Passkey</label>
                <input
                  type="password"
                  id="wizard-passkey-input"
                  class="sakra-input-tactile text-center tracking-widest text-lg font-bold"
                  placeholder="••••••••"
                />
                <span id="wizard-auth-error" class="text-[9px] text-rose-500 font-bold uppercase tracking-wide mt-1 hidden"></span>
              </div>
            </div>
          </div>

          <!-- STEP 6: Final Confirmation -->
          <div class="wizard-step" data-step="6">
            <h4 class="text-sm font-bold text-text-primary mb-4 uppercase tracking-wider text-center text-rose-500">Step 6: Permanent Archival Confirmation</h4>
            <div class="p-5 bg-rose-500/10 border border-rose-500/20 rounded-lg text-xs text-rose-400 flex flex-col gap-3 max-w-md mx-auto">
              <div class="flex items-center gap-2 font-bold uppercase tracking-wider justify-center">
                <i data-lucide="shield-alert" class="w-5 h-5"></i>
                <span>IRREVERSIBLE ACTION</span>
              </div>
              <p class="leading-relaxed text-center font-semibold">
                This action will permanently close the customer's loan. No future payments can be recorded. Customer lifecycle history will remain archived.
              </p>
              <h5 class="text-center font-bold text-white mt-2 uppercase tracking-widest">CONTINUE CLOSURE?</h5>
            </div>
          </div>

          <!-- STEP 7: Success & Certificate -->
          <div class="wizard-step" data-step="7">
            <div class="flex flex-col items-center justify-center text-center py-4">
              <div class="success-checkmark-svg mb-4">
                <svg class="success-checkmark-svg" viewBox="0 0 52 52">
                  <circle class="success-checkmark-circle" cx="26" cy="26" r="25"/>
                  <path class="success-checkmark-check" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
                </svg>
              </div>
              <h4 class="text-base font-extrabold text-emerald-400 uppercase tracking-widest">Settlement Succeeded</h4>
              <p class="text-xs text-text-secondary mt-1 max-w-sm">The ledger account status is successfully updated to closed.</p>
              
              <div id="certificate-container" class="mt-6 w-full"></div>
            </div>
          </div>
        </div>

        <!-- Footer Buttons -->
        <div class="px-6 py-4 border-t border-white/5 flex items-center justify-between bg-slate-950/20" id="wizard-footer">
          <button type="button" class="px-4 py-2 border border-white/10 hover:bg-white/5 rounded text-[9px] uppercase tracking-widest font-bold text-text-secondary bg-transparent cursor-pointer disabled:opacity-30 disabled:pointer-events-none" id="wizard-prev-btn">
            Back
          </button>
          <div class="flex items-center gap-1" id="wizard-indicators">
            <!-- Step indicators loaded dynamically -->
          </div>
          <button type="button" class="sakra-btn-tactile bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded text-[9px] uppercase tracking-widest font-bold border-0 cursor-pointer flex items-center gap-1.5 shadow-md" id="wizard-next-btn">
            Continue
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    this.modalEl = overlay;

    // Attach actions
    document.getElementById("wizard-close-btn").addEventListener("click", () => this.destroy());
    document.getElementById("wizard-prev-btn").addEventListener("click", () => this.prevStep());
    document.getElementById("wizard-next-btn").addEventListener("click", () => this.nextStep());

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  showStep(stepNum) {
    this.currentStep = stepNum;
    const steps = this.modalEl.querySelectorAll(".wizard-step");
    steps.forEach(step => {
      if (parseInt(step.getAttribute("data-step")) === stepNum) {
        step.classList.add("active");
      } else {
        step.classList.remove("active");
      }
    });

    // Update buttons
    const prevBtn = document.getElementById("wizard-prev-btn");
    const nextBtn = document.getElementById("wizard-next-btn");
    const indicators = document.getElementById("wizard-indicators");

    if (stepNum === 1) {
      prevBtn.disabled = true;
    } else {
      prevBtn.disabled = false;
    }

    if (stepNum === 7) {
      prevBtn.classList.add("hidden");
      nextBtn.innerText = "Complete Lifecycle";
      indicators.innerHTML = "";
    } else {
      prevBtn.classList.remove("hidden");
      nextBtn.innerText = stepNum === 6 ? "Close Loan" : "Continue";
      
      // Indicators layout
      let indHtml = "";
      for (let i = 1; i <= 6; i++) {
        const activeClass = i === stepNum ? "bg-blue-500 scale-125" : "bg-white/20";
        indHtml += `<span class="w-1.5 h-1.5 rounded-full transition-all duration-200 ${activeClass}"></span>`;
      }
      indicators.innerHTML = indHtml;
    }

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  async nextStep() {
    if (this.currentStep === 1) {
      this.showStep(2);
    } else if (this.currentStep === 2) {
      this.showStep(3);
    } else if (this.currentStep === 3) {
      const inputVal = parseFloat(document.getElementById("wizard-amount-input").value);
      if (isNaN(inputVal) || inputVal < 0) {
        alert("Please enter a valid amount.");
        return;
      }
      this.enteredAmount = inputVal;
      if (this.enteredAmount !== this.summaryData.remaining_balance) {
        this.showStep(4);
      } else {
        this.showStep(5);
      }
    } else if (this.currentStep === 4) {
      this.showStep(5);
    } else if (this.currentStep === 5) {
      const passVal = document.getElementById("wizard-passkey-input").value;
      if (!passVal) {
        alert("Please enter the authorization passkey.");
        return;
      }
      this.passkey = passVal;
      
      // Call backend to verify auth
      try {
        const nextBtn = document.getElementById("wizard-next-btn");
        nextBtn.disabled = true;
        nextBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin mr-1"></i> Verifying...`;
        if (window.lucide) window.lucide.createIcons();

        await api.post(`/loan-closure/${this.loanId}/verify-auth`, { passkey: this.passkey });
        
        nextBtn.disabled = false;
        nextBtn.innerText = "Continue";
        this.showStep(6);
      } catch (err) {
        const nextBtn = document.getElementById("wizard-next-btn");
        nextBtn.disabled = false;
        nextBtn.innerText = "Continue";
        const errorMsg = err.message || (err.errors && err.errors.detail) || "Invalid passkey";
        const errorLabel = document.getElementById("wizard-auth-error");
        errorLabel.innerText = errorMsg;
        errorLabel.classList.remove("hidden");
      }
    } else if (this.currentStep === 6) {
      // Execute loan closure
      try {
        const nextBtn = document.getElementById("wizard-next-btn");
        nextBtn.disabled = true;
        nextBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin mr-1"></i> Finalizing Closure...`;
        if (window.lucide) window.lucide.createIcons();

        await api.post(`/loan-closure/${this.loanId}/close`, {
          passkey: this.passkey,
          final_amount_received: this.enteredAmount,
          remarks: `Settlement execution matching ledger record. Amount: ₹${this.enteredAmount}.`
        });

        this.showStep(7);
        this.loadCertificate();
      } catch (err) {
        const nextBtn = document.getElementById("wizard-next-btn");
        nextBtn.disabled = false;
        nextBtn.innerText = "Close Loan";
        alert("Failed to close loan: " + (err.message || err));
      }
    } else if (this.currentStep === 7) {
      this.destroy();
      if (this.onComplete) {
        this.onComplete();
      }
    }
  }

  prevStep() {
    if (this.currentStep === 4) {
      this.showStep(3);
    } else if (this.currentStep === 5) {
      if (this.enteredAmount !== this.summaryData.remaining_balance) {
        this.showStep(4);
      } else {
        this.showStep(3);
      }
    } else {
      this.showStep(this.currentStep - 1);
    }
  }

  async loadCertificate() {
    try {
      const res = await api.get(`/loan-closure/${this.loanId}/certificate`);
      const cert = res.data || res;
      const certContainer = document.getElementById("certificate-container");
      
      certContainer.innerHTML = `
        <div class="settlement-certificate p-5 border border-white/10 bg-slate-950/60 rounded-lg text-left text-xs text-text-secondary mt-4 font-sans select-none">
          <div class="text-center mb-4 pb-3 border-b border-white/5">
            <h5 class="text-sm font-extrabold text-text-primary tracking-widest">LOAN SETTLEMENT CERTIFICATE</h5>
            <span class="text-[9px] text-text-muted uppercase tracking-wider">SAKRA FINANCE CORP</span>
          </div>

          <div class="grid grid-cols-2 gap-3 font-medium">
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Borrower Name</span>
              <span class="text-text-primary font-bold">${cert.customer_name}</span>
            </div>
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Loan Reference ID</span>
              <span class="text-text-primary font-mono font-bold">#${cert.loan_id}</span>
            </div>
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Principal Repaid</span>
              <span class="font-mono">${formatCurrency(cert.principal)}</span>
            </div>
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Interest Repaid</span>
              <span class="font-mono">${formatCurrency(cert.interest)}</span>
            </div>
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Settlement Amount</span>
              <span class="font-mono text-emerald-400 font-bold">${formatCurrency(cert.settlement_amount)}</span>
            </div>
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Total Amount Paid</span>
              <span class="font-mono text-text-primary font-bold">${formatCurrency(cert.total_paid)}</span>
            </div>
            <div class="h-px bg-white/5 col-span-2 my-1"></div>
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Settlement Date</span>
              <span class="font-mono">${cert.settlement_date} ${cert.settlement_time}</span>
            </div>
            <div>
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Verification Code</span>
              <span class="text-blue-400 font-mono font-bold">${cert.digital_verification_id}</span>
            </div>
            <div class="col-span-2">
              <span class="text-[9px] uppercase tracking-wider text-text-muted block">Settlement Reference ID</span>
              <span class="font-mono font-bold text-text-primary break-all">${cert.settlement_reference}</span>
            </div>
          </div>

          <div class="mt-5 flex items-center justify-end gap-3 no-print">
            <button type="button" class="px-3 py-1.5 rounded border border-white/10 bg-slate-900 text-[10px] font-bold text-text-secondary cursor-pointer hover:bg-slate-800 transition-all flex items-center gap-1" id="cert-print-btn">
              <i data-lucide="printer" class="w-3.5 h-3.5"></i> Print
            </button>
            <button type="button" class="sakra-btn-tactile bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded text-[10px] font-bold cursor-pointer transition-all flex items-center gap-1" id="cert-download-btn">
              <i data-lucide="download" class="w-3.5 h-3.5"></i> Download PDF
            </button>
          </div>
        </div>
      `;

      document.getElementById("cert-print-btn").addEventListener("click", () => window.print());
      document.getElementById("cert-download-btn").addEventListener("click", () => window.print()); // Prints to PDF using native printing

      if (window.lucide) {
        window.lucide.createIcons();
      }
    } catch (err) {
      alert("Failed to load digital certificate: " + err.message);
    }
  }

  destroy() {
    if (this.modalEl) {
      this.modalEl.remove();
      this.modalEl = null;
    }
  }
}

export async function renderActivityTimeline(customerId, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = `<div class="flex justify-center items-center py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin text-primary"></i></div>`;
  if (window.lucide) window.lucide.createIcons();

  try {
    const res = await api.get(`/loan-closure/customers/${customerId}/timeline`);
    const events = res.data?.events || [];

    if (events.length === 0) {
      container.innerHTML = `<div class="text-center py-10 text-xs text-text-muted">No activity records logged.</div>`;
      return;
    }

    container.innerHTML = `
      <div class="activity-timeline">
        ${events.map(event => {
          let dotClass = "timeline-dot border-white/20";
          let icon = "activity";
          
          if (event.type === "LOAN_CLOSURE") {
            dotClass = "timeline-dot closure";
            icon = "shield-check";
          } else if (event.type === "PAYMENT") {
            dotClass = "timeline-dot payment";
            icon = "wallet";
          } else if (event.type === "AUDIT_LOG") {
            dotClass = "timeline-dot audit";
            icon = "fingerprint";
          } else if (event.type === "NOTIFICATION") {
            icon = "bell";
          } else if (event.type === "CREDIT_SCORE") {
            icon = "trending-up";
          }

          const eventTime = new Date(event.timestamp).toLocaleString();

          return `
            <div class="timeline-event pl-4 select-none">
              <span class="${dotClass}">
                <i data-lucide="${icon}" class="w-3 h-3 text-white"></i>
              </span>
              <div class="glass-card bg-slate-950/20 border-white/5 p-4 rounded-lg flex flex-col gap-1.5">
                <div class="flex items-center justify-between gap-4">
                  <span class="text-xs font-bold text-text-primary uppercase tracking-wide">${event.title}</span>
                  <span class="text-[9px] font-mono text-text-muted">${eventTime}</span>
                </div>
                <p class="text-xs text-text-secondary leading-relaxed">${event.description}</p>
                <div class="flex items-center justify-between text-[9px] text-text-muted font-bold mt-1 font-mono">
                  <span>Actor: ${event.actor || "System"}</span>
                  ${event.metadata && event.metadata.ip ? `<span>IP: ${event.metadata.ip}</span>` : ""}
                </div>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;

    if (window.lucide) {
      window.lucide.createIcons();
    }
  } catch (err) {
    container.innerHTML = `<div class="text-center py-10 text-xs text-rose-400">Failed to load activity history: ${err.message || err}</div>`;
  }
}
