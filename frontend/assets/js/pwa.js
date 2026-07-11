/**
 * SAKRA FINANCE — PWA Service Worker Registration & Install Prompt
 * Registers the service worker, handles auto-updates, and provides install prompts.
 */

let deferredPrompt = null;
let refreshing = false;

// ── Register Service Worker with Update Detection ──────────────────
export function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
          scope: '/',
        });
        console.log('[PWA] Service Worker registered with scope:', registration.scope);

        // If there's already a waiting worker on load, prompt to update
        if (registration.waiting) {
          showUpdatePrompt(registration.waiting);
        }

        // Listen for new service workers installing
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              // Show prompt when the new worker has finished installing and is waiting
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                showUpdatePrompt(newWorker);
              }
            });
          }
        });

      } catch (error) {
        console.error('[PWA] Service Worker registration failed:', error);
      }
    });

    // Reload the page once the new service worker takes over control
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!refreshing) {
        refreshing = true;
        window.location.reload();
      }
    });
  }
}

// ── Update Notification UI ───────────────────────────────────────────
function showUpdatePrompt(waitingWorker) {
  // Prevent duplicate prompts
  if (document.getElementById('sakra-pwa-update-banner')) return;

  const banner = document.createElement('div');
  banner.id = 'sakra-pwa-update-banner';
  banner.innerHTML = `
    <div class="pwa-update-content">
      <div class="pwa-update-text">
        <strong>A new version of Sakra Finance is available.</strong>
        <span>Refresh to load the latest enterprise configurations.</span>
      </div>
      <div class="pwa-update-actions">
        <button id="pwa-update-btn" class="pwa-btn-update">Refresh</button>
        <button id="pwa-update-close-btn" class="pwa-btn-dismiss" aria-label="Dismiss">✕</button>
      </div>
    </div>
  `;

  document.body.appendChild(banner);

  // Animate in
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      banner.classList.add('pwa-banner-visible');
    });
  });

  // Attach handlers
  document.getElementById('pwa-update-btn').addEventListener('click', () => {
    waitingWorker.postMessage({ type: 'SKIP_WAITING' });
    banner.remove();
  });

  document.getElementById('pwa-update-close-btn').addEventListener('click', () => {
    banner.remove();
  });
}

// ── Install Promotion (Chrome Install Button) ──────────────────────
export function initInstallPrompt() {
  // Capture the beforeinstallprompt event
  window.addEventListener('beforeinstallprompt', (e) => {
    console.log('[PWA] Chrome beforeinstallprompt event captured');
    e.preventDefault();
    deferredPrompt = e;
    showInstallBanner();
  });

  // Hide banner once app is installed
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    hideInstallBanner();
    console.log('[PWA] App installed successfully');
  });

  // Check if running in standalone mode (already installed)
  if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone) {
    return; // Already installed, don't show prompt
  }
}

function showInstallBanner() {
  // Don't show if already dismissed in this session
  if (sessionStorage.getItem('sakra-pwa-dismissed')) return;

  // Don't show if already installed
  if (window.matchMedia('(display-mode: standalone)').matches) return;

  // Prevent duplicate banners
  if (document.getElementById('sakra-pwa-install-banner')) return;

  // Create the install banner
  const banner = document.createElement('div');
  banner.id = 'sakra-pwa-install-banner';
  banner.innerHTML = `
    <div class="pwa-install-content">
      <div class="pwa-install-icon">
        <img src="/icons/icon-96x96.png" alt="Sakra Finance" width="40" height="40" />
      </div>
      <div class="pwa-install-text">
        <strong>Install Sakra Finance</strong>
        <span>Add to home screen for the best experience</span>
      </div>
      <div class="pwa-install-actions">
        <button id="pwa-install-btn" class="pwa-btn-install">Install</button>
        <button id="pwa-dismiss-btn" class="pwa-btn-dismiss" aria-label="Dismiss">✕</button>
      </div>
    </div>
  `;

  document.body.appendChild(banner);

  // Animate in
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      banner.classList.add('pwa-banner-visible');
    });
  });

  // Attach handlers
  document.getElementById('pwa-install-btn').addEventListener('click', handleInstallClick);
  document.getElementById('pwa-dismiss-btn').addEventListener('click', () => {
    sessionStorage.setItem('sakra-pwa-dismissed', '1');
    hideInstallBanner();
  });
}

function hideInstallBanner() {
  const banner = document.getElementById('sakra-pwa-install-banner');
  if (banner) {
    banner.classList.remove('pwa-banner-visible');
    setTimeout(() => banner.remove(), 350);
  }
}

async function handleInstallClick() {
  if (!deferredPrompt) return;

  deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  console.log('[PWA] Install prompt outcome:', outcome);
  deferredPrompt = null;
  hideInstallBanner();
}
