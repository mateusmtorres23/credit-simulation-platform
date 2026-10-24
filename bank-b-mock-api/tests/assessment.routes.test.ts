import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { makeAssessmentRequest } from "./fixtures.js";

describe("Bank B routes", () => {
  let app: FastifyInstance;
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
    { full_name: " " }, { email_address: "invalid" }, { tax_id: "123" },
    { employer_tax_id: "123" }, { income_cents: 0 },
  ])("rejects invalid applicant fields: %j", async (overrides) => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: makeAssessmentRequest(overrides) });
    expect(response.statusCode).toBe(400);
  });

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

