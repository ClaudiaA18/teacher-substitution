import json
import statistics as st
import sys

from tt_core import Instance, load
from substitute import Context, load_solution, DEFAULT_WEIGHTS
from gen_scenarios import generate
from simulate import run_simulation

inst = Instance(load("ro_school.json"))
ctx = Context(inst, load_solution("sol_school.json"))
T = list(inst.teachers)
SEEDS = range(1, 6)
out = {}


def ms(v):
    return round(st.mean(v), 3), round(st.stdev(v), 3) if len(v) > 1 else 0.0


def run(p, amp=0.0, weights=DEFAULT_WEIGHTS, methods=("greedy", "cpsat"), seeds=SEEDS, fair=1.0):
    agg = {}
    for s in seeds:
        days = generate(T, inst.D, 190, p, 2.0, s, amp)
        rows, summ = run_simulation(ctx, days, list(methods), weights, fair)
        for x in summ:
            m = x["method"]
            r = [y for y in rows if y["method"] == m]
            n = max(1, x["lessons_to_cover"])
            rec = 100 * x["instr_hours_recovered"] / n
            peak_abs = max(y["absent"] for y in r)
            peak_tasks = max(y["tasks"] for y in r)
            worst_unc = max((y["tasks"] - y["covered"]) for y in r)
            vals = {"lessons": x["lessons_to_cover"], "recovered_%": rec, "same_%": x["same_subject_%"],
                    "uncovered_%": x["uncovered_%"], "gini": x["gini"], "max_teacher": x["max_subs_teacher"],
                    "trips": x["extra_trips"], "peak_absent": peak_abs, "peak_tasks": peak_tasks,
                    "worst_day_uncovered": worst_unc, "max_ms": max(y["time_ms"] for y in r)}
            for k, v in vals.items():
                agg.setdefault(m, {}).setdefault(k, []).append(v)
    return {m: {k: ms(v) for k, v in d.items()} for m, d in agg.items()}


part = sys.argv[1] if len(sys.argv) > 1 else "all"

if part in ("all", "sens"):
    out["sensitivity_p"] = {str(p): run(p, seeds=range(1, 4)) for p in (0.015, 0.026, 0.035, 0.045, 0.060)}
if part in ("all", "season"):
    out["seasonal"] = {str(a): run(0.026, amp=a) for a in (0.0, 0.3, 0.6)}
    out["seasonal_p90"] = {str(a): run(0.045, amp=a) for a in (0.0, 0.6)}
if part in ("all", "ablation"):
    base = dict(DEFAULT_WEIGHTS)
    variants = {
        "base": base,
        "no_subject": {**base, "same_subject": 0.0, "related": 0.0},
        "no_presence": {**base, "in_school": 0.0, "adjacent": 0.0, "fills_gap": 0.0, "extends_day": 0.0},
        "no_class": {**base, "teaches_class": 0.0},
        "no_load_terms": {**base, "day_load": 0.0, "cum_subs": 0.0},
        "subject_x2": {**base, "same_subject": 6.0, "related": 3.0},
        "uniform": {k: (1.0 if v > 0 else -1.0) for k, v in base.items()},
    }
    out["ablation"] = {k: run(0.026, weights=w) for k, w in variants.items()}

json.dump(out, open(f"/tmp/exp_{part}.json", "w"), indent=1)
for sec, d in out.items():
    print(f"\n== {sec}")
    for key, md in d.items():
        for m, kv in md.items():
            print(f"  {key:>12} {m:<8} " + "  ".join(f"{k}={v[0]}" for k, v in kv.items()))
