"""Command-line interface for AifaQuant."""

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from ..backtest import BacktestEngine, compute_metrics
from ..config.settings import Settings
from ..data.adapters import IndexMCPAdapter, StockMCPAdapter
from ..data.pipeline import DailyUpdatePipeline
from ..data.storage import DuckDBStore
from ..features import FeatureBuilder
from ..models import LGBRankerModel
from ..models.registry import ModelRegistry
from ..models.rolling_trainer import RollingTrainer
from ..paper_trading import PaperTradingEngine
from ..strategy import TopKDropoutStrategy

app = typer.Typer(help="AifaQuant - A股 AI 量化研究框架")
console = Console()


@app.command()
def test_connection():
    """Test connectivity to iFind MCP stock server and list available tools."""
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
def list_tools():
    """Alias for test-connection."""
    test_connection()


@app.command()
def data_update(
    symbols: list[str] | None = typer.Option(None, "--symbol", "-s", help="Stock symbols to update"),
    symbol_file: str | None = typer.Option(None, "--symbol-file", help="Path to file with one symbol per line"),
    start: str = typer.Option("20230101", "--start", help="Start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="End date YYYYMMDD"),
    full: bool = typer.Option(False, "--full", help="Full refresh instead of incremental"),
    universe: str = typer.Option(
        "上证50", "--universe", help="Stock universe query (e.g., 上证50, 沪深300, 全部A股)"
    ),
    sample: int | None = typer.Option(None, "--sample", help="Limit universe to first N stocks for testing"),
    workers: int = typer.Option(3, "--workers", help="Concurrent download workers"),
    fundamental: bool = typer.Option(False, "--fundamental", help="Also fetch and cache PE/PB/ROE fundamental data"),
    macro: bool = typer.Option(False, "--macro", help="Also fetch and cache CPI/PMI/M2 macro data"),
    skip_daily: bool = typer.Option(
        False, "--skip-daily", help="Skip daily quote download (useful when only updating fundamental/macro)"
    ),
):
    """Fetch daily quotes from iFind MCP and persist to DuckDB."""
    # Map friendly universe names to iFind queries
    universe_queries = {
        "上证50": "上证50成分股",
        "沪深300": "沪深300成分股",
        "全部A股": "A股上市股票列表",
    }
    query = universe_queries.get(universe, universe)

    if symbol_file:
        from pathlib import Path
        symbols = [line.strip() for line in Path(symbol_file).read_text(encoding="utf-8").splitlines() if line.strip()]

    pipeline = DailyUpdatePipeline(Settings(), max_workers=workers)
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
        fundamental_rows = pipeline.update_fundamental_data(
            symbols=target_symbols, start_date=start, end_date=end
        )
        print(f"[bold green]基本面数据共写入 {fundamental_rows} 条[/bold green]")

    if macro:
        macro_rows = pipeline.update_macro_data(start_date=start, end_date=end)
        print(f"[bold green]宏观数据共写入 {macro_rows} 条[/bold green]")


@app.command()
def backtest(
    start: str = typer.Option("20240101", "--start", help="Backtest start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="Backtest end date YYYYMMDD"),
    model_name: str = typer.Option("lgb_stock_selector", "--model", help="Model artifact name"),
    top_k: int = typer.Option(3, "--top-k", help="Number of stocks to hold"),
    freq: int = typer.Option(5, "--freq", help="Rebalance frequency in days"),
    initial_cash: float = typer.Option(1_000_000.0, "--cash", help="Initial capital"),
    rolling: bool = typer.Option(False, "--rolling", help="Use rolling window training to avoid look-ahead bias"),
    benchmark: str = typer.Option("000300.SH", "--benchmark", help="Benchmark index symbol"),
    include_fundamental: bool = typer.Option(
        True, "--fundamental/--no-fundamental", help="Include fundamental factors (PE/PB/ROE)"
    ),
    include_macro: bool = typer.Option(True, "--macro/--no-macro", help="Include macro factors (CPI/PMI/M2)"),
    include_sentiment: bool = typer.Option(
        True, "--sentiment/--no-sentiment", help="Include news sentiment factors"
    ),
    corr_threshold: float = typer.Option(
        0.95,
        "--corr-threshold",
        help="Drop one feature from each pair with abs correlation >= threshold (set 1.0 to disable)",
    ),
    cache_only: bool = typer.Option(
        False, "--cache-only", help="Only use cached fundamental/macro data; do not call iFind for missing data"
    ),
):
    """Run backtest using trained model and TopK-Dropout strategy."""
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
        corr_threshold=corr_threshold,
        cache_only=cache_only,
    )
    if features.empty:
        print("[red]没有可用特征数据[/red]")
        raise typer.Exit(code=1)

    feature_cols = builder.feature_columns(features)

    if rolling:
        print("[yellow]正在滚动训练生成 out-of-sample 预测...[/yellow]")
        trainer = RollingTrainer(train_window_days=252 * 2, min_train_samples=500, settings=settings)
        # Align retraining dates with rebalance frequency to avoid training every day.
        all_dates = sorted(features["trade_date"].unique())
        rebalance_dates = all_dates[::freq]
        preds = trainer.predict_rolling(features, rebalance_dates=rebalance_dates)
        features = features.merge(preds, on=["symbol", "trade_date"], how="inner")
    else:
        # Load pre-trained model
        registry = ModelRegistry(settings)
        model_path = registry.path(model_name)
        if not model_path.exists():
            print(f"[red]模型不存在: {model_path}，请先运行 train 命令或使用 --rolling[/red]")
            raise typer.Exit(code=1)
        model = LGBRankerModel()
        model.load(str(model_path))
        print(f"[green]已加载模型: {model_path}[/green]")
        pred_df = features.dropna(subset=feature_cols).copy()
        pred_df["pred_score"] = model.predict(pred_df[feature_cols])
        features = pred_df

    # Load raw quotes for execution
    store = DuckDBStore(settings)
    symbols = features["symbol"].unique().tolist()
    quotes = store.load_daily_quotes(symbols, start_date=start, end_date=end)

    # Run backtest
    strategy = TopKDropoutStrategy(top_k=top_k, rebalance_freq=freq)
    engine = BacktestEngine(initial_cash=initial_cash, rebalance_freq=freq)
    equity = engine.run(quotes, features, LGBRankerModel(), strategy, start_date=start, end_date=end)

    if equity.empty:
        print("[red]回测未产生结果[/red]")
        raise typer.Exit(code=1)

    # Fetch benchmark
    bench_df = None
    try:
        index_adapter = IndexMCPAdapter(settings)
        bench_df = index_adapter.get_daily_data(benchmark, start_date=start, end_date=end)
        if bench_df.empty or "close" not in bench_df.columns:
            bench_df = None
    except Exception as e:
        print(f"[yellow]获取基准 {benchmark} 失败: {e}[/yellow]")

    metrics = compute_metrics(equity, benchmark_curve=bench_df)
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
    console.print(table)

    # Save equity curve and plot
    report_dir = settings.data_dir_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"equity_{start}_{end}.csv"
    equity.to_csv(report_path, index=False)

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
        suffix = "_rolling" if rolling else ""
        plot_path = report_dir / f"equity_{start}_{end}{suffix}.png"
        plt.savefig(plot_path)
        plt.close()
        print(f"[green]权益曲线图已保存: {plot_path}[/green]")
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
    include_sentiment: bool = typer.Option(
        True, "--sentiment/--no-sentiment", help="Include news sentiment factors"
    ),
    corr_threshold: float = typer.Option(
        0.95,
        "--corr-threshold",
        help="Drop one feature from each pair with abs correlation >= threshold (set 1.0 to disable)",
    ),
    cache_only: bool = typer.Option(
        False, "--cache-only", help="Only use cached fundamental/macro data; do not call iFind for missing data"
    ),
):
    """Train a LightGBM stock selection model."""
    settings = Settings()
    builder = FeatureBuilder(settings)
    df = builder.build_features(
        start_date=start,
        end_date=end,
        label_horizon=horizon,
        include_sentiment=include_sentiment,
        corr_threshold=corr_threshold,
        cache_only=cache_only,
    )
    if df.empty:
        print("[red]没有可用数据，请先运行 data-update[/red]")
        raise typer.Exit(code=1)

    features = builder.feature_columns(df)
    # Drop rows with NaN in features or label
    df_clean = df.dropna(subset=features + ["label_binary"])
    X = df_clean[features]
    y = df_clean["label_binary"]

    print(f"[yellow]训练样本数: {len(df_clean)}, 特征数: {len(features)}[/yellow]")

    model = LGBRankerModel()
    model.fit(X, y, features)

    registry = ModelRegistry(settings)
    model_path = registry.path(model_name)
    model.save(str(model_path))
    print(f"[green]模型已保存到 {model_path}[/green]")

    print("[bold]Top 10 重要特征:[/bold]")
    for feat, score in model.feature_importance.head(10).items():
        print(f"  {feat}: {score:.0f}")


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
    include_fundamental: bool = typer.Option(
        True, "--fundamental/--no-fundamental", help="包含基本面因子"
    ),
    include_macro: bool = typer.Option(True, "--macro/--no-macro", help="包含宏观因子"),
    include_sentiment: bool = typer.Option(
        False, "--sentiment/--no-sentiment", help="包含新闻情绪因子"
    ),
    corr_threshold: float = typer.Option(
        0.95,
        "--corr-threshold",
        help="高相关性特征剔除阈值",
    ),
):
    """运行一次模拟交易循环。"""
    if reset:
        engine = PaperTradingEngine(initial_cash=cash)
        engine.reset(cash=cash)
        print("[cyan]已重置模拟账户[/cyan]")

    engine = PaperTradingEngine(
        model_name=model_name,
        top_k=top_k,
        rebalance_freq=freq,
        initial_cash=cash,
        include_fundamental=include_fundamental,
        include_macro=include_macro,
        include_sentiment=include_sentiment,
        corr_threshold=corr_threshold,
    )

    try:
        result = engine.run(trade_date=date, dry_run=dry_run)
    except Exception as e:
        print(f"[red]模拟交易失败: {e}[/red]")
        raise typer.Exit(code=1)

    print(f"\n[bold]交易日期: {result.trade_date.date()}[/bold]")
    selected = result.signals[result.signals["selected"]]
    print(f"[cyan]选股数量: {len(selected)} / {len(result.signals)}[/cyan]")

    sig_table = Table(title="选股信号")
    sig_table.add_column("排名", style="cyan")
    sig_table.add_column("股票", style="cyan")
    sig_table.add_column("分数", style="magenta")
    for i, row in selected.iterrows():
        sig_table.add_row(str(row["rank"]), str(row["symbol"]), f"{row['score']:.4f}")
    console.print(sig_table)

    if result.orders:
        order_table = Table(title="交易计划" if dry_run else "已执行订单")
        order_table.add_column("股票", style="cyan")
        order_table.add_column("方向", style="magenta")
        order_table.add_column("数量", style="magenta")
        order_table.add_column("状态", style="magenta")
        for order in result.orders:
            order_table.add_row(
                str(order["symbol"]),
                str(order["side"]).upper(),
                str(order["quantity"]),
                str(order.get("status", "planned")),
            )
        console.print(order_table)
    else:
        print("[yellow]今日无交易[/yellow]")

    nav_table = Table(title="账户净值")
    nav_table.add_column("项目", style="cyan")
    nav_table.add_column("数值", style="magenta")
    nav_table.add_row("现金", f"{result.cash:,.2f}")
    nav_table.add_row("市值", f"{result.market_value:,.2f}")
    nav_table.add_row("总资产", f"{result.total_value:,.2f}")
    console.print(nav_table)

    if dry_run:
        print("[yellow]这是 dry-run，未写入数据库[/yellow]")
    else:
        print("[green]模拟交易状态已持久化到 DuckDB[/green]")


if __name__ == "__main__":
    app()
