"""MLflow pyfunc wrapper that returns the default probability for each applicant."""
import mlflow.pyfunc
import pandas as pd


class DefaultProbabilityModel(mlflow.pyfunc.PythonModel):
    def __init__(self, estimator):
        self.estimator = estimator

    def predict(self, context, model_input: pd.DataFrame, params=None):
        return self.estimator.predict_proba(model_input)[:, 1]
