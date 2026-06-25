import {
  mysqlTable,
  serial,
  varchar,
  date,
  int,
  boolean,
  json,
  timestamp,
  decimal,
  bigint,
} from "drizzle-orm/mysql-core";

// Backtest runs table
export const backtestRuns = mysqlTable("backtest_runs", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  startDate: date("start_date").notNull(),
  endDate: date("end_date").notNull(),
  topK: int("top_k").notNull().default(10),
  rebalanceFreq: int("rebalance_freq").notNull().default(5),
  rolling: boolean("rolling").notNull().default(true),
  benchmark: varchar("benchmark", { length: 50 }).notNull().default("CSI300"),
  metrics: json("metrics"),
  status: varchar("status", { length: 20 }).notNull().default("completed"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

// Equity curve data points
export const equityCurve = mysqlTable("equity_curve", {
  id: serial("id").primaryKey(),
  backtestId: bigint("backtest_id", { mode: "number", unsigned: true }).notNull(),
  tradeDate: date("trade_date").notNull(),
  totalValue: decimal("total_value", { precision: 18, scale: 4 }).notNull(),
  normalizedValue: decimal("normalized_value", { precision: 18, scale: 6 }).notNull(),
  benchmarkNormalized: decimal("benchmark_normalized", { precision: 18, scale: 6 }).notNull(),
});

// Model registry
export const modelRegistry = mysqlTable("model_registry", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  path: varchar("path", { length: 500 }),
  featureColumns: json("feature_columns"),
  trainStart: date("train_start"),
  trainEnd: date("train_end"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

// Factor importance scores
export const factorImportance = mysqlTable("factor_importance", {
  id: serial("id").primaryKey(),
  modelId: bigint("model_id", { mode: "number", unsigned: true }).notNull(),
  factorName: varchar("factor_name", { length: 100 }).notNull(),
  importance: decimal("importance", { precision: 10, scale: 6 }).notNull(),
  rank: int("rank").notNull(),
});
