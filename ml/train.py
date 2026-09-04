import pandas as pd
import joblib

from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)


# Reproducibility
RANDOM_SEED = 42


# Features used by the V1 model
FEATURES = [
    "cpu_usage",
    "memory_usage",
    "heartbeat_status",
    "dag_parse_time",
    "recent_changes",
    "scheduler_pod_status",
    "worker_restarts",
]


# Target column
TARGET = "incident_class"


def load_dataset():
    """
    Load the synthetic incident dataset.
    """

    project_root = Path(__file__).resolve().parents[1]

    dataset_path = (
        project_root
        / "backend"
        / "data"
        / "synthetic_incidents.csv"
    )

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}\n"
            "Run 'python ml/generate_data.py' first."
        )

    df = pd.read_csv(dataset_path)

    print(f"Loaded dataset: {dataset_path}")
    print(f"Number of records: {len(df)}")

    return df


def prepare_data(df):
    """
    Separate input features (X) from the target (y).
    """

    X = df[FEATURES]
    y = df[TARGET]

    return X, y


def train_model(X_train, y_train):
    """
    Train the Random Forest classifier.
    """

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    return model


def evaluate_model(model, X_test, y_test):
    """
    Evaluate the trained model using the test dataset.
    """

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    print("\n" + "=" * 60)
    print("MODEL EVALUATION")
    print("=" * 60)

    print(f"\nAccuracy: {accuracy:.4f}")

    print("\nClassification Report:")
    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0,
        )
    )

    print("Confusion Matrix:")

    classes = model.classes_

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=classes,
    )

    confusion_df = pd.DataFrame(
        matrix,
        index=classes,
        columns=classes,
    )

    print(confusion_df)

    return accuracy


def save_model(model):
    """
    Save the trained model together with its metadata.
    """

    project_root = Path(__file__).resolve().parents[1]

    model_dir = project_root / "backend" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "incident_classifier.joblib"

    model_bundle = {
        "model": model,
        "features": FEATURES,
        "classes": list(model.classes_),
    }

    joblib.dump(model_bundle, model_path)

    print(f"\nModel saved to: {model_path}")

    return model_path


def main():
    print("=" * 60)
    print("AIRFLOW SUPPORT INTELLIGENCE")
    print("V1 Incident Classifier Training")
    print("=" * 60)

    # 1. Load dataset
    df = load_dataset()

    # 2. Prepare features and target
    X, y = prepare_data(df)

    print("\nFeatures:")
    for feature in FEATURES:
        print(f"  - {feature}")

    print(f"\nTarget: {TARGET}")

    # 3. Split dataset into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    print("\nDataset split:")
    print(f"  Training records: {len(X_train)}")
    print(f"  Testing records:  {len(X_test)}")

    # 4. Train Random Forest
    print("\nTraining Random Forest...")

    model = train_model(
        X_train,
        y_train,
    )

    print("Training completed.")

    # 5. Evaluate model
    accuracy = evaluate_model(
        model,
        X_test,
        y_test,
    )

    # 6. Show feature importance
    print("\nFeature Importance:")

    feature_importance = pd.DataFrame(
        {
            "feature": FEATURES,
            "importance": model.feature_importances_,
        }
    ).sort_values(
        by="importance",
        ascending=False,
    )

    print(feature_importance.to_string(index=False))

    # 7. Save model
    save_model(model)

    print("\n" + "=" * 60)
    print("TRAINING PIPELINE COMPLETED")
    print("=" * 60)

    print(f"\nFinal test accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    main()