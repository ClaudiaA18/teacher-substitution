import json, os, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import exp_real as r
e = r.e
orig = e.ctx.candidates
def present_only(task, d, absent, cum, weights):
    return [c for c in orig(task, d, absent, cum, weights) if e.ctx.busy[(c[0], d)]]
e.ctx.candidates = present_only

def job(a):
    country, rule, seed = a
    p, L = e.COUNTRIES[country]
    days = e.spells(p, L, seed)
    cap = None if rule == "all" else int(rule)
    return [dict(country=country, rule=rule, seed=seed, method=m, **e.simulate(days, m, cap)) for m in ("greedy", "cpsat")]

if __name__ == "__main__":
    jobs = [(c, rr, s) for c in e.COUNTRIES for rr in ("all", "5") for s in range(1, 21)]
    with Pool() as pool:
        out = pool.map(job, jobs)
    json.dump([x for xs in out for x in xs], open(os.path.join(HERE, os.environ.get("OUT", "results_traian_present.json")), "w"))
