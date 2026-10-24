import { describe, expect, it } from "vitest";
import { assessCredit } from "../src/assessment/service.js";
import { makeAssessmentRequest } from "./fixtures.js";

describe("Bank B assessment", () => {
  it("returns Bank B conditions for an eligible request", () => {
    expect(assessCredit(makeAssessmentRequest())).toEqual({
      decision: { code: "ACCEPTED", conditions: {
        principal_cents: 100_000, installments: 12, monthly_rate_bps: 210, payment_cents: 9514,
      } },
    });
  });

  it("rejects income below the minimum", () => {
    expect(assessCredit(makeAssessmentRequest({ income_cents: 199_999 }))).toEqual({ decision: { code: "DECLINED", reasons: ["LOW_INCOME"] } });
  });

  it("rejects amounts above its own limit", () => {
    expect(assessCredit(makeAssessmentRequest({}, { amount_cents: 3_000_001 }))).toEqual({ decision: { code: "DECLINED", reasons: ["LIMIT_EXCEEDED"] } });
  });

  it.each([11, 61])("rejects an unsupported term of %i months", (installments) => {
    expect(assessCredit(makeAssessmentRequest({}, { installments }))).toEqual({ decision: { code: "DECLINED", reasons: ["INVALID_TERM"] } });
  });

  it.each([12, 60])("accepts minimum income and a boundary term of %i months", (installments) => {
    expect(assessCredit(makeAssessmentRequest({ income_cents: 200_000 }, { installments })).decision.code).toBe("ACCEPTED");
  });

  it("accepts its exact amount limit with sufficient income", () => {
    expect(assessCredit(makeAssessmentRequest({ income_cents: 10_000_000 }, { amount_cents: 3_000_000 })).decision.code).toBe("ACCEPTED");
  });

  it("rejects installments above the margin", () => {
    expect(assessCredit(makeAssessmentRequest({}, { amount_cents: 3_000_000 }))).toEqual({ decision: { code: "DECLINED", reasons: ["INSUFFICIENT_MARGIN"] } });
  });

  it("accepts a rounded installment equal to the margin", () => {
    const result = assessCredit(makeAssessmentRequest({ income_cents: 200_000 }, { amount_cents: 525_534 }));
    expect(result.decision.code).toBe("ACCEPTED");
    if (result.decision.code === "ACCEPTED") expect(result.decision.conditions.payment_cents).toBe(50_000);
  });

  it("rejects a rounded installment one cent above the margin", () => {
    expect(assessCredit(makeAssessmentRequest({ income_cents: 200_000 }, { amount_cents: 525_544 }))).toEqual({ decision: { code: "DECLINED", reasons: ["INSUFFICIENT_MARGIN"] } });
  });

  it("collects initial policy failures", () => {
    expect(assessCredit(makeAssessmentRequest({ income_cents: 100_000 }, { amount_cents: 3_000_001, installments: 11 }))).toEqual({ decision: { code: "DECLINED", reasons: ["LOW_INCOME", "LIMIT_EXCEEDED", "INVALID_TERM"] } });
  });

  it("returns a positive payment for the minimum amount at every supported term", () => {
    for (let installments = 12; installments <= 60; installments++) {
      const result = assessCredit(makeAssessmentRequest({}, { amount_cents: 100, installments }));
      expect(result.decision.code).toBe("ACCEPTED");
      if (result.decision.code === "ACCEPTED") expect(result.decision.conditions.payment_cents).toBeGreaterThanOrEqual(1);
    }
  });

  it("is deterministic and preserves its input", () => {
    const input = makeAssessmentRequest();
    const original = structuredClone(input);
    expect(assessCredit(input)).toEqual(assessCredit(input));
    expect(input).toEqual(original);
  });
});

