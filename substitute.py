import json
import time
from collections import defaultdict

from ortools.sat.python import cp_model

DEFAULT_WEIGHTS = {
    "same_subject": 3.0, "related": 1.5, "teaches_class": 1.0, "in_school": 2.0,
    "adjacent": 0.5, "fills_gap": 0.5, "extends_day": -0.5, "day_load": -0.2, "cum_subs": -0.3,
}
UNCOVERED = 1000


def day_gaps(periods):
    if not periods:
        return 0
    return max(periods) - min(periods) + 1 - len(periods)


class Context:
    def __init__(self, inst, entries):
        self.inst = inst
        self.busy = defaultdict(set)
        self.by_day = defaultdict(list)
        self.classes_of = defaultdict(set)
        for e in entries:
            self.busy[(e["teacher"], e["day"])].add(e["period"])
            self.by_day[e["day"]].append(e)
        for l in inst.lessons.values():
            for s in l["audience"]:
                self.classes_of[l["teacher"]].add(s["class"])
        self.subj, self.rel = {}, {}
        for tid, t in inst.teachers.items():
            own = {l["subject"] for l in inst.lessons.values() if l["teacher"] == tid}
            self.subj[tid] = set(t.get("subjects", own)) | own
            self.rel[tid] = set(t.get("related", []))
        self.max_subs = inst.raw.get("substitution", {}).get("max_subs_per_day", 2)

    def tasks(self, d, absent):
        A = set(absent)
        out = []
        for e in self.by_day[d]:
            if e["teacher"] in A:
                l = self.inst.lessons[e["lesson"]]
                out.append({"lesson": e["lesson"], "subject": l["subject"], "period": e["period"],
                            "classes": {s["class"] for s in l["audience"]}, "absent": e["teacher"]})
        return sorted(out, key=lambda x: x["period"])

    def features(self, task, t, d, cum):
        own = self.busy[(t, d)]
        p = task["period"]
        f = {
            "same_subject": float(task["subject"] in self.subj[t]),
            "related": float(task["subject"] not in self.subj[t] and task["subject"] in self.rel[t]),
            "teaches_class": float(bool(task["classes"] & self.classes_of[t])),
            "in_school": float(bool(own)),
            "adjacent": float((p - 1) in own or (p + 1) in own),
            "fills_gap": float(bool(own) and min(own) < p < max(own)),
            "extends_day": float(bool(own) and (p < min(own) or p > max(own))),
            "day_load": float(len(own)),
            "cum_subs": float(cum.get(t, 0)),
        }
        return f

    def candidates(self, task, d, absent, cum, weights):
        A = set(absent)
        p = task["period"]
        out = []
        for t, tt in self.inst.teachers.items():
            if t in A or p in self.busy[(t, d)] or (d, p) in self.inst.unavail[t]:
                continue
            f = self.features(task, t, d, cum)
            out.append((t, sum(weights.get(k, 0) * v for k, v in f.items()), f))
        return out

    def cap(self, t, d):
        return min(self.max_subs, self.inst.teachers[t]["max_per_day"] - len(self.busy[(t, d)]))


def solve_greedy(ctx, d, tasks, cands):
    used, load, assign = set(), defaultdict(int), {}
    order = sorted(range(len(tasks)), key=lambda i: (tasks[i]["period"], len(cands[i])))
    for i in order:
        p = tasks[i]["period"]
        best = None
        for t, s, _ in cands[i]:
            if (t, p) in used or load[t] >= ctx.cap(t, d):
                continue
            if best is None or s > best[1]:
                best = (t, s)
        if best:
            assign[i] = best[0]
            used.add((best[0], p))
            load[best[0]] += 1
    return assign


def solve_hungarian(ctx, d, tasks, cands):
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    load, assign = defaultdict(int), {}
    for p in sorted({t["period"] for t in tasks}):
        rows = [i for i, t in enumerate(tasks) if t["period"] == p]
        cols = sorted({t for i in rows for t, _, _ in cands[i] if load[t] < ctx.cap(t, d)})
        if not cols:
            continue
        n = len(rows)
        M = np.full((n, len(cols) + n), float(UNCOVERED))
        for r, i in enumerate(rows):
            for t, s, _ in cands[i]:
                if t in cols:
                    M[r, cols.index(t)] = -s
        ri, ci = linear_sum_assignment(M)
        for r, c in zip(ri, ci):
            if c < len(cols):
                t = cols[c]
                assign[rows[r]] = t
                load[t] += 1
    return assign


def solve_cpsat(ctx, d, tasks, cands, cum, fair_w=1.0, time_limit=10):
    m = cp_model.CpModel()
    y = {}
    for i, cs in enumerate(cands):
        for t, s, _ in cs:
            y[i, t] = m.new_bool_var("")
    for i in range(len(tasks)):
        m.add(sum(y[i, t] for t, _, _ in cands[i]) <= 1)
    by_tp, by_t = defaultdict(list), defaultdict(list)
    for (i, t), v in y.items():
        by_tp[(t, tasks[i]["period"])].append(v)
        by_t[t].append(v)
    for vs in by_tp.values():
        m.add(sum(vs) <= 1)
    for t, vs in by_t.items():
        m.add(sum(vs) <= max(0, ctx.cap(t, d)))
    top = max(list(cum.values()) + [0]) + ctx.max_subs
    mx = m.new_int_var(0, top, "mx")
    for t, vs in by_t.items():
        m.add(mx >= cum.get(t, 0) + sum(vs))
    covered = sum(y.values()) if y else 0
    score = sum(int(round(100 * s)) * y[i, t] for i, cs in enumerate(cands) for t, s, _ in cs)
    m.maximize(UNCOVERED * 100 * covered + score - int(round(fair_w * 100)) * mx)
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = time_limit
    sv.parameters.num_workers = 1
    sv.solve(m)
    return {i: t for (i, t), v in y.items() if sv.value(v)}


METHODS = {"greedy": solve_greedy, "hungarian": solve_hungarian, "cpsat": solve_cpsat}


def run_day(ctx, method, d, absent, cum, weights, fair=1.0):
    tasks = ctx.tasks(d, absent)
    cands = [ctx.candidates(t, d, absent, cum, weights) for t in tasks]
    t0 = time.perf_counter()
    if method == "cpsat":
        assign = solve_cpsat(ctx, d, tasks, cands, cum, fair_w=fair)
    else:
        assign = METHODS[method](ctx, d, tasks, cands)
    dt = time.perf_counter() - t0
    feat = {(i, t): f for i, cs in enumerate(cands) for t, _, f in cs}
    sc = {(i, t): s for i, cs in enumerate(cands) for t, s, _ in cs}
    extra = defaultdict(set)
    for i, t in assign.items():
        extra[t].add(tasks[i]["period"])
    gap_delta = sum(day_gaps(ctx.busy[(t, d)] | ps) - day_gaps(ctx.busy[(t, d)]) for t, ps in extra.items())
    res = {
        "tasks": len(tasks), "covered": len(assign),
        "same_subject": sum(feat[i, t]["same_subject"] for i, t in assign.items()),
        "related": sum(feat[i, t]["related"] for i, t in assign.items()),
        "trips": sum(1 for t in extra if not ctx.busy[(t, d)]),
        "gap_delta": gap_delta, "score": sum(sc[i, t] for i, t in assign.items()),
        "time_ms": 1000 * dt,
    }
    res["supervision"] = res["covered"] - res["same_subject"] - res["related"]
    plan = [{"lesson": tasks[i]["lesson"], "period": tasks[i]["period"], "absent": tasks[i]["absent"],
             "substitute": t} for i, t in sorted(assign.items())]
    return res, plan, extra


def load_solution(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["entries"]
