from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from prometheus_client import Gauge, make_asgi_app
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CCA] %(levelname)s: %(message)s"
)
logger = logging.getLogger("cca")

app = FastAPI(title="Central Composition Agent", version="1.0.0")


class ScoreReport(BaseModel):
    service: str
    score: float
    components: Dict[str, float]
    status: str
    timestamp: str


class WorkflowComposition(BaseModel):
    workflow: str
    selected: List[dict]
    excluded: List[dict]
    composition_time: str
    all_healthy: bool


scores_table: Dict[str, ScoreReport] = {}

WORKFLOWS = {
    "checkout": ["service-auth", "service-orders", "service-payment", "service-notification"],
    "login":    ["service-auth"],
    "orders":   ["service-auth", "service-orders"],
}

ISOLATION_THRESHOLD = 0.50
SCORE_TTL = timedelta(minutes=3)

CCA_SCORE_GAUGE = Gauge(
    "cca_service_score",
    "Score agrégé par service selon le CCA",
    ["service", "status"]
)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "CCA", "services_tracked": len(scores_table)}


@app.post("/api/scores")
async def receive_score(report: ScoreReport):
    scores_table[report.service] = report
    logger.info(f"Score reçu: {report.service} = {report.score:.4f} [{report.status}]")
    CCA_SCORE_GAUGE.labels(service=report.service, status=report.status).set(report.score)
    if report.score < ISOLATION_THRESHOLD:
        logger.warning(f"ISOLATION: {report.service} score={report.score:.4f} < {ISOLATION_THRESHOLD}")
    return {"received": True, "service": report.service}


@app.get("/api/compose", response_model=WorkflowComposition)
def compose_workflow(workflow: str):
    if workflow not in WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow} inconnu")

    required_services = WORKFLOWS[workflow]
    selected = []
    excluded = []
    now = datetime.utcnow()

    for service in required_services:
        report = scores_table.get(service)
        if report is None:
            excluded.append({"service": service, "reason": "Pas encore évalué par un LSA", "score": None})
            continue

        report_time = datetime.fromisoformat(report.timestamp)
        if now - report_time > SCORE_TTL:
            excluded.append({"service": service, "reason": f"Score expiré (>{SCORE_TTL.seconds}s)", "score": report.score})
            continue

        if report.score >= ISOLATION_THRESHOLD:
            selected.append({"service": service, "score": report.score, "status": report.status, "components": report.components})
        else:
            excluded.append({"service": service, "reason": f"Score trop bas ({report.score:.4f} < {ISOLATION_THRESHOLD})", "score": report.score, "status": report.status})

    selected.sort(key=lambda x: x["score"], reverse=True)

    return WorkflowComposition(
        workflow=workflow,
        selected=selected,
        excluded=excluded,
        composition_time=now.isoformat(),
        all_healthy=len(excluded) == 0
    )


@app.get("/api/status")
def get_status():
    now = datetime.utcnow()
    status_list = []
    for service, report in scores_table.items():
        age = (now - datetime.fromisoformat(report.timestamp)).seconds
        status_list.append({
            "service": service,
            "score": report.score,
            "status": report.status,
            "components": report.components,
            "last_update_seconds": age,
            "isolated": report.score < ISOLATION_THRESHOLD
        })
    status_list.sort(key=lambda x: x["score"], reverse=True)
    return {"services": status_list, "isolation_threshold": ISOLATION_THRESHOLD}


metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
