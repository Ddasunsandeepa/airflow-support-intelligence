from pathlib import Path

import joblib
import pandas as pd
import shap

from backend.app.runbook import get_runbook
from backend.app.recommendation import generate_recommendation

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Model path
MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "incident_classifier.joblib"


def load_model():
    """
    Load the trained Random Forest model bundle.
    """
    return joblib.load(MODEL_PATH)


def get_shap_explanation(model, input_df, predicted_class):
    """
    Generate SHAP feature contributions for the predicted class.
    """

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(input_df)

    class_index = list(model.classes_).index(predicted_class)

    # Handle different SHAP output formats.
    if isinstance(shap_values, list):
        values = shap_values[class_index][0]

    elif hasattr(shap_values, "ndim") and shap_values.ndim == 3:
        values = shap_values[0, :, class_index]

    else:
        values = shap_values[0]

    explanation = []

    for feature, value, shap_value in zip(
        input_df.columns,
        input_df.iloc[0].values,
        values,
    ):
        explanation.append(
            {
                "feature": feature,
                "value": float(value),
                "shap_value": float(shap_value),
            }
        )

    # Strongest contributors first
    explanation.sort(
        key=lambda item: abs(item["shap_value"]),
        reverse=True,
    )

    return explanation


def analyze_incident(incident: dict) -> dict:
    """
    Perform incident prediction, confidence calculation,
    SHAP explanation, and runbook retrieval.
    """

    # Load model bundle
    bundle = load_model()

    model = bundle["model"]
    features = bundle["features"]

    # Convert incident into DataFrame
    input_df = pd.DataFrame([incident])[features]

    # --------------------------------------------------
    # 1. Prediction
    # --------------------------------------------------

    prediction = model.predict(input_df)[0]

    # --------------------------------------------------
    # 2. Confidence
    # --------------------------------------------------

    probabilities = model.predict_proba(input_df)[0]
    confidence = float(max(probabilities))

    # --------------------------------------------------
    # 3. SHAP explanation
    # --------------------------------------------------

    explanation = get_shap_explanation(
        model,
        input_df,
        prediction,
    )

    # --------------------------------------------------
    # 4. Runbook retrieval
    # --------------------------------------------------

    runbook = get_runbook(prediction)

    recommendation = generate_recommendation(
    incident_class=prediction,
    confidence=confidence,
    explanation=explanation,
    )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    return {
        "incident_class": prediction,
        "confidence": confidence,
        "explanation": explanation,
        "runbook": runbook["runbook"],
        "runbook_status": runbook["status"],
        "runbook_content": runbook["content"],
        "recommendation": recommendation,
    }


if __name__ == "__main__":

    # Example incident
    incident = {
        "cpu_usage": 94,
        "memory_usage": 88,
        "heartbeat_status": 0,
        "dag_parse_time": 24,
        "recent_changes": 12,
        "scheduler_pod_status": 1,
        "worker_restarts": 2,
    }

    result = analyze_incident(incident)

    print("\n=== AIRFLOW SUPPORT INTELLIGENCE ===\n")

    print(f"Incident Class : {result['incident_class']}")
    print(f"Confidence     : {result['confidence']:.2%}")
    print(f"Runbook        : {result['runbook']}")
    print(f"Runbook Status : {result['runbook_status']}")

    print("\n=== SHAP EXPLANATION ===\n")

    for item in result["explanation"]:
        direction = "supports" if item["shap_value"] > 0 else "pushes away from"

        print(
            f"{item['feature']:<22} "
            f"value={item['value']:<6.2f} "
            f"SHAP={item['shap_value']:+.6f} "
            f"({direction} {result['incident_class']})"
        )

    print("\n=== TOP CONTRIBUTORS ===\n")

    for item in result["explanation"][:3]:
        print(
            f"- {item['feature']} "
            f"({item['shap_value']:+.6f})"
        )

    print("\n=== RUNBOOK PREVIEW ===\n")

    print(result["runbook_content"][:1000])

    print("\n=== L1 RECOMMENDATION ===\n")

    recommendation = result["recommendation"]

    print(f"Decision: {recommendation['decision']}")

    print("\nStrongest Evidence:")

    for item in recommendation["top_evidence"]:
        print(
            f"- {item['feature']} "
            f"(value={item['value']:.2f}, "
            f"SHAP={item['shap_value']:+.6f})"
        )

    print("\nRecommended L1 Checks:")

    for index, check in enumerate(
        recommendation["l1_checks"],
        start=1,
    ):
        print(f"{index}. {check}")