import json, sys
from collections import Counter
from multiprocessing import Pool
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tt_core import Instance, load
from substitute import Context, load_solution, DEFAULT_WEIGHTS
from gen_scenarios import generate
from simulate import run_simulation
inst = Instance(load(ROOT + "/ro_school.json"))
ctx = Context(inst, load_solution(ROOT + "/sol_school.json"))
T = list(inst.teachers)

def absence_stats(days):
    c = Counter(t for d in days for t in d["absent"])
    n = len(T)
    return dict(share_any=sum(1 for t in T if c[t] > 0) / n,
                share_10=sum(1 for t in T if c[t] > 10) / n,
                days_per_teacher=sum(c.values()) / n)

def job(a):
    p, L, seed = a
    days = generate(T, inst.D, 190, p, L, seed, 0.0)
    _, s = run_simulation(ctx, days, ["greedy", "cpsat"], dict(DEFAULT_WEIGHTS), 1.0)
    st = absence_stats(days)
    return [dict(p=p, L=L, seed=seed, **st, **x) for x in s]

if __name__ == "__main__":
    P = (0.009, 0.026, 0.039, 0.049, 0.059, 0.068)
    Ls = (1.0, 2.0, 5.7, 8.4)
    jobs = [(p, L, s) for p in P for L in Ls for s in range(1, 21)]
    with Pool() as pool:
        out = pool.map(job, jobs)
    json.dump([r for rs in out for r in rs], open(os.path.join(ROOT, "experimente", "results_grid.json"), "w"))
