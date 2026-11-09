"""Compare current loan-feature distributions with the training reference."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from train import FEATURES, make_data

WARNING_THRESHOLD = 0.1
ALERT_THRESHOLD = 0.2


def population_stability_index(reference: pd.Series, current: pd.Series) -> float:
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, 11)))
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    reference_bins = pd.cut(reference, bins=edges, include_lowest=True)
    current_bins = pd.cut(current, bins=edges, include_lowest=True)
    reference_share = reference_bins.value_counts(normalize=True, sort=False).to_numpy()
    current_share = current_bins.value_counts(normalize=True, sort=False).to_numpy()
    reference_share = np.clip(reference_share, 1e-6, None)
    current_share = np.clip(current_share, 1e-6, None)
    return float(np.sum((current_share - reference_share) * np.log(current_share / reference_share)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/drift-monitor.png")
    args = parser.parse_args()

    reference = make_data(n=5000, seed=42)[FEATURES]
    current = make_data(n=1000, seed=43)[FEATURES].copy()
    current["amount_usd"] = (current["amount_usd"] * 1.35).clip(upper=5000)
    current["late_payments"] = current["late_payments"] + 1
    scores = {feature: population_stability_index(reference[feature], current[feature]) for feature in FEATURES}

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    colors = [
        "#d9534f" if value >= ALERT_THRESHOLD else "#f0ad4e" if value >= WARNING_THRESHOLD else "#5cb85c"
        for value in scores.values()
    ]
    fig, axis = plt.subplots(figsize=(9, 4.5))
    axis.bar(scores.keys(), scores.values(), color=colors)
    axis.axhline(WARNING_THRESHOLD, color="#d99a00", linestyle="--", label="warning threshold (PSI 0.10)")
    axis.axhline(ALERT_THRESHOLD, color="#b22222", linestyle="--", label="alert threshold (PSI 0.20)")
    axis.set_ylabel("Population Stability Index (PSI)")
    axis.set_title("Loan feature drift: current sample vs training reference")
    axis.tick_params(axis="x", rotation=20)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)

    for feature, value in scores.items():
        status = "ALERT" if value >= ALERT_THRESHOLD else "WARNING" if value >= WARNING_THRESHOLD else "OK"
        print(f"{feature}: PSI={value:.3f} {status}")
    print(f"Thresholds: warning >= {WARNING_THRESHOLD:.2f}; alert >= {ALERT_THRESHOLD:.2f}")
    print(f"Chart: {output.resolve()}")


if __name__ == "__main__":
    main()
