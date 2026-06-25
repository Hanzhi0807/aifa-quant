import { createRouter, publicQuery } from "../middleware";

export const healthRouter = createRouter({
  check: publicQuery.query(() => ({
    status: "ok",
    version: "0.2.0",
    timestamp: new Date().toISOString(),
  })),
});
