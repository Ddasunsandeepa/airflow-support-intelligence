# Configuration Incident Runbook

## Purpose

Use this runbook when Airflow behavior appears inconsistent with
the expected configuration or when recent configuration changes
correlate with an incident.

## Typical Evidence

- Recent configuration changes
- Unexpected Airflow component behavior
- Scheduler or task behavior inconsistent with expectations
- Normal CPU and memory but abnormal application behavior
- Environment behavior changes after a deployment or configuration update

## L1 Investigation

### 1. Review Recent Changes

Identify recent changes to:

- Airflow configuration
- environment variables
- deployment configuration
- DAG configuration
- provider configuration

### 2. Compare Expected and Actual Configuration

Determine whether the active environment configuration matches
the expected configuration.

### 3. Check Component Behavior

Correlate configuration changes with:

- scheduler behavior
- DAG parsing
- task execution
- worker behavior
- Kubernetes behavior

### 4. Review Logs

Look for configuration-related warnings or errors.

### 5. Check Version and Provider Compatibility

Determine whether recent Airflow or provider changes may affect
the observed behavior.

## Possible Causes

- Incorrect configuration
- Recent configuration change
- Environment variable mismatch
- Provider compatibility issue
- Deployment configuration problem

## Escalation Criteria

Escalate when:

- Production configuration must be changed
- The configuration behavior is unclear
- A version or provider compatibility issue is suspected
- The issue requires deeper platform investigation
- The impact extends across multiple environments or teams

## Safety

Do not modify production configuration without following the
approved change-management process.