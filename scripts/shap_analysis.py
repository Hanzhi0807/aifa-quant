"""SHAP analysis for the trained LightGBM stock selection model.

Usage:
    python scripts/shap_analysis.py --model lgb_stock_selector --start 20230101 --end 20241231
"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd  # noqa: E402

from aifa_quant.config.settings import Settings  # noqa: E402
from aifa_quant.features.builder import FeatureBuilder  # noqa: E402
from aifa_quant.models import LGBRankerModel  # noqa: E402
from aifa_quant.models.registry import ModelRegistry  # noqa: E402


def main(
    model_name: str = "lgb_stock_selector",
    start: str = "20230101",
    end: str = "20241231",
    horizon: int = 5,
    output_dir: str | None = None,
    sample_size: int | None = 5000,
) -> None:
    """Run SHAP analysis on a trained model."""
    try:
        import shap
    except ImportError as e:
        print("[red]缺少 shap 依赖，请先运行: pip install shap[/red]")
        raise e

    settings = Settings()
    registry = ModelRegistry(settings)
    model_path = registry.path(model_name)
    if not model_path.exists():
        print(f"[red]模型不存在: {model_path}，请先训练模型[/red]")
        sys.exit(1)

    model = LGBRankerModel()
    model.load(str(model_path))
    print(f"[green]已加载模型: {model_path}[/green]")

    builder = FeatureBuilder(settings)
    df = builder.build_features(start_date=start, end_date=end, label_horizon=horizon)
    if df.empty:
        print("[red]没有可用特征数据[/red]")
        sys.exit(1)

    features = model.feature_names
    df_clean = df.dropna(subset=features)
    if sample_size and len(df_clean) > sample_size:
        df_clean = df_clean.sample(n=sample_size, random_state=42)
    X = df_clean[features]

    print(f"[yellow]计算 SHAP 值，样本数: {len(X)}，特征数: {len(features)}[/yellow]")
    explainer = shap.TreeExplainer(model.model)
    shap_values = explainer.shap_values(X)

    out_dir = Path(output_dir or settings.data_dir_path / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save SHAP summary CSV
    mean_shap = pd.DataFrame(
        {"feature": features, "mean_shap": shap_values.mean(axis=0) if hasattr(shap_values, "mean") else [0] * len(features)}
    )
    mean_shap = mean_shap.sort_values("mean_shap", key=lambda x: x.abs(), ascending=False)
    csv_path = out_dir / f"shap_summary_{model_name}_{start}_{end}.csv"
    mean_shap.to_csv(csv_path, index=False)
    print(f"[green]SHAP 汇总已保存: {csv_path}[/green]")

    # Save a subset of SHAP values for downstream inspection
    shap_df = pd.DataFrame(shap_values, columns=features)
    shap_df["expected_value"] = explainer.expected_value
    shap_df.to_parquet(out_dir / f"shap_values_{model_name}_{start}_{end}.parquet", index=False)

    print("\n[bold]Top 10 特征（按平均 |SHAP|）:[/bold]")
    for _, row in mean_shap.head(10).iterrows():
        print(f"  {row['feature']}: {row['mean_shap']:.6f}")

    # Try to render a summary plot
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, max(6, len(features) * 0.25)))
        shap.summary_plot(shap_values, X, show=False)
        plot_path = out_dir / f"shap_summary_{model_name}_{start}_{end}.png"
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"[green]SHAP 汇总图已保存: {plot_path}[/green]")
    except Exception as e:
        print(f"[yellow]绘图失败: {e}[/yellow]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SHAP analysis for AifaQuant model")
    parser.add_argument("--model", default="lgb_stock_selector", help="Model artifact name")
    parser.add_argument("--start", default="20230101", help="Start date YYYYMMDD")
    parser.add_argument("--end", default="20241231", help="End date YYYYMMDD")
    parser.add_argument("--horizon", type=int, default=5, help="Forecast horizon")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--sample-size", type=int, default=5000, help="Max samples for SHAP computation")
    args = parser.parse_args()

    main(
        model_name=args.model,
        start=args.start,
        end=args.end,
        horizon=args.horizon,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
    )
