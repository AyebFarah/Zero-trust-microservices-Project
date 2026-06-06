import numpy as np
import json
import sys
sys.path.insert(0, '.')
from ahp_weights import compute_ahp, matrix
from ewm_weights import compute_ewm

ALPHA = 0.60
DATASET_PATH = "../dataset/security_dataset.csv"
OUTPUT_PATH = "../agents/lsa/weights_optimal.json"
labels = ["C","I","B","P","R"]

ahp_arr, _, _, CR = compute_ahp(matrix)
ahp = {l: float(w) for l, w in zip(labels, ahp_arr)}
ewm = compute_ewm(DATASET_PATH)

final = {l: round(ALPHA*ahp[l] + (1-ALPHA)*ewm[l], 4) for l in labels}
total = sum(final.values())
final = {l: round(v/total, 4) for l, v in final.items()}

result = {
    "weights": {
        "w1_C": final["C"], "w2_I": final["I"], "w3_B": final["B"],
        "w4_P": final["P"], "w5_R": final["R"]
    },
    "method": "AHP+EWM", "alpha": ALPHA, "CR_AHP": round(float(CR), 4)
}

with open(OUTPUT_PATH, "w") as f:
    json.dump(result, f, indent=2)

print("\n=== POIDS FINAUX ===")
for l in labels:
    print(f"  w({l}): AHP={ahp[l]:.4f}  EWM={ewm[l]:.4f}  FINAL={final[l]:.4f}")
print(f"\nFormule: S = {final['C']}*C + {final['I']}*I + {final['B']}*B + {final['P']}*P + {final['R']}*R")
print(f"Somme: {sum(final.values()):.4f}")
print(f"✅ {OUTPUT_PATH}")
