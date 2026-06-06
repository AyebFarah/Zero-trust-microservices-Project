import numpy as np
import pandas as pd

np.random.seed(42)

scenarios = {
    "none":               {"count": 1745, "C": (0.95,0.05), "I": (0.95,0.05), "B": (0.95,0.05), "P": (0.95,0.05), "R": (0.95,0.05), "label": 0},
    "mtls_permissive":    {"count": 250,  "C": (0.30,0.15), "I": (0.90,0.05), "B": (0.90,0.05), "P": (0.85,0.05), "R": (0.90,0.05), "label": 1},
    "opa_compromised":    {"count": 200,  "C": (0.90,0.05), "I": (0.20,0.15), "B": (0.85,0.05), "P": (0.25,0.15), "R": (0.88,0.05), "label": 1},
    "falco_shell":        {"count": 200,  "C": (0.90,0.05), "I": (0.88,0.05), "B": (0.15,0.15), "P": (0.88,0.05), "R": (0.90,0.05), "label": 1},
    "falco_sensitive":    {"count": 150,  "C": (0.88,0.05), "I": (0.85,0.05), "B": (0.40,0.20), "P": (0.80,0.10), "R": (0.88,0.05), "label": 1},
    "service_crash":      {"count": 200,  "C": (0.85,0.05), "I": (0.85,0.05), "B": (0.85,0.05), "P": (0.85,0.05), "R": (0.10,0.15), "label": 1},
    "multi_attack":       {"count": 251,  "C": (0.25,0.15), "I": (0.20,0.15), "B": (0.15,0.15), "P": (0.20,0.15), "R": (0.30,0.20), "label": 1},
}

rows = []
for scenario, p in scenarios.items():
    for _ in range(p["count"]):
        rows.append({
            "C": np.clip(np.random.normal(p["C"][0], p["C"][1]), 0, 1),
            "I": np.clip(np.random.normal(p["I"][0], p["I"][1]), 0, 1),
            "B": np.clip(np.random.normal(p["B"][0], p["B"][1]), 0, 1),
            "P": np.clip(np.random.normal(p["P"][0], p["P"][1]), 0, 1),
            "R": np.clip(np.random.normal(p["R"][0], p["R"][1]), 0, 1),
            "scenario": scenario, "label": p["label"]
        })

df = pd.DataFrame(rows)
df.to_csv("../dataset/security_dataset.csv", index=False)
print(f"Dataset: {len(df)} échantillons")
print(df["scenario"].value_counts())
