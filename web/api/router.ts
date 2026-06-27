import { createRouter, publicQuery } from "./middleware";
import { healthRouter } from "./routers/health";
import { dbInfoRouter } from "./routers/dbInfo";
import { backtestRouter } from "./routers/backtest";
import { equityCurveRouter } from "./routers/equityCurve";
import { metricsRouter } from "./routers/metrics";
import { modelRouter } from "./routers/model";
import { factorRouter } from "./routers/factor";
import { factorStoreRouter } from "./routers/factorStore";
import { backtestRunnerRouter } from "./routers/backtestRunner";
import { refreshRouter } from "./routers/refresh";
import { riskRouter } from "./routers/risk";
import { strategiesRouter } from "./routers/strategies";

export const appRouter = createRouter({
  ping: publicQuery.query(() => ({ ok: true, ts: Date.now() })),
  health: healthRouter,
  dbInfo: dbInfoRouter,
  backtest: backtestRouter,
  equityCurve: equityCurveRouter,
  metrics: metricsRouter,
  model: modelRouter,
  factor: factorRouter,
  factorStore: factorStoreRouter,
  backtestRunner: backtestRunnerRouter,
  refresh: refreshRouter,
  risk: riskRouter,
  strategies: strategiesRouter,
});

export type AppRouter = typeof appRouter;
