import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { domainToASCII } from "node:url";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { makeAssessmentRequest } from "./fixtures.js";

describe("Bank B routes", () => {
  let app: FastifyInstance;
  const hindiEmail = "cliente@उदाहरण.भारत";
  const hindiPunycodeEmail = `cliente@${domainToASCII("उदाहरण.भारत")}`;
  beforeEach(async () => {
    app = buildApp({ slowResponseDelayMs: 60 });
    await app.ready();
  });
  afterEach(async () => { await app.close(); });

  it("returns the nested Bank B approval contract", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: makeAssessmentRequest() });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ decision: { code: "ACCEPTED", conditions: {
      principal_cents: 100_000, installments: 12, monthly_rate_bps: 210, payment_cents: 9514,
    } } });
  });

  it.each([
    "cliente@example.com",
    "josé@example.com",
    "cliente@bücher.de",
    "cliente@xn--bcher-kva.de",
    hindiEmail,
    hindiPunycodeEmail,
  ])("accepts internationalized email %s", async (email) => {
    const normal = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: makeAssessmentRequest({ email_address: email }),
    });
    const slow = await app.inject({
      method: "POST",
      url: "/evaluations/slow",
      payload: makeAssessmentRequest({ email_address: email }),
    });
    const unavailable = await app.inject({
      method: "POST",
      url: "/evaluations/unavailable",
      payload: makeAssessmentRequest({ email_address: email }),
    });

    expect(normal.statusCode).toBe(200);
    expect(normal.json().decision.code).toBe("ACCEPTED");
    expect(slow.statusCode).toBe(200);
    expect(slow.json()).toEqual(normal.json());
    expect(unavailable.statusCode).toBe(503);
  });

  it("keeps the credit decision independent of the email", async () => {
    const ascii = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: makeAssessmentRequest({ email_address: "cliente@example.com" }),
    });
    const internationalized = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: makeAssessmentRequest({ email_address: "josé@example.com" }),
    });
    expect(internationalized.statusCode).toBe(200);
    expect(internationalized.json()).toEqual(ascii.json());
  });

  it("accepts a percent sign in the local part", async () => {
    const request = makeAssessmentRequest();
    const response = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: {
        ...request,
        applicant: { ...request.applicant, email_address: "cliente%tag@example.com" },
      },
    });
    expect(response.statusCode).toBe(200);
  });

  it.each(["normal", "slow"])("returns business rejection as HTTP 200 in %s", async (scenario) => {
    const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: makeAssessmentRequest({ income_cents: 100_000 }) });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ decision: { code: "DECLINED", reasons: ["LOW_INCOME"] } });
  });

  it("delays slow responses without changing the offer", async () => {
    const payload = makeAssessmentRequest();
    const normal = await app.inject({ method: "POST", url: "/evaluations/normal", payload });
    const startedAt = performance.now();
    const slow = await app.inject({ method: "POST", url: "/evaluations/slow", payload });
    expect(performance.now() - startedAt).toBeGreaterThanOrEqual(50);
    expect(slow.statusCode).toBe(200);
    expect(slow.json()).toEqual(normal.json());
  });

  it("returns its own technical error contract and stays healthy", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/unavailable", payload: makeAssessmentRequest() });
    expect(response.statusCode).toBe(503);
    expect(response.json()).toEqual({ error: { code: "SERVICE_UNAVAILABLE", detail: "Bank B temporarily unavailable" } });
    expect((await app.inject({ method: "GET", url: "/health" })).statusCode).toBe(200);
  });

  it.each(["normal", "slow", "unavailable"])("validates input before running %s", async (scenario) => {
    const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: {} });
    expect(response.statusCode).toBe(400);
  });

  it.each([
    { full_name: " " }, { email_address: "invalid" },
    { email_address: "missing@" },
    { email_address: "a".repeat(250) + "@a.com" },
    { tax_id: "123" },
    { employer_tax_id: "123" }, { income_cents: 0 },
  ])("rejects invalid applicant fields: %j", async (overrides) => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: makeAssessmentRequest(overrides) });
    expect(response.statusCode).toBe(400);
  });

  it("rejects an email with an invalid JSON type", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: {
        ...makeAssessmentRequest(),
        applicant: { ...makeAssessmentRequest().applicant, email_address: 123 },
      },
    });
    expect(response.statusCode).toBe(400);
  });

  it.each(["normal", "slow", "unavailable"])(
    "rejects invalid email syntax before running %s",
    async (scenario) => {
      for (const email of [
        "missing@",
        "a".repeat(250) + "@a.com",
        "cliente@-invalid.example",
        "cliente@invalid-.example",
        "cliente@\u0000.example",
        "cliente@example.com/path",
        "cliente@example.com?x",
        "cliente@example.com#x",
        "cliente@exa%6dple.com",
        "cliente@example.com\\suffix",
        "cliente@example .com",
      ]) {
        const request = makeAssessmentRequest();
        const response = await app.inject({
          method: "POST",
          url: `/evaluations/${scenario}`,
          payload: {
            ...request,
            applicant: { ...request.applicant, email_address: email },
          },
        });
        expect(response.statusCode).toBe(400);
      }
    },
  );

  it.each([
    { amount_cents: 0 }, { amount_cents: 1.5 }, { amount_cents: Number.MAX_SAFE_INTEGER + 1 },
    { installments: 0 }, { installments: 121 }, { installments: 12.5 },
  ])("rejects invalid loan fields: %j", async (overrides) => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: makeAssessmentRequest({}, overrides) });
    expect(response.statusCode).toBe(400);
  });

  it.each(["normal", "slow", "unavailable"])("rejects sub-minimum amounts before running %s", async (scenario) => {
    for (const amount_cents of [1, 99]) {
      const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: makeAssessmentRequest({}, { amount_cents }) });
      expect(response.statusCode).toBe(400);
    }
  });

  it.each(["normal", "slow"])("serializes the minimum amount at the longest term in %s", async (scenario) => {
    const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: makeAssessmentRequest({}, { amount_cents: 100, installments: 60 }) });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ decision: { code: "ACCEPTED", conditions: {
      principal_cents: 100, installments: 60, monthly_rate_bps: 210, payment_cents: 3,
    } } });
  });

  it("keeps income limits independent of the requested minimum", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: makeAssessmentRequest({ income_cents: 1 }, { amount_cents: 100 }) });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ decision: { code: "DECLINED", reasons: ["LOW_INCOME"] } });
  });

  it("rejects malformed JSON", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", headers: { "content-type": "application/json" }, payload: "{" });
    expect(response.statusCode).toBe(400);
  });

  it("requires the route prefix", async () => {
    expect((await app.inject({ method: "POST", url: "/normal", payload: makeAssessmentRequest() })).statusCode).toBe(404);
  });
});
