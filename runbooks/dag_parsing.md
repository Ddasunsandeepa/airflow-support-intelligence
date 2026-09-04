# DAG Parsing Incident Runbook

## Purpose

Use this runbook when DAG parsing appears unusually slow,
delayed, or unhealthy.

## Typical Evidence

- Increased DAG parsing time
- DAG processing delays
- New or modified DAGs not appearing as expected
- Scheduler heartbeat remains healthy while parsing performance degrades
- Large increase in recent DAG changes

## L1 Investigation

### 1. Check DAG Parsing Performance

Review DAG parsing duration and compare it with the normal
environment baseline.

### 2. Review Recent DAG Changes

Check for recently modified or newly deployed DAGs.

Pay attention to:

- large changes
- expensive imports
- excessive task definitions
- unusual Python code execution during DAG parsing

### 3. Check Scheduler and DAG Processor Health

Verify that the relevant Airflow components are running normally.

### 4. Review Logs

Look for:

- import errors
- syntax errors
- timeout messages
- dependency problems
- repeated parsing failures

### 5. Compare Affected DAGs

Determine whether the problem affects:

- one DAG
- several DAGs
- most DAGs

A broad impact may indicate an environment-level issue.

## Possible Causes

- Slow DAG parsing
- Invalid DAG code
- Expensive imports
- Dependency problems
- Large or inefficient DAG definitions
- Resource constraints

## Escalation Criteria

Escalate when:

- Multiple DAGs are affected without an obvious cause
- Parsing remains degraded after standard checks
- Infrastructure or platform changes are required
- The issue requires code-level investigation beyond L1 scope
- Evidence is inconclusive

## Safety

Do not modify production DAGs or remove dependencies without
following the approved support and change process.