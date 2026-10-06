from datetime import datetime

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def calculate_customer_discounts():
    """
    Controlled synthetic customer-discount workload.

    This DAG intentionally contains a source-code defect for demonstrating
    the complete AI-assisted source-remediation workflow.

    Expected business rule:
    - Gold customers receive a 20% discount.
    - Silver customers receive a 10% discount.
    - Other customers receive no discount.
    - Missing customer tiers must be handled safely.
    """

    customers = [
        {
            "customer_id": "CUST-1001",
            "tier": "gold",
            "order_total": 500.0,
        },
        {
            "customer_id": "CUST-1002",
            "tier": "silver",
            "order_total": 300.0,
        },
        {
            "customer_id": "CUST-1003",
            "tier": None,
            "order_total": 250.0,
        },
    ]

    processed_customers = []

    for customer in customers:
        customer_id = customer["customer_id"]
        tier = customer["tier"]
        order_total = customer["order_total"]

        print(
            "CUSTOMER INPUT: "
            f"CustomerId={customer_id}, "
            f"Tier={tier}, "
            f"OrderTotal={order_total}"
        )

        normalized_tier = tier.lower()

        if normalized_tier == "gold":
            discount_rate = 0.20
        elif normalized_tier == "silver":
            discount_rate = 0.10
        else:
            discount_rate = 0.0

        discount_amount = order_total * discount_rate
        final_total = order_total - discount_amount

        processed_customers.append(
            {
                "customer_id": customer_id,
                "tier": normalized_tier,
                "discount_rate": discount_rate,
                "discount_amount": discount_amount,
                "final_total": final_total,
            }
        )

        print(
            "CUSTOMER RESULT: "
            f"CustomerId={customer_id}, "
            f"DiscountRate={discount_rate}, "
            f"FinalTotal={final_total}"
        )

    print(
        "DISCOUNT PROCESSING COMPLETE: "
        f"ProcessedCustomers={len(processed_customers)}"
    )

    return processed_customers


with DAG(
    dag_id="support_intelligence_customer_discount_remediation_demo",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=[
        "support-intelligence",
        "synthetic",
        "application-code",
        "source-remediation",
    ],
) as dag:

    calculate_discounts = PythonOperator(
        task_id="calculate_customer_discounts",
        python_callable=calculate_customer_discounts,
    )