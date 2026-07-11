export function applyTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  if (saved === "dark") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", saved);
  }
}

export function setTheme(themeName) {
  if (themeName === "dark") {
    localStorage.setItem("theme", "dark");
    document.documentElement.removeAttribute("data-theme");
  } else {
    localStorage.setItem("theme", themeName);
    document.documentElement.setAttribute("data-theme", themeName);
  }
}

// Auto-run on load
applyTheme();
