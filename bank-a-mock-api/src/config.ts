export type AppConfig = {
  host: string;
  port: number;
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  const host = (env.HOST ?? "0.0.0.0").trim();
  const rawPort = env.PORT ?? "3001";

  if (host.length === 0) {
    throw new Error("HOST must not be empty");
  }

  if (!/^\d+$/.test(rawPort)) {
    throw new Error("PORT must be an integer between 1 and 65535");
  }

  const port = Number(rawPort);

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("PORT must be an integer between 1 and 65535");
  }

  return { host, port };
}
