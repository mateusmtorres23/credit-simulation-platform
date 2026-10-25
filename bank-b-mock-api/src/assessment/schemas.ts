import { Type } from "typebox";
import type { Static } from "typebox";

const moneySchema = Type.Integer({ minimum: 1, maximum: Number.MAX_SAFE_INTEGER });

export const assessmentRequestSchema = Type.Object({
  applicant: Type.Object({
    full_name: Type.String({ minLength: 1, maxLength: 150, pattern: "\\S" }),
    email_address: Type.String({ format: "idn-email", maxLength: 254 }),
    tax_id: Type.String({ pattern: "^[0-9]{11}$" }),
    income_cents: moneySchema,
    employer_tax_id: Type.String({ pattern: "^[0-9]{14}$" }),
  }, { additionalProperties: false }),
  loan: Type.Object({
    amount_cents: Type.Integer({ minimum: 100, maximum: Number.MAX_SAFE_INTEGER }),
    installments: Type.Integer({ minimum: 1, maximum: 120 }),
  }, { additionalProperties: false }),
}, { additionalProperties: false });

export const rejectionReasonSchema = Type.Union([
  Type.Literal("LOW_INCOME"),
  Type.Literal("LIMIT_EXCEEDED"),
  Type.Literal("INVALID_TERM"),
  Type.Literal("INSUFFICIENT_MARGIN"),
]);

export const assessmentResponseSchema = Type.Union([
  Type.Object({
    decision: Type.Object({
      code: Type.Literal("ACCEPTED"),
      conditions: Type.Object({
        principal_cents: moneySchema,
        installments: Type.Integer({ minimum: 1, maximum: 120 }),
        monthly_rate_bps: Type.Integer({ minimum: 0, maximum: Number.MAX_SAFE_INTEGER }),
        payment_cents: moneySchema,
      }, { additionalProperties: false }),
    }, { additionalProperties: false }),
  }, { additionalProperties: false }),
  Type.Object({
    decision: Type.Object({
      code: Type.Literal("DECLINED"),
      reasons: Type.Array(rejectionReasonSchema, { minItems: 1, uniqueItems: true }),
    }, { additionalProperties: false }),
  }, { additionalProperties: false }),
]);

export const unavailableResponseSchema = Type.Object({
  error: Type.Object({
    code: Type.Literal("SERVICE_UNAVAILABLE"),
    detail: Type.String({ minLength: 1 }),
  }, { additionalProperties: false }),
}, { additionalProperties: false });

export type AssessmentRequest = Static<typeof assessmentRequestSchema>;
export type AssessmentResponse = Static<typeof assessmentResponseSchema>;
export type RejectionReason = Static<typeof rejectionReasonSchema>;
