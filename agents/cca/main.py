from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from prometheus_client import Gauge, Counter, start_http_server
import logging, threading, json, ssl, urllib.request, urllib.error, os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CCA] %(levelname)s: %(message)s")
logger = logging.getLogger("cca")

app = FastAPI(title="Central Composition Agent", version="3.0.0")

ISOLATION_THRESHOLD = 0.50
RECOVERY_THRESHOLD_SCORE = 0.65
RECOVERY_THRESHOLD = 3
SCORE_TTL = timedelta(minutes=10)
K8S_API = "https://kubernetes.default.svc.cluster.local"
NAMESPACE_APP = "app"
METRICS_PORT = int(os.getenv("METRICS_PORT", "9091"))

SERVICE_CONTEXTS = {
    "service-payment": ["ctx-a", "ctx-b"],
    "service-auth": ["ctx-a", "ctx-b"],
    "service-orders": ["ctx-a", "ctx-b"],
    "service-notification": ["ctx-a", "ctx-b"],
}

WORKFLOWS = {
    "checkout": ["service-auth", "service-orders", "service-payment", "service-notification"],
    "login": ["service-auth"],
    "orders": ["service-auth", "service-orders"],
}

class ScoreReport(BaseModel):
    service: str
    score: float
    components: Dict[str, float]
    status: str
    timestamp: str

scores_table: Dict[str, ScoreReport] = {}
active_routing: Dict[str, str] = {s: "ctx-a" for s in SERVICE_CONTEXTS}
isolated_services: Dict[str, dict] = {}
recovery_counter: Dict[str, int] = {}
routing_history: List[dict] = []

CCA_SCORE_GAUGE = Gauge("cca_service_score", "Score par service et contexte", ["service", "context", "status"])
CCA_ACTIVE_CTX = Gauge("cca_active_context", "Contexte actif", ["service", "context"])
CCA_BASCULEMENTS = Counter("cca_basculements_total", "Basculements effectués", ["service"])

def get_k8s_token() -> str:
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("Token K8s non trouvé — mode simulation")
        return ""

def get_ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def k8s_patch_service(service_name: str, target_context: str) -> bool:
    token = get_k8s_token()
    if not token:
        logger.warning(f"[SIMULATION] Patch {service_name} -> {target_context}")
        return True
    body = json.dumps({"spec": {"selector": {"app": service_name, "context": target_context}}}).encode()
    url = f"{K8S_API}/api/v1/namespaces/{NAMESPACE_APP}/services/{service_name}"
    req = urllib.request.Request(url, data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/merge-patch+json"},
        method="PATCH")
    try:
        urllib.request.urlopen(req, context=get_ssl_ctx(), timeout=5)
        logger.info(f" Patch K8s OK : {service_name} -> context={target_context}")
        return True
    except Exception as e:
        logger.error(f" Patch K8s {service_name}: {e}")
        return False

def k8s_apply_deny(service_name: str, context: str) -> bool:
    token = get_k8s_token()
    if not token:
        logger.warning(f"[SIMULATION] DENY {service_name}:{context}")
        return True
    policy = {
        "apiVersion": "security.istio.io/v1beta1", "kind": "AuthorizationPolicy",
        "metadata": {"name": f"deny-{service_name}-{context}", "namespace": NAMESPACE_APP},
        "spec": {
            "selector": {"matchLabels": {"app": service_name, "context": context}},
            "action": "DENY",
            "rules": [{"from": [{"source": {"namespaces": [NAMESPACE_APP]}}]}]
        }
    }
    url = f"{K8S_API}/apis/security.istio.io/v1beta1/namespaces/{NAMESPACE_APP}/authorizationpolicies"
    req = urllib.request.Request(url, data=json.dumps(policy).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST")
    try:
        urllib.request.urlopen(req, context=get_ssl_ctx(), timeout=5)
        logger.info(f" ISOLATION ACTIVE : {service_name}-{context}")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return True
        logger.error(f"Erreur DENY policy: {e.code}")
        return False
    except Exception as e:
        logger.error(f"Erreur DENY: {e}")
        return False

def k8s_delete_deny(service_name: str, context: str) -> bool:
    token = get_k8s_token()
    if not token:
        logger.warning(f"[SIMULATION] Suppression DENY {service_name}:{context}")
        return True
    url = f"{K8S_API}/apis/security.istio.io/v1beta1/namespaces/{NAMESPACE_APP}/authorizationpolicies/deny-{service_name}-{context}"
    req = urllib.request.Request(url,
        headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    try:
        urllib.request.urlopen(req, context=get_ssl_ctx(), timeout=5)
        logger.info(f" DENY supprimée : {service_name}-{context}")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return True
        logger.error(f"Erreur suppression DENY: {e.code}")
        return False
    except Exception as e:
        logger.error(f"Erreur suppression: {e}")
        return False

def select_best_context(service_name: str, excluded: str) -> Optional[str]:
    candidates = {}
    now = datetime.utcnow()
    for ctx in SERVICE_CONTEXTS.get(service_name, []):
        if ctx == excluded:
            continue
        key = f"{service_name}:{ctx}"
        if key in isolated_services:
            continue
        report = scores_table.get(key)
        if not report:
            continue
        if now - datetime.fromisoformat(report.timestamp) > SCORE_TTL:
            continue
        if report.score >= ISOLATION_THRESHOLD:
            candidates[ctx] = report.score
    if not candidates:
        logger.error(f"Aucun contexte sain pour {service_name}")
        return None
    best = max(candidates, key=candidates.get)
    logger.info(f"[DÉCISION] {service_name} -> {best} (score={candidates[best]:.4f})")
    return best

def handle_critical(service_name: str, context: str, score: float):
    key = f"{service_name}:{context}"
    if key in isolated_services:
        if score >= RECOVERY_THRESHOLD_SCORE:
            recovery_counter[key] = recovery_counter.get(key, 0) + 1
            logger.info(f"Récupération {key}: {recovery_counter[key]}/{RECOVERY_THRESHOLD}")
            if recovery_counter[key] >= RECOVERY_THRESHOLD:
                k8s_delete_deny(service_name, context)
                del isolated_services[key]
                del recovery_counter[key]
                logger.info(f" {key} réintégré")
        else:
            recovery_counter[key] = 0
        return
    logger.warning(f" Score critique : {key} = {score:.4f} < {ISOLATION_THRESHOLD}")
    k8s_apply_deny(service_name, context)
    isolated_services[key] = {"isolated_at": datetime.utcnow().isoformat(), "score": score}
    recovery_counter[key] = 0
    best_ctx = select_best_context(service_name, excluded=context)
    if not best_ctx:
        return
    previous = active_routing.get(service_name, "ctx-a")
    if k8s_patch_service(service_name, best_ctx):
        active_routing[service_name] = best_ctx
        CCA_BASCULEMENTS.labels(service=service_name).inc()
        routing_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "service": service_name,
            "from_context": previous,
            "to_context": best_ctx,
            "trigger_score": score
        })
        logger.info(f" BASCULEMENT : {service_name} {previous} -> {best_ctx}")

@app.get("/health")
def health():
    return {"status": "healthy", "version": "3.0.0", "services_tracked": len(scores_table)}

@app.post("/api/scores")
async def receive_score(report: ScoreReport):
    scores_table[report.service] = report
    parts = report.service.split(":")
    svc = parts[0]
    ctx = parts[1] if len(parts) > 1 else "ctx-a"
    CCA_SCORE_GAUGE.labels(service=svc, context=ctx, status=report.status).set(report.score)
    active_ctx = active_routing.get(svc, "ctx-a")
    for c in SERVICE_CONTEXTS.get(svc, []):
        CCA_ACTIVE_CTX.labels(service=svc, context=c).set(1 if c == active_ctx else 0)
    logger.info(f"Score reçu: {report.service} = {report.score:.4f} [{report.status}]")
    if report.score < ISOLATION_THRESHOLD:
        handle_critical(svc, ctx, report.score)
    return {"received": True, "service": report.service}

@app.get("/api/compose")
def compose_workflow(workflow: str):
    if workflow not in WORKFLOWS:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow}' inconnu")
    selected, excluded = [], []
    now = datetime.utcnow()
    for svc in WORKFLOWS[workflow]:
        active_ctx = active_routing.get(svc, "ctx-a")
        key = f"{svc}:{active_ctx}"
        report = scores_table.get(key)
        if not report:
            excluded.append({"service": svc, "reason": "Pas encore évalué", "score": None})
            continue
        if now - datetime.fromisoformat(report.timestamp) > SCORE_TTL:
            excluded.append({"service": svc, "reason": "Score expiré", "score": report.score})
            continue
        if report.score >= ISOLATION_THRESHOLD:
            selected.append({"service": svc, "context": active_ctx, "score": report.score, "status": report.status})
        else:
            excluded.append({"service": svc, "reason": f"Score trop bas ({report.score:.4f})", "score": report.score})
    selected.sort(key=lambda x: x["score"], reverse=True)
    return {"workflow": workflow, "selected": selected, "excluded": excluded,
            "composition_time": now.isoformat(), "all_healthy": len(excluded) == 0}

@app.get("/api/status")
def get_status():
    now = datetime.utcnow()
    result = {}
    for svc in SERVICE_CONTEXTS:
        result[svc] = {"active_context": active_routing.get(svc, "ctx-a"), "contexts": {}}
        for ctx in SERVICE_CONTEXTS[svc]:
            key = f"{svc}:{ctx}"
            report = scores_table.get(key)
            if report:
                age = (now - datetime.fromisoformat(report.timestamp)).seconds
                result[svc]["contexts"][ctx] = {
                    "score": report.score, "status": report.status,
                    "isolated": key in isolated_services, "age_seconds": age
                }
            else:
                result[svc]["contexts"][ctx] = {"score": None, "status": "UNKNOWN", "isolated": False}
    return {"services": result, "isolation_threshold": ISOLATION_THRESHOLD}

@app.get("/api/routing")
def get_routing():
    return {
        "routing": {
            svc: {
                "active_context": active_routing.get(svc, "ctx-a"),
                "contexts": {
                    ctx: {
                        "score": scores_table.get(f"{svc}:{ctx}", ScoreReport(
                            service=f"{svc}:{ctx}", score=0, components={},
                            status="UNKNOWN", timestamp=datetime.utcnow().isoformat()
                        )).score,
                        "isolated": f"{svc}:{ctx}" in isolated_services
                    }
                    for ctx in SERVICE_CONTEXTS.get(svc, [])
                }
            }
            for svc in SERVICE_CONTEXTS
        },
        "routing_history": routing_history[-20:],
        "isolated_services": list(isolated_services.keys())
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Métriques Prometheus sur port {METRICS_PORT}")
    start_http_server(METRICS_PORT)
    uvicorn.run(app, host="0.0.0.0", port=8080)
