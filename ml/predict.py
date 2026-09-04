import joblib
import pandas as pd

from pathlib import Path


def load_model():
    """
    Load the trained incident classification model
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

    bundle = joblib.load(model_path)

    return bundle


def predict_incident(bundle, incident):
    """
    Predict the incident class and probabilities
    for a new incident.
    """

    model = bundle["model"]
    features = bundle["features"]

    # Convert the incident dictionary into a DataFrame.
    # The feature order comes from the saved model metadata.
    input_df = pd.DataFrame(
        [incident],
        columns=features,
    )

    prediction = model.predict(input_df)[0]

    probabilities = model.predict_proba(input_df)[0]

    confidence = max(probabilities)

    return prediction, confidence, probabilities


def main():

    # Load trained model
    bundle = load_model()

    # Example new Airflow incident
    incident = {
        "cpu_usage": 94,
        "memory_usage": 88,
        "heartbeat_status": 0,
        "dag_parse_time": 24,
        "recent_changes": 12,
        "scheduler_pod_status": 1,
        "worker_restarts": 2,
    }

    prediction, confidence, probabilities = predict_incident(
        bundle,
        incident,
    )

    model = bundle["model"]

    print("=" * 60)
    print("AIRFLOW SUPPORT INTELLIGENCE")
    print("INCIDENT PREDICTION")
    print("=" * 60)

    print("\nInput Evidence:")

    for feature, value in incident.items():
        print(f"  {feature:<25}: {value}")

    print("\nPrediction:")
    print(f"  Incident Class: {prediction}")

    print(f"\nConfidence:")
    print(f"  {confidence:.2%}")

    print("\nClass Probabilities:")

    for class_name, probability in zip(
        model.classes_,
        probabilities,
    ):
        print(
            f"  {class_name:<20}: {probability:.2%}"
        )

    print("\n" + "=" * 60)
    print("PREDICTION COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()