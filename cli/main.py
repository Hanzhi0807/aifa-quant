"""Command-line interface for AifaQuant."""

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from ..backtest import BacktestEngine, compute_metrics
from ..config.settings import Settings
from ..data.adapters import StockMCPAdapter
from ..data.pipeline import DailyUpdatePipeline
from ..data.storage import DuckDBStore
from ..features import FeatureBuilder
from ..models import LGBRankerModel
from ..models.registry import ModelRegistry
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
    start: str = typer.Option("20230101", "--start", help="Start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="End date YYYYMMDD"),
    full: bool = typer.Option(False, "--full", help="Full refresh instead of incremental"),
):
    """Fetch daily quotes from iFind MCP and persist to DuckDB."""
    pipeline = DailyUpdatePipeline(Settings())
    total_rows = pipeline.update_daily_quotes(
        symbols=symbols or None,
        start_date=start,
        end_date=end,
        incremental=not full,
    )
    print(f"[bold green]共写入 {total_rows} 条数据[/bold green]")


@app.command()
def backtest(
    start: str = typer.Option("20240101", "--start", help="Backtest start date YYYYMMDD"),
    end: str = typer.Option("20241231", "--end", help="Backtest end date YYYYMMDD"),
    model_name: str = typer.Option("lgb_stock_selector", "--model", help="Model artifact name"),
    top_k: int = typer.Option(3, "--top-k", help="Number of stocks to hold"),
    freq: int = typer.Option(5, "--freq", help="Rebalance frequency in days"),
    initial_cash: float = typer.Option(1_000_000.0, "--cash", help="Initial capital"),
):
    """Run backtest using trained model and TopK-Dropout strategy."""
    settings = Settings()

    # Load model
    registry = ModelRegistry(settings)
    model_path = registry.path(model_name)
    if not model_path.exists():
        print(f"[red]模型不存在: {model_path}，请先运行 train 命令[/red]")
        raise typer.Exit(code=1)
    model = LGBRankerModel()
    model.load(str(model_path))
    print(f"[green]已加载模型: {model_path}[/green]")

    # Load features
    builder = FeatureBuilder(settings)
    features = builder.build_features(start_date=start, end_date=end)
    if features.empty:
        print("[red]没有可用特征数据[/red]")
        raise typer.Exit(code=1)

    # Load raw quotes for execution
    store = DuckDBStore(settings)
    symbols = features["symbol"].unique().tolist()
    quotes = store.load_daily_quotes(symbols, start_date=start, end_date=end)

    # Run backtest
    strategy = TopKDropoutStrategy(top_k=top_k, rebalance_freq=freq)
    engine = BacktestEngine(initial_cash=initial_cash, rebalance_freq=freq)
    equity = engine.run(quotes, features, model, strategy, start_date=start, end_date=end)

    if equity.empty:
        print("[red]回测未产生结果[/red]")
        raise typer.Exit(code=1)

    metrics = compute_metrics(equity)
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
        plt.title("Equity Curve")
        plt.xlabel("Date")
        plt.ylabel("Normalized Value")
        plt.legend()
        plt.grid(True)
        plot_path = report_dir / f"equity_{start}_{end}.png"
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
):
    """Train a LightGBM stock selection model."""
    settings = Settings()
    builder = FeatureBuilder(settings)
    df = builder.build_features(start_date=start, end_date=end, label_horizon=horizon)
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


if __name__ == "__main__":
    app()
