import { setTimeout as delay } from "node:timers/promises";
import type { FastifyPluginAsyncTypebox } from "@fastify/type-provider-typebox";
import { assessmentRequestSchema, assessmentResponseSchema, unavailableResponseSchema } from "./schemas.js";
import { assessCredit } from "./service.js";

type AssessmentRouteOptions = { slowResponseDelayMs: number };

export const assessmentRoutes: FastifyPluginAsyncTypebox<AssessmentRouteOptions> = async (app, options) => {
  const schema = { body: assessmentRequestSchema, response: { 200: assessmentResponseSchema } };

  app.post("/normal", { schema }, async (request) => assessCredit(request.body));

  app.post("/slow", { schema }, async (request) => {
    await delay(options.slowResponseDelayMs);
    return assessCredit(request.body);
  });

  app.post("/unavailable", {
    schema: { body: assessmentRequestSchema, response: { 503: unavailableResponseSchema } },
  }, async (_request, reply) => {
    return reply.code(503).send({
      error: { code: "SERVICE_UNAVAILABLE", detail: "Bank B temporarily unavailable" },
    });
  });
};
