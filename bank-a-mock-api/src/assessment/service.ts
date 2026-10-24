import type {
  AssessmentRequest,
  AssessmentResponse,
  RejectionReason,
} from "./schemas.js";

const MIN_MONTHLY_INCOME_CENTS = 150_000;
const MAX_AMOUNT_CENTS = 5_000_000;
const MIN_TERM_MONTHS = 6;
const MAX_TERM_MONTHS = 48;
const MONTHLY_INTEREST_RATE_BPS = 180;
const MAX_INCOME_COMMITMENT_PERCENT = 30;

function calculateInstallmentCents(amountCents: number, termMonths: number): number {
  const monthlyRate = MONTHLY_INTEREST_RATE_BPS / 10_000;
  const installment =
    (amountCents * monthlyRate) / (1 - (1 + monthlyRate) ** -termMonths);

  return Math.round(installment);
}

export function assessCredit(input: AssessmentRequest): AssessmentResponse {
  const reasons: RejectionReason[] = [];

  if (input.monthlyIncomeCents < MIN_MONTHLY_INCOME_CENTS) {
    reasons.push("INCOME_BELOW_MINIMUM");
  }

  if (input.requestedAmountCents > MAX_AMOUNT_CENTS) {
    reasons.push("AMOUNT_ABOVE_LIMIT");
  }

  if (input.termMonths < MIN_TERM_MONTHS || input.termMonths > MAX_TERM_MONTHS) {
    reasons.push("TERM_NOT_SUPPORTED");
  }

  if (reasons.length > 0) {
    return { approved: false, reasons };
  }

  const installmentCents = calculateInstallmentCents(
    input.requestedAmountCents,
    input.termMonths,
  );
  const availableMarginCents = Math.floor(
    (input.monthlyIncomeCents * MAX_INCOME_COMMITMENT_PERCENT) / 100,
  );

  if (installmentCents > availableMarginCents) {
    return { approved: false, reasons: ["INSTALLMENT_ABOVE_MARGIN"] };
  }

  return {
    approved: true,
    offer: {
      amountCents: input.requestedAmountCents,
      termMonths: input.termMonths,
      monthlyInterestRateBps: MONTHLY_INTEREST_RATE_BPS,
      installmentCents,
    },
  };
}
