export function formatCurrency(val) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(val || 0);
}

export function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });
  } catch {
    return dateStr;
  }
}

export function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function formatInterestRate(rate) {
  const num = parseFloat(rate);
  if (isNaN(num)) return "0%";
  // Strip trailing zeros from DB DECIMAL(8,4) values like "17.0000" → "17"
  const cleaned = String(num);
  const parts = cleaned.split('.');
  if (parts.length === 1) {
    return `${parts[0]}%`;
  }
  const decimals = parts[1].length;
  if (decimals === 1) {
    return `${num.toFixed(2)}%`;
  }
  return `${num.toFixed(Math.min(decimals, 4))}%`;
}
