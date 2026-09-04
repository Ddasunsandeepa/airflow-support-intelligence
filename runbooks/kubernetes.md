# Kubernetes Incident Runbook

## Purpose

Use this runbook when Kubernetes health appears to be contributing
to an Airflow operational issue.

## Typical Evidence

- Airflow pod is unhealthy
- Scheduler pod is not running
- Repeated pod restarts
- Container termination
- Scheduling failures
- Kubernetes events associated with an affected pod

## L1 Investigation

### 1. Check Pod Status

Verify the state of affected Airflow pods.

Look for:

- Running
- Pending
- Failed
- CrashLoopBackOff
- Restarting

### 2. Check Restart Counts

Determine whether the affected pod is repeatedly restarting.

### 3. Check Container Status

Review:

- container termination reason
- readiness state
- liveness state
- startup state

### 4. Check Kubernetes Events

Review recent events associated with the affected pod.

Look for:

- scheduling failures
- resource pressure
- image problems
- volume problems
- node-related issues

### 5. Correlate With Airflow Evidence

Compare Kubernetes evidence with:

- scheduler heartbeat
- Airflow logs
- task state
- CPU usage
- memory usage

## Possible Causes

- Pod failure
- Container failure
- Resource constraints
- Node problems
- Configuration problems
- Deployment problems

## Escalation Criteria

Escalate when:

- Pods repeatedly fail
- Node-level problems are suspected
- Cluster-level problems are suspected
- Infrastructure changes are required
- The problem affects multiple workloads
- L1 cannot determine the cause safely

## Safety

Do not delete pods, modify deployments, or change cluster
configuration unless the approved operational procedure explicitly
authorizes the action.