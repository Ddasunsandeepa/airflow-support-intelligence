"""Intentionally buggy source-remediation demo. Reset only through the demo script."""
from datetime import datetime, timezone

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator


def summarize_transactions():
    records = [
        {"id": 1, "amount": 120.0},
        {"id": 2, "amount": None},
        {"id": 3, "amount": 80.0},
    ]
    total = sum(record["amount"] for record in records)
    print(f"Transaction total: {total}")
    return total


with DAG(
    dag_id="support_intelligence_code_remediation_demo",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=False,
    tags=["support-intelligence", "source-remediation"],
) as dag:
    PythonOperator(
        task_id="summarize_transactions",
        python_callable=summarize_transactions,
        retries=0,
    )
