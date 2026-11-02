import json
import os
import sys
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tt_core import Instance, load
from substitute import Context, load_solution, DEFAULT_WEIGHTS
from gen_scenarios import generate
from simulate import run_simulation

DIS = ROOT + "/"
inst = Instance(load(DIS + "ro_school.json"))
ctx = Context(inst, load_solution(DIS + "sol_school.json"))
TEACHERS = list(inst.teachers)


def job(args):
    tag, p, seed, methods, fair, amp = args
    days = generate(TEACHERS, inst.D, 190, p, 2.0, seed, amp)
    _, summ = run_simulation(ctx, days, methods, dict(DEFAULT_WEIGHTS), fair)
    absent = sum(len(d["absent"]) for d in days) / len(days)
    return [dict(tag=tag, p=p, seed=seed, fair=fair, amp=amp, absent_day=absent, **s) for s in summ]


def main():
    jobs = []
    S20 = range(1, 21)
    for p in (0.026, 0.045):
        jobs += [("main", p, s, ["greedy", "hungarian", "cpsat"], 1.0, 0.0) for s in S20]
    for lam in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0):
        jobs += [("lambda", 0.026, s, ["cpsat"], lam, 0.0) for s in range(1, 6)]
    jobs += [("lambda_ref", 0.026, s, ["greedy"], 1.0, 0.0) for s in range(1, 6)]
    for base in (0.026, 0.045):
        for d in (0.0, 0.15, 0.3):
            p = round(base * 0.342 * (1 - d), 5)
            jobs += [(f"ro_{base}_{d}", p, s, ["greedy", "hungarian", "cpsat"], 1.0, 0.0) for s in S20]
    for p in (0.009, 0.015, 0.026, 0.035, 0.045, 0.06):
        jobs += [("sens", p, s, ["greedy", "cpsat"], 1.0, 0.0) for s in S20]
    for p in (0.026, 0.045):
        jobs += [("winter", p, s, ["greedy", "cpsat"], 1.0, 0.6) for s in range(1, 6)]
    with Pool() as pool:
        out = pool.map(job, jobs)
    rows = [r for rs in out for r in rs]
    with open(os.path.join(ROOT, "experimente", "results.json"), "w") as f:
        json.dump(rows, f)
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
