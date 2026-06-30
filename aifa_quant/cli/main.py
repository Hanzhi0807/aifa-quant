"""Command-line interface for AifaQuant."""

import json

import pandas as pd
import typer
from rich import print
from rich.console import Console
from rich.table import Table

from ..analysis import (
    compute_factor_decay,
    compute_ic_summary,
    compute_quantile_returns,
    explain_model,
)
from ..backtest import BacktestEngine, compute_metrics
from ..config.settings import Settings
from ..data.adapters import AkShareAdapter, IndexMCPAdapter, StockMCPAdapter, TushareAdapter
from ..data.pipeline import DailyUpdatePipeline
from ..data.storage import DuckDBStore
from ..features import FeatureBuilder
from ..models import EnsembleModel, LGBLambdaRankModel, LGBRankerModel, XGBRankerModel
from ..models.registry import ModelRegistry
from ..models.rolling_trainer import RollingTrainer
from ..paper_trading import PaperTradingEngine
from ..research import generate_weekly_report
from ..strategy import TopKDropoutStrategy
from ..strategy.profiles import apply_profile_score
from ..strategy.templates import get_template, list_templates

app = typer.Typer(help="AifaQuant - A股 AI 量化研究框架")
console = Console()


def _confirm_ifind_usage(action: str, yes: bool) -> None:
    """Prompt user before any operation that calls iFind MCP."""
    if yes:
        return
    message = f"以下操作将调用 iFind MCP：{action}。是否继续？"
    if not typer.confirm(message, default=False):
        print("[cyan]已取消操作[/cyan]")
        raise typer.Exit(code=0)


@app.command()
def test_connection(
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
):
    """Test connectivity to iFind MCP stock server and list available tools."""
    _confirm_ifind_usage("test-connection", yes)
    settings = Settings()
    adapter = StockMCPAdapter(settings)
    try:
        tools = adapter.list_tools()
        print(f"[green]连接成功！发现 {len(tools)} 个工具[/green]")
        table = Table(title="iFind Stock MCP Tools")
        table.add_column("Tool Name", style="cyan")
        table.add_column("Description", style="magenta")
        for tool in tools:
            table.add_row(tool.get("name", ""), tool.get("description", "")[:60])
        console.print(table)
    except Exception as e:
        print(f"[red]连接失败: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def list_tools(
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
):
    """Alias for test-connection."""
    test_connection(yes=yes)


@app.command()
def data_update(
    symbols: list[str] | None = typer.Option(None, "--symbol", "-s", help="Stock symbols to update"),
    symbol_file: str | None = typer.Option(None, "--symbol-file", help="Path to file with one symbol per line"),
    start: str = typer.Option("20230101", "--start", help="Start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="End date YYYYMMDD"),
    full: bool = typer.Option(False, "--full", help="Full refresh instead of incremental"),
    universe: str = typer.Option("沪深300", "--universe", help="Stock universe query (e.g., 上证50, 沪深300, 全部A股)"),
    sample: int | None = typer.Option(None, "--sample", help="Limit universe to first N stocks for testing"),
    workers: int = typer.Option(3, "--workers", help="Concurrent download workers"),
    fundamental: bool = typer.Option(False, "--fundamental", help="Also fetch and cache PE/PB/ROE fundamental data"),
    macro: bool = typer.Option(False, "--macro", help="Also fetch and cache CPI/PMI/M2 macro data"),
    skip_daily: bool = typer.Option(
        False, "--skip-daily", help="Skip daily quote download (useful when only updating fundamental/macro)"
    ),
    source: str = typer.Option("akshare", "--source", help="Data source: akshare (default), tushare, or ifind"),
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
):
    """Fetch daily quotes from the configured source and persist to DuckDB."""
    # Map friendly universe names to iFind queries when iFind is selected
    ifind_used = source == "ifind" or fundamental or macro
    if ifind_used:
        action_parts = [f"source={source}"]
        if fundamental:
            action_parts.append("fundamental")
        if macro:
            action_parts.append("macro")
        _confirm_ifind_usage("data-update " + ", ".join(action_parts), yes)

    if source == "ifind":
        universe_queries = {
            "上证50": "上证50成分股",
            "沪深300": "沪深300成分股",
            "全部A股": "A股上市股票列表",
        }
        query = universe_queries.get(universe, universe)
    elif source == "tushare":
        # Tushare uses index ts_code like 000300.SH
        query = universe if universe.endswith(".SH") or universe.endswith(".SZ") else "000300.SH"
    else:
        query = universe

    if symbol_file:
        from pathlib import Path

        symbols = [line.strip() for line in Path(symbol_file).read_text(encoding="utf-8").splitlines() if line.strip()]

    pipeline = DailyUpdatePipeline(Settings(), max_workers=workers, data_source=source)
    if symbols:
        target_symbols = symbols
    else:
        target_symbols = pipeline.fetch_stock_universe(query=query)
        print(f"[cyan]获取到 {len(target_symbols)} 只股票[/cyan]")

    if sample is not None and sample > 0:
        target_symbols = target_symbols[:sample]
        print(f"[cyan]已限制为前 {len(target_symbols)} 只股票[/cyan]")
    if not skip_daily:
        total_rows = pipeline.update_daily_quotes(
            symbols=target_symbols,
            start_date=start,
            end_date=end,
            incremental=not full,
        )
        print(f"[bold green]日线数据共写入 {total_rows} 条[/bold green]")
    else:
        print("[cyan]已跳过日线下载[/cyan]")

    if fundamental:
        fundamental_rows = pipeline.update_fundamental_data(symbols=target_symbols, start_date=start, end_date=end)
        print(f"[bold green]基本面数据共写入 {fundamental_rows} 条[/bold green]")

    if macro:
        macro_rows = pipeline.update_macro_data(start_date=start, end_date=end)
        print(f"[bold green]宏观数据共写入 {macro_rows} 条[/bold green]")


@app.command()
def backtest(
    start: str = typer.Option("20240101", "--start", help="Backtest start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="Backtest end date YYYYMMDD"),
    model_name: str = typer.Option("lgb_stock_selector", "--model", help="Model artifact name"),
    strategy_name: str = typer.Option("topk_dropout", "--strategy", help="Strategy name: topk_dropout (default)"),
    template: str | None = typer.Option(
        None, "--template", help="Strategy template name (overrides top_k/freq/dropout)"
    ),
    top_k: int = typer.Option(3, "--top-k", help="Number of stocks to hold"),
    freq: int = typer.Option(5, "--freq", help="Rebalance frequency in days"),
    dropout_threshold: int | None = typer.Option(
        None, "--dropout-threshold", help="Drop held stock if rank exceeds this"
    ),
    initial_cash: float = typer.Option(1_000_000.0, "--cash", help="Initial capital"),
    rolling: bool = typer.Option(False, "--rolling", help="Use rolling window training to avoid look-ahead bias"),
    rolling_model: str = typer.Option("lambdarank", "--rolling-model", help="Model type for rolling training: classifier, lambdarank, xgboost"),
    label_type: str = typer.Option("excess_quantile", "--label-type", help="Label scheme for rolling training: binary, excess_quantile, triple_barrier"),
    drop_middle: bool = typer.Option(False, "--drop-middle", help="Drop middle quantile for excess_quantile labels"),
    pt_mult: float = typer.Option(2.0, "--pt-mult", help="Profit-taking ATR multiplier for triple_barrier"),
    sl_mult: float = typer.Option(1.0, "--sl-mult", help="Stop-loss ATR multiplier for triple_barrier"),
    max_holding: int = typer.Option(10, "--max-holding", help="Max holding days for triple_barrier"),
    benchmark: str = typer.Option("000300.SH", "--benchmark", help="Benchmark index symbol"),
    include_fundamental: bool = typer.Option(
        True, "--fundamental/--no-fundamental", help="Include fundamental factors (PE/PB/ROE)"
    ),
    include_macro: bool = typer.Option(True, "--macro/--no-macro", help="Include macro factors (CPI/PMI/M2)"),
    include_sentiment: bool = typer.Option(True, "--sentiment/--no-sentiment", help="Include news sentiment factors"),
    neutralize: bool = typer.Option(True, "--neutralize/--no-neutralize", help="Neutralize alpha/momentum/volatility factors against industry and market cap"),
    corr_threshold: float = typer.Option(
        0.95,
        "--corr-threshold",
        help="Rolling backtests: drop one feature from each train-window pair with abs correlation >= threshold (set 1.0 to disable)",
    ),
    cache_only: bool = typer.Option(
        False, "--cache-only", help="Only use cached fundamental/macro data; do not call iFind for missing data"
    ),
    source: str = typer.Option("akshare", "--source", help="Data source: akshare (default), tushare, or ifind"),
    ensemble_path: str | None = typer.Option(
        None, "--ensemble", help="Path to ensemble config JSON; overrides single model"
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
    profile: str | None = typer.Option(None, "--profile", help="Strategy profile to apply factor weighting"),
    save_paper_nav: bool = typer.Option(
        False, "--save-paper-nav", help="Write equity curve to paper_nav for the selected profile"
    ),
    save_paper_positions: bool = typer.Option(
        False, "--save-paper-positions", help="Write final positions to paper_positions for the selected profile"
    ),
    min_liquidity: float = typer.Option(
        5000.0, "--min-liquidity", help="Minimum 20-day average daily amount in 万元"
    ),
    weighting: str = typer.Option(
        "equal", "--weighting", help="Portfolio weighting: equal (default) or qp"
    ),
):
    """Run backtest using trained model and TopK-Dropout strategy."""
    if profile:
        from ..strategy.profiles import get_profile

        pf = get_profile(profile)
        if pf:
            top_k = pf.top_k
            print(f"[cyan]应用策略 profile {profile}: top_k={top_k}[/cyan]")

    if template:
        tmpl = get_template(template)
        top_k = tmpl.top_k
        freq = tmpl.rebalance_freq
        if dropout_threshold is None:
            dropout_threshold = tmpl.dropout_threshold
        print(f"[cyan]应用策略模板 {template}: top_k={top_k}, freq={freq}, dropout={dropout_threshold}[/cyan]")

    ifind_used = source == "ifind" or ((include_fundamental or include_macro or include_sentiment) and not cache_only)
    if ifind_used:
        action_parts = [f"source={source}"]
        if include_fundamental and not cache_only:
            action_parts.append("fundamental")
        if include_macro and not cache_only:
            action_parts.append("macro")
        if include_sentiment:
            action_parts.append("sentiment")
        _confirm_ifind_usage("backtest " + ", ".join(action_parts), yes)

    settings = Settings()
    builder = FeatureBuilder(settings)

    # Load features
    print("[yellow]正在构建特征...[/yellow]")
    features = builder.build_features(
        start_date=start,
        end_date=end,
        include_fundamental=include_fundamental,
        include_macro=include_macro,
        include_sentiment=include_sentiment,
        neutralize=neutralize,
        corr_threshold=corr_threshold,
        cache_only=cache_only,
        label_type=label_type if rolling else "excess_quantile",
        drop_middle=drop_middle if rolling else False,
        pt_mult=pt_mult,
        sl_mult=sl_mult,
        max_holding=max_holding,
    )
    if features.empty:
        print("[red]没有可用特征数据[/red]")
        raise typer.Exit(code=1)

    feature_cols = builder.feature_columns(features)

    model = None
    if rolling:
        print("[yellow]正在滚动训练生成 out-of-sample 预测...[/yellow]")
        model_factory = {
            "classifier": LGBRankerModel,
            "lambdarank": LGBLambdaRankModel,
            "xgboost": XGBRankerModel,
        }.get(rolling_model)
        if model_factory is None:
            print(f"[red]未知滚动模型类型: {rolling_model}[/red]")
            raise typer.Exit(code=1)
        trainer = RollingTrainer(
            model_factory=model_factory,
            train_window_days=252 * 2,
            min_train_samples=500,
            settings=settings,
            label_horizon=5,
            label_type=label_type,
            corr_threshold=corr_threshold,
        )
        # Align retraining dates with rebalance frequency to avoid training every day.
        all_dates = sorted(features["trade_date"].unique())
        rebalance_dates = all_dates[::freq]
        preds = trainer.predict_rolling(features, rebalance_dates=rebalance_dates)
        features = features.merge(preds, on=["symbol", "trade_date"], how="inner")
    else:
        # Load pre-trained model or ensemble
        if ensemble_path:
            registry_dir = settings.models_dir_path
            model = EnsembleModel.from_config(ensemble_path, registry_dir=registry_dir)
            print(f"[green]已加载 Ensemble: {ensemble_path}[/green]")
        else:
            registry = ModelRegistry(settings)
            model_path = registry.path(model_name)
            if not model_path.exists():
                print(f"[red]模型不存在: {model_path}，请先运行 train 命令、使用 --ensemble 或 --rolling[/red]")
                raise typer.Exit(code=1)
            model = LGBRankerModel()
            model.load(str(model_path))
            print(f"[green]已加载模型: {model_path}[/green]")
        pred_df = features.dropna(subset=feature_cols).copy()
        pred_df["pred_score"] = model.predict(pred_df[feature_cols])
        if profile:
            pred_df = apply_profile_score(pred_df, profile, feature_cols)
        features = pred_df

    # Load raw quotes for execution (include CSI300 for regime filter)
    store = DuckDBStore(settings)
    symbols = features["symbol"].unique().tolist()
    all_symbols = list(set(symbols + ["000300.SH"]))
    quotes = store.load_daily_quotes(all_symbols, start_date=start, end_date=end)

    # Load industry map and ST flags for concentration control / limit ratios
    industry_map: dict[str, str] | None = None
    st_symbols: set[str] = set()
    try:
        universe = store.load_stock_universe()
        if not universe.empty and "industry" in universe.columns:
            industry_map = dict(zip(universe["symbol"], universe["industry"]))
        if "is_st" in universe.columns:
            st_symbols = set(universe.loc[universe["is_st"].astype(bool), "symbol"].tolist())
    except Exception:
        pass

    # Warn if corr_threshold has no effect in non-rolling mode
    if not rolling and corr_threshold is not None and corr_threshold < 1.0:
        print(
            f"[yellow]警告: --corr-threshold={corr_threshold} 在非 --rolling 模式下不生效。"
            "相关性筛选仅在滚动训练窗口内执行。请用 --rolling 或在 train 命令中筛选。[/yellow]"
        )

    # Determine regime threshold from profile
    regime_threshold = 0.0
    max_industry_pct = 0.30
    if profile:
        from ..strategy.profiles import get_profile as _get_profile
        pf = _get_profile(profile)
        if pf:
            regime_threshold = pf.regime_ma_threshold
            max_industry_pct = pf.max_industry_pct

    # Select strategy
    if strategy_name == "topk_dropout":
        strategy = TopKDropoutStrategy(
            top_k=top_k, rebalance_freq=freq,
            dropout_threshold=dropout_threshold,
            max_industry_pct=max_industry_pct,
            min_liquidity_wan=min_liquidity,
        )
    else:
        print(f"[red]未知策略: {strategy_name}[/red]")
        raise typer.Exit(code=1)

    # Run backtest with regime filter, industry map and ST symbols
    optimizer = None
    if weighting == "qp":
        from ..strategy.optimizer import MeanVarianceOptimizer, OptimizerConfig
        optimizer = MeanVarianceOptimizer(OptimizerConfig())
        print("[cyan]启用 QP 均值-方差优化器[/cyan]")
    engine = BacktestEngine(
        initial_cash=initial_cash, rebalance_freq=freq,
        regime_ma_threshold=regime_threshold,
        industry_map=industry_map,
        st_symbols=st_symbols,
        weighting=weighting,
        optimizer=optimizer,
    )
    equity = engine.run(quotes, features, model, strategy, start_date=start, end_date=end)

    if equity.empty:
        print("[red]回测未产生结果[/red]")
        raise typer.Exit(code=1)

    # Fetch benchmark
    bench_df = None
    try:
        if source == "akshare":
            index_adapter = AkShareAdapter(settings)
            bench_df = index_adapter.get_index_data(benchmark, start_date=start, end_date=end)
        elif source == "tushare":
            index_adapter = TushareAdapter(settings)
            bench_df = index_adapter.get_index_data(benchmark, start_date=start, end_date=end)
        else:
            index_adapter = IndexMCPAdapter(settings)
            bench_df = index_adapter.get_daily_data(benchmark, start_date=start, end_date=end)
        if bench_df.empty or "close" not in bench_df.columns:
            bench_df = None
    except Exception as e:
        print(f"[yellow]获取基准 {benchmark} 失败: {e}[/yellow]")

    metrics = compute_metrics(equity, benchmark_curve=bench_df, trades=engine.trades, features=features)
    print("\n[bold]回测绩效[/bold]")
    table = Table(title="Performance Metrics")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="magenta")
    table.add_row("总收益率", f"{metrics['total_return']:.2%}")
    table.add_row("年化收益率", f"{metrics['annual_return']:.2%}")
    table.add_row("年化波动率", f"{metrics['annual_volatility']:.2%}")
    table.add_row("夏普比率", f"{metrics['sharpe_ratio']:.3f}")
    table.add_row("最大回撤", f"{metrics['max_drawdown']:.2%}")
    table.add_row("日胜率", f"{metrics['win_rate']:.2%}")
    if "benchmark_total_return" in metrics:
        table.add_row("基准总收益", f"{metrics['benchmark_total_return']:.2%}")
        table.add_row("超额收益", f"{metrics['excess_return']:.2%}")
        table.add_row("超额夏普", f"{metrics['excess_sharpe']:.3f}")
    if "mean_rankic" in metrics:
        table.add_row("平均 RankIC", f"{metrics['mean_rankic']:.4f}")
        table.add_row("ICIR", f"{metrics['icir']:.3f}")
    if "monthly_turnover" in metrics:
        table.add_row("月均单边换手", f"{metrics['monthly_turnover']:.2%}")
        table.add_row("年化换手", f"{metrics['avg_annual_turnover']:.2%}")
    console.print(table)

    # Save equity curve, metrics, trades and plot
    report_dir = settings.data_dir_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"equity_{start}_{end}.csv"
    equity.to_csv(report_path, index=False)

    suffix = "_rolling" if rolling else ""

    if engine.trades:
        trades_df = pd.DataFrame(
            [
                {
                    "trade_date": t.trade_date,
                    "symbol": t.symbol,
                    "action": t.action,
                    "shares": t.shares,
                    "price": t.price,
                    "amount": t.amount,
                }
                for t in engine.trades
            ]
        )
        trades_path = report_dir / f"trades_{start}_{end}{suffix}.csv"
        trades_df.to_csv(trades_path, index=False)
        print(f"[green]交易记录已保存: {trades_path}[/green]")

    metrics_path = report_dir / f"metrics_{start}_{end}{suffix}.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)

    if save_paper_nav and profile:
        from ..strategy.profiles import get_profile

        pf = get_profile(profile)
        profile_id = pf.id if pf else profile
        print(f"[cyan]将权益曲线写入 paper_nav (profile={profile_id})...[/cyan]")
        store = DuckDBStore(settings)
        store.conn.execute(
            "DELETE FROM paper_nav WHERE profile = ? AND trade_date >= ? AND trade_date <= ?",
            [profile_id, pd.to_datetime(start).date(), pd.to_datetime(end).date()],
        )
        for _, row in equity.iterrows():
            total = float(row["total_value"])
            store.conn.execute(
                """
                INSERT INTO paper_nav (profile, trade_date, cash, market_value, total_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                [profile_id, pd.to_datetime(row["trade_date"]).date(), 0.0, total, total],
            )
        print(f"[green]已写入 {len(equity)} 条 paper_nav 记录[/green]")

    if save_paper_positions and profile:
        pf = get_profile(profile)
        profile_id = pf.id if pf else profile
        print(f"[cyan]将最终持仓写入 paper_positions (profile={profile_id})...[/cyan]")
        store.conn.execute("DELETE FROM paper_positions WHERE profile = ?", [profile_id])
        positions = [
            (profile_id, sym, int(pos.shares), float(pos.cost_basis))
            for sym, pos in engine.positions.items()
            if pos.shares > 0
        ]
        if positions:
            store.conn.executemany(
                "INSERT INTO paper_positions (profile, symbol, shares, cost_basis) VALUES (?, ?, ?, ?)",
                positions,
            )

        # Update the final NAV row so market_value > 0 and cash/positions are consistent.
        final_total = float(equity.iloc[-1]["total_value"])
        final_cash = float(engine.cash)
        final_mv = final_total - final_cash
        store.conn.execute(
            """
            UPDATE paper_nav
            SET cash = ?, market_value = ?, total_value = ?
            WHERE profile = ? AND trade_date = ?
            """,
            [final_cash, final_mv, final_total, profile_id, pd.to_datetime(end).date()],
        )
        print(f"[green]已写入 {len(positions)} 只持仓，最新净值 {final_total:,.2f} 元[/green]")

    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(12, 6))
        plt.plot(equity["trade_date"], equity["total_value"] / equity["total_value"].iloc[0], label="Strategy")
        if bench_df is not None and not bench_df.empty:
            bench_norm = bench_df.sort_values("trade_date").reset_index(drop=True)
            bench_norm["normalized"] = bench_norm["close"] / bench_norm["close"].iloc[0]
            plt.plot(bench_norm["trade_date"], bench_norm["normalized"], label=f"Benchmark {benchmark}")
        plt.title("Equity Curve")
        plt.xlabel("Date")
        plt.ylabel("Normalized Value")
        plt.legend()
        plt.grid(True)
        plot_path = report_dir / f"equity_{start}_{end}{suffix}.png"
        plt.savefig(plot_path)
        plt.close()
        print(f"[green]权益曲线图已保存: {plot_path}[/green]")
    except Exception as e:
        print(f"[yellow]绘图失败: {e}[/yellow]")


@app.command()
def factor_analysis(
    start: str = typer.Option("20230101", "--start", help="Start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="End date YYYYMMDD"),
    feature: str | None = typer.Option(
        None, "--feature", help="Analyze a single feature; if omitted, analyze all features"
    ),
    method: str = typer.Option("spearman", "--method", help="IC method: pearson or spearman"),
    horizon: int = typer.Option(5, "--horizon", help="Forward return horizon in days"),
    n_quantiles: int = typer.Option(10, "--quantiles", help="Number of quantile buckets"),
    include_sentiment: bool = typer.Option(False, "--sentiment/--no-sentiment", help="Include news sentiment factors"),
    corr_threshold: float = typer.Option(0.95, "--corr-threshold", help="Compatibility option; filtering is applied only inside rolling backtests"),
    cache_only: bool = typer.Option(True, "--cache-only", help="Only use cached fundamental/macro data"),
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
):
    """Analyze factor effectiveness (IC/RankIC/ICIR/quantile/decay)."""
    if not cache_only or include_sentiment:
        action_parts = []
        if not cache_only:
            action_parts.append("fundamental/macro（如缓存缺失）")
        if include_sentiment:
            action_parts.append("sentiment")
        _confirm_ifind_usage("factor-analysis " + ", ".join(action_parts), yes)

    settings = Settings()
    builder = FeatureBuilder(settings)
    print("[yellow]正在构建特征...[/yellow]")
    df = builder.build_features(
        start_date=start,
        end_date=end,
        label_horizon=horizon,
        include_sentiment=include_sentiment,
        corr_threshold=corr_threshold,
        cache_only=cache_only,
    )
    if df.empty:
        print("[red]没有可用特征数据[/red]")
        raise typer.Exit(code=1)

    feature_cols = builder.feature_columns(df)
    if feature and feature not in feature_cols:
        print(f"[red]指定因子不存在: {feature}[/red]")
        raise typer.Exit(code=1)

    target_features = [feature] if feature else feature_cols
    forward_col = "label_return"

    report_dir = settings.data_dir_path / "reports" / "factor_analysis"
    report_dir.mkdir(parents=True, exist_ok=True)

    # IC summary for all target features
    print(f"[yellow]正在计算 {len(target_features)} 个因子的 IC...[/yellow]")
    summaries = []
    for feat in target_features:
        summary = compute_ic_summary(df, feat, forward_col, method=method)
        if summary:
            summaries.append(summary)

    if not summaries:
        print("[red]无法计算任何因子的 IC[/red]")
        raise typer.Exit(code=1)

    summary_df = pd.DataFrame(summaries).sort_values("icir", ascending=False)
    summary_path = report_dir / f"ic_summary_{start}_{end}.csv"
    summary_df.to_csv(summary_path, index=False)

    table = Table(title="因子有效性摘要（按 ICIR 排序）")
    table.add_column("因子", style="cyan")
    table.add_column("Mean IC", style="magenta")
    table.add_column("ICIR", style="magenta")
    table.add_column("胜率", style="magenta")
    table.add_column("期数", style="magenta")
    for _, row in summary_df.head(20).iterrows():
        table.add_row(
            str(row["feature"]),
            f"{row['mean_ic']:.4f}",
            f"{row['icir']:.3f}",
            f"{row['win_rate']:.2%}",
            str(int(row["n_periods"])),
        )
    console.print(table)
    print(f"[green]完整 IC 摘要已保存: {summary_path}[/green]")

    # Single-feature deep analysis
    if feature:
        print(f"[yellow]正在分析因子 {feature} 的分层收益与衰减...[/yellow]")
        quantile_df = compute_quantile_returns(df, feature, forward_col, n_quantiles=n_quantiles)
        quantile_path = report_dir / f"quantile_{feature}_{start}_{end}.csv"
        quantile_df.to_csv(quantile_path, index=False)

        decay_df = compute_factor_decay(df, feature, price_col="close", method=method)
        decay_path = report_dir / f"decay_{feature}_{start}_{end}.csv"
        decay_df.to_csv(decay_path, index=False)

        try:
            from ..analysis.factor_analysis import plot_ic_distribution, plot_quantile_returns

            ic_series = pd.Series(
                [s["mean_ic"] for s in summaries if s["feature"] == feature],
                index=[pd.Timestamp.now()],
            )
            # Actually plot the IC time series
            from ..analysis.factor_analysis import compute_ic

            ic_series = compute_ic(df, feature, forward_col, method)
            plot_ic_distribution(
                ic_series,
                title=f"{feature} IC Distribution",
                output_path=str(report_dir / f"ic_hist_{feature}_{start}_{end}.png"),
            )
            plot_quantile_returns(
                quantile_df,
                title=f"{feature} Quantile Returns",
                output_path=str(report_dir / f"quantile_{feature}_{start}_{end}.png"),
            )
            print(f"[green]图表已保存到 {report_dir}[/green]")
        except Exception as e:
            print(f"[yellow]绘图失败: {e}[/yellow]")


@app.command()
def db_info():
    """Show stored data summary."""
    store = DuckDBStore()
    count = store.conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()[0]
    symbols = store.conn.execute("SELECT COUNT(DISTINCT symbol) FROM daily_quotes").fetchone()[0]
    date_range = store.conn.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_quotes").fetchone()
    print(f"[bold]数据库:[/bold] {store.db_path}")
    print(f"[bold]股票数:[/bold] {symbols}")
    print(f"[bold]总记录:[/bold] {count}")
    print(f"[bold]日期范围:[/bold] {date_range[0]} ~ {date_range[1]}")


@app.command()
def train(
    start: str = typer.Option("20230101", "--start", help="Training start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="Training end date YYYYMMDD"),
    horizon: int = typer.Option(5, "--horizon", help="Forecast horizon in days"),
    model_name: str = typer.Option("lgb_stock_selector", "--name", help="Model artifact name"),
    model: str = typer.Option("lambdarank", "--model", help="Model type: classifier, lambdarank, xgboost"),
    model_type: str | None = typer.Option(None, "--model-type", help="Deprecated; use --model"),
    label_type: str = typer.Option("excess_quantile", "--label-type", help="Label scheme: binary, excess_quantile, triple_barrier"),
    drop_middle: bool = typer.Option(False, "--drop-middle", help="Drop middle quantile for excess_quantile labels"),
    pt_mult: float = typer.Option(2.0, "--pt-mult", help="Profit-taking ATR multiplier for triple_barrier"),
    sl_mult: float = typer.Option(1.0, "--sl-mult", help="Stop-loss ATR multiplier for triple_barrier"),
    max_holding: int = typer.Option(10, "--max-holding", help="Max holding days for triple_barrier"),
    template: str | None = typer.Option(
        None, "--template", help="Strategy template name (overrides horizon/model)"
    ),
    include_fundamental: bool = typer.Option(
        True, "--fundamental/--no-fundamental", help="Include fundamental factors (PE/PB/ROE)"
    ),
    include_macro: bool = typer.Option(True, "--macro/--no-macro", help="Include macro factors (CPI/PMI/M2)"),
    include_sentiment: bool = typer.Option(True, "--sentiment/--no-sentiment", help="Include news sentiment factors"),
    neutralize: bool = typer.Option(True, "--neutralize/--no-neutralize", help="Neutralize alpha/momentum/volatility factors against industry and market cap"),
    corr_threshold: float = typer.Option(
        0.95,
        "--corr-threshold",
        help="Compatibility option; filtering is applied only inside rolling backtests",
    ),
    cache_only: bool = typer.Option(
        False, "--cache-only", help="Only use cached fundamental/macro data; do not call iFind for missing data"
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
):
    """Train a LightGBM stock selection model."""
    if model_type is not None:
        model = model_type

    if template:
        tmpl = get_template(template)
        horizon = tmpl.horizon
        # Templates historically use "binary"/"lambdarank"; map to new naming.
        model = tmpl.model_type if tmpl.model_type != "binary" else "classifier"
        print(f"[cyan]应用策略模板 {template}: horizon={horizon}, model={model}[/cyan]")

    ifind_used = ((include_fundamental or include_macro) and not cache_only) or include_sentiment
    if ifind_used:
        action_parts = []
        if include_fundamental and not cache_only:
            action_parts.append("fundamental")
        if include_macro and not cache_only:
            action_parts.append("macro")
        if include_sentiment:
            action_parts.append("sentiment")
        _confirm_ifind_usage("train " + ", ".join(action_parts), yes)

    settings = Settings()
    builder = FeatureBuilder(settings)
    df = builder.build_features(
        start_date=start,
        end_date=end,
        label_horizon=horizon,
        label_type=label_type,
        drop_middle=drop_middle,
        pt_mult=pt_mult,
        sl_mult=sl_mult,
        max_holding=max_holding,
        include_fundamental=include_fundamental,
        include_macro=include_macro,
        include_sentiment=include_sentiment,
        neutralize=neutralize,
        corr_threshold=corr_threshold,
        cache_only=cache_only,
    )
    if df.empty:
        print("[red]没有可用数据，请先运行 data-update[/red]")
        raise typer.Exit(code=1)

    features = builder.feature_columns(df)
    df_clean = df.dropna(subset=features + ["label_rank", "label_binary", "label_return"])
    X = df_clean[features]

    model_factory_map = {
        "lambdarank": LGBLambdaRankModel,
        "classifier": LGBRankerModel,
        "binary": LGBRankerModel,
        "xgboost": XGBRankerModel,
    }
    model_cls = model_factory_map.get(model)
    if model_cls is None:
        print(f"[red]未知模型类型: {model}[/red]")
        raise typer.Exit(code=1)

    is_ranker = getattr(model_cls(), "is_ranker", False)
    label_col = "label_rank" if is_ranker else "label_binary"
    y = df_clean[label_col]
    model = model_cls()
    fit_kwargs: dict = {}
    if is_ranker:
        fit_kwargs["groups"] = df_clean["trade_date"]
        print(f"[yellow]训练 LambdaRank 模型，样本数: {len(df_clean)}, 特征数: {len(features)}[/yellow]")
    else:
        print(f"[yellow]训练 {'XGBoost' if 'xgb' in model_cls.__name__.lower() else 'LightGBM 二分类'} 模型，样本数: {len(df_clean)}, 特征数: {len(features)}[/yellow]")
    model.fit(X, y, features, **fit_kwargs)

    registry = ModelRegistry(settings)
    model_path = registry.path(model_name)
    model.save(str(model_path))
    print(f"[green]模型已保存到 {model_path}[/green]")

    print("[bold]Top 10 重要特征:[/bold]")
    for feat, score in model.feature_importance.head(10).items():
        print(f"  {feat}: {score:.0f}")


@app.command()
def weekly_report(
    model_name: str = typer.Option("lgb_stock_selector", "--model", help="Model artifact name"),
    top_k: int = typer.Option(10, "--top-k", help="Number of picks"),
    lookback_days: int = typer.Option(60, "--lookback", help="Feature lookback days"),
    benchmark: str = typer.Option("000300.SH", "--benchmark", help="Benchmark index"),
    output_dir: str | None = typer.Option(None, "--output", help="Output directory"),
    cache_only: bool = typer.Option(True, "--cache-only", help="Use cached data only"),
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
):
    """Generate weekly AI stock pick report."""
    if not cache_only:
        _confirm_ifind_usage("weekly-report fundamental/macro（如缓存缺失）", yes)
    try:
        path = generate_weekly_report(
            model_name=model_name,
            top_k=top_k,
            lookback_days=lookback_days,
            benchmark=benchmark,
            output_dir=output_dir,
            cache_only=cache_only,
        )
        print(f"[green]选股报告已生成: {path}[/green]")

        # Push to Supabase
        try:
            import os
            import sys as _sys
            from pathlib import Path as _Path
            if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
                _proj_root = str(_Path(__file__).resolve().parent.parent.parent)
                if _proj_root not in _sys.path:
                    _sys.path.insert(0, _proj_root)
                from scripts.push_to_supabase import get_supabase_client, push_weekly_report
                client = get_supabase_client()
                push_weekly_report(client, path)
                print("[green]报告已同步到云端[/green]")
        except Exception as e:
            print(f"[yellow]云端同步跳过: {e}[/yellow]")

    except Exception as e:
        print(f"[red]生成报告失败: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def explain(
    model_name: str = typer.Option("lgb_stock_selector", "--model", help="Model artifact name"),
    start: str = typer.Option("20240101", "--start", help="Feature start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="Feature end date YYYYMMDD"),
    max_samples: int = typer.Option(500, "--max-samples", help="Max rows for TreeSHAP"),
    output_dir: str = typer.Option("./data_store/reports/shap", "--output", help="Directory to save SHAP outputs"),
    include_sentiment: bool = typer.Option(True, "--sentiment/--no-sentiment", help="Include news sentiment factors"),
    corr_threshold: float = typer.Option(0.95, "--corr-threshold", help="Compatibility option; filtering is applied only inside rolling backtests"),
    cache_only: bool = typer.Option(False, "--cache-only", help="Only use cached fundamental/macro data"),
    yes: bool = typer.Option(False, "--yes", help="Skip iFind usage confirmation"),
):
    """Explain model predictions using SHAP."""
    ifind_used = not cache_only or include_sentiment
    if ifind_used:
        action_parts = []
        if not cache_only:
            action_parts.append("fundamental/macro（如缓存缺失）")
        if include_sentiment:
            action_parts.append("sentiment")
        _confirm_ifind_usage("explain " + ", ".join(action_parts), yes)

    settings = Settings()
    registry = ModelRegistry(settings)
    model_path = registry.path(model_name)
    if not model_path.exists():
        print(f"[red]模型不存在: {model_path}[/red]")
        raise typer.Exit(code=1)

    builder = FeatureBuilder(settings)
    df = builder.build_features(
        start_date=start,
        end_date=end,
        include_fundamental=True,
        include_macro=True,
        include_sentiment=include_sentiment,
        corr_threshold=corr_threshold,
        cache_only=cache_only,
        prediction_mode=True,
    )
    if df.empty:
        print("[red]没有可用特征数据[/red]")
        raise typer.Exit(code=1)

    features = builder.feature_columns(df)
    df_clean = df.dropna(subset=features)
    if df_clean.empty:
        print("[red]没有完整特征的行[/red]")
        raise typer.Exit(code=1)

    print(f"[yellow]使用 {min(max_samples, len(df_clean))}/{len(df_clean)} 条样本进行 SHAP 解释...[/yellow]")
    explain_model(
        str(model_path),
        df_clean,
        feature_names=features,
        max_samples=max_samples,
        output_dir=output_dir,
    )
    print(f"[green]SHAP 解释结果已保存到 {output_dir}[/green]")

    # Push to Supabase
    try:
        import os
        import sys as _sys
        from pathlib import Path as _Path
        if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
            _proj_root = str(_Path(__file__).resolve().parent.parent.parent)
            if _proj_root not in _sys.path:
                _sys.path.insert(0, _proj_root)
            from scripts.push_to_supabase import get_supabase_client, push_shap_summary
            client = get_supabase_client()
            push_shap_summary(client, _Path(output_dir) / "shap_summary.csv", end)
            print("[green]SHAP 数据已同步到云端[/green]")
    except Exception as e:
        print(f"[yellow]云端同步跳过: {e}[/yellow]")


@app.command("list-templates")
def strategy_templates():
    """List available strategy templates."""
    table = Table(title="策略模板")
    table.add_column("名称", style="cyan")
    table.add_column("描述", style="magenta")
    table.add_column("TopK", style="green")
    table.add_column("调仓周期", style="green")
    table.add_column("模型", style="green")
    for template in list_templates():
        table.add_row(
            template.name,
            template.description,
            str(template.top_k),
            str(template.rebalance_freq),
            template.model_type,
        )
    console.print(table)


# ------------------------------------------------------------------
# Paper trading commands
# ------------------------------------------------------------------
paper_app = typer.Typer(help="本地模拟交易（纸交易）")
app.add_typer(paper_app, name="paper-trade")


@paper_app.command("reset")
def paper_reset(
    cash: float = typer.Option(1_000_000.0, "--cash", help="初始资金"),
):
    """清空模拟交易状态并重置为初始资金。"""
    engine = PaperTradingEngine(initial_cash=cash)
    engine.reset(cash=cash)
    print(f"[green]模拟账户已重置，初始资金: {cash:,.2f}[/green]")


@paper_app.command("status")
def paper_status():
    """查看当前模拟账户的现金、持仓和最新净值。"""
    store = DuckDBStore()
    cash = store.load_paper_cash()
    positions = store.load_paper_positions()
    nav = store.load_paper_nav()

    if cash is None:
        print("[yellow]尚未初始化模拟账户，请运行 paper-trade reset[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="模拟账户状态")
    table.add_column("项目", style="cyan")
    table.add_column("数值", style="magenta")
    table.add_row("现金", f"{cash:,.2f}")
    table.add_row("持仓数", str(len(positions)))
    if not nav.empty:
        latest = nav.sort_values("updated_at").iloc[-1]
        table.add_row("最新净值日", str(latest["trade_date"]))
        table.add_row("总市值", f"{latest['market_value']:,.2f}")
        table.add_row("总资产", f"{latest['total_value']:,.2f}")
    console.print(table)

    if not positions.empty:
        pos_table = Table(title="当前持仓")
        pos_table.add_column("股票", style="cyan")
        pos_table.add_column("股数", style="magenta")
        pos_table.add_column("成本", style="magenta")
        for _, row in positions.iterrows():
            pos_table.add_row(str(row["symbol"]), f"{row['shares']}", f"{row['cost_basis']:.3f}")
        console.print(pos_table)


@paper_app.command("run")
def paper_run(
    date: str | None = typer.Option(None, "--date", help="交易日期 YYYYMMDD，默认最新缓存日"),
    model_name: str = typer.Option("lgb_stock_selector", "--model", help="模型名称"),
    top_k: int = typer.Option(5, "--top-k", help="持仓数量"),
    freq: int = typer.Option(5, "--freq", help="再平衡周期（天）"),
    cash: float = typer.Option(1_000_000.0, "--cash", help="初始资金"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只打印计划交易，不写入数据库"),
    reset: bool = typer.Option(False, "--reset", help="运行前先清空模拟账户"),
    include_fundamental: bool = typer.Option(True, "--fundamental/--no-fundamental", help="包含基本面因子"),
    include_macro: bool = typer.Option(True, "--macro/--no-macro", help="包含宏观因子"),
    include_sentiment: bool = typer.Option(False, "--sentiment/--no-sentiment", help="包含新闻情绪因子"),
    corr_threshold: float = typer.Option(
        0.95,
        "--corr-threshold",
        help="兼容参数；高相关性筛选仅用于 rolling 回测训练窗口",
    ),
    profile: str = typer.Option(
        "balanced", "--profile", help="策略 profile（aggressive/balanced/conservative/growth/value）"
    ),
    all_profiles: bool = typer.Option(False, "--all-profiles", help="依次运行所有策略 profile"),
    weighting: str = typer.Option(
        "vol", "--weighting", help="仓位加权: vol (波动率目标,默认) / qp (均值方差优化) / equal"
    ),
):
    """运行一次模拟交易循环。"""
    from ..strategy.profiles import list_profiles

    profiles = list_profiles() if all_profiles else [p for p in list_profiles() if p.id == profile]
    if not profiles:
        print(f"[red]未找到 profile: {profile}[/red]")
        raise typer.Exit(code=1)

    for pf in profiles:
        if reset:
            engine = PaperTradingEngine(initial_cash=cash, profile=pf.id)
            engine.reset(cash=cash)
            print(f"[cyan]已重置 {pf.label} 模拟账户[/cyan]")

        engine = PaperTradingEngine(
            model_name=model_name,
            top_k=pf.top_k,
            rebalance_freq=freq,
            initial_cash=cash,
            include_fundamental=include_fundamental,
            include_macro=include_macro,
            include_sentiment=include_sentiment,
            corr_threshold=corr_threshold,
            profile=pf.id,
            weighting=weighting,
        )

        try:
            result = engine.run(trade_date=date, dry_run=dry_run)
        except Exception as e:
            print(f"[red]{pf.label} 模拟交易失败: {e}[/red]")
            continue

        print(f"\n[bold]{pf.label}[/bold]")
        print(f"[bold]交易日期: {result.trade_date.date()}[/bold]")
        selected = result.signals[result.signals["selected"]]
        print(f"[cyan]选股数量: {len(selected)} / {len(result.signals)}[/cyan]")
        if result.market_choppy:
            print("[yellow]⚠ 大盘震荡，已跳过新买入[/yellow]")

        sig_table = Table(title=f"{pf.name} 选股信号")
        sig_table.add_column("排名", style="cyan")
        sig_table.add_column("股票", style="cyan")
        sig_table.add_column("分数", style="magenta")
        for i, row in selected.iterrows():
            sig_table.add_row(str(row["rank"]), str(row["symbol"]), f"{row['score']:.4f}")
        console.print(sig_table)

        if result.stop_signals:
            stop_table = Table(title="止损信号")
            stop_table.add_column("股票", style="red")
            stop_table.add_column("类型", style="yellow")
            stop_table.add_column("原因", style="yellow")
            for s in result.stop_signals:
                stop_table.add_row(s.symbol, s.type, s.reason)
            console.print(stop_table)

        nav_table = Table(title=f"{pf.name} 账户净值")
        nav_table.add_column("项目", style="cyan")
        nav_table.add_column("数值", style="magenta")
        nav_table.add_row("现金", f"{result.cash:,.2f}")
        nav_table.add_row("市值", f"{result.market_value:,.2f}")
        nav_table.add_row("总资产", f"{result.total_value:,.2f}")
        console.print(nav_table)

    if dry_run:
        print("[yellow]这是 dry-run，未写入数据库[/yellow]")
    else:
        print("[green]所有策略状态已持久化到 DuckDB[/green]")


if __name__ == "__main__":
    app()
