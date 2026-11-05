import json, os, random, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tt_core import Instance, load
from substitute import Context, load_solution, DEFAULT_WEIGHTS, METHODS, solve_cpsat
from simulate import gini
from gen_scenarios import seasonal

inst = Instance(load(os.path.join(ROOT, "ro_school.json")))
ctx = Context(inst, load_solution(os.path.join(ROOT, "sol_school.json")))
T = list(inst.teachers)
L_ASSUMED = 9.6
COUNTRIES = {
    "England 2024/25": (5.0 / 190, 5.6),
    "Scotland 2022/23": (6.8 / 190, L_ASSUMED),
    "Wales 2023/24": (12.2 * 0.606 / 190, 8.4),
    "Northern Ireland 2025/26": (10.2 / 190, 11.7),
    "Netherlands 2025": (0.059, 10.7),
    "Denmark 2024": (12.7 / 190, L_ASSUMED),
    "France 2007-15": (13.0 / 190, L_ASSUMED),
}

def spells(p, L, seed, n_days=190):
    rnd = random.Random(seed)
    left = {t: 0 for t in T}
    age = {t: 0 for t in T}
    days = []
    q = p / (L * (1 - p) + p)
    for i in range(n_days):
        absent = []
        for t in T:
            if left[t] == 0 and rnd.random() < q:
                n = 1
                while rnd.random() > 1 / L:
                    n += 1
                left[t], age[t] = n, 0
            if left[t] > 0:
                age[t] += 1
                absent.append((t, age[t]))
                left[t] -= 1
        days.append({"i": i, "day": i % inst.D, "absent": absent})
    return days

def simulate(days, method, cap_days, w=DEFAULT_WEIGHTS, fair=1.0):
    cum, tot = defaultdict(int), defaultdict(float)
    for day in days:
        d = day["day"]
        allabs = [t for t, _ in day["absent"]]
        cover = [t for t, a in day["absent"] if cap_days is None or a <= cap_days]
        tasks = ctx.tasks(d, cover)
        cands = [ctx.candidates(x, d, allabs, cum, w) for x in tasks]
        if method == "cpsat":
            assign = solve_cpsat(ctx, d, tasks, cands, cum, fair_w=fair)
        else:
            assign = METHODS[method](ctx, d, tasks, cands)
        feat = {(i, t): f for i, cs in enumerate(cands) for t, _, f in cs}
        extra = defaultdict(int)
        for i, t in assign.items():
            extra[t] += 1
            tot["rec"] += feat[i, t]["same_subject"] + feat[i, t]["related"]
        for t, k in extra.items():
            cum[t] += k
            tot["trips"] += int(not ctx.busy[(t, d)])
        tot["tasks"] += len(tasks)
        tot["covered"] += len(assign)
        tot["hired_days"] += len(allabs) - len(cover)
    loads = [cum.get(t, 0) for t in T]
    n = tot["tasks"] or 1
    return dict(tasks=tot["tasks"], covered=100 * tot["covered"] / n, rec_pct=100 * tot["rec"] / n,
                rec=tot["rec"], gini=gini(loads), max_load=max(loads), mean_load=sum(loads) / len(T),
                hired_days=tot["hired_days"], trips=tot["trips"])

def job(a):
    country, rule, seed = a
    p, L = COUNTRIES[country]
    days = spells(p, L, seed)
    c = Counter(t for d in days for t, _ in d["absent"])
    share = sum(1 for t in T if c[t] > 0) / len(T)
    cap = None if rule == "all" else int(rule)
    return [dict(country=country, rule=rule, seed=seed, p=p, L=L, share_any=share,
                 method=m, **simulate(days, m, cap)) for m in ("greedy", "cpsat")]

if __name__ == "__main__":
    rules = sys.argv[1:] or ["all", "5"]
    jobs = [(c, r, s) for c in COUNTRIES for r in rules for s in range(1, 21)]
    with Pool() as pool:
        out = pool.map(job, jobs)
    name = "results_countries2_" + "_".join(rules) + ".json"
    json.dump([r for rs in out for r in rs], open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "w"))
