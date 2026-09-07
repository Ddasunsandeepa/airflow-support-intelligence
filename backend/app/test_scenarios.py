from backend.app.analyze import analyze_incident


SCENARIOS = {
    "Scheduler scenario": {
        "expected": "Scheduler",
        "evidence": {
            "cpu_usage": 85,
            "memory_usage": 75,
            "heartbeat_status": 0,
            "dag_parse_time": 10,
            "recent_changes": 2,
            "scheduler_pod_status": 1,
            "worker_restarts": 1,
        },
    },

    "DAG Parsing scenario": {
        "expected": "DAG Parsing",
        "evidence": {
            "cpu_usage": 35,
            "memory_usage": 45,
            "heartbeat_status": 1,
            "dag_parse_time": 40,
            "recent_changes": 20,
            "scheduler_pod_status": 1,
            "worker_restarts": 0,
        },
    },

    "Resource scenario": {
        "expected": "Resource",
        "evidence": {
            "cpu_usage": 95,
            "memory_usage": 92,
            "heartbeat_status": 0,
            "dag_parse_time": 15,
            "recent_changes": 2,
            "scheduler_pod_status": 1,
            "worker_restarts": 3,
        },
    },

    "Kubernetes scenario": {
        "expected": "Kubernetes",
        "evidence": {
            "cpu_usage": 50,
            "memory_usage": 60,
            "heartbeat_status": 1,
            "dag_parse_time": 10,
            "recent_changes": 2,
            "scheduler_pod_status": 0,
            "worker_restarts": 6,
        },
    },

    "Configuration scenario": {
        "expected": "Configuration",
        "evidence": {
            "cpu_usage": 40,
            "memory_usage": 50,
            "heartbeat_status": 1,
            "dag_parse_time": 8,
            "recent_changes": 15,
            "scheduler_pod_status": 1,
            "worker_restarts": 0,
        },
    },

    "Unknown scenario": {
        "expected": "Unknown",
        "evidence": {
            "cpu_usage": 52,
            "memory_usage": 55,
            "heartbeat_status": 1,
            "dag_parse_time": 9,
            "recent_changes": 1,
            "scheduler_pod_status": 1,
            "worker_restarts": 0,
        },
    },
}

def main():

    print("\n==========================================")
    print(" AIRFLOW SUPPORT INTELLIGENCE VALIDATION")
    print("==========================================\n")

    for scenario_name, scenario in SCENARIOS.items():

        expected = scenario["expected"]
        incident = scenario["evidence"]

        result = analyze_incident(incident)

        prediction = result["incident_class"]
        confidence = result["confidence"]

        passed = prediction == expected

        status = "PASS" if passed else "FAIL"

        print(f"--- {scenario_name} ---")

        print(f"Expected   : {expected}")
        print(f"Prediction : {prediction}")
        print(f"Confidence : {confidence:.2%}")
        print(f"Runbook    : {result['runbook']}")
        print(f"Status     : {status}")

        print("Top Evidence:")

        for item in result["explanation"][:3]:
            print(
                f"  - {item['feature']} "
                f"({item['shap_value']:+.4f})"
            )

        print()

if __name__ == "__main__":
    main()