import type { AssessmentRequest } from "../src/assessment/schemas.js";

export function makeAssessmentRequest(
  overrides: Partial<AssessmentRequest> = {},
): AssessmentRequest {
  return {
    name: "Cliente Ficticio",
    email: "cliente@example.com",
    cpf: "00000000000",
    employerCnpj: "00000000000000",
    monthlyIncomeCents: 300_000,
    requestedAmountCents: 100_000,
    termMonths: 12,
    ...overrides,
  };
}
