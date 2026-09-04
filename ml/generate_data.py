import random
import pandas as pd
from pathlib import Path


# Reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)


# Number of synthetic incident scenarios to generate
NUM_SAMPLES = 1000


# Incident classes from our V1 proposal
INCIDENT_CLASSES = [
    "Scheduler",
    "DAG Parsing",
    "Resource",
    "Kubernetes",
    "Configuration",
    "Unknown",
]


def generate_scheduler_scenario():
    """
    Generate a synthetic Scheduler incident.

    Typical signs:
    - degraded scheduler heartbeat
    - high CPU usage
    - moderate/high memory usage
    - moderate DAG parsing time
    """

    return {
        "cpu_usage": random.uniform(70, 95),
        "memory_usage": random.uniform(60, 90),
        "heartbeat_status": random.choice([0, 0, 0, 1]),
        "dag_parse_time": random.uniform(5, 20),
        "recent_changes": random.randint(0, 8),
        "scheduler_pod_status": 1,
        "worker_restarts": random.randint(0, 3),
        "incident_class": "Scheduler",
    }


def generate_dag_parsing_scenario():
    """
    Generate a synthetic DAG Parsing incident.

    Typical signs:
    - healthy scheduler heartbeat
    - very high DAG parsing time
    - moderate CPU usage
    - relatively high recent changes
    """

    return {
        "cpu_usage": random.uniform(30, 70),
        "memory_usage": random.uniform(40, 75),
        "heartbeat_status": 1,
        "dag_parse_time": random.uniform(20, 60),
        "recent_changes": random.randint(6, 20),
        "scheduler_pod_status": 1,
        "worker_restarts": random.randint(0, 2),
        "incident_class": "DAG Parsing",
    }


def generate_resource_scenario():
    """
    Generate a synthetic Resource incident.

    Typical signs:
    - very high CPU usage
    - very high memory usage
    - potentially degraded heartbeat
    - increased worker restarts
    """

    return {
        "cpu_usage": random.uniform(85, 100),
        "memory_usage": random.uniform(85, 100),
        "heartbeat_status": random.choice([0, 0, 1]),
        "dag_parse_time": random.uniform(5, 25),
        "recent_changes": random.randint(0, 10),
        "scheduler_pod_status": 1,
        "worker_restarts": random.randint(1, 5),
        "incident_class": "Resource",
    }


def generate_kubernetes_scenario():
    """
    Generate a synthetic Kubernetes incident.

    Typical signs:
    - scheduler pod unhealthy
    - multiple worker/pod restarts
    """

    return {
        "cpu_usage": random.uniform(20, 80),
        "memory_usage": random.uniform(30, 80),
        "heartbeat_status": random.choice([0, 1]),
        "dag_parse_time": random.uniform(5, 25),
        "recent_changes": random.randint(0, 8),
        "scheduler_pod_status": 0,
        "worker_restarts": random.randint(4, 15),
        "incident_class": "Kubernetes",
    }


def generate_configuration_scenario():
    """
    Generate a synthetic Configuration incident.

    V1 limitation:
    We do not currently have a dedicated configuration feature.
    Therefore, recent_changes acts as an indirect configuration signal.

    Typical signs:
    - normal CPU
    - normal memory
    - healthy heartbeat
    - normal DAG parsing
    - relatively high recent changes
    - healthy scheduler pod
    """

    return {
        "cpu_usage": random.uniform(20, 60),
        "memory_usage": random.uniform(30, 65),
        "heartbeat_status": 1,
        "dag_parse_time": random.uniform(2, 10),
        "recent_changes": random.randint(10, 20),
        "scheduler_pod_status": 1,
        "worker_restarts": random.randint(0, 2),
        "incident_class": "Configuration",
    }


def generate_unknown_scenario():
    """
    Generate a synthetic Unknown incident.

    Unknown represents situations where the available evidence
    is weak, conflicting, or insufficient for confident classification.
    """

    scenario_type = random.choice([
        "weak",
        "scheduler_resource_conflict",
        "parsing_configuration_conflict",
        "kubernetes_resource_conflict",
    ])

    if scenario_type == "weak":
        return {
            "cpu_usage": random.uniform(35, 65),
            "memory_usage": random.uniform(40, 70),
            "heartbeat_status": 1,
            "dag_parse_time": random.uniform(5, 15),
            "recent_changes": random.randint(2, 8),
            "scheduler_pod_status": 1,
            "worker_restarts": random.randint(0, 2),
            "incident_class": "Unknown",
        }

    if scenario_type == "scheduler_resource_conflict":
        return {
            "cpu_usage": random.uniform(85, 95),
            "memory_usage": random.uniform(40, 60),
            "heartbeat_status": 0,
            "dag_parse_time": random.uniform(5, 15),
            "recent_changes": random.randint(2, 8),
            "scheduler_pod_status": 1,
            "worker_restarts": random.randint(0, 2),
            "incident_class": "Unknown",
        }

    if scenario_type == "parsing_configuration_conflict":
        return {
            "cpu_usage": random.uniform(35, 65),
            "memory_usage": random.uniform(40, 70),
            "heartbeat_status": 1,
            "dag_parse_time": random.uniform(20, 35),
            "recent_changes": random.randint(12, 20),
            "scheduler_pod_status": 1,
            "worker_restarts": random.randint(0, 2),
            "incident_class": "Unknown",
        }

    return {
        "cpu_usage": random.uniform(75, 90),
        "memory_usage": random.uniform(75, 90),
        "heartbeat_status": random.choice([0, 1]),
        "dag_parse_time": random.uniform(10, 25),
        "recent_changes": random.randint(3, 12),
        "scheduler_pod_status": 0,
        "worker_restarts": random.randint(3, 8),
        "incident_class": "Unknown",
    }


def generate_dataset(num_samples=NUM_SAMPLES):
    """
    Generate the complete synthetic incident dataset.

    The dataset is approximately balanced across the six
    incident classes so that the initial ML evaluation
    is not dominated by one class.
    """

    data = []

    base_samples = num_samples // len(INCIDENT_CLASSES)
    remainder = num_samples % len(INCIDENT_CLASSES)

    generators = {
        "Scheduler": generate_scheduler_scenario,
        "DAG Parsing": generate_dag_parsing_scenario,
        "Resource": generate_resource_scenario,
        "Kubernetes": generate_kubernetes_scenario,
        "Configuration": generate_configuration_scenario,
        "Unknown": generate_unknown_scenario,
    }

    for index, incident_class in enumerate(INCIDENT_CLASSES):

        class_count = base_samples

        if index < remainder:
            class_count += 1

        generator = generators[incident_class]

        for _ in range(class_count):
            data.append(generator())

    # Shuffle the generated records
    random.shuffle(data)

    return pd.DataFrame(data)


def main():
    # Generate dataset
    df = generate_dataset()

    # Determine project root
    project_root = Path(__file__).resolve().parents[1]

    # Create backend/data directory
    output_dir = project_root / "backend" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save dataset
    output_file = output_dir / "synthetic_incidents.csv"
    df.to_csv(output_file, index=False)

    print(f"Generated {len(df)} synthetic incident records.")
    print(f"Saved dataset to: {output_file}")

    print("\nIncident distribution:")
    print(df["incident_class"].value_counts())

    print("\nFirst 10 records:")
    print(df.head(10))


if __name__ == "__main__":
    main()