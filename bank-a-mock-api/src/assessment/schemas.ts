import { Type } from "typebox";
import type { Static } from "typebox";

const positiveMoneySchema = Type.Integer({
  minimum: 1,
  maximum: Number.MAX_SAFE_INTEGER,
  description: "Amount in BRL cents",
});

export const assessmentRequestSchema = Type.Object(
  {
    name: Type.String({ minLength: 1, maxLength: 150, pattern: "\\S" }),
    email: Type.String({ format: "email", maxLength: 254 }),
    cpf: Type.String({ pattern: "^[0-9]{11}$" }),
    monthlyIncomeCents: positiveMoneySchema,
    employerCnpj: Type.String({ pattern: "^[0-9]{14}$" }),
    requestedAmountCents: Type.Integer({
      minimum: 100,
      maximum: Number.MAX_SAFE_INTEGER,
      description: "Requested amount in BRL cents; minimum BRL 1.00",
    }),
    termMonths: Type.Integer({ minimum: 1, maximum: 120 }),
  },
  { additionalProperties: false },
);

export const rejectionReasonSchema = Type.Union([
  Type.Literal("INCOME_BELOW_MINIMUM"),
  Type.Literal("AMOUNT_ABOVE_LIMIT"),
  Type.Literal("TERM_NOT_SUPPORTED"),
  Type.Literal("INSTALLMENT_ABOVE_MARGIN"),
]);

export const assessmentResponseSchema = Type.Union([
  Type.Object(
    {
      approved: Type.Literal(true),
      offer: Type.Object(
        {
          amountCents: positiveMoneySchema,
          termMonths: Type.Integer({ minimum: 1, maximum: 120 }),
          monthlyInterestRateBps: Type.Integer({ minimum: 0 }),
          installmentCents: positiveMoneySchema,
        },
        { additionalProperties: false },
      ),
    },
    { additionalProperties: false },
  ),
  Type.Object(
    {
      approved: Type.Literal(false),
      reasons: Type.Array(rejectionReasonSchema, {
        minItems: 1,
        uniqueItems: true,
      }),
    },
    { additionalProperties: false },
  ),
]);

export const unavailableResponseSchema = Type.Object(
  {
    code: Type.Literal("BANK_UNAVAILABLE"),
    message: Type.String({ minLength: 1 }),
  },
  { additionalProperties: false },
);

export type AssessmentRequest = Static<typeof assessmentRequestSchema>;
export type AssessmentResponse = Static<typeof assessmentResponseSchema>;
export type RejectionReason = Static<typeof rejectionReasonSchema>;
export type UnavailableResponse = Static<typeof unavailableResponseSchema>;
