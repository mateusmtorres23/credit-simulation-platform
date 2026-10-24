import Fastify from "fastify";
import type { FastifyInstance } from "fastify";
import { assessmentRoutes } from "./assessment/routes.js";

type AppOptions = {
  slowResponseDelayMs?: number;
};

export function buildApp(options: AppOptions = {}): FastifyInstance {
  const app = Fastify({ logger: true });

  app.register(assessmentRoutes, {
    prefix: "/evaluations",
    slowResponseDelayMs: options.slowResponseDelayMs ?? 8000,
  });

  app.get("/health", async () => {
    return { status: "ok" };
  });

  return app;
}
