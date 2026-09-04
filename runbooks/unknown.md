# Unknown Incident Runbook

## Purpose

Use this runbook when available evidence is insufficient,
conflicting, or does not strongly match a known incident class.

## Typical Evidence

- Conflicting operational signals
- Insufficient monitoring data
- No clear dominant incident pattern
- Multiple possible causes
- Model classification confidence is relatively low

## L1 Investigation

### 1. Validate Available Evidence

Confirm that the required monitoring and Airflow information
is available.

### 2. Check Basic Airflow Health

Review:

- Scheduler health
- DAG processing
- task states
- worker health
- recent errors

### 3. Check Infrastructure Health

If applicable, review:

- Kubernetes pod status
- resource utilization
- recent infrastructure events

### 4. Review Recent Changes

Look for recent:

- deployments
- configuration changes
- DAG changes
- provider changes
- infrastructure changes

### 5. Gather Additional Evidence

If the available evidence does not support a clear classification,
collect additional logs, metrics, traces, or ticket information
according to the approved support process.

## Escalation Criteria

Escalate when:

- Evidence remains inconclusive
- Multiple components appear affected
- A production change is required
- A security issue is suspected
- The issue requires deeper Airflow or infrastructure expertise

## Safety

Do not make assumptions when evidence is insufficient.
Do not perform production changes without an approved procedure.