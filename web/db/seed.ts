import fs from "fs";
import path from "path";
import { getDb } from "../api/queries/connection";
import { backtestRuns, equityCurve, modelRegistry, factorImportance } from "./schema";

const seedPath = path.join(import.meta.dirname, "seed-data.json");

function loadRealData() {
  if (!fs.existsSync(seedPath)) return null;
  try {
    return JSON.parse(fs.readFileSync(seedPath, "utf-8"));
  } catch (err) {
    console.warn("Failed to parse seed-data.json, falling back to mock data", err);
    return null;
  }
}

const realData = loadRealData();

const mockBacktestRuns = [
  {
    name: "LightGBM 滚动 2024",
    startDate: new Date("2023-01-03"),
    endDate: new Date("2024-12-31"),
    topK: 10,
    rebalanceFreq: 5,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
      totalReturn: 0.2655,
      annualReturn: 0.1278,
      sharpeRatio: 1.35,
      maxDrawdown: -0.1523,
      volatility: 0.185,
      winRate: 0.62,
      profitFactor: 1.85,
      benchmarkTotalReturn: 0.1468,
      excessReturn: 0.1187,
      informationRatio: 0.92,
      calmarRatio: 0.84,
      sortinoRatio: 1.68,
    },
  },
  {
    name: "LightGBM 固定窗口 2024",
    startDate: new Date("2023-01-03"),
    endDate: new Date("2024-12-31"),
    topK: 15,
    rebalanceFreq: 10,
    rolling: false,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
      totalReturn: 0.1987,
      annualReturn: 0.0956,
      sharpeRatio: 1.12,
      maxDrawdown: -0.1892,
      volatility: 0.162,
      winRate: 0.58,
      profitFactor: 1.62,
      benchmarkTotalReturn: 0.1468,
      excessReturn: 0.0519,
      informationRatio: 0.45,
      calmarRatio: 0.51,
      sortinoRatio: 1.35,
    },
  },
  {
    name: "LightGBM 滚动 2024Q4",
    startDate: new Date("2024-10-01"),
    endDate: new Date("2024-12-31"),
    topK: 8,
    rebalanceFreq: 3,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
      totalReturn: 0.0892,
      annualReturn: 0.3568,
      sharpeRatio: 2.15,
      maxDrawdown: -0.0456,
      volatility: 0.142,
      winRate: 0.71,
      profitFactor: 2.35,
      benchmarkTotalReturn: 0.0523,
      excessReturn: 0.0369,
      informationRatio: 1.25,
      calmarRatio: 2.15,
      sortinoRatio: 2.85,
    },
  },
  {
    name: "XGBoost 滚动 2024",
    startDate: new Date("2023-06-01"),
    endDate: new Date("2024-12-31"),
    topK: 10,
    rebalanceFreq: 5,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
      totalReturn: 0.2234,
      annualReturn: 0.1277,
      sharpeRatio: 1.28,
      maxDrawdown: -0.1734,
      volatility: 0.195,
      winRate: 0.59,
      profitFactor: 1.72,
      benchmarkTotalReturn: 0.1234,
      excessReturn: 0.10,
      informationRatio: 0.78,
      calmarRatio: 0.74,
      sortinoRatio: 1.55,
    },
  },
  {
    name: "集成模型 2024",
    startDate: new Date("2023-01-03"),
    endDate: new Date("2024-12-31"),
    topK: 12,
    rebalanceFreq: 7,
    rolling: true,
    benchmark: "沪深300",
    status: "completed",
    metrics: {
      totalReturn: 0.3123,
      annualReturn: 0.1502,
      sharpeRatio: 1.52,
      maxDrawdown: -0.1345,
      volatility: 0.172,
      winRate: 0.65,
      profitFactor: 1.95,
      benchmarkTotalReturn: 0.1468,
      excessReturn: 0.1655,
      informationRatio: 1.18,
      calmarRatio: 1.12,
      sortinoRatio: 1.95,
    },
  },
];

function generateMockEquityCurve(backtestId: number) {
  const tradingDays: string[] = [];
  const start = new Date("2023-01-03");
  const end = new Date("2024-12-31");
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const day = d.getDay();
    if (day !== 0 && day !== 6) {
      tradingDays.push(d.toISOString().split("T")[0]);
    }
  }

  let portfolioValue = 1.0;
  let benchmarkValue = 1.0;
  const equityData: {
    backtestId: number;
    tradeDate: Date;
    totalValue: string;
    normalizedValue: string;
    benchmarkNormalized: string;
  }[] = [];

  for (let i = 0; i < tradingDays.length; i++) {
    const date = tradingDays[i];
    const portfolioDailyReturn =
      Math.sin(i * 0.05) * 0.005 + 0.0004 + (Math.random() - 0.5) * 0.008;
    const benchmarkDailyReturn =
      Math.sin(i * 0.03) * 0.004 + 0.0002 + (Math.random() - 0.5) * 0.012;

    portfolioValue *= 1 + portfolioDailyReturn;
    benchmarkValue *= 1 + benchmarkDailyReturn;

    equityData.push({
      backtestId,
      tradeDate: new Date(date),
      totalValue: String((portfolioValue * 1000000).toFixed(4)),
      normalizedValue: String(portfolioValue.toFixed(6)),
      benchmarkNormalized: String(benchmarkValue.toFixed(6)),
    });
  }
  return equityData;
}

const mockModels = [
  {
    name: "LightGBM 滚动 v1",
    path: "models/lightgbm_rolling_v1.pkl",
    featureColumns: [
      "rsi_14",
      "macd_signal",
      "pe_ttm",
      "pb_lf",
      "roe_ttm",
      "volatility_20d",
      "turnover_20d",
      "momentum_20d",
      "momentum_60d",
      "amt_ratio",
      "close_ratio",
      "high_low_ratio",
      "vol_ratio",
      "industry_momentum",
      "market_cap",
    ],
    trainStart: new Date("2018-01-01"),
    trainEnd: new Date("2022-12-31"),
  },
  {
    name: "XGBoost 滚动 v1",
    path: "models/xgboost_rolling_v1.pkl",
    featureColumns: [
      "rsi_14",
      "macd_signal",
      "pe_ttm",
      "pb_lf",
      "roe_ttm",
      "volatility_20d",
      "turnover_20d",
      "momentum_20d",
      "momentum_60d",
      "amt_ratio",
      "close_ratio",
      "high_low_ratio",
    ],
    trainStart: new Date("2019-01-01"),
    trainEnd: new Date("2023-06-30"),
  },
  {
    name: "集成 Stacking v1",
    path: "models/ensemble_stacking_v1.pkl",
    featureColumns: [
      "rsi_14",
      "macd_signal",
      "pe_ttm",
      "pb_lf",
      "roe_ttm",
      "volatility_20d",
      "turnover_20d",
      "momentum_20d",
      "momentum_60d",
      "amt_ratio",
      "close_ratio",
      "high_low_ratio",
      "vol_ratio",
      "industry_momentum",
      "market_cap",
      "beta_60d",
      "alpha_60d",
    ],
    trainStart: new Date("2018-01-01"),
    trainEnd: new Date("2023-12-31"),
  },
];

const mockFactors = [
  { factorName: "momentum_60d", importance: "0.15234", rank: 1 },
  { factorName: "roe_ttm", importance: "0.12892", rank: 2 },
  { factorName: "rsi_14", importance: "0.11567", rank: 3 },
  { factorName: "volatility_20d", importance: "0.09845", rank: 4 },
  { factorName: "pe_ttm", importance: "0.08723", rank: 5 },
  { factorName: "pb_lf", importance: "0.07654", rank: 6 },
  { factorName: "turnover_20d", importance: "0.07231", rank: 7 },
  { factorName: "momentum_20d", importance: "0.06892", rank: 8 },
  { factorName: "macd_signal", importance: "0.06123", rank: 9 },
  { factorName: "market_cap", importance: "0.05432", rank: 10 },
  { factorName: "close_ratio", importance: "0.04876", rank: 11 },
  { factorName: "amt_ratio", importance: "0.04215", rank: 12 },
  { factorName: "high_low_ratio", importance: "0.03892", rank: 13 },
  { factorName: "vol_ratio", importance: "0.03218", rank: 14 },
  { factorName: "industry_momentum", importance: "0.02186", rank: 15 },
];

async function seed() {
  const db = getDb();
  console.log("Seeding database...");

  const useReal = realData && realData.backtestRuns?.length > 0;
  if (useReal) {
    console.log(`Using real backtest data from ${seedPath}`);
  }

  // Backtest runs
  const runsToInsert = useReal
    ? realData.backtestRuns.map((run: any) => ({
        ...run,
        startDate: new Date(run.startDate),
        endDate: new Date(run.endDate),
        createdAt: run.createdAt ? new Date(run.createdAt) : new Date(),
        metrics: JSON.stringify(run.metrics),
      }))
    : mockBacktestRuns.map((run) => ({ ...run, metrics: JSON.stringify(run.metrics) }));

  await db.insert(backtestRuns).values(runsToInsert);
  console.log(`Inserted ${runsToInsert.length} backtest runs`);

  // Equity curve
  const equityData = useReal
    ? realData.equityCurve.map((row: any) => ({
        backtestId: 1,
        tradeDate: new Date(row.tradeDate),
        totalValue: String(row.totalValue),
        normalizedValue: String(row.normalizedValue),
        benchmarkNormalized: String(row.benchmarkNormalized),
      }))
    : generateMockEquityCurve(1);

  const chunkSize = 100;
  for (let i = 0; i < equityData.length; i += chunkSize) {
    const chunk = equityData.slice(i, i + chunkSize);
    await db.insert(equityCurve).values(chunk);
  }
  console.log(`Inserted ${equityData.length} equity curve points`);

  // Models
  const modelsToInsert = useReal
    ? realData.models.map((model: any) => ({
        ...model,
        trainStart: model.trainStart ? new Date(model.trainStart) : null,
        trainEnd: model.trainEnd ? new Date(model.trainEnd) : null,
        createdAt: model.createdAt ? new Date(model.createdAt) : new Date(),
        featureColumns: JSON.stringify(model.featureColumns),
      }))
    : mockModels.map((model) => ({
        ...model,
        featureColumns: JSON.stringify(model.featureColumns),
      }));

  await db.insert(modelRegistry).values(modelsToInsert);
  console.log(`Inserted ${modelsToInsert.length} models`);

  // Factors
  const factorsToInsert = useReal
    ? realData.factors.map((f: any) => ({ ...f, modelId: 1 }))
    : mockFactors.map((f) => ({ ...f, modelId: 1 }));

  await db.insert(factorImportance).values(factorsToInsert);
  console.log(`Inserted ${factorsToInsert.length} factor importances`);
  console.log("Seed complete!");
}

seed().catch((err) => {
  console.error("Seed error:", err);
  process.exit(1);
});
