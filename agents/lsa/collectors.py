import asyncio
import httpx
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

OPA_URL = os.getenv("OPA_URL", "http://opa.security.svc.cluster.local:8181")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090")
TARGET_SERVICE = os.getenv("TARGET_SERVICE", "service-payment")


class DataCollector:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)

    async def collect_mtls_status(self) -> float:
        try:
            query = f"sum(rate(istio_requests_total{{destination_service_name='{TARGET_SERVICE}',security_policy='mutual_tls'}}[5m]))"
            resp = await self.client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
            data = resp.json()
            mtls_rate = float(data["data"]["result"][0]["value"][1]) if data["data"]["result"] else 0.0

            query_total = f"sum(rate(istio_requests_total{{destination_service_name='{TARGET_SERVICE}'}}[5m]))"
            resp2 = await self.client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query_total})
            data2 = resp2.json()
            total_rate = float(data2["data"]["result"][0]["value"][1]) if data2["data"]["result"] else 1.0

            if total_rate == 0:
                return 1.0
            return min(1.0, mtls_rate / total_rate)
        except Exception as e:
            logger.error(f"Erreur collecte mTLS: {e}")
            return 0.5

    async def collect_opa_violations(self) -> float:
        try:
            payload = {
                "input": {
                    "source_service": TARGET_SERVICE,
                    "check_violations": True,
                    "time_window": "5m"
                }
            }
            resp = await self.client.post(f"{OPA_URL}/v1/data/microservices/authz", json=payload)
            result = resp.json().get("result", {})
            violations = result.get("violations", [])
            nb_violations = len(violations)
            logger.info(f"OPA violations pour {TARGET_SERVICE}: {nb_violations}")
            return max(0.0, 1.0 - (nb_violations * 0.1))
        except Exception as e:
            logger.error(f"Erreur collecte OPA: {e}")
            return 0.5

    async def collect_falco_alerts(self) -> float:
        try:
            queries = {
                "CRITICAL": f"increase(falco_events_total{{container_name='{TARGET_SERVICE}',priority='Critical'}}[5m])",
                "ERROR": f"increase(falco_events_total{{container_name='{TARGET_SERVICE}',priority='Error'}}[5m])",
                "WARNING": f"increase(falco_events_total{{container_name='{TARGET_SERVICE}',priority='Warning'}}[5m])",
            }
            weights = {"CRITICAL": 0.3, "ERROR": 0.2, "WARNING": 0.1}
            total_penalty = 0.0
            for priority, query in queries.items():
                resp = await self.client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                count = float(data["data"]["result"][0]["value"][1]) if data["data"]["result"] else 0.0
                total_penalty += count * weights[priority]
                logger.info(f"Falco {priority} pour {TARGET_SERVICE}: {count}")
            return max(0.0, 1.0 - total_penalty)
        except Exception as e:
            logger.error(f"Erreur collecte Falco: {e}")
            return 0.5

    async def collect_policy_compliance(self) -> float:
        try:
            resp = await self.client.post(
                f"{OPA_URL}/v1/data/microservices/authz/compliance_score",
                json={"input": {"source_service": TARGET_SERVICE}}
            )
            score = resp.json().get("result", 0.5)
            return float(score)
        except Exception as e:
            logger.error(f"Erreur collecte compliance: {e}")
            return 0.5

    async def collect_reliability(self) -> float:
        try:
            query_errors = f"rate(istio_requests_total{{destination_service_name='{TARGET_SERVICE}',response_code=~'5..'}}[5m])"
            query_total = f"rate(istio_requests_total{{destination_service_name='{TARGET_SERVICE}'}}[5m])"
            resp_err = await self.client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query_errors})
            resp_tot = await self.client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query_total})
            errors = float(resp_err.json()["data"]["result"][0]["value"][1]) if resp_err.json()["data"]["result"] else 0.0
            total = float(resp_tot.json()["data"]["result"][0]["value"][1]) if resp_tot.json()["data"]["result"] else 1.0
            error_rate = errors / total if total > 0 else 0.0
            return max(0.0, 1.0 - (error_rate * 10))
        except Exception as e:
            logger.error(f"Erreur collecte reliability: {e}")
            return 0.5

    async def collect_all(self) -> dict:
        C, I, B, P, R = await asyncio.gather(
            self.collect_mtls_status(),
            self.collect_opa_violations(),
            self.collect_falco_alerts(),
            self.collect_policy_compliance(),
            self.collect_reliability(),
        )
        return {"C": C, "I": I, "B": B, "P": P, "R": R}
