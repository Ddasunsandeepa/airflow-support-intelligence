def generate_recommendation(
    incident_class: str,
    confidence: float,
    explanation: list,
) -> dict:
    """
    Generate controlled L1 support recommendations
    based on the predicted incident class and
    strongest SHAP contributors.
    """

    recommendations = {
        "Scheduler": [
            "Check scheduler heartbeat status.",
            "Review scheduler logs for errors or repeated failures.",
            "Check scheduler CPU and memory utilization.",
            "Review recent DAG or configuration changes.",
            "Check whether affected tasks are remaining in queued or scheduled states.",
        ],
        "DAG Parsing": [
            "Check DAG parsing duration and parsing latency.",
            "Review recent DAG code or deployment changes.",
            "Check DAG processor and scheduler health.",
            "Review parsing-related logs for errors or timeouts.",
            "Determine whether the issue affects one DAG or multiple DAGs.",
        ],
        "Resource": [
            "Check CPU utilization for affected Airflow components.",
            "Check memory utilization and memory pressure.",
            "Check scheduler health and heartbeat status.",
            "Review worker activity and worker restarts.",
            "Check Kubernetes or infrastructure resource evidence if applicable.",
            "Review recent workload, configuration, or infrastructure changes.",
        ],
        "Kubernetes": [
            "Check the affected pod status.",
            "Review pod restart counts and container states.",
            "Check Kubernetes events for scheduling or resource issues.",
            "Review CPU and memory limits for affected workloads.",
            "Correlate Kubernetes evidence with Airflow component health.",
        ],
        "Configuration": [
            "Review recent configuration or environment changes.",
            "Compare the current configuration with the expected configuration.",
            "Check recent DAG, provider, or deployment changes.",
            "Review Airflow logs for configuration-related errors.",
            "Check version and provider compatibility if applicable.",
        ],
        "Unknown": [
            "Validate the available incident evidence.",
            "Check basic Airflow component health.",
            "Check infrastructure or Kubernetes health if applicable.",
            "Review recent changes.",
            "Gather additional evidence before determining the incident class.",
        ],
    }

    checks = recommendations.get(
        incident_class,
        recommendations["Unknown"],
    )

    # Take the strongest SHAP contributors.
    top_contributors = explanation[:3]

    evidence = []

    for item in top_contributors:
        direction = (
            "supports"
            if item["shap_value"] > 0
            else "pushes away from"
        )

        evidence.append(
            {
                "feature": item["feature"],
                "value": item["value"],
                "shap_value": item["shap_value"],
                "interpretation": (
                    f"{item['feature']} {direction} "
                    f"the {incident_class} classification."
                ),
            }
        )

    # Simple escalation guidance.
    if confidence >= 0.80:
        decision = "Proceed with L1 investigation"
    elif confidence >= 0.60:
        decision = "Proceed with L1 investigation and gather additional evidence"
    else:
        decision = "Gather additional evidence and consider escalation"

    return {
        "incident_class": incident_class,
        "confidence": confidence,
        "top_evidence": evidence,
        "l1_checks": checks,
        "decision": decision,
    }