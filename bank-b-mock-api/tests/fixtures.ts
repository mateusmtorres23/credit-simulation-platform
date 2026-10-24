import type { AssessmentRequest } from "../src/assessment/schemas.js";

export function makeAssessmentRequest(
  applicant: Partial<AssessmentRequest["applicant"]> = {},
  loan: Partial<AssessmentRequest["loan"]> = {},
): AssessmentRequest {
  return {
    applicant: {
      full_name: "Cliente Ficticio", email_address: "cliente@example.com",
      tax_id: "00000000000", employer_tax_id: "00000000000000",
      income_cents: 300_000, ...applicant,
    },
    loan: { amount_cents: 100_000, installments: 12, ...loan },
  };
}
