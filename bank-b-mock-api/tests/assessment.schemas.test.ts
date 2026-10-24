import { describe, expect, it } from "vitest";
import { Check } from "typebox/value";
import { assessmentResponseSchema } from "../src/assessment/schemas.js";

const makeApproval = (rate: number) => ({ decision: { code: "ACCEPTED", conditions: { principal_cents: 100_000, installments: 12, monthly_rate_bps: rate, payment_cents: 9514 } } });

describe("approval interest rate contract", () => {
  it.each([0, 180, 210, Number.MAX_SAFE_INTEGER])("accepts rate %s", (rate) => {
    expect(Check(assessmentResponseSchema, makeApproval(rate))).toBe(true);
  });

  it.each([-1, 0.5, Number.MAX_SAFE_INTEGER + 1])("rejects rate %s", (rate) => {
    expect(Check(assessmentResponseSchema, makeApproval(rate))).toBe(false);
  });
});
