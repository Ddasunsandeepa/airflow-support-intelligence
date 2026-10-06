"""Explicitly install/reset ONE demo to its intentional bug; never part of the test suite."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.source_validation import BASELINE, DEMO_DAG_ID, DEMO_POLICIES, demo_baseline, resolve_writable_demo
from backend.app.source_updater import atomic_write


def reset_demo(dag_id):
    """Restore only a registered baseline; neither destination nor source is user supplied."""
    baseline = demo_baseline(dag_id)
    target = resolve_writable_demo(dag_id, must_exist=False)
    if not target.parent.is_dir():
        raise ValueError("Configured DAG root does not exist.")
    if target.exists():
        backups = BASELINE.parents[1] / "data" / "source_backups"
        backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backups / f"{dag_id}-reset-{stamp}.bak"
        with backup.open("xb") as handle:
            handle.write(target.read_bytes())
        print(f"Previous demo source backed up: {backup}")
    atomic_write(target, baseline.read_bytes())
    print(f"Restored intentional bug: {target}")
    print("Wait for Airflow to parse this source before triggering the failure run.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-reset", action="store_true", required=True,
                        help="Explicitly restore the intentional bug in the single allowlisted demo.")
    parser.add_argument("--dag-id", choices=tuple(DEMO_POLICIES), default=DEMO_DAG_ID)
    args = parser.parse_args()
    reset_demo(args.dag_id)


if __name__ == "__main__":
    main()
