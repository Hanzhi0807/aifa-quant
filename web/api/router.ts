import { createRouter, publicQuery } from "./middleware";
import { healthRouter } from "./routers/health";
import { dbInfoRouter } from "./routers/dbInfo";
import { backtestRouter } from "./routers/backtest";
import { equityCurveRouter } from "./routers/equityCurve";
import { metricsRouter } from "./routers/metrics";
import { modelRouter } from "./routers/model";
import { factorRouter } from "./routers/factor";

export const appRouter = createRouter({
  ping: publicQuery.query(() => ({ ok: true, ts: Date.now() })),
  health: healthRouter,
  dbInfo: dbInfoRouter,
  backtest: backtestRouter,
  equityCurve: equityCurveRouter,
  metrics: metricsRouter,
  model: modelRouter,
  factor: factorRouter,
});

export type AppRouter = typeof appRouter;
