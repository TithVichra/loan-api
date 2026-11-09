"""Export the registered champion configuration as a self-contained serving artifact.

The champion is the logistic-regression candidate (C=0.05) selected in Module 5
(run 08fd0fb618b94c4184734a7202cc5a7c). Retraining is deterministic, so this
reproduces the registered version 1 exactly. The bundle carries the model
version and the evidence needed to audit what is deployed.
"""
from pathlib import Path

import joblib
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from train import FEATURES, make_data
from train_tracked import candidates

SOURCE_RUN = "08fd0fb618b94c4184734a7202cc5a7c"
CHAMPION_VERSION = "1"


def main() -> None:
    name, estimator = next(c for c in candidates() if c[0] == "logistic-c-0.05")
    data = make_data()
    X_train, X_test, y_train, y_test = train_test_split(
        data[FEATURES], data["defaulted"], test_size=0.2, random_state=42, stratify=data["defaulted"])
    estimator.fit(X_train, y_train)
    probabilities = estimator.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 3),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 3),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 3),
    }
    bundle = {
        "model": estimator,
        "version": CHAMPION_VERSION,
        "features": FEATURES,
        "source_run": SOURCE_RUN,
        "candidate": name,
        "metrics": metrics,
    }
    output = Path("champion_model.joblib")
    joblib.dump(bundle, output)
    print(f"Exported {name} as champion version {CHAMPION_VERSION} to {output} ({metrics})")


if __name__ == "__main__":
    main()
