# Scheduler Incident Runbook

## Purpose

Use this runbook when evidence suggests that the Airflow Scheduler
may be unhealthy, delayed, or unable to schedule task instances normally.

## Typical Evidence

- Degraded or missing scheduler heartbeat
- Increased scheduler CPU usage
- Increased scheduler memory usage
- Tasks remaining in a non-running state longer than expected
- Increased scheduling latency
- Scheduler process or pod appears unhealthy

## L1 Investigation

### 1. Check Scheduler Health

Verify whether the Airflow Scheduler is running and producing
regular heartbeat activity.

### 2. Check Scheduler Resource Usage

Review:

- CPU utilization
- Memory utilization
- Resource limits and requests
- Recent resource spikes

### 3. Check Scheduler Logs

Look for:

- Repeated errors
- Database connection problems
- Scheduling delays
- Executor-related errors
- Repeated retries or failures

### 4. Check DAG and Task States

Determine whether affected tasks are:

- scheduled
- queued
- running
- failed
- upstream_failed

Look for patterns across multiple DAGs rather than focusing on
a single task initially.

### 5. Check Recent Changes

Review recent:

- Airflow configuration changes
- DAG changes
- dependency changes
- deployment changes
- infrastructure changes

## Possible Causes

- Scheduler resource pressure
- Scheduler process failure
- Database connectivity problems
- Configuration issues
- Executor-related problems
- Infrastructure problems

## Escalation Criteria

Escalate when:

- Scheduler remains unhealthy after standard L1 checks
- Scheduler repeatedly fails or restarts
- Database or infrastructure problems are suspected
- The issue requires configuration or platform-level changes
- Evidence is insufficient to determine the cause

## Safety

Do not make production configuration or infrastructure changes
without following the organization's approved change process.