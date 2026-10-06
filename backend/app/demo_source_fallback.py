"""Explicit infrastructure-test fallbacks only. Never the ordinary AI proposal path."""
import ast
from backend.app.source_validation import DEMO_POLICIES, CUSTOMER_DAG_ID, get_demo_policy, validate_structure


def generate_demo_fallback(dag_id, source):
    if dag_id not in DEMO_POLICIES:
        return None
    from backend.app.source_change_provider import _replace_function_source
    from backend.app.source_patch_generator import StructuredSourcePatch
    target_function = get_demo_policy(dag_id)["function"]
    customer_demo = dag_id == CUSTOMER_DAG_ID
    if customer_demo:
        try:
            tree = ast.parse(source)
            function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == target_function)
            original_function = ast.get_source_segment(source, function)
            buggy_line = "normalized_tier = tier.lower()"
            if original_function.count(buggy_line) != 1:
                return None
            replacement = original_function.replace(
                buggy_line,
                'normalized_tier = tier.strip().lower() if isinstance(tier, str) and tier.strip() else ""',
            )
            proposed = _replace_function_source(source, target_function, replacement)
            validate_structure(source, proposed, dag_id)
            patch = StructuredSourcePatch(
                target_function=target_function, summary="Handle missing customer tiers before string normalization.",
                reasoning="Controlled fallback: normalize only non-empty strings; missing or invalid tiers receive no discount. Preserve the customer fixture and discount rules.",
                proposed_function=replacement,
                tests_to_run=["Verify three processed customers and final totals 400.0, 270.0, 250.0.",
                              "Check missing, blank and non-string tiers receive no discount.",
                              "Validate and approve the exact source revision, then verify Airflow parsing and task/DAG success."],
            )
            return proposed, patch, "controlled_demo_fallback"
        except (ValueError, SyntaxError, TypeError, StopIteration):
            return None

    replacement = '''def summarize_transactions():
    records = [
        {"id": 1, "amount": 120.0},
        {"id": 2, "amount": None},
        {"id": 3, "amount": 80.0},
    ]
    valid_amounts = [
        record["amount"] for record in records
        if isinstance(record.get("amount"), (int, float))
    ]
    if not valid_amounts:
        raise ValueError("No valid transaction amounts available.")
    total = sum(valid_amounts)
    print(f"Transaction total: {total}")
    return total
'''
    try:
        # Fallback is supported only for the known sum/None defect, never arbitrary code.
        if 'total = sum(record["amount"] for record in records)' not in source:
            return None
        proposed = _replace_function_source(source, target_function, replacement)
        validate_structure(source, proposed, dag_id)
        patch = StructuredSourcePatch(
            target_function=target_function,
            summary="Filter invalid transaction amounts before summing.",
            reasoning="Controlled fallback: the demo includes a None amount, which cannot be added to a float.",
            proposed_function=replacement,
            tests_to_run=["Review that the fixture totals 200.0.", "After approval, verify the corrected Airflow task and DAG succeed."],
        )
        return proposed, patch, "controlled_demo_fallback"
    except (ValueError, SyntaxError, TypeError):
        return None
