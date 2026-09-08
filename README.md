# Adaptive Airflow Support Intelligence Platform

### AI-Assisted L1 Incident Investigation, Explainability & Escalation Support

An Airflow-specific operational intelligence platform designed to assist L1 engineers in investigating Airflow incidents by automatically detecting failures, collecting operational evidence, classifying incident types, explaining ML predictions, mapping incidents to runbooks, and providing investigation and escalation guidance.

> **V1 Working Proof of Concept — September 2026**

---

## Overview

Airflow incident investigation often requires engineers to correlate information from multiple sources, including:

- Airflow DAG and task states
- Task failure logs
- Scheduler signals
- DAG parsing information
- Kubernetes-related evidence
- Operational metrics
- Recent changes
- Support runbooks

This information can be fragmented across different tools, making incident investigation dependent on manual correlation and engineer experience.

The **Adaptive Airflow Support Intelligence Platform** explores a specialized intelligence layer above existing Airflow and operational tooling.

The platform aims to help answer:

> **What is likely wrong? Why does the system think that? What should the L1 engineer check next? Should the incident remain at L1 or be escalated?**

The system does **not** automatically modify production systems. The final decision remains with the support engineer.

---

## Key Features

### Automatic Incident Detection

The platform monitors Airflow for new failed DAG runs and automatically initiates the investigation workflow.

```text
New Airflow Failure
        ↓
Automatic Incident Detection
        ↓
Evidence Collection
        ↓
Incident Analysis
```

No manual incident selection is required for the V1 demonstration.

### Airflow Evidence Collection

The backend connects to Airflow through the Airflow REST API and collects available operational evidence such as:

- DAG information
- DAG run state
- Task instance state
- Failed task information
- Operator information
- Task duration
- Retry information
- Failure logs
- Exception type
- Exception message
- DAG import errors

### ML-Based Incident Classification

A Random Forest classifier is used to classify incidents into six V1 categories:

- Scheduler
- DAG Parsing
- Resource
- Kubernetes
- Configuration
- Unknown

The model is trained using synthetic, scenario-based incident data.

### Explainable AI with SHAP

The platform uses SHAP to provide feature-level explanations for the ML prediction.

Instead of only displaying:

```text
Incident: Resource
Confidence: 73.5%
```

the system can also show which features contributed most strongly to the prediction.

Example:

```text
Top contributing features:

Memory Usage       → strong contribution
CPU Usage          → strong contribution
DAG Parse Time     → moderate contribution
```

SHAP explanations describe the model's decision contribution and should not be interpreted as proof of causal relationships.

### Runbook Mapping

The predicted incident class is mapped to the corresponding support runbook.

```text
Incident Classification
        ↓
Runbook Matching
        ↓
Airflow-Specific L1 Checks
```

Current runbooks include:

```text
runbooks/
├── scheduler.md
├── dag_parsing.md
├── resource.md
├── kubernetes.md
├── configuration.md
└── unknown.md
```

### L1 Recommendation & Escalation Guidance

The platform generates investigation guidance based on:

- Predicted incident type
- Model confidence
- SHAP contributors
- Available evidence
- Matched runbook

The output provides suggested L1 investigation steps and indicates whether additional evidence should be gathered or escalation should be considered.

The system supports the engineer rather than replacing the engineer's decision.

---

## V1 Architecture

```text
                    ┌─────────────────────┐
                    │   Local Airflow     │
                    │                     │
                    │ DAGs / Tasks / Logs │
                    └──────────┬──────────┘
                               │
                         Airflow REST API
                               │
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Evidence Engine   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Feature Pipeline  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Random Forest Model │
                    │  Incident Classifier│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   SHAP Explanation  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Runbook Engine    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ L1 Recommendation   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   React + Vite      │
                    │    L1 Dashboard     │
                    └─────────────────────┘
```

## Investigation Workflow

The complete V1 workflow is:

```text
New DAG Failure
      ↓
Automatic Detection
      ↓
Airflow Evidence Collection
      ↓
Feature Extraction
      ↓
ML Classification
      ↓
SHAP Explanation
      ↓
Runbook Matching
      ↓
L1 Recommendation
      ↓
Resolve / Escalate
```

---

## ML Training

The training dataset is generated synthetically using scenario-based incident patterns.

The generated dataset contains approximately 1,000 synthetic incident records covering the six V1 incident classes.

### Features

The current ML feature set includes:

- cpu_usage
- memory_usage
- heartbeat_status
- dag_parse_time
- recent_changes
- scheduler_pod_status
- worker_restarts

### Model

- Algorithm: Random Forest Classifier
- Estimators: 200
- Train/Test Split: 80/20
- Random State: 42

The trained model is stored as:

```text
backend/models/incident_classifier.joblib
```

### Current ML Validation

The current Random Forest model achieved:

**Held-out Test Accuracy: 94%**

The result is based on the synthetic dataset used for the V1 proof of concept.

It is not production performance and should not be interpreted as an accuracy estimate for real-world Airflow incidents.

The main observed classification confusion was between:

- DAG Parsing ↔ Unknown
- Scheduler ↔ Resource

Further validation with broader and more realistic incident data is planned.

---

## Synthetic Incident Scenarios

The project includes controlled Airflow DAGs that generate synthetic failures for demonstration and testing.

Examples include:

### Resource Failure

Simulates a resource-pressure failure using synthetic CPU, memory, and worker restart signals.

### Kubernetes Failure

Simulates Kubernetes-style failure evidence such as:

```text
PodStatus=CrashLoopBackOff
RestartCount=5
ExitCode=137
```

The scenario does not modify or interact with a real Kubernetes cluster.

### Kubernetes Image Failure

Simulates:

```text
PodStatus=ImagePullBackOff
```

### DAG Parsing Failure

A controlled import failure is used to generate an actual Airflow DAG parsing/import error.

### Configuration Failure

A controlled failure simulates a missing Airflow configuration dependency:

```text
Connection=customer_database
ConfigStatus=MISSING_CONNECTION
```

These scenarios are intended for local testing and demonstration only.

---

## Data Strategy

The V1 implementation separates operational knowledge, ML training data, and demonstration data.

### Reference Environment

Used to understand:

- Airflow support workflows
- Incident patterns
- Operational evidence
- L1 investigation processes

### Synthetic ML Dataset

Used for:

- Model training
- Model evaluation
- Controlled experiments

This avoids requiring confidential production incident data.

### Local Airflow Environment

Used to generate actual Airflow failure evidence and demonstrate the end-to-end investigation workflow.

No customer production credentials or confidential customer data are required for the V1 demonstration.

---

## Technology Stack

### Frontend
- React
- Vite

### Backend
- Python
- FastAPI

### Machine Learning
- Pandas
- Scikit-learn
- Random Forest
- SHAP
- Joblib

### Airflow
- Apache Airflow
- Airflow REST API
- Docker

### Support Intelligence
- Evidence Engine
- Feature Pipeline
- Incident Classifier
- SHAP Explanation
- Runbook Engine
- L1 Recommendation Engine

---

## Project Structure

```text
airflow-support-intelligence/
│
├── backend/
│   ├── app/
│   │   ├── analyze.py
│   │   ├── evidence.py
│   │   ├── airflow_adapter.py
│   │   ├── runbook.py
│   │   └── recommendation.py
│   │
│   ├── data/
│   │   └── synthetic_incidents.csv
│   │
│   └── models/
│       └── incident_classifier.joblib
│
├── frontend/
│   └── ...
│
├── ml/
│   ├── generate_data.py
│   ├── train.py
│   ├── predict.py
│   └── explain.py
│
├── runbooks/
│   ├── scheduler.md
│   ├── dag_parsing.md
│   ├── resource.md
│   ├── kubernetes.md
│   ├── configuration.md
│   └── unknown.md
│
├── dags/
│   ├── support_intelligence_failure.py
│   ├── support_intelligence_resource_failure.py
│   ├── support_intelligence_kubernetes_failure.py
│   ├── support_intelligence_kubernetes_image_failure.py
│   ├── support_intelligence_dag_parsing_failure.py
│   └── support_intelligence_configuration_failure.py
│
└── README.md
```

---

## Getting Started

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd airflow-support-intelligence
```

### 2. Start the Local Airflow Environment

Start the local Airflow environment using the project's Docker configuration.

Verify that Airflow is available before starting the intelligence backend.

### 3. Install Backend Dependencies

Create and activate a Python virtual environment:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r backend/requirements.txt
```

### 4. Train the ML Model

Generate the synthetic training dataset:

```bash
python ml/generate_data.py
```

Train the Random Forest classifier:

```bash
python ml/train.py
```

The trained model will be saved under:

```text
backend/models/
```

### 5. Start the FastAPI Backend

From the project root:

```bash
uvicorn backend.main:app --reload
```

The backend provides the APIs required by the frontend and connects to the configured Airflow REST API.

### 6. Start the Frontend

Install frontend dependencies:

```bash
npm install
```

Start the Vite development server:

```bash
npm run dev
```

Open the dashboard using the URL shown by Vite.

---

## Demonstration

The V1 demonstration follows this process:

1. Start Airflow
2. Start the FastAPI backend
3. Start the React frontend
4. Trigger a synthetic failure DAG
5. Airflow records the failed DAG run
6. Backend automatically detects the new failure
7. Airflow evidence is collected
8. Incident intelligence is generated
9. Frontend displays the investigation result

The dashboard can display:

- Incident detection status
- Incident classification
- Model confidence
- Airflow evidence
- Failed task information
- Failure logs
- SHAP contributors
- Matched runbook
- L1 investigation checks
- Escalation guidance

### Example Investigation

A synthetic Kubernetes image failure may produce evidence such as:

```text
Failure:
Synthetic Kubernetes image failure detected

PodStatus:
ImagePullBackOff

RestartCount:
0

ExitCode:
1
```

The intelligence layer can then combine the available evidence and produce an output similar to:

```text
Incident Class:
Kubernetes

Confidence:
94%

Runbook:
kubernetes.md

Recommendation:
Inspect the corresponding Kubernetes pod
and review pod events for image retrieval/startup issues.
```

The exact classification and confidence depend on the evidence available to the system.

---

## Design Principles

### 1. Human-in-the-Loop

The platform provides investigation support rather than autonomous production remediation.

```text
System → Investigate & Recommend
Engineer → Decide & Act
```

### 2. Explainability

ML predictions should provide supporting explanations so engineers can understand which features influenced the prediction.

### 3. Airflow Specialization

The project is not intended to replace general AIOps or ITSM platforms.

The focus is on applying operational intelligence specifically to the Airflow L1 investigation workflow.

### 4. Evidence-Driven Investigation

The platform aims to reduce the need for engineers to manually correlate information from multiple operational sources.

### 5. Safe Demonstration

The V1 proof of concept uses synthetic incident scenarios and a local Airflow environment.

No automatic production modification is performed.

---

## Existing AIOps vs. This V1

General AIOps and ITSM platforms already provide capabilities such as:

- Incident management
- Alert correlation
- Event intelligence
- Generic anomaly detection
- Automation

This project takes a narrower approach:

| General AIOps | This V1 |
|---|---|
| Broad IT operations | Airflow-specific |
| Multiple technology domains | Airflow incident patterns |
| Generic incident triage | Airflow L1 investigation |
| General AI insights | ML + SHAP explanation |
| General workflows | Airflow-specific runbooks |
| Broad automation | Human-controlled L1 guidance |

The goal is therefore specialization rather than replacing existing AIOps platforms.

---

## Evaluation

The V1 evaluation considers both technical and operational measures.

### Technical Metrics
- Classification accuracy
- Precision
- Recall
- F1-score
- Explanation consistency

### Operational Metrics
- Runbook retrieval accuracy
- Escalation accuracy
- Investigation time
- Evidence coverage

These metrics will become more meaningful as the system is evaluated against broader and more realistic incident scenarios.

---

## Roadmap

### V1 — L1 Airflow Incident Intelligence

Current focus:

- Automatic incident detection
- Airflow evidence collection
- Incident classification
- SHAP explanation
- Runbook mapping
- L1 recommendations
- Escalation guidance

### V2 — Broader L1 Intelligence

Planned expansion:

- More incident categories
- Additional Airflow operational signals
- Broader evidence correlation
- Improved classification
- Expanded runbook coverage

### V3 — L2 RCA Assistance

Potential capabilities:

- Deeper root-cause analysis
- Cross-system evidence correlation
- Historical incident comparison
- Advanced investigation assistance

### V4 — L3 Operational Intelligence

Potential capabilities:

- Advanced operational analytics
- Broader infrastructure intelligence
- Predictive operational insights
- Advanced support automation

---

## Current Status

**V1 Working Proof of Concept**

Implemented:

- [x] Synthetic incident dataset generation
- [x] Random Forest incident classifier
- [x] Model evaluation
- [x] SHAP explanations
- [x] Airflow REST API integration
- [x] Airflow evidence collection
- [x] Synthetic Airflow failure scenarios
- [x] Automatic failed-run detection
- [x] Runbook mapping
- [x] L1 recommendation generation
- [x] React + Vite dashboard
- [x] End-to-end demonstration workflow

Planned:

- [ ] PostgreSQL persistence
- [ ] Kubernetes telemetry integration
- [ ] Prometheus integration
- [ ] Grafana integration
- [ ] OpenTelemetry integration
- [ ] Broader incident dataset
- [ ] Expanded incident classification
- [ ] Historical incident analysis
- [ ] Advanced L2 RCA assistance

---

## Disclaimer

This repository represents a working proof of concept.

The ML results are based on synthetic data and are not representative of production performance.

Synthetic failure DAGs are designed for controlled local demonstration and testing. They do not intentionally modify or disrupt production infrastructure.

The platform provides recommendations and investigation assistance; it does not autonomously perform production remediation.

---

## Author

**Dasun Sandeepa**
Intern – Software Engineer, Airflow Support
iVedha Inc.

---

## License

This project is intended for research, educational, and proof-of-concept purposes.
