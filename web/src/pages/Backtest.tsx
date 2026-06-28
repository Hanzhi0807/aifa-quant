import { useState } from "react";
import {
  Play,
  RotateCcw,
  Settings,
  BarChart3,
  TrendingUp,
  ListOrdered,
  ShieldAlert,
  PieChart,
  Cpu,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { trpc } from "@/providers/trpc";
import GlassCard from "@/components/layout/GlassCard";
import EquityCurveChart from "@/components/dashboard/EquityCurveChart";
import MetricsGrid from "@/components/dashboard/MetricsGrid";
import FactorChart from "@/components/dashboard/FactorChart";

interface BacktestRun {
  id: number;
  name: string;
  startDate: string;
  endDate: string;
  topK: number;
  rebalanceFreq: number;
  rolling: boolean;
  benchmark: string;
  status: string;
  metrics: Record<string, number> | null;
  createdAt: string;
}

interface OrderRow {
  orderId: string;
  tradeDate: string;
  symbol: string;
  side: string;
  quantity: number;
  fillPrice: number;
  commission: number;
  stampDuty: number;
  status: string;
}

interface RiskPosition {
  symbol: string;
  name: string;
  shares: number;
  costBasis: number;
  currentPrice: number;
  stopLossPrice: number | null;
  takeProfitPrice: number | null;
  atr: number | null;
  unrealizedPnlPct: number;
}

const PROFILES = [
  { id: "balanced", label: "均衡型" },
  { id: "aggressive", label: "激进型" },
  { id: "conservative", label: "稳健型" },
  { id: "growth", label: "成长型" },
  { id: "value", label: "价值型" },
];

const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
};

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "已完成",
    running: "运行中",
    failed: "失败",
    pending: "待运行",
  };
  const cls =
    status === "completed"
      ? "status-completed"
      : status === "running"
        ? "status-running animate-pulse-cyan"
        : "status-failed";
  return <span className={cls}>{map[status] || status}</span>;
}

export default function Backtest() {
  const [tab, setTab] = useState<
    "config" | "metrics" | "equity" | "orders" | "risk" | "factors" | "model"
  >("config");
  const [profile, setProfile] = useState("balanced");
  const [search, setSearch] = useState("");

  const [start, setStart] = useState("20250101");
  const [end, setEnd] = useState(todayStr());
  const [topK, setTopK] = useState(5);
  const [freq, setFreq] = useState(5);
  const [rolling, setRolling] = useState(true);
  const [benchmark, setBenchmark] = useState("000300.SH");

  const utils = trpc.useUtils();

  const { data: backtests, isLoading: btLoading } = trpc.backtest.list.useQuery();
  const { data: orders, isLoading: ordersLoading } = trpc.orders.list.useQuery({ profile });
  const { data: riskStatus, isLoading: riskLoading } = trpc.risk.status.useQuery({ profile });
  const { data: models, isLoading: modelsLoading } = trpc.model.list.useQuery();

  const runMutation = trpc.backtestRunner.run.useMutation({
    onSuccess: async (res) => {
      if (res.success) {
        toast.success("回测完成", { description: "已生成最新报告" });
        await utils.backtest.list.invalidate();
        await utils.metrics.latest.invalidate();
        await utils.equityCurve.latest.invalidate();
      } else {
        toast.error("回测失败", { description: res.error });
      }
    },
    onError: (err) => toast.error("回测失败", { description: err.message }),
  });

  const runs = (backtests || []) as BacktestRun[];
  const filtered = runs.filter((r) => r.name.toLowerCase().includes(search.toLowerCase()));

  const latestRun = runs[0];
  const runMetrics = latestRun?.metrics || null;

  const tabs = [
    { key: "config", label: "配置 / 执行", icon: Settings },
    { key: "metrics", label: "绩效指标", icon: BarChart3 },
    { key: "equity", label: "权益曲线", icon: TrendingUp },
    { key: "orders", label: "订单历史", icon: ListOrdered },
    { key: "risk", label: "ATR 风控", icon: ShieldAlert },
    { key: "factors", label: "因子重要性", icon: PieChart },
    { key: "model", label: "模型信息", icon: Cpu },
  ] as const;

  const onRun = () => {
    runMutation.mutate({ start, end, topK, freq, rolling, benchmark });
  };

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        <div className="animate-fade-in">
          <h1 className="text-2xl font-bold text-white mb-1">回测 / 绩效</h1>
          <p className="text-sm text-[var(--text-secondary)]">
            运行真实回测、查看绩效指标、订单、风控与模型细节
          </p>
        </div>

        <div className="flex flex-wrap gap-2 bg-white/5 p-1 rounded-xl">
          {tabs.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                  tab === t.key
                    ? "bg-[var(--cyan)]/15 text-[var(--cyan)]"
                    : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            );
          })}
        </div>

        {tab === "config" && (
          <div className="space-y-6">
            <GlassCard title="运行新回测" subtitle="调用 Python CLI 执行真实回测">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">开始日期</span>
                  <input
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">结束日期</span>
                  <input
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">基准</span>
                  <select
                    value={benchmark}
                    onChange={(e) => setBenchmark(e.target.value)}
                    className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                  >
                    <option value="000300.SH">沪深 300</option>
                    <option value="000001.SH">上证指数</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">Top-K</span>
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-[var(--text-muted)]">调仓频率（天）</span>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={freq}
                    onChange={(e) => setFreq(Number(e.target.value))}
                    className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
                  />
                </label>
                <label className="flex items-center gap-2 mt-5">
                  <input
                    type="checkbox"
                    checked={rolling}
                    onChange={(e) => setRolling(e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-black/30"
                  />
                  <span className="text-sm text-[var(--text-secondary)]">滚动训练</span>
                </label>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={onRun}
                  disabled={runMutation.isPending}
                  className="flex items-center gap-2 px-5 py-2.5 bg-[var(--cyan)]/15 hover:bg-[var(--cyan)]/25 text-[var(--cyan)] rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {runMutation.isPending ? (
                    <RotateCcw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  {runMutation.isPending ? "运行中..." : "执行回测"}
                </button>
                <code className="hidden md:block flex-1 bg-black/30 rounded-lg px-3 py-2 text-xs text-[var(--text-muted)] font-mono border border-white/5 truncate">
                  python -m aifa_quant.cli.main backtest --start {start} --end {end}
                  {rolling ? " --rolling" : ""} --benchmark {benchmark} --top-k {topK} --freq {freq}
                  --no-sentiment --cache-only
                </code>
              </div>
              {runMutation.data && !runMutation.data.success && (
                <pre className="mt-4 bg-red-500/5 border border-red-500/20 rounded-lg p-3 text-xs text-red-200 overflow-auto max-h-40">
                  {runMutation.data.stderr || runMutation.data.error}
                </pre>
              )}
              {runMutation.data?.success && (
                <pre className="mt-4 bg-black/30 border border-white/5 rounded-lg p-3 text-xs text-[var(--text-secondary)] overflow-auto max-h-40">
                  {runMutation.data.stdout}
                </pre>
              )}
            </GlassCard>

            <GlassCard
              title="回测历史"
              action={
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                  <input
                    type="text"
                    placeholder="搜索回测..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="bg-white/5 border border-white/5 rounded-full pl-9 pr-4 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--cyan)]/30 w-56"
                  />
                </div>
              }
            >
              {btLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-14 bg-white/5 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">名称</th>
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">时间区间</th>
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">Top-K</th>
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">调仓频率</th>
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">滚动训练</th>
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">收益率</th>
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3 pr-4">夏普</th>
                        <th className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-3">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((run) => (
                        <tr key={run.id} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                          <td className="py-3.5 pr-4 text-sm font-medium text-white">{run.name}</td>
                          <td className="py-3.5 pr-4 text-xs text-[var(--text-secondary)]">{run.startDate} ~ {run.endDate}</td>
                          <td className="py-3.5 pr-4 text-sm text-[var(--text-secondary)]">{run.topK}</td>
                          <td className="py-3.5 pr-4 text-sm text-[var(--text-secondary)]">{run.rebalanceFreq}d</td>
                          <td className={`py-3.5 pr-4 text-xs font-medium ${run.rolling ? "text-[var(--green)]" : "text-[var(--text-muted)]"}`}>{run.rolling ? "是" : "否"}</td>
                          <td className={`py-3.5 pr-4 text-sm font-medium ${(run.metrics?.totalReturn || 0) >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                            {run.metrics?.totalReturn ? `${(run.metrics.totalReturn * 100).toFixed(2)}%` : "-"}
                          </td>
                          <td className="py-3.5 pr-4 text-sm text-[var(--cyan)]">{run.metrics?.sharpeRatio?.toFixed(2) || "-"}</td>
                          <td className="py-3.5"><StatusBadge status={run.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filtered.length === 0 && (
                    <div className="text-center py-12">
                      <p className="text-sm text-[var(--text-muted)]">暂无回测记录</p>
                    </div>
                  )}
                </div>
              )}
            </GlassCard>
          </div>
        )}

        {tab === "metrics" && (
          <div className="space-y-6">
            {!runMetrics && !btLoading && (
              <div className="glass-card rounded-2xl p-6 text-center text-sm text-[var(--text-muted)]">
                暂无回测绩效数据
              </div>
            )}
            <MetricsGrid />
          </div>
        )}

        {tab === "equity" && (
          <div className="space-y-6">
            <EquityCurveChart />
          </div>
        )}

        {tab === "orders" && (
          <GlassCard title="订单历史" subtitle={`当前选中策略：${PROFILES.find((p) => p.id === profile)?.label}`}>
            <div className="flex flex-wrap gap-2 mb-4">
              {PROFILES.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setProfile(p.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    profile === p.id
                      ? "bg-[var(--cyan)]/15 text-[var(--cyan)]"
                      : "bg-white/5 text-[var(--text-muted)] hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {ordersLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-12 bg-white/5 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : orders && orders.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/5 text-[var(--text-muted)] text-xs">
                      <th className="text-left py-2 pr-4">日期</th>
                      <th className="text-left py-2 pr-4">股票</th>
                      <th className="text-left py-2 pr-4">方向</th>
                      <th className="text-right py-2 pr-4">数量</th>
                      <th className="text-right py-2 pr-4">成交价</th>
                      <th className="text-right py-2 pr-4">佣金</th>
                      <th className="text-right py-2 pr-4">印花税</th>
                      <th className="text-left py-2">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(orders as OrderRow[]).map((o) => (
                      <tr key={o.orderId} className="border-b border-white/[0.03]">
                        <td className="py-3 pr-4 text-[var(--text-secondary)]">{o.tradeDate}</td>
                        <td className="py-3 pr-4 text-white font-medium">{o.symbol}</td>
                        <td className="py-3 pr-4">
                          <span className={`px-2 py-0.5 rounded-full text-xs ${o.side === "BUY" ? "bg-[var(--green)]/10 text-[var(--green)]" : "bg-[var(--red)]/10 text-[var(--red)]"}`}>
                            {o.side === "BUY" ? "买入" : "卖出"}
                          </span>
                        </td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">{o.quantity}</td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{o.fillPrice.toFixed(2)}</td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{o.commission.toFixed(2)}</td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{o.stampDuty.toFixed(2)}</td>
                        <td className="py-3 text-[var(--text-secondary)]">{o.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-[var(--text-muted)]">暂无订单数据</p>
            )}
          </GlassCard>
        )}

        {tab === "risk" && (
          <GlassCard title="ATR 风控" subtitle={`当前选中策略：${PROFILES.find((p) => p.id === profile)?.label}`}>
            <div className="flex flex-wrap gap-2 mb-4">
              {PROFILES.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setProfile(p.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    profile === p.id
                      ? "bg-[var(--cyan)]/15 text-[var(--cyan)]"
                      : "bg-white/5 text-[var(--text-muted)] hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {riskLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-12 bg-white/5 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : riskStatus?.positions && riskStatus.positions.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/5 text-[var(--text-muted)] text-xs">
                      <th className="text-left py-2 pr-4">股票</th>
                      <th className="text-right py-2 pr-4">持仓股数</th>
                      <th className="text-right py-2 pr-4">成本价</th>
                      <th className="text-right py-2 pr-4">最新价</th>
                      <th className="text-right py-2 pr-4">浮盈亏</th>
                      <th className="text-right py-2 pr-4">ATR</th>
                      <th className="text-right py-2 pr-4">止损价</th>
                      <th className="text-right py-2">止盈价</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(riskStatus.positions as RiskPosition[]).map((pos) => (
                      <tr key={pos.symbol} className="border-b border-white/[0.03]">
                        <td className="py-3 pr-4">
                          <span className="text-white font-medium">{pos.name || pos.symbol}</span>
                          <span className="ml-2 text-xs text-[var(--text-muted)]">{pos.symbol}</span>
                        </td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">{pos.shares}</td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{pos.costBasis.toFixed(2)}</td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">¥{pos.currentPrice.toFixed(2)}</td>
                        <td className={`text-right py-3 pr-4 ${pos.unrealizedPnlPct >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                          {(pos.unrealizedPnlPct * 100).toFixed(1)}%
                        </td>
                        <td className="text-right py-3 pr-4 text-[var(--text-secondary)]">{pos.atr != null ? pos.atr.toFixed(2) : "-"}</td>
                        <td className="text-right py-3 pr-4 text-[var(--red)]">{pos.stopLossPrice != null ? pos.stopLossPrice.toFixed(2) : "-"}</td>
                        <td className="text-right py-3 text-[var(--green)]">{pos.takeProfitPrice != null ? pos.takeProfitPrice.toFixed(2) : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-[var(--text-muted)]">暂无风控数据</p>
            )}
            <p className="text-xs text-[var(--text-muted)] mt-4">
              止损/止盈价基于 14 日 ATR 动态计算。盘中不触发调仓，每日收盘后按最新收盘价重新评估。
            </p>
          </GlassCard>
        )}

        {tab === "factors" && (
          <div className="space-y-6">
            <FactorChart />
            {modelsLoading ? (
              <div className="h-32 bg-white/5 rounded-xl animate-pulse" />
            ) : !models || models.length === 0 ? (
              <div className="glass-card rounded-2xl p-6 text-center text-sm text-[var(--text-muted)]">
                暂无模型数据
              </div>
            ) : null}
          </div>
        )}

        {tab === "model" && (
          <GlassCard title="模型信息" subtitle="最新 LightGBM 滚动模型">
            {modelsLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-12 bg-white/5 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : models && models.length > 0 ? (
              <div className="space-y-4">
                {models.slice(0, 1).map((m) => (
                  <div key={m.id} className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div className="bg-white/[0.03] rounded-xl p-4">
                      <p className="text-xs text-[var(--text-muted)] mb-1">模型名称</p>
                      <p className="text-white font-medium">{m.name}</p>
                    </div>
                    <div className="bg-white/[0.03] rounded-xl p-4">
                      <p className="text-xs text-[var(--text-muted)] mb-1">路径</p>
                      <p className="text-[var(--cyan)] font-mono text-xs break-all">{m.path}</p>
                    </div>
                    <div className="bg-white/[0.03] rounded-xl p-4">
                      <p className="text-xs text-[var(--text-muted)] mb-1">训练区间</p>
                      <p className="text-white">{m.trainStart} ~ {m.trainEnd}</p>
                    </div>
                    <div className="bg-white/[0.03] rounded-xl p-4">
                      <p className="text-xs text-[var(--text-muted)] mb-1">特征数</p>
                      <p className="text-white">{m.featureColumns.length}</p>
                    </div>
                    <div className="bg-white/[0.03] rounded-xl p-4 md:col-span-2">
                      <p className="text-xs text-[var(--text-muted)] mb-2">特征列示例</p>
                      <div className="flex flex-wrap gap-1.5">
                        {m.featureColumns.slice(0, 30).map((col) => (
                          <span key={col} className="px-2 py-0.5 bg-white/5 rounded-md text-[10px] text-[var(--text-secondary)]">
                            {col}
                          </span>
                        ))}
                        {m.featureColumns.length > 30 && (
                          <span className="px-2 py-0.5 text-[10px] text-[var(--text-muted)]">+{m.featureColumns.length - 30}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-muted)]">暂无模型信息</p>
            )}
          </GlassCard>
        )}

        <footer className="text-center pt-6 border-t border-white/5">
          <p className="text-xs text-[var(--text-muted)]">
            AifaQuant — 回测数据来自真实 CLI 输出，历史表现不代表未来收益。
          </p>
        </footer>
      </div>
    </div>
  );
}
