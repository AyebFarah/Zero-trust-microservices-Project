import numpy as np
import pandas as pd

def compute_ewm(path):
    df = pd.read_csv(path)
    X = df[["C","I","B","P","R"]].values
    n, m = X.shape
    labels = ["C","I","B","P","R"]
    x_min, x_max = X.min(axis=0), X.max(axis=0)
    X_norm = (X - x_min) / (x_max - x_min + 1e-10)
    P = X_norm / (X_norm.sum(axis=0) + 1e-10)
    P_safe = np.where(P > 0, P, 1e-10)
    entropy = -(1/np.log(n)) * np.sum(P_safe * np.log(P_safe), axis=0)
    divergence = 1 - entropy
    weights = divergence / divergence.sum()
    print("=== EWM ===")
    for l, e, w in zip(labels, entropy, weights):
        print(f"  {l}: entropie={e:.4f}  w_EWM={w:.4f}")
    return {l: float(w) for l, w in zip(labels, weights)}

if __name__ == "__main__":
    compute_ewm("../dataset/security_dataset.csv")
