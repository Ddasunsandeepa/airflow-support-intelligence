# Application Code incident

1. Confirm a runtime Python exception in an executing failed task. A failed
   PythonOperator alone does not establish a source defect.
2. Inspect the actual task logs and stack trace; identify the affected source
   function and line using safely resolved current DAG source.
3. Check input/data assumptions: empty collections, zero denominators, missing
   keys, nulls, invalid types and conversions. Review recent task source changes.
4. Distinguish source defects from DAG import errors, container failures, resource
   pressure, scheduler faults and configuration problems. Prefer direct domain
   evidence. ValueError alone is ambiguous; a missing endpoint is configuration.
5. Use Developer Copilot for a review-only proposal when the evidence supports a
   code-level correction. Safe source retrieval does not grant permission to write.
   Unsupported DAGs remain investigation-only under the existing source policy.
6. Validate Python syntax and DAG structure, test the failing input/edge case, and
   review the exact diff. Require human approval of the exact revision/hash before
   explicitly applying a supported proposal. Never modify source automatically.
7. Confirm Airflow recognizes/parses the reviewed source before triggering it.
   Verify the corrected task and DAG result. Record feedback; do not automatically
   retry patches. A runtime recovery flag is not a fix for a source defect.

Deterministic signal confidence is a rule strength, not a calibrated probability
of root cause. Keep human review required and investigate conflicting evidence.
