import json, os, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp_countries2 import spells, simulate, COUNTRIES, DEFAULT_WEIGHTS
P, L = COUNTRIES["England 2024/25"]
W = dict(DEFAULT_WEIGHTS)
VARIANTS = {
    "ours": W,
    "no_subject": {**W, "same_subject": 0.0, "related": 0.0},
    "no_presence": {**W, "in_school": 0.0, "adjacent": 0.0, "fills_gap": 0.0, "extends_day": 0.0},
    "no_load": {**W, "day_load": 0.0, "cum_subs": 0.0},
}
def job(a):
    kind, par, seed = a
    days = spells(P, L, seed)
    if kind == "greedy_w":
        r = simulate(days, "greedy", None, {**W, "cum_subs": -par})
    elif kind == "cpsat_l":
        r = simulate(days, "cpsat", None, W, par)
    else:
        m, v = par
        r = simulate(days, m, None, VARIANTS[v])
    return dict(kind=kind, par=str(par), seed=seed, **r)
if __name__ == "__main__":
    jobs = [("greedy_w", w, s) for w in (0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0) for s in range(1, 21)]
    jobs += [("cpsat_l", l, s) for l in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0) for s in range(1, 21)]
    jobs += [("weights", (m, v), s) for m in ("greedy", "cpsat") for v in VARIANTS for s in range(1, 21)]
    with Pool() as pool:
        out = pool.map(job, jobs)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results_england.json"), "w"))
