# Resource Incident Runbook

## Purpose

Use this runbook when Airflow components show signs of CPU,
memory, or workload-related resource pressure.

## Typical Evidence

- High CPU utilization
- High memory utilization
- Increased worker restarts
- Degraded scheduler heartbeat
- Increased task execution or scheduling latency
- Resource usage significantly above the normal baseline

## L1 Investigation

### 1. Check CPU Utilization

Review CPU usage for the affected Airflow components.

Determine whether high utilization is:

- temporary
- sustained
- isolated to one component
- affecting multiple components

### 2. Check Memory Utilization

Review memory consumption and determine whether the component
is approaching its configured limits.

Look for:

- sustained high memory usage
- memory pressure
- repeated restarts
- possible out-of-memory events

### 3. Check Scheduler Health

If the scheduler heartbeat is degraded, determine whether
resource pressure may be affecting scheduler performance.

### 4. Check Worker Activity

Review:

- worker restarts
- task workload
- task concurrency
- queue behavior
- resource consumption

### 5. Check Kubernetes or Infrastructure Evidence

If Airflow is deployed on Kubernetes, review:

- pod status
- pod restarts
- CPU limits
- memory limits
- scheduling events

### 6. Review Recent Changes

Check whether a recent:

- DAG deployment
- workload increase
- configuration change
- infrastructure change

correlates with the resource increase.

## Possible Causes

- CPU saturation
- Memory pressure
- Increased workload
- Inefficient workloads
- Incorrect resource configuration
- Infrastructure constraints

## Escalation Criteria

Escalate when:

- Resource pressure persists
- Components repeatedly restart
- Out-of-memory conditions are observed
- Infrastructure changes are required
- Resource behavior cannot be explained by normal workload
- The issue affects multiple critical components

## Safety

Do not change production resource limits or restart infrastructure
components unless the organization's approved operational procedure
authorizes the action.