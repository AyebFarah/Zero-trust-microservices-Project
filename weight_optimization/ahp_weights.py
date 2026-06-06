import numpy as np

matrix = np.array([
    [1,    2,    1,    3,    5  ],
    [1/2,  1,    1/2,  2,    4  ],
    [1,    2,    1,    3,    5  ],
    [1/3,  1/2,  1/3,  1,    2  ],
    [1/5,  1/4,  1/5,  1/2,  1  ]
])

def compute_ahp(matrix):
    n = matrix.shape[0]
    gm = np.prod(matrix, axis=1) ** (1/n)
    weights = gm / gm.sum()
    lambda_max = np.dot(matrix.sum(axis=0), weights)
    CI = (lambda_max - n) / (n - 1)
    CR = CI / 1.11
    return weights, lambda_max, CI, CR

if __name__ == "__main__":
    labels = ["C", "I", "B", "P", "R"]
    weights, lambda_max, CI, CR = compute_ahp(matrix)
    print("=== AHP ===")
    for l, w in zip(labels, weights):
        print(f"  w_AHP({l}) = {w:.4f}")
    print(f"  CR = {CR:.4f} {'✅' if CR < 0.10 else '❌'}")
