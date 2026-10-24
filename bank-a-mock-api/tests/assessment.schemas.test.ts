import { describe, expect, it } from "vitest";
import { Check } from "typebox/value";
import { assessmentResponseSchema } from "../src/assessment/schemas.js";

const makeApproval = (rate: number) => ({ approved: true, offer: { amountCents: 100_000, termMonths: 12, monthlyInterestRateBps: rate, installmentCents: 9340 } });

describe("approval interest rate contract", () => {
  it.each([0, 180, 210, Number.MAX_SAFE_INTEGER])("accepts rate %s", (rate) => {
    expect(Check(assessmentResponseSchema, makeApproval(rate))).toBe(true);
  });

  it.each([-1, 0.5, Number.MAX_SAFE_INTEGER + 1])("rejects rate %s", (rate) => {
    expect(Check(assessmentResponseSchema, makeApproval(rate))).toBe(false);
  });
});
