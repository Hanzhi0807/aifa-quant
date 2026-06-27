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
import { picksRouter } from "./routers/picks";
import { portfolioRouter } from "./routers/portfolio";
import { weeklyPicksRouter } from "./routers/weeklyPicks";
import { refreshRouter } from "./routers/refresh";

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
  picks: picksRouter,
  portfolio: portfolioRouter,
  weeklyPicks: weeklyPicksRouter,
  refresh: refreshRouter,
});

export type AppRouter = typeof appRouter;
