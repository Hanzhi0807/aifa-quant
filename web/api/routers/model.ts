import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { getDb } from "../queries/connection";
import { modelRegistry } from "@db/schema";
import { eq } from "drizzle-orm";

const mockModels = [
  {
    id: 1,
    name: "LightGBM_Rolling_v1",
    path: "models/lightgbm_rolling_v1.pkl",
    featureColumns: [
      "rsi_14", "macd_signal", "pe_ttm", "pb_lf", "roe_ttm",
      "volatility_20d", "turnover_20d", "momentum_20d", "momentum_60d",
      "amt_ratio", "close_ratio", "high_low_ratio", "vol_ratio",
      "industry_momentum", "market_cap",
    ],
    trainStart: "2018-01-01",
    trainEnd: "2022-12-31",
    createdAt: new Date("2024-01-15T10:00:00"),
  },
  {
    id: 2,
    name: "XGBoost_Rolling_v1",
    path: "models/xgboost_rolling_v1.pkl",
    featureColumns: [
      "rsi_14", "macd_signal", "pe_ttm", "pb_lf", "roe_ttm",
      "volatility_20d", "turnover_20d", "momentum_20d", "momentum_60d",
      "amt_ratio", "close_ratio", "high_low_ratio",
    ],
    trainStart: "2019-01-01",
    trainEnd: "2023-06-30",
    createdAt: new Date("2024-06-20T14:00:00"),
  },
  {
    id: 3,
    name: "Ensemble_Stacking_v1",
    path: "models/ensemble_stacking_v1.pkl",
    featureColumns: [
      "rsi_14", "macd_signal", "pe_ttm", "pb_lf", "roe_ttm",
      "volatility_20d", "turnover_20d", "momentum_20d", "momentum_60d",
      "amt_ratio", "close_ratio", "high_low_ratio", "vol_ratio",
      "industry_momentum", "market_cap", "beta_60d", "alpha_60d",
    ],
    trainStart: "2018-01-01",
    trainEnd: "2023-12-31",
    createdAt: new Date("2024-03-10T09:00:00"),
  },
];

export const modelRouter = createRouter({
  list: publicQuery.query(async () => {
    try {
      const db = getDb();
      const models = await db.select().from(modelRegistry);
      return models.map((m) => ({
        ...m,
        featureColumns: m.featureColumns
          ? JSON.parse(m.featureColumns as string)
          : [],
      }));
    } catch {
      return mockModels;
    }
  }),

  getById: publicQuery
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = getDb();
        const [model] = await db
          .select()
          .from(modelRegistry)
          .where(eq(modelRegistry.id, input.id));
        if (!model) return null;
        return {
          ...model,
          featureColumns: model.featureColumns
            ? JSON.parse(model.featureColumns as string)
            : [],
        };
      } catch {
        return mockModels.find((m) => m.id === input.id) || null;
      }
    }),
});
