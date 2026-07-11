import api from "./api.js";

let translations = {};
let currentLanguage = "en";

// Lazy loaders using dynamic ES imports
const localeLoaders = {
  en: () => import("../../src/locales/en.json"),
  te: () => import("../../src/locales/te.json")
};

/**
 * Load a translation pack by language code.
 */
export async function loadLanguage(lang) {
  if (translations[lang]) {
    return translations[lang];
  }
  try {
    let data;
    if (localeLoaders[lang]) {
      const module = await localeLoaders[lang]();
      data = module.default;
    } else {
      // Direct HTTP fetch fallback
      const res = await fetch(`/src/locales/${lang}.json`);
      data = await res.json();
    }
    translations[lang] = data;
    return data;
  } catch (err) {
    console.error(`Failed to load translation pack for lang: ${lang}`, err);
    return null;
  }
}

/**
 * Get translation for a key. Falls back to English, then to key itself.
 */
export function t(key) {
  const trans = translations[currentLanguage];
  if (trans && trans[key] !== undefined) {
    return trans[key];
  }
  const engTrans = translations["en"];
  if (engTrans && engTrans[key] !== undefined) {
    return engTrans[key];
  }
  return key;
}

/**
 * Walks the DOM and translates all elements containing data-i18n attributes.
 */
export function translatePage() {
  // 1. Element text content translations
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    const translation = t(key);
    if (!translation) return;

    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
      el.setAttribute("placeholder", translation);
    } else {
      // Find first non-empty text node child to translate text without destroying sub-elements (like <i> icons)
      let textNode = Array.from(el.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0);
      if (textNode) {
        textNode.textContent = translation;
      } else if (el.children.length === 0) {
        el.textContent = translation;
      }
    }
  });

  // 2. Input placeholder explicit translations
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.getAttribute("data-i18n-placeholder");
    const translation = t(key);
    if (translation) {
      el.setAttribute("placeholder", translation);
    }
  });

  // 3. Tooltip / title translations
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const key = el.getAttribute("data-i18n-title");
    const translation = t(key);
    if (translation) {
      el.setAttribute("title", translation);
    }
  });

  // 4. Page title update
  const headTitle = document.querySelector("title");
  if (headTitle) {
    const titleKey = headTitle.getAttribute("data-i18n");
    if (titleKey) {
      const trans = t(titleKey);
      if (trans) {
        document.title = trans;
      }
    }
  }
}

/**
 * Switch active application language. Saves settings and notifies pages.
 */
export async function setAppLanguage(lang) {
  currentLanguage = lang;
  localStorage.setItem("language", lang);
  window.currentLanguage = lang;

  // Verify language pack is loaded
  await loadLanguage(lang);

  // Apply layout attributes (LTR/RTL support included)
  const rtlLanguages = ["ar", "ur", "he", "fa"];
  const isRtl = rtlLanguages.includes(lang);
  document.documentElement.dir = isRtl ? "rtl" : "ltr";
  document.documentElement.lang = lang;

  // Run DOM translations
  translatePage();

  // Re-instantiate icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Sync DB language preference asynchronously
  const cachedUserStr = localStorage.getItem("user");
  if (cachedUserStr) {
    try {
      const user = JSON.parse(cachedUserStr);
      if (user.preferred_language !== lang) {
        user.preferred_language = lang;
        localStorage.setItem("user", JSON.stringify(user));
        
        await api.patch("/auth/me/language", { preferred_language: lang });
      }
    } catch (e) {
      console.warn("Could not sync language preference to server profile:", e);
    }
  }

  // Update dynamic helpers in window scope
  setupLocaleAwareHelpers();

  // Dispatch custom language change event to trigger re-renders on page scripts
  window.dispatchEvent(new CustomEvent("language-changed", { detail: lang }));
}

/**
 * Configure locale-aware formatting helpers for dates & numbers.
 */
function setupLocaleAwareHelpers() {
  const currentLocale = currentLanguage === "te" ? "te-IN" : "en-IN";

  window.formatCurrency = function(val) {
    return new Intl.NumberFormat(currentLocale, {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(val || 0);
  };

  window.formatDate = function(dateStr) {
    if (!dateStr) return "—";
    try {
      let target = dateStr;
      if (typeof dateStr === "string" && dateStr.length === 10) {
        target = `${dateStr}T00:00:00`;
      }
      return new Date(target).toLocaleDateString(currentLocale, {
        year: "numeric",
        month: "short",
        day: "numeric",
        timeZone: "Asia/Kolkata"
      });
    } catch {
      return dateStr;
    }
  };

  window.formatDateTime = function(dateStr) {
    if (!dateStr) return "—";
    try {
      return new Date(dateStr).toLocaleString(currentLocale, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
        timeZone: "Asia/Kolkata"
      }) + " IST";
    } catch {
      return dateStr;
    }
  };
}

/**
 * Initialize translation system: Profile -> LocalStorage -> Browser Language.
 */
export async function initI18n(user) {
  let lang = "en";

  if (user && user.preferred_language) {
    lang = user.preferred_language;
  } else {
    const localLang = localStorage.getItem("language");
    if (localLang) {
      lang = localLang;
    } else {
      const browserLang = navigator.language || navigator.userLanguage;
      if (browserLang && browserLang.startsWith("te")) {
        lang = "te";
      }
    }
  }

  // Register methods globally
  window.t = t;
  window.setAppLanguage = setAppLanguage;
  window.translatePage = translatePage;
  window.currentLanguage = lang;

  // Load fallback English translation
  await loadLanguage("en");
  
  // Set preferred language
  await setAppLanguage(lang);
}
