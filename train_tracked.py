"""Train and log six loan-default candidates to the configured MLflow server."""
import os
import sys

import mlflow
from mlflow.models import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from serving import DefaultProbabilityModel
from train import FEATURES, make_data


def candidates():
    return [
        ("logistic-c-0.05", make_pipeline(
            StandardScaler(), LogisticRegression(C=0.05, class_weight="balanced", max_iter=1000))),
        ("logistic-c-0.1", make_pipeline(
            StandardScaler(), LogisticRegression(C=0.1, class_weight="balanced", max_iter=1000))),
        ("logistic-c-1.0", make_pipeline(
            StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000))),
        ("forest-depth-4", RandomForestClassifier(
            n_estimators=150, max_depth=4, min_samples_leaf=5, class_weight="balanced", random_state=42)),
        ("forest-depth-8", RandomForestClassifier(
            n_estimators=150, max_depth=8, min_samples_leaf=5, class_weight="balanced", random_state=42)),
        ("forest-unlimited", RandomForestClassifier(
            n_estimators=150, max_depth=None, min_samples_leaf=5, class_weight="balanced", random_state=42)),
    ]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))
    mlflow.set_experiment("loan-default-candidates")

    data = make_data()
    X_train, X_test, y_train, y_test = train_test_split(
        data[FEATURES], data["defaulted"], test_size=0.2, random_state=42, stratify=data["defaulted"])

    for name, estimator in candidates():
        with mlflow.start_run(run_name=name) as run:
            estimator.fit(X_train, y_train)
            probabilities = estimator.predict_proba(X_test)[:, 1]
            predictions = (probabilities >= 0.5).astype(int)
            signature = infer_signature(X_train, estimator.predict_proba(X_train)[:, 1])
            mlflow.log_params({
                "model_type": "logistic_regression" if name.startswith("logistic") else "random_forest",
                "threshold": 0.5,
                "test_size": 0.2,
                "random_state": 42,
                **estimator.get_params(deep=True),
            })
            mlflow.log_metrics({
                "recall": recall_score(y_test, predictions, zero_division=0),
                "precision": precision_score(y_test, predictions, zero_division=0),
                "roc_auc": roc_auc_score(y_test, probabilities),
                "accuracy": accuracy_score(y_test, predictions),
            })
            mlflow.pyfunc.log_model(
                name="model",
                python_model=DefaultProbabilityModel(estimator),
                code_paths=["serving.py"],
                signature=signature,
                input_example=X_test.head(2),
            )
            metrics = mlflow.get_run(run.info.run_id).data.metrics
            print(
                f"{name}: recall={metrics['recall']:.3f} "
                f"precision={metrics['precision']:.3f} AUC={metrics['roc_auc']:.3f} "
                f"run_id={run.info.run_id}"
            )


if __name__ == "__main__":
    main()
