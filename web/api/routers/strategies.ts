import { z } from "zod";
import { createRouter, publicQuery } from "../middleware";
import { isDuckDBAvailable, queryDuckDB } from "../queries/duckdb";

const PROFILES = ["aggressive", "balanced", "conservative", "growth", "value"] as const;

interface PosRow { symbol: string; shares: number; cost_basis: number; }
interface NavRow { trade_date: Date; cash: number; market_value: number; total_value: number; }
interface QuoteRow { symbol: string; close: number; trade_date: Date; }
interface NameRow { symbol: string; name: string; }

interface EquityPoint {
  tradeDate: string;
  normalizedValue: number;
  csi300Normalized?: number;
  sseNormalized?: number;
}

const PROFILE_LABELS: Record<string, {
  name: string;
  desc: string;
  topK: number;
  targetRiskPct: number;
  atrStopLoss: number;
  atrTakeProfit: number;
  factorWeights: Record<string, number>;
}> = {
  aggressive: {
    name: "激进型",
    desc: "高集中度，追求高收益",
    topK: 5,
    targetRiskPct: 0.03,
    atrStopLoss: 1.5,
    atrTakeProfit: 4.0,
    factorWeights: { momentum: 1.5, return: 1.5, alpha: 1.3, volume: 1.2 },
  },
  balanced: {
    name: "均衡型",
    desc: "攻守兼备，适合大多数人",
    topK: 8,
    targetRiskPct: 0.02,
    atrStopLoss: 1.0,
    atrTakeProfit: 3.0,
    factorWeights: {},
  },
  conservative: {
    name: "稳健型",
    desc: "分散持仓，严格控制回撤",
    topK: 12,
    targetRiskPct: 0.012,
    atrStopLoss: 0.75,
    atrTakeProfit: 2.0,
    factorWeights: { pe: 1.5, pb: 1.5, roe: 1.5 },
  },
  growth: {
    name: "成长型",
    desc: "聚焦高成长潜力股",
    topK: 6,
    targetRiskPct: 0.025,
    atrStopLoss: 1.0,
    atrTakeProfit: 3.0,
    factorWeights: { roe: 2.0, revenue: 2.0, gross_margin: 1.5, momentum: 1.3 },
  },
  value: {
    name: "价值型",
    desc: "低估值选股，安全边际优先",
    topK: 8,
    targetRiskPct: 0.015,
    atrStopLoss: 0.75,
    atrTakeProfit: 2.5,
    factorWeights: { pe: 2.0, pb: 2.0, ps: 1.5, dividend: 2.0, roe: 1.3 },
  },
};

export interface StrategyPick {
  symbol: string;
  name: string;
  rank: number;
  close: number;
  weight: number;
  pnlPct: number;
  shares: number;
}

export interface StrategyBrief {
  id: string;
  name: string;
  description: string;
  topK: number;
  pickCount: number;
  totalValue: number;
  totalReturn: number | null;
  tradeDate: string;
}

function formatDate(d: Date | string | undefined): string {
  if (!d) return "-";
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toISOString().split("T")[0];
}

async function getProfileNav(profile: string): Promise<NavRow | null> {
  const rows = await queryDuckDB<NavRow>(
    `SELECT trade_date, cash, market_value, total_value
     FROM paper_nav WHERE profile = ? AND market_value > 0
     ORDER BY trade_date DESC LIMIT 1`,
    [profile],
  );
  return rows[0] || null;
}

function oneYearBefore(d: Date): Date {
  const start = new Date(d);
  start.setFullYear(start.getFullYear() - 1);
  return start;
}

async function getProfileNavWindow(profile: string): Promise<{ latest: NavRow; startDate: Date } | null> {
  const latest = await getProfileNav(profile);
  if (!latest) return null;
  return { latest, startDate: oneYearBefore(new Date(latest.trade_date)) };
}

async function getProfilePicks(profile: string): Promise<{
  tradeDate: string; picks: StrategyPick[]; totalValue: number;
} | null> {
  const nav = await getProfileNav(profile);
  if (!nav) return null;

  const totalValue = Number(nav.total_value);
  const positions = await queryDuckDB<PosRow>(
    `SELECT symbol, shares, cost_basis FROM paper_positions
     WHERE profile = ? AND shares > 0 ORDER BY symbol`,
    [profile],
  );
  if (positions.length === 0) return null;

  const symbols = positions.map((p) => `'${p.symbol}'`).join(",");
  const quotes = await queryDuckDB<QuoteRow>(
    `SELECT q.symbol, q.close, q.trade_date FROM daily_quotes q
     INNER JOIN (SELECT symbol, MAX(trade_date) AS td FROM daily_quotes
       WHERE symbol IN (${symbols}) GROUP BY symbol) m
     ON q.symbol = m.symbol AND q.trade_date = m.td`,
  );
  const quoteMap = new Map(quotes.map((q) => [q.symbol, q.close]));

  const names = await queryDuckDB<NameRow>(
    `SELECT symbol, COALESCE(name, symbol) AS name FROM stock_universe WHERE symbol IN (${symbols})`,
  );
  const nameMap = new Map(names.map((r) => [r.symbol, r.name]));

  const totalMv = positions.reduce((sum, p) => {
    const close = quoteMap.get(p.symbol) || Number(p.cost_basis);
    return sum + close * Number(p.shares);
  }, 0);
  const actualTotal = totalValue || (Number(nav.cash) + totalMv) || 1;

  const picks: StrategyPick[] = positions
    .map((p, idx) => {
      const close = quoteMap.get(p.symbol) || Number(p.cost_basis);
      const mv = close * Number(p.shares);
      const cost = Number(p.cost_basis) * Number(p.shares);
      return {
        symbol: p.symbol,
        name: nameMap.get(p.symbol) || p.symbol,
        rank: idx + 1,
        close: Number(close),
        weight: actualTotal > 0 ? mv / actualTotal : 0,
        pnlPct: cost > 0 ? (mv - cost) / cost : 0,
        shares: Number(p.shares),
      };
    })
    .sort((a, b) => b.weight - a.weight);

  return { tradeDate: formatDate(nav.trade_date), picks, totalValue: actualTotal };
}

export const strategiesRouter = createRouter({
  list: publicQuery.query(async () => {
    if (!isDuckDBAvailable()) return [];

    const briefs: StrategyBrief[] = [];
    for (const profile of PROFILES) {
      const label = PROFILE_LABELS[profile];
      const picks = await getProfilePicks(profile);
      const window = await getProfileNavWindow(profile);
      let totalReturn: number | null = null;
      if (window) {
        const startStr = formatDate(window.startDate);
        const navRows = await queryDuckDB<NavRow>(
          `SELECT total_value FROM paper_nav
           WHERE profile = ? AND market_value > 0 AND trade_date >= ?
           ORDER BY trade_date`,
          [profile, startStr],
        );
        if (navRows.length >= 2) {
          const first = Number(navRows[0].total_value);
          const last = Number(navRows[navRows.length - 1].total_value);
          if (first > 0) totalReturn = last / first - 1;
        }
      }
      briefs.push({
        id: profile,
        name: label.name,
        description: label.desc,
        topK: label.topK,
        pickCount: picks?.picks.length || 0,
        totalValue: picks?.totalValue || 0,
        totalReturn,
        tradeDate: picks?.tradeDate || "-",
      });
    }
    return briefs;
  }),

  getPicks: publicQuery
    .input(z.object({ profile: z.string().default("balanced") }))
    .query(async ({ input }) => {
      if (!isDuckDBAvailable()) return null;
      return getProfilePicks(input.profile);
    }),

  getEquity: publicQuery
    .input(z.object({ profile: z.string().default("balanced") }))
    .query(async ({ input }) => {
      if (!isDuckDBAvailable()) return null;
      const window = await getProfileNavWindow(input.profile);
      if (!window) return null;
      const startStr = formatDate(window.startDate);
      const endStr = formatDate(window.latest.trade_date);
      const rows = await queryDuckDB<NavRow>(
        `SELECT trade_date, total_value FROM paper_nav
         WHERE profile = ? AND market_value > 0 AND trade_date >= ? AND trade_date <= ?
         ORDER BY trade_date`,
        [input.profile, startStr, endStr],
      );
      if (rows.length < 2) return null;
      const first = Number(rows[0].total_value);
      if (first <= 0) return null;

      // Load benchmark closes for the same window
      const benchRows = await queryDuckDB<QuoteRow>(
        `SELECT symbol, trade_date, close FROM daily_quotes
         WHERE symbol IN ('000300.SH', '000001.SH')
           AND trade_date >= ? AND trade_date <= ?
         ORDER BY symbol, trade_date`,
        [startStr, endStr],
      );

      const csi = benchRows.filter((r) => r.symbol === "000300.SH");
      const sse = benchRows.filter((r) => r.symbol === "000001.SH");
      const csiFirst = csi.length > 0 ? Number(csi[0].close) : 0;
      const sseFirst = sse.length > 0 ? Number(sse[0].close) : 0;
      const csiMap = new Map(csi.map((r) => [formatDate(r.trade_date), Number(r.close)]));
      const sseMap = new Map(sse.map((r) => [formatDate(r.trade_date), Number(r.close)]));

      let lastCsi = csiFirst || 0;
      let lastSse = sseFirst || 0;

      const points: EquityPoint[] = rows.map((r) => {
        const tradeDate = formatDate(r.trade_date);
        if (csiMap.has(tradeDate)) lastCsi = csiMap.get(tradeDate)!;
        if (sseMap.has(tradeDate)) lastSse = sseMap.get(tradeDate)!;
        const point: EquityPoint = {
          tradeDate,
          normalizedValue: Number((Number(r.total_value) / first).toFixed(6)),
        };
        if (csiFirst > 0 && lastCsi > 0) {
          point.csi300Normalized = Number((lastCsi / csiFirst).toFixed(6));
        }
        if (sseFirst > 0 && lastSse > 0) {
          point.sseNormalized = Number((lastSse / sseFirst).toFixed(6));
        }
        return point;
      });

      return points;
    }),

  getProfile: publicQuery
    .input(z.object({ profile: z.string().default("balanced") }))
    .query(async ({ input }) => {
      const label = PROFILE_LABELS[input.profile];
      if (!label) return null;
      return {
        id: input.profile,
        name: label.name,
        description: label.desc,
        topK: label.topK,
        targetRiskPct: label.targetRiskPct,
        atrStopLoss: label.atrStopLoss,
        atrTakeProfit: label.atrTakeProfit,
        factorWeights: label.factorWeights,
      };
    }),
});
