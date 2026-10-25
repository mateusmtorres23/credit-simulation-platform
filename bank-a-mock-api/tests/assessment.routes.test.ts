import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { domainToASCII } from "node:url";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { makeAssessmentRequest } from "./fixtures.js";

describe("assessment routes", () => {
  let app: FastifyInstance;
  const slowResponseDelayMs = 60;
  const hindiEmail = "cliente@उदाहरण.भारत";
  const hindiPunycodeEmail = `cliente@${domainToASCII("उदाहरण.भारत")}`;

  beforeEach(async () => {
    app = buildApp({ slowResponseDelayMs });
    await app.ready();
  });

  afterEach(async () => {
    await app.close();
  });

  it("returns an approved offer as JSON", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: makeAssessmentRequest() });
    expect(response.statusCode).toBe(200);
    expect(response.headers["content-type"]).toContain("application/json");
    expect(response.json()).toEqual({
      approved: true,
      offer: { amountCents: 100_000, termMonths: 12, monthlyInterestRateBps: 180, installmentCents: 9340 },
    });
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
      payload: makeAssessmentRequest({ email }),
    });
    const slow = await app.inject({
      method: "POST",
      url: "/evaluations/slow",
      payload: makeAssessmentRequest({ email }),
    });
    const unavailable = await app.inject({
      method: "POST",
      url: "/evaluations/unavailable",
      payload: makeAssessmentRequest({ email }),
    });

    expect(normal.statusCode).toBe(200);
    expect(normal.json().approved).toBe(true);
    expect(slow.statusCode).toBe(200);
    expect(slow.json()).toEqual(normal.json());
    expect(unavailable.statusCode).toBe(503);
  });

  it("keeps the credit decision independent of the email", async () => {
    const ascii = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: makeAssessmentRequest({ email: "cliente@example.com" }),
    });
    const internationalized = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: makeAssessmentRequest({ email: "josé@example.com" }),
    });
    expect(internationalized.statusCode).toBe(200);
    expect(internationalized.json()).toEqual(ascii.json());
  });

  it("accepts a percent sign in the local part", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: makeAssessmentRequest({ email: "cliente%tag@example.com" }),
    });
    expect(response.statusCode).toBe(200);
  });

  it.each(["normal", "slow"])("returns business rejection with HTTP 200 in %s", async (scenario) => {
    const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: makeAssessmentRequest({ monthlyIncomeCents: 100_000 }) });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ approved: false, reasons: ["INCOME_BELOW_MINIMUM"] });
  });

  it("delays the slow scenario and returns the same offer as normal", async () => {
    const payload = makeAssessmentRequest();
    const normal = await app.inject({ method: "POST", url: "/evaluations/normal", payload });
    const startedAt = performance.now();
    const slow = await app.inject({ method: "POST", url: "/evaluations/slow", payload });
    const elapsedMs = performance.now() - startedAt;
    expect(slow.statusCode).toBe(200);
    expect(slow.json()).toEqual(normal.json());
    // Allow timer precision variation without imposing a flaky upper time limit.
    expect(elapsedMs).toBeGreaterThanOrEqual(slowResponseDelayMs - 10);
  });

  it("returns technical unavailability without a credit rejection", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/unavailable", payload: makeAssessmentRequest() });
    expect(response.statusCode).toBe(503);
    expect(response.json()).toEqual({ code: "BANK_UNAVAILABLE", message: "Bank temporarily unavailable" });
    const health = await app.inject({ method: "GET", url: "/health" });
    expect(health.statusCode).toBe(200);
  });

  it.each(["normal", "slow", "unavailable"])("validates required fields before running %s", async (scenario) => {
    const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: {} });
    expect(response.statusCode).toBe(400);
    expect(response.json()).not.toHaveProperty("approved");
  });

  it.each([
    { name: "" }, { name: "   " }, { name: "a".repeat(151) },
    { email: "invalid" }, { email: "missing@" },
    { email: "a".repeat(250) + "@a.com" },
    { cpf: "123" }, { employerCnpj: "123" },
    { monthlyIncomeCents: 0 }, { monthlyIncomeCents: -1 },
    { requestedAmountCents: 1.5 }, { requestedAmountCents: Number.MAX_SAFE_INTEGER + 1 },
    { termMonths: 0 }, { termMonths: 121 }, { termMonths: 6.5 },
  ])("rejects invalid fields: %j", async (overrides) => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: { ...makeAssessmentRequest(), ...overrides } });
    expect(response.statusCode).toBe(400);
  });

  it("rejects an email with an invalid JSON type", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/evaluations/normal",
      payload: { ...makeAssessmentRequest(), email: 123 },
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
        const response = await app.inject({
          method: "POST",
          url: `/evaluations/${scenario}`,
          payload: { ...makeAssessmentRequest(), email },
        });
        expect(response.statusCode).toBe(400);
      }
    },
  );

  it.each(["normal", "slow", "unavailable"])("rejects sub-minimum amounts before running %s", async (scenario) => {
    for (const requestedAmountCents of [1, 99]) {
      const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: makeAssessmentRequest({ requestedAmountCents }) });
      expect(response.statusCode).toBe(400);
    }
  });

  it.each(["normal", "slow"])("serializes the minimum amount at the longest term in %s", async (scenario) => {
    const response = await app.inject({ method: "POST", url: `/evaluations/${scenario}`, payload: makeAssessmentRequest({ requestedAmountCents: 100, termMonths: 48 }) });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ approved: true, offer: {
      amountCents: 100, termMonths: 48, monthlyInterestRateBps: 180, installmentCents: 3,
    } });
  });

  it("keeps income and output money limits independent of the requested minimum", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: makeAssessmentRequest({ requestedAmountCents: 100, monthlyIncomeCents: 1 }) });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ approved: false, reasons: ["INCOME_BELOW_MINIMUM"] });
  });

  it("rejects malformed JSON", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", headers: { "content-type": "application/json" }, payload: "{" });
    expect(response.statusCode).toBe(400);
  });

  it("ignores additional fields and does not let them override a rejection", async () => {
    const response = await app.inject({ method: "POST", url: "/evaluations/normal", payload: { ...makeAssessmentRequest({ monthlyIncomeCents: 100_000 }), approved: true, unexpected: "ignored" } });
    expect(response.statusCode).toBe(200);
    expect(response.json()).not.toHaveProperty("unexpected");
    expect(response.json()).toEqual({ approved: false, reasons: ["INCOME_BELOW_MINIMUM"] });
  });

  it("does not expose the plugin paths without their prefix", async () => {
    const response = await app.inject({ method: "POST", url: "/normal", payload: makeAssessmentRequest() });
    expect(response.statusCode).toBe(404);
  });
});
