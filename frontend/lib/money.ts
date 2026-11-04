/**
 * Money helpers. Money is handled exclusively as integer paise (1/100 INR).
 */

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Render a paise amount as ``₹1,23,456.00`` using Indian locale grouping. */
export function formatINR(paise: number): string {
  if (!Number.isFinite(paise)) {
    throw new TypeError("paise must be a finite integer");
  }
  const rupees = paise / 100;
  return INR.format(rupees);
}

/**
 * Convert a rupee value (user-entered) to integer paise.
 *
 * Accepts a plain number or a string. Trailing/leading whitespace is
 * trimmed. Non-numeric input or more than two decimal places throws.
 */
export function paiseFromRupees(rupees: number | string): number {
  if (typeof rupees === "number") {
    if (!Number.isFinite(rupees)) {
      throw new TypeError("rupees must be a finite number");
    }
    return Math.round(rupees * 100);
  }
  const trimmed = rupees.trim();
  if (!/^-?\d+(\.\d{1,2})?$/.test(trimmed)) {
    throw new TypeError(
      "rupees must be a decimal with at most two fractional digits",
    );
  }
  const parsed = Number.parseFloat(trimmed);
  return Math.round(parsed * 100);
}
