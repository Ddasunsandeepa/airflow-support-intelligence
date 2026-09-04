import joblib
import pandas as pd
import shap

from pathlib import Path


def load_model():
    """
    Load the trained Random Forest model
    and its metadata.
    """

    project_root = Path(__file__).resolve().parents[1]

    model_path = (
        project_root
        / "backend"
        / "models"
        / "incident_classifier.joblib"
    )

    if not model_path.exists():
        raise FileNotFoundError(
            f"Trained model not found: {model_path}\n"
            "Run 'python ml/train.py' first."
        )

    return joblib.load(model_path)


def explain_incident(bundle, incident):
    """
    Generate SHAP explanations for a single incident.
    """

    model = bundle["model"]
    features = bundle["features"]

    # Convert incident into the exact feature structure
    # expected by the trained model.
    input_df = pd.DataFrame(
        [incident],
        columns=features,
    )

    # Model prediction
    prediction = model.predict(input_df)[0]

    probabilities = model.predict_proba(input_df)[0]

    confidence = max(probabilities)

    # Create SHAP TreeExplainer for Random Forest
    explainer = shap.TreeExplainer(model)

    shap_values = explainer.shap_values(input_df)

    return (
        prediction,
        confidence,
        probabilities,
        shap_values,
        input_df,
    )


def main():

    # Load model
    bundle = load_model()

    model = bundle["model"]

    # Same incident used in predict.py
    incident = {
        "cpu_usage": 94,
        "memory_usage": 88,
        "heartbeat_status": 0,
        "dag_parse_time": 24,
        "recent_changes": 12,
        "scheduler_pod_status": 1,
        "worker_restarts": 2,
    }

    (
        prediction,
        confidence,
        probabilities,
        shap_values,
        input_df,
    ) = explain_incident(
        bundle,
        incident,
    )

    print("=" * 65)
    print("AIRFLOW SUPPORT INTELLIGENCE")
    print("SHAP EXPLANATION")
    print("=" * 65)

    print("\nPrediction:")
    print(f"  Incident Class: {prediction}")

    print(f"\nModel Confidence:")
    print(f"  {confidence:.2%}")

    print("\nInput Evidence:")

    for feature, value in incident.items():
        print(f"  {feature:<25}: {value}")

    # Determine which class the model predicted
    predicted_class_index = list(model.classes_).index(
        prediction
    )

    # SHAP output can have different structures depending
    # on the installed SHAP version.
    if isinstance(shap_values, list):

        class_shap_values = shap_values[
            predicted_class_index
        ][0]

    else:

        shap_array = shap_values

        if len(shap_array.shape) == 3:
            class_shap_values = shap_array[
                0,
                :,
                predicted_class_index,
            ]

        else:
            class_shap_values = shap_array[0]

    # Combine feature names, input values, and SHAP values
    explanation_df = pd.DataFrame(
        {
            "feature": input_df.columns,
            "value": input_df.iloc[0].values,
            "shap_value": class_shap_values,
        }
    )

    # Absolute SHAP value shows contribution magnitude
    explanation_df["absolute_shap"] = (
        explanation_df["shap_value"].abs()
    )

    explanation_df = explanation_df.sort_values(
        by="absolute_shap",
        ascending=False,
    )

    print("\nSHAP Feature Contributions:")

    print(
        explanation_df[
            [
                "feature",
                "value",
                "shap_value",
            ]
        ].to_string(index=False)
    )

    print("\nTop Contributing Evidence:")

    top_features = explanation_df.head(5)

    for _, row in top_features.iterrows():

        direction = (
            "supports"
            if row["shap_value"] > 0
            else "pushes away from"
        )

        print(
            f"  - {row['feature']}: "
            f"{direction} '{prediction}' "
            f"(SHAP = {row['shap_value']:.4f})"
        )

    print("\n" + "=" * 65)
    print("SHAP EXPLANATION COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    main()