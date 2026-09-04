from fastapi import FastAPI
from pydantic import BaseModel

from backend.app.analyze import analyze_incident
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="Airflow Support Intelligence",
    description="AI-assisted L1 Airflow incident investigation and support guidance",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncidentEvidence(BaseModel):
    cpu_usage: float
    memory_usage: float
    heartbeat_status: int
    dag_parse_time: float
    recent_changes: int
    scheduler_pod_status: int
    worker_restarts: int


@app.get("/")
def root():
    return {
        "service": "Airflow Support Intelligence",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.post("/analyze")
def analyze(evidence: IncidentEvidence):

    incident = evidence.model_dump()

    result = analyze_incident(incident)

    recommendation = result["recommendation"]

    return {
        "incident": {
            "class": result["incident_class"],
            "confidence": result["confidence"],
        },

        "explanation": {
            "top_contributors": recommendation["top_evidence"],
        },

        "guidance": {
        "runbook": result["runbook"],
        "runbook_status": result["runbook_status"],
        "runbook_content": result["runbook_content"],
        "l1_checks": recommendation["l1_checks"],
        },

        "escalation": {
            "recommendation": recommendation["decision"],
        },
    }