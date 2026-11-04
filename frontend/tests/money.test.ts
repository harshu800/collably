import { describe, expect, it } from "vitest";
import { formatINR, paiseFromRupees } from "@/lib/money";

describe("formatINR", () => {
  it("renders zero correctly", () => {
    expect(formatINR(0)).toMatch(/₹\s*0\.00/);
  });

  it("renders rupees with Indian grouping", () => {
    // 1234567 paise = 12,345.67 rupees
    const out = formatINR(1_234_567);
    expect(out).toContain("12,345.67");
  });

  it("rejects non-finite values", () => {
    expect(() => formatINR(Number.NaN)).toThrow();
    expect(() => formatINR(Number.POSITIVE_INFINITY)).toThrow();
  });
});

describe("paiseFromRupees", () => {
  it("converts a plain number", () => {
    expect(paiseFromRupees(10)).toBe(1000);
  });

  it("converts a decimal number", () => {
    expect(paiseFromRupees(12.34)).toBe(1234);
  });

  it("converts a decimal string", () => {
    expect(paiseFromRupees("12.34")).toBe(1234);
    expect(paiseFromRupees(" 7 ")).toBe(700);
  });

  it("rejects more than two decimal places", () => {
    expect(() => paiseFromRupees("12.345")).toThrow();
  });

  it("rejects non-numeric input", () => {
    expect(() => paiseFromRupees("abc")).toThrow();
  });
});
