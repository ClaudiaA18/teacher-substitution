import json, os, random, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from exp_countries2 import spells, simulate, COUNTRIES, DEFAULT_WEIGHTS
P, L = COUNTRIES["England 2024/25"]

def weights(k):
    if k == 0: return dict(DEFAULT_WEIGHTS)
    r = random.Random(1000 + k)
    return {n: v * r.uniform(0.5, 1.5) for n, v in DEFAULT_WEIGHTS.items()}

def job(a):
    m, k, seed = a
    r = simulate(spells(P, L, seed), m, None, weights(k))
    return dict(method=m, k=k, seed=seed, **r)

if __name__ == "__main__":
    jobs = [(m, k, s) for m in ("greedy", "cpsat") for k in range(21) for s in range(1, 11)]
    with Pool() as pool:
        out = pool.map(job, jobs)
    json.dump(out, open(os.path.join(HERE, "results_robust.json"), "w"))
