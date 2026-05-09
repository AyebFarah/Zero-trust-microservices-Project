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
        "w1": 0.25,
        "w2": 0.20,
        "w3": 0.25,
        "w4": 0.20,
        "w5": 0.10,
    }
    THRESHOLD_CRITICAL = 0.30
    THRESHOLD_WARNING  = 0.60
    THRESHOLD_HEALTHY  = 0.80

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.weights = self.DEFAULT_WEIGHTS

    def compute(self, components: dict) -> SecurityScore:
        w = self.weights
        C = components.get("C", 0.5)
        I = components.get("I", 0.5)
        B = components.get("B", 0.5)
        P = components.get("P", 0.5)
        R = components.get("R", 0.5)

        total = (w["w1"]*C + w["w2"]*I + w["w3"]*B + w["w4"]*P + w["w5"]*R)
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
            C=round(C,4), I=round(I,4), B=round(B,4),
            P=round(P,4), R=round(R,4),
            total=total,
            timestamp=datetime.utcnow().isoformat(),
            status=status
        )
        logger.info(f"Score {self.service_name}: {total:.4f} ({status})")
        return score
