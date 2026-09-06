import { MoneyValue } from "./types";

/**
 * Formats integer minor units (paise, cents) to standard currency display.
 * Never uses floating-point arithmetic for mathematical calculations.
 */
export function formatMoney(money?: MoneyValue): string {
  if (!money) return "—";
  const majorUnits = (money.amount / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `₹${majorUnits} ${money.currency}`;
}

export function formatTimestamp(isoString?: string): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString("en-IN", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    });
  } catch {
    return isoString;
  }
}

export function formatDateFull(isoString?: string): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    return d.toLocaleString("en-IN", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function truncateHash(hash?: string, head = 8, tail = 6): string {
  if (!hash) return "—";
  if (hash.length <= head + tail) return hash;
  return `${hash.slice(0, head)}...${hash.slice(-tail)}`;
}
