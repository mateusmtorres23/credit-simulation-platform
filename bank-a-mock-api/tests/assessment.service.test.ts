import { describe, expect, it } from "vitest";
import { assessCredit } from "../src/assessment/service.js";
import type { AssessmentRequest, RejectionReason } from "../src/assessment/schemas.js";
import { makeAssessmentRequest } from "./fixtures.js";

describe("assessCredit", () => {
  it("approves an eligible request with the estimated offer", () => {
    expect(assessCredit(makeAssessmentRequest())).toEqual({
      approved: true,
      offer: {
        amountCents: 100_000,
        termMonths: 12,
        monthlyInterestRateBps: 180,
        installmentCents: 9340,
      },
    });
  });

  const rejectionCases: {
    name: string;
    overrides: Partial<AssessmentRequest>;
    reason: RejectionReason;
  }[] = [
    { name: "income below minimum", overrides: { monthlyIncomeCents: 149_999 }, reason: "INCOME_BELOW_MINIMUM" },
    { name: "amount above limit", overrides: { requestedAmountCents: 5_000_001 }, reason: "AMOUNT_ABOVE_LIMIT" },
    { name: "term below minimum", overrides: { termMonths: 5 }, reason: "TERM_NOT_SUPPORTED" },
    { name: "term above maximum", overrides: { termMonths: 49 }, reason: "TERM_NOT_SUPPORTED" },
    { name: "installment above margin", overrides: { requestedAmountCents: 5_000_000, termMonths: 6 }, reason: "INSTALLMENT_ABOVE_MARGIN" },
  ];

  it.each(rejectionCases)("rejects $name", ({ overrides, reason }) => {
    expect(assessCredit(makeAssessmentRequest(overrides))).toEqual({
      approved: false,
      reasons: [reason],
    });
  });

  it("collects initial policy failures without calculating a margin decision", () => {
    expect(assessCredit(makeAssessmentRequest({
      monthlyIncomeCents: 100_000,
      requestedAmountCents: 5_000_001,
      termMonths: 5,
    }))).toEqual({
      approved: false,
      reasons: ["INCOME_BELOW_MINIMUM", "AMOUNT_ABOVE_LIMIT", "TERM_NOT_SUPPORTED"],
    });
  });

  it.each([6, 48])("accepts the term boundary of %i months and minimum income", (termMonths) => {
    expect(assessCredit(makeAssessmentRequest({ termMonths, monthlyIncomeCents: 150_000 })).approved).toBe(true);
  });

  it("accepts the maximum amount when income supports the installment", () => {
    expect(assessCredit(makeAssessmentRequest({ requestedAmountCents: 5_000_000, monthlyIncomeCents: 10_000_000 })).approved).toBe(true);
  });

  it("accepts a rounded installment equal to the margin", () => {
    const result = assessCredit(makeAssessmentRequest({
      requestedAmountCents: 253_774, termMonths: 6, monthlyIncomeCents: 150_000,
    }));
    expect(result.approved).toBe(true);
    if (result.approved) expect(result.offer.installmentCents).toBe(45_000);
  });

  it("rejects an installment just above the margin", () => {
    expect(assessCredit(makeAssessmentRequest({
      requestedAmountCents: 253_784, termMonths: 6, monthlyIncomeCents: 150_000,
    }))).toEqual({ approved: false, reasons: ["INSTALLMENT_ABOVE_MARGIN"] });
  });

  it("returns a positive installment for the minimum amount at every supported term", () => {
    for (let termMonths = 6; termMonths <= 48; termMonths++) {
      const result = assessCredit(makeAssessmentRequest({ requestedAmountCents: 100, termMonths }));
      expect(result.approved).toBe(true);
      if (result.approved) expect(result.offer.installmentCents).toBeGreaterThanOrEqual(1);
    }
  });

  it("returns the same result without mutating the request", () => {
    const request = makeAssessmentRequest();
    const original = structuredClone(request);
    const first = assessCredit(request);
    expect(assessCredit(request)).toEqual(first);
    expect(request).toEqual(original);
  });
});
