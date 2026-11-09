"""Register the recall leader and best alternative model type, then assign aliases."""
import os

import mlflow
from mlflow import MlflowClient

MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "loan-default")


def main():
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))
    client = MlflowClient()
    experiment = client.get_experiment_by_name("loan-default-candidates")
    if experiment is None:
        raise RuntimeError("Experiment 'loan-default-candidates' does not exist; run train_tracked.py first.")

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="attributes.status = 'FINISHED'",
        order_by=["metrics.recall DESC"],
        max_results=100,
    )
    if not runs:
        raise RuntimeError("No finished candidate runs were found.")

    champion = runs[0]
    champion_type = champion.data.params["model_type"]
    alternatives = [run for run in runs if run.data.params["model_type"] != champion_type]
    if not alternatives:
        raise RuntimeError("Candidates must include at least two model types to assign a challenger.")
    challenger = max(alternatives, key=lambda run: run.data.metrics["roc_auc"])

    choices = [
        ("champion", champion, "Highest-recall candidate; selected to prioritize identifying likely defaults."),
        ("challenger", challenger, "Best-AUC candidate from the alternative model type; retained for comparison."),
    ]
    for alias, run, rationale in choices:
        registered = mlflow.register_model(f"runs:/{run.info.run_id}/model", MODEL_NAME)
        client.update_model_version(
            name=MODEL_NAME,
            version=registered.version,
            description=(
                f"{rationale} Recall={run.data.metrics['recall']:.3f}, "
                f"precision={run.data.metrics['precision']:.3f}, "
                f"AUC={run.data.metrics['roc_auc']:.3f}; "
                f"source run={run.info.run_id}."
            ),
        )
        client.set_registered_model_alias(MODEL_NAME, alias, registered.version)
        print(
            f"{alias}: {MODEL_NAME} version {registered.version}, run={run.info.run_id}, "
            f"recall={run.data.metrics['recall']:.3f}, "
            f"precision={run.data.metrics['precision']:.3f}, "
            f"AUC={run.data.metrics['roc_auc']:.3f}"
        )


if __name__ == "__main__":
    main()
