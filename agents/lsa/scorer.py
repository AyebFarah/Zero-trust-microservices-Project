import json
import yaml
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SecurityScore:
    '''Représente le score de sécurité d un service à un instant T'''
    service_name: str
    C: float  # Confidentialité (mTLS + token)
    I: float  # Intégrité (violations OPA)
    B: float  # Comportement (alertes Falco)
    P: float  # Policy compliance (OPA)
    R: float  # Reliability (error rate)
    total: float
    timestamp: str
    status: str  # 'HEALTHY', 'WARNING', 'CRITICAL', 'ISOLATED'


class SecurityScorer:
    # Poids par défaut de la formule (fallback si weights_optimal.json absent)
    # Somme = 1.0
    DEFAULT_WEIGHTS = {
        'w1': 0.25,  # C : confidentialité (mTLS)
        'w2': 0.20,  # I : intégrité (OPA violations)
        'w3': 0.25,  # B : comportement (Falco)
        'w4': 0.20,  # P : policy compliance
        'w5': 0.10,  # R : reliability (error rate)
    }

    # Seuils de statut
    THRESHOLD_CRITICAL = 0.30  # Score < 0.3 : service isolé par le CCA
    THRESHOLD_WARNING = 0.60   # Score < 0.6 : alerte
    THRESHOLD_HEALTHY = 0.80   # Score >= 0.8 : service sain

    def __init__(self, service_name: str, weights_file: str = "weights_optimal.json"):
        self.service_name = service_name
        self.weights, self.weights_source = self._load_weights(weights_file)

    def _load_weights(self, weights_file: str):
        '''
        Charge les poids AHP+EWM depuis le JSON généré par
        weight_optimization/combine_weights.py.
        Si le fichier est absent, invalide, ou incomplet, retombe sur les
        poids par défaut (0.25/0.20/0.25/0.20/0.10).
        '''
        try:
            with open(weights_file) as f:
                loaded = json.load(f)
            w = loaded["weights"]
            weights = {
                "w1": w["w1_C"],
                "w2": w["w2_I"],
                "w3": w["w3_B"],
                "w4": w["w4_P"],
                "w5": w["w5_R"],
            }
            logger.info(f"Poids AHP+EWM chargés depuis {weights_file}: {weights}")
            return weights, "AHP+EWM"
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"{weights_file} indisponible ({e}), poids par défaut utilisés")
            return self.DEFAULT_WEIGHTS, "default"

    def compute(self, components: dict) -> SecurityScore:
        '''
        Calcule le score total S = w1*C + w2*I + w3*B + w4*P + w5*R
        components : dict avec clés C, I, B, P, R (valeurs 0.0 à 1.0)
        '''
        w = self.weights
        C = components.get('C', 0.5)
        I = components.get('I', 0.5)
        B = components.get('B', 0.5)
        P = components.get('P', 0.5)
        R = components.get('R', 0.5)

        total = (w['w1'] * C + w['w2'] * I + w['w3'] * B +
                 w['w4'] * P + w['w5'] * R)
        total = round(min(1.0, max(0.0, total)), 4)

        # Déterminer le statut
        if total < self.THRESHOLD_CRITICAL:
            status = 'ISOLATED'   # CCA doit exclure ce service
        elif total < self.THRESHOLD_WARNING:
            status = 'CRITICAL'   # Alerte critique
        elif total < self.THRESHOLD_HEALTHY:
            status = 'WARNING'    # Surveillance accrue
        else:
            status = 'HEALTHY'    # Service sain

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
            f"C={C:.2f} I={I:.2f} B={B:.2f} P={P:.2f} R={R:.2f} "
            f"(poids: {self.weights_source})"
        )
        return score
