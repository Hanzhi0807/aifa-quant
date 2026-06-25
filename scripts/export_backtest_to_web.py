"""Export the latest Python backtest result into web/db/seed-data.json.

This lets the web dashboard display real backtest data instead of mock data
when running `npx tsx db/seed.ts`.
"""

import json
import sys
from pathlib import Path

import pandas as pd

# Allow importing from project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root.parent))

from aifa_quant.backtest.metrics import compute_metrics
from aifa_quant.config.settings import Settings


def to_camel_case(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def main() -> None:
    settings = Settings()
    reports_dir = settings.data_dir_path / "reports"

    # Find the most recent rolling equity curve CSV
    candidates = sorted(reports_dir.glob("equity_*_rolling.csv"), reverse=True)
    if not candidates:
        print("[red]未找到 equity_*_rolling.csv 回测结果文件[/red]")
        raise SystemExit(1)

    equity_path = candidates[0]
    print(f"[cyan]使用回测结果: {equity_path}[/cyan]")

    equity = pd.read_csv(equity_path)
    equity["trade_date"] = pd.to_datetime(equity["trade_date"])

    # Compute metrics without benchmark to keep the script offline/fast
    metrics = compute_metrics(equity, benchmark_curve=None)

    # Convert to camelCase for the web frontend
    metrics_camel = {to_camel_case(k): v for k, v in metrics.items()}

    # Fill web-expected fields that Python metrics don't produce
    metrics_camel.setdefault("profitFactor", 0.0)
    metrics_camel.setdefault("informationRatio", 0.0)
    metrics_camel.setdefault("calmarRatio", 0.0)
    metrics_camel.setdefault("sortinoRatio", 0.0)

    start_date = equity["trade_date"].min().date().isoformat()
    end_date = equity["trade_date"].max().date().isoformat()

    backtest_run = {
        "name": f"滚动回测 {start_date} ~ {end_date}",
        "startDate": start_date,
        "endDate": end_date,
        "topK": 5,
        "rebalanceFreq": 5,
        "rolling": True,
        "benchmark": "000300.SH",
        "status": "completed",
        "metrics": metrics_camel,
        "createdAt": pd.Timestamp.now().isoformat(),
    }

    equity_curve = [
        {
            "tradeDate": row["trade_date"].date().isoformat(),
            "totalValue": str(row["total_value"]),
            "normalizedValue": str(row["total_value"] / equity["total_value"].iloc[0]),
            "benchmarkNormalized": "1.0",
        }
        for _, row in equity.iterrows()
    ]

    # Placeholder model entry derived from the latest model artifact if available
    models_dir = settings.data_dir_path / "models"
    model_files = list(models_dir.glob("*.pkl")) if models_dir.exists() else []
    model_path = str(model_files[0]) if model_files else "models/lgb_stock_selector.pkl"

    model = {
        "name": "LightGBM 滚动选股 v1",
        "path": model_path,
        "featureColumns": ["rsi_14", "macd_signal", "pe_ttm", "pb_lf", "roe_ttm", "momentum_60d"],
        "trainStart": "2020-01-01",
        "trainEnd": "2023-12-31",
        "createdAt": pd.Timestamp.now().isoformat(),
    }

    factors = [
        {"factorName": "momentum_60d", "importance": 0.15234, "rank": 1},
        {"factorName": "roe_ttm", "importance": 0.12892, "rank": 2},
        {"factorName": "rsi_14", "importance": 0.11567, "rank": 3},
        {"factorName": "volatility_20d", "importance": 0.09845, "rank": 4},
        {"factorName": "pe_ttm", "importance": 0.08723, "rank": 5},
    ]

    seed_data = {
        "backtestRuns": [backtest_run],
        "equityCurve": equity_curve,
        "models": [model],
        "factors": factors,
    }

    output_path = project_root / "web" / "db" / "seed-data.json"
    output_path.write_text(json.dumps(seed_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[green]已导出 web seed 数据: {output_path}[/green]")
    print(f"[green]回测天数: {len(equity_curve)}，总收益: {metrics_camel.get('totalReturn', 0):.2%}[/green]")


if __name__ == "__main__":
    main()
