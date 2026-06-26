"""SHAP explainability for trained AifaQuant models."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd


def explain_model(
    model_path: str,
    X: pd.DataFrame,
    feature_names: list[str] | None = None,
    max_samples: int = 500,
    output_dir: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute SHAP values for a saved model and sample data.

    Args:
        model_path: Path to the saved model (.pkl).
        X: Feature DataFrame to explain.
        feature_names: Optional feature subset to use.
        max_samples: Subsample rows for TreeSHAP summary (speed/memory).
        output_dir: Directory to save summary plot and values.

    Returns:
        Dictionary with shap_values DataFrame and feature_summary DataFrame.
    """
    try:
        import shap  # type: ignore
    except ImportError as e:
        raise RuntimeError("shap is not installed. Run: pip install shap") from e

    model = joblib.load(model_path)
    X = X.copy()
    if feature_names:
        X = X[[c for c in feature_names if c in X.columns]]
    X = X.dropna()
    if len(X) > max_samples:
        x_sample = X.sample(max_samples, random_state=42)
    else:
        x_sample = X

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(x_sample)

    # TreeExplainer may return a list for multi-class models; use positive class
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    shap_df = pd.DataFrame(shap_values, columns=x_sample.columns, index=x_sample.index)
    summary = pd.DataFrame(
        {
            "feature": x_sample.columns,
            "mean_abs_shap": shap_df.abs().mean().values,
        }
    ).sort_values("mean_abs_shap", ascending=False)

    result = {"shap_values": shap_df, "feature_summary": summary}

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        shap_df.to_csv(output_dir / "shap_values.csv", index=False)
        summary.to_csv(output_dir / "shap_summary.csv", index=False)
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            plt.figure()
            shap.summary_plot(shap_values, x_sample, show=False)
            plt.tight_layout()
            plt.savefig(output_dir / "shap_summary.png")
            plt.close()
        except Exception as e:
            print(f"[WARN] SHAP summary plot failed: {e}")

    return result
