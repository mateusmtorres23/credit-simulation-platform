import { buildApp } from "./app.js";
import { loadConfig } from "./config.js";

const app = buildApp();

async function shutdown(signal: NodeJS.Signals): Promise<void> {
  app.log.info({ signal }, "Shutting down server");

  try {
    await app.close();
  } catch (error) {
    app.log.error(error, "Failed to shut down server");
    process.exitCode = 1;
  }
}

try {
  const config = loadConfig();

  await app.listen({ host: config.host, port: config.port });

  process.once("SIGINT", () => shutdown("SIGINT"));
  process.once("SIGTERM", () => shutdown("SIGTERM"));
} catch (error) {
  app.log.error(error, "Failed to start server");
  process.exitCode = 1;

  try {
    await app.close();
  } catch (closeError) {
    app.log.error(closeError, "Failed to clean up after startup error");
  }
}
