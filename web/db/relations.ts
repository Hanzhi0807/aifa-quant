import { relations } from "drizzle-orm";
import { backtestRuns, equityCurve, modelRegistry, factorImportance } from "./schema";

export const backtestRunsRelations = relations(backtestRuns, ({ many }) => ({
  equityCurves: many(equityCurve),
}));

export const equityCurveRelations = relations(equityCurve, ({ one }) => ({
  backtest: one(backtestRuns, {
    fields: [equityCurve.backtestId],
    references: [backtestRuns.id],
  }),
}));

export const modelRegistryRelations = relations(modelRegistry, ({ many }) => ({
  factors: many(factorImportance),
}));

export const factorImportanceRelations = relations(factorImportance, ({ one }) => ({
  model: one(modelRegistry, {
    fields: [factorImportance.modelId],
    references: [modelRegistry.id],
  }),
}));
