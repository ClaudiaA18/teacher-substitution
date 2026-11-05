import json, os, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import exp_countries2 as e
from substitute import Context
from types import SimpleNamespace
SCHOOL = os.environ.get("SCHOOL", "traian_anon.json")
d = json.load(open(os.path.join(HERE, SCHOOL)))
inst = SimpleNamespace(D=5, teachers=d["teachers"], lessons=d["lessons"], unavail={t: set() for t in d["teachers"]},
                       raw={"substitution": {"max_subs_per_day": 2}})
e.inst, e.ctx, e.T = inst, Context(inst, d["entries"]), list(d["teachers"])

def job(a):
    country, rule, seed = a
    p, L = e.COUNTRIES[country]
    days = e.spells(p, L, seed)
    cap = None if rule == "all" else int(rule)
    return [dict(country=country, rule=rule, seed=seed, method=m, **e.simulate(days, m, cap)) for m in ("greedy", "cpsat")]

if __name__ == "__main__":
    jobs = [(c, r, s) for c in e.COUNTRIES for r in ("all", "5") for s in range(1, 21)]
    with Pool() as pool:
        out = pool.map(job, jobs)
    json.dump([r for rs in out for r in rs], open(os.path.join(HERE, os.environ.get("OUT", "results_traian.json")), "w"))
