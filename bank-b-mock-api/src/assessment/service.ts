import type { AssessmentRequest, AssessmentResponse, RejectionReason } from "./schemas.js";

const MIN_INCOME_CENTS = 200_000;
const MAX_AMOUNT_CENTS = 3_000_000;
const MIN_TERM_MONTHS = 12;
const MAX_TERM_MONTHS = 60;
const MONTHLY_RATE_BPS = 210;
const MAX_COMMITMENT_PERCENT = 25;

export function assessCredit(input: AssessmentRequest): AssessmentResponse {
  const reasons: RejectionReason[] = [];
  const { applicant, loan } = input;

  if (applicant.income_cents < MIN_INCOME_CENTS) reasons.push("LOW_INCOME");
  if (loan.amount_cents > MAX_AMOUNT_CENTS) reasons.push("LIMIT_EXCEEDED");
  if (loan.installments < MIN_TERM_MONTHS || loan.installments > MAX_TERM_MONTHS) {
    reasons.push("INVALID_TERM");
  }

  if (reasons.length > 0) return { decision: { code: "DECLINED", reasons } };

  const monthlyRate = MONTHLY_RATE_BPS / 10_000;
  const paymentCents = Math.round(
    (loan.amount_cents * monthlyRate) / (1 - (1 + monthlyRate) ** -loan.installments),
  );
  const marginCents = Math.floor((applicant.income_cents * MAX_COMMITMENT_PERCENT) / 100);

  if (paymentCents > marginCents) {
    return { decision: { code: "DECLINED", reasons: ["INSUFFICIENT_MARGIN"] } };
  }

  return {
    decision: {
      code: "ACCEPTED",
      conditions: {
        principal_cents: loan.amount_cents,
        installments: loan.installments,
        monthly_rate_bps: MONTHLY_RATE_BPS,
        payment_cents: paymentCents,
      },
    },
  };
}
