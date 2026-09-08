from dataclasses import asdict

from backend.app.evidence import AirflowEvidence


ML_FEATURES = [
    "cpu_usage",
    "memory_usage",
    "heartbeat_status",
    "dag_parse_time",
    "recent_changes",
    "scheduler_pod_status",
    "worker_restarts",
]


def map_airflow_evidence(evidence: AirflowEvidence) -> dict:
    """
    Convert AirflowEvidence into a normalized evidence dictionary.

    This function preserves unavailable signals as None rather than
    inventing values for them.
    """

    raw = asdict(evidence)

    ml_features = {
        feature: raw.get(feature)
        for feature in ML_FEATURES
    }

    available_features = [
        feature
        for feature, value in ml_features.items()
        if value is not None
    ]

    unavailable_features = [
        feature
        for feature, value in ml_features.items()
        if value is None
    ]

    operational_evidence = {
        key: value
        for key, value in raw.items()
        if key not in ML_FEATURES
    }

    return {
        "ml_features": ml_features,
        "available_features": available_features,
        "unavailable_features": unavailable_features,
        "operational_evidence": operational_evidence,
    }


if __name__ == "__main__":
    from backend.app.airflow_adapter import AirflowAdapter

    adapter = AirflowAdapter()
    evidence = adapter.get_evidence()

    mapped = map_airflow_evidence(evidence)

    print("\n=== AIRFLOW EVIDENCE MAPPING ===\n")

    print("Available ML features:")
    for feature in mapped["available_features"]:
        print(
            f"- {feature}: "
            f"{mapped['ml_features'][feature]}"
        )

    print("\nUnavailable ML features:")
    for feature in mapped["unavailable_features"]:
        print(f"- {feature}")

    print("\nOperational evidence:")

    for feature, value in mapped["operational_evidence"].items():
        print(f"- {feature}: {value}")