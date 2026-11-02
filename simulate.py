import argparse
import csv
import json
import os
from collections import defaultdict

from tt_core import Instance, load
from substitute import Context, run_day, load_solution, DEFAULT_WEIGHTS, METHODS


def gini(xs):
    xs = sorted(xs)
    n, s = len(xs), sum(xs)
    if n == 0 or s == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs)) / (n * s)


def run_simulation(ctx, days, methods, weights, fair=1.0, show_day=None, inst=None):
    inst = inst or ctx.inst
    rows, summary = [], []
    for method in methods:
        if method not in METHODS:
            raise SystemExit(f"unknown method {method}")
        cum = defaultdict(int)
        tot = defaultdict(float)
        for day in days:
            res, plan, extra = run_day(ctx, method, day["day"], day["absent"], cum, weights, fair)
            for t, ps in extra.items():
                cum[t] += len(ps)
            for k, v in res.items():
                tot[k] += v
            rows.append({"method": method, "i": day["i"], "day": day["day"], "absent": len(day["absent"]), **res})
            if show_day == day["i"]:
                print(f"\n[{method}] day {day['i']} ({inst.days[day['day']]}) absent={day['absent']}")
                for x in plan:
                    print(f"   {inst.labels[x['period']]}  {x['lesson']:<14} {x['absent']} -> {x['substitute']}")
        n = tot["tasks"] or 1
        loads = [cum.get(t, 0) for t in inst.teachers]
        summary.append({
            "method": method, "lessons_to_cover": int(tot["tasks"]),
            "covered_%": round(100 * tot["covered"] / n, 1),
            "same_subject_%": round(100 * tot["same_subject"] / n, 1),
            "related_%": round(100 * tot["related"] / n, 1),
            "supervision_%": round(100 * tot["supervision"] / n, 1),
            "uncovered_%": round(100 * (tot["tasks"] - tot["covered"]) / n, 1),
            "instr_hours_recovered": int(tot["same_subject"] + tot["related"]),
            "extra_trips": int(tot["trips"]), "gap_delta": int(tot["gap_delta"]),
            "gini": round(gini(loads), 3), "max_subs_teacher": max(loads),
            "avg_ms_per_day": round(tot["time_ms"] / max(1, len(days)), 2),
        })
    return rows, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("solution")
    ap.add_argument("scenarios")
    ap.add_argument("--methods", default="greedy,hungarian,cpsat")
    ap.add_argument("--weights", default=None)
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--show-day", type=int, default=None)
    ap.add_argument("--fair", type=float, default=1.0)
    a = ap.parse_args()

    inst = Instance(load(a.instance))
    ctx = Context(inst, load_solution(a.solution))
    weights = dict(DEFAULT_WEIGHTS)
    if a.weights:
        with open(a.weights, encoding="utf-8") as f:
            weights.update(json.load(f))
    with open(a.scenarios, encoding="utf-8") as f:
        sc = json.load(f)
    os.makedirs(a.outdir, exist_ok=True)

    rows, summary = run_simulation(ctx, sc["days"], a.methods.split(","), weights, a.fair,
                                   show_day=a.show_day, inst=inst)

    with open(os.path.join(a.outdir, "sim_days.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(a.outdir, "sim_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    keys = list(summary[0].keys())
    print("\n" + " | ".join(f"{k:>14}" for k in keys))
    for s in summary:
        print(" | ".join(f"{str(s[k]):>14}" for k in keys))
    print(f"\nsaved: {a.outdir}/sim_days.csv, {a.outdir}/sim_summary.csv")


if __name__ == "__main__":
    main()
