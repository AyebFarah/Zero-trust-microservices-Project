import asyncio
import logging
import os
import httpx
from prometheus_client import Gauge, Counter, start_http_server
from collectors import DataCollector
from scorer import SecurityScorer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LSA-%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("main")

TARGET_SERVICE   = os.getenv("TARGET_SERVICE", "service-payment")
CCA_URL          = os.getenv("CCA_URL", "http://cca.agents.svc.cluster.local:8080")
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "30"))
METRICS_PORT     = int(os.getenv("METRICS_PORT", "9090"))

SCORE_GAUGE = Gauge(
    "security_score",
    "Score de sécurité du microservice (0.0 à 1.0)",
    ["service", "component"]
)
SCORE_TOTAL_GAUGE = Gauge(
    "security_score_total",
    "Score de sécurité total du microservice",
    ["service", "status"]
)
COLLECT_ERRORS = Counter(
    "lsa_collect_errors_total",
    "Nombre d'erreurs lors de la collecte",
    ["service", "source"]
)


async def send_score_to_cca(score):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            payload = {
                "service":     score.service_name,
                "score":       score.total,
                "components":  {"C": score.C, "I": score.I, "B": score.B, "P": score.P, "R": score.R},
                "status":      score.status,
                "timestamp":   score.timestamp,
            }
            resp = await client.post(f"{CCA_URL}/api/scores", json=payload)
            if resp.status_code == 200:
                logger.info("Score envoyé au CCA : OK")
            else:
                logger.warning(f"CCA a répondu {resp.status_code}")
    except Exception as e:
        logger.error(f"Impossible de contacter le CCA: {e}")


async def run_collection_loop(collector: DataCollector, scorer: SecurityScorer):
    while True:
        try:
            logger.info(f"=== Début collecte pour {TARGET_SERVICE} ===")
            components = await collector.collect_all()
            logger.info(f"Composantes: {components}")

            score = scorer.compute(components)

            for component, value in components.items():
                SCORE_GAUGE.labels(service=TARGET_SERVICE, component=component).set(value)
            SCORE_TOTAL_GAUGE.labels(service=TARGET_SERVICE, status=score.status).set(score.total)

            await send_score_to_cca(score)
            logger.info(f"Score {TARGET_SERVICE}: {score.total:.4f} [{score.status}]")
        except Exception as e:
            logger.error(f"Erreur dans la boucle de collecte: {e}")
            COLLECT_ERRORS.labels(service=TARGET_SERVICE, source="main").inc()

        await asyncio.sleep(COLLECT_INTERVAL)


async def main():
    logger.info(f"Démarrage du serveur Prometheus sur le port {METRICS_PORT}")
    start_http_server(METRICS_PORT)
    collector = DataCollector()
    scorer    = SecurityScorer(service_name=TARGET_SERVICE)
    logger.info(f"LSA démarré pour {TARGET_SERVICE} | intervalle: {COLLECT_INTERVAL}s")
    await run_collection_loop(collector, scorer)


if __name__ == "__main__":
    asyncio.run(main())
