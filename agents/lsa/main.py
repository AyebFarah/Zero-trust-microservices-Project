import asyncio
import logging
import os
import httpx
from prometheus_client import Gauge, Counter, start_http_server
from collectors import DataCollector
from scorer import SecurityScorer

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [LSA] %(levelname)s: %(message)s")
logger = logging.getLogger("main")

TARGET_SERVICE = os.getenv("TARGET_SERVICE", "service-payment:ctx-a")
CCA_URL = os.getenv("CCA_URL", "http://cca.agents.svc.cluster.local:8080")
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "30"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))

parts = TARGET_SERVICE.split(":")
SERVICE_NAME = parts[0]
CONTEXT = parts[1] if len(parts) > 1 else "ctx-a"

SCORE_GAUGE = Gauge("security_score", "Score par composante", ["service", "component"])
SCORE_TOTAL = Gauge("security_score_total", "Score total", ["service", "status"])
COLLECT_ERRORS = Counter("lsa_collect_errors_total", "Erreurs collecte", ["service"])

async def run_loop(collector: DataCollector, scorer: SecurityScorer):
    while True:
        try:
            components = await collector.collect_all()
            score = scorer.compute(components)
            for comp, val in components.items():
                SCORE_GAUGE.labels(service=TARGET_SERVICE, component=comp).set(val)
            SCORE_TOTAL.labels(service=TARGET_SERVICE, status=score.status).set(score.total)
            await send_to_cca(score)
        except Exception as e:
            logger.error(f"Erreur boucle: {e}")
            COLLECT_ERRORS.labels(service=TARGET_SERVICE).inc()
        await asyncio.sleep(COLLECT_INTERVAL)

async def send_to_cca(score):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            payload = {
                "service": TARGET_SERVICE,
                "score": score.total,
                "components": {"C": score.C, "I": score.I, "B": score.B,
                               "P": score.P, "R": score.R},
                "status": score.status,
                "timestamp": score.timestamp
            }
            resp = await client.post(f"{CCA_URL}/api/scores", json=payload)
            if resp.status_code == 200:
                logger.info(f" Score envoyé : {TARGET_SERVICE} = {score.total:.4f} [{score.status}]")
            else:
                logger.warning(f"CCA répondu {resp.status_code}")
    except Exception as e:
        logger.error(f"Impossible de contacter le CCA: {e}")

async def main():
    logger.info(f"LSA démarré : {TARGET_SERVICE} (service={SERVICE_NAME}, context={CONTEXT})")
    start_http_server(METRICS_PORT)
    collector = DataCollector()
    scorer = SecurityScorer(service_name=TARGET_SERVICE)
    await run_loop(collector, scorer)

if __name__ == "__main__":
    asyncio.run(main())

