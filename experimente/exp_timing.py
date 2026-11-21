import json, os, sys, time
from collections import defaultdict
from types import SimpleNamespace
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import exp_countries2 as e
from substitute import Context

def setup(school):
    if school == "real":
        d = json.load(open(os.path.join(HERE, "traian_anon.json")))
        inst = SimpleNamespace(D=5, teachers=d["teachers"], lessons=d["lessons"], unavail={t: set() for t in d["teachers"]},
                               raw={"substitution": {"max_subs_per_day": 2}})
        e.inst, e.ctx, e.T = inst, Context(inst, d["entries"]), list(d["teachers"])

def run(country, method, seed):
    p, L = e.COUNTRIES[country]
    cum, rows = defaultdict(int), []
    for day in e.spells(p, L, seed):
        d = day["day"]
        absent = [t for t, _ in day["absent"]]
        t0 = time.perf_counter()
        tasks = e.ctx.tasks(d, absent)
        cands = [e.ctx.candidates(x, d, absent, cum, e.DEFAULT_WEIGHTS) for x in tasks]
        a = e.solve_cpsat(e.ctx, d, tasks, cands, cum, fair_w=1.0) if method == "cpsat" else e.METHODS[method](e.ctx, d, tasks, cands)
        dt = time.perf_counter() - t0
        for t in a.values(): cum[t] += 1
        if tasks: rows.append((len(tasks), dt))
    return rows

if __name__ == "__main__":
    school = sys.argv[1] if len(sys.argv) > 1 else "generated"
    setup(school)
    out = {}
    for method in ("greedy", "hungarian", "cpsat"):
        rows = [r for s in range(1, 6) for r in run("France 2007-15", method, s)]
        ts = sorted(r[1] for r in rows)
        out[method] = dict(days=len(rows), max_tasks=max(r[0] for r in rows), mean_tasks=sum(r[0] for r in rows) / len(rows),
                           median_s=ts[len(ts) // 2], p95_s=ts[int(0.95 * len(ts))], max_s=ts[-1])
        print(school, method, {k: round(v, 4) for k, v in out[method].items()})
    json.dump(out, open(os.path.join(HERE, f"results_timing_{school}.json"), "w"), indent=1)
