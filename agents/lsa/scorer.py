import json
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class SecurityScore:
    service_name: str
    C: float
    I: float
    B: float
    P: float
    R: float
    total: float
    timestamp: str
    status: str

class SecurityScorer:
    DEFAULT_WEIGHTS = {
        "w1": 0.2410,
        "w2": 0.2232,
        "w3": 0.3116,
        "w4": 0.1436,
        "w5": 0.0807,
    }
    THRESHOLD_CRITICAL = 0.30
    THRESHOLD_WARNING  = 0.60
    THRESHOLD_HEALTHY  = 0.80

    def __init__(self, service_name: str, weights_file: str = "weights_optimal.json"):
        self.service_name = service_name
        self.weights = self._load_weights(weights_file)

    def _load_weights(self, weights_file: str) -> dict:
        try:
            with open(weights_file) as f:
                data = json.load(f)
            w = data["weights"]
            loaded = {
                "w1": w["w1_C"],
                "w2": w["w2_I"],
                "w3": w["w3_B"],
                "w4": w["w4_P"],
                "w5": w["w5_R"],
            }
            logger.info(
                f"Poids AHP+EWM chargés : "
                f"C={loaded['w1']} I={loaded['w2']} B={loaded['w3']} "
                f"P={loaded['w4']} R={loaded['w5']}"
            )
            return loaded
        except Exception as e:
            logger.warning(f"weights_optimal.json non trouvé ({e}) — poids AHP+EWM par défaut")
            return self.DEFAULT_WEIGHTS

    def compute(self, components: dict) -> SecurityScore:
        w = self.weights
        C = components.get("C", 0.5)
        I = components.get("I", 0.5)
        B = components.get("B", 0.5)
        P = components.get("P", 0.5)
        R = components.get("R", 0.5)

        total = w["w1"]*C + w["w2"]*I + w["w3"]*B + w["w4"]*P + w["w5"]*R
        total = round(min(1.0, max(0.0, total)), 4)

        if total < self.THRESHOLD_CRITICAL:
            status = "ISOLATED"
        elif total < self.THRESHOLD_WARNING:
            status = "CRITICAL"
        elif total < self.THRESHOLD_HEALTHY:
            status = "WARNING"
        else:
            status = "HEALTHY"

        score = SecurityScore(
            service_name=self.service_name,
            C=round(C, 4), I=round(I, 4), B=round(B, 4),
            P=round(P, 4), R=round(R, 4),
            total=total,
            timestamp=datetime.utcnow().isoformat(),
            status=status
        )
        logger.info(
            f"Score {self.service_name}: {total:.4f} [{status}] "
            f"C={C:.2f} I={I:.2f} B={B:.2f} P={P:.2f} R={R:.2f} (poids: AHP+EWM)"
        )
        return score
