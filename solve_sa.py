import argparse
import json
import math
import random
import time

from tt_core import (Instance, load, evaluate, assign_rooms, print_class_tables,
                     print_teacher_tables, print_metrics, save_solution)


def day_gaps(row):
    first = last = -1
    busy = 0
    for p, a in enumerate(row):
        if a:
            busy += 1
            if first < 0:
                first = p
            last = p
    return last - first + 1 - busy if busy else 0


class State:
    def __init__(self, inst, hw):
        self.inst, self.hw = inst, hw
        D, P = inst.D, inst.P
        self.D, self.P = D, P
        self.w = inst.w
        self.late = inst.soft["late_period_from"]
        nu = len(inst.units)
        self.T = {t: [[0] * P for _ in range(D)] for t in inst.teachers}
        self.K = [[[0] * P for _ in range(D)] for _ in inst.cohorts]
        self.R = {rt: [[0] * P for _ in range(D)] for rt in inst.room_count}
        self.U = [[0] * D for _ in range(nu)]
        self.CL = {c: [0] * D for c in inst.classes}
        self.slots = [[] for _ in range(nu)]
        self.occ = [set() for _ in range(nu)]
        self.coh = [[] for _ in range(nu)]
        for ki, us in inst.units_of_cohort.items():
            for ui in us:
                self.coh[ui].append(ki)
        self.cmax = [inst.classes[c].get("max_per_day", P) for c, _ in inst.cohorts]
        self.allowed = []
        for u in inst.units:
            a = [(d, p) for d in range(D) for p in range(P)
                 if not any((d, p) in inst.unavail[t] for t in u["teachers"])]
            self.allowed.append(a)
        self.allowed_set = [set(a) for a in self.allowed]

    def place(self, ui, d, p, s):
        u = self.inst.units[ui]
        for t in u["teachers"]:
            self.T[t][d][p] += s
        for k in self.coh[ui]:
            self.K[k][d][p] += s
        for rt, n in u["rooms"].items():
            self.R[rt][d][p] += s * n
        self.U[ui][d] += s
        for c in u["classes"]:
            self.CL[c][d] += s

    def add(self, ui, d, p):
        self.place(ui, d, p, 1)
        self.slots[ui].append((d, p))
        self.occ[ui].add((d, p))

    def keys(self, ui, days):
        u = self.inst.units[ui]
        ks = set()
        for d in days:
            for t in u["teachers"]:
                ks.add(("T", t, d))
            for k in self.coh[ui]:
                ks.add(("K", k, d))
            for rt in u["rooms"]:
                ks.add(("R", rt, d))
            ks.add(("U", ui, d))
        for c in u["classes"]:
            ks.add(("C", c))
        if u["hard"]:
            ks.add(("L", ui))
        return ks

    def contrib(self, key):
        kind = key[0]
        w = self.w
        if kind == "T":
            row = self.T[key[1]][key[2]]
            h = sum(a - 1 for a in row if a > 1)
            h += max(0, sum(row) - self.inst.teachers[key[1]]["max_per_day"])
            return h, w["teacher_gap"] * day_gaps(row)
        if kind == "K":
            row = self.K[key[1]][key[2]]
            h = sum(a - 1 for a in row if a > 1) + max(0, sum(row) - self.cmax[key[1]])
            return h, w["student_gap"] * day_gaps(row)
        if kind == "R":
            n = self.inst.room_count[key[1]]
            return sum(a - n for a in self.R[key[1]][key[2]] if a > n), 0
        if kind == "U":
            c = self.U[key[1]][key[2]]
            return max(0, c - self.inst.units[key[1]]["max_per_day"]), w["same_subject_same_day"] * max(0, c - 1)
        if kind == "C":
            L = self.CL[key[1]]
            return 0, w["day_imbalance"] * (max(L) - min(L))
        return 0, w["hard_subject_late"] * sum(1 for d, p in self.slots[key[1]] if p >= self.late)

    def cost_of(self, ks):
        h = s = 0
        for k in ks:
            a, b = self.contrib(k)
            h += a
            s += b
        return h, s

    def all_keys(self):
        ks = set()
        for ui in range(len(self.inst.units)):
            ks |= self.keys(ui, range(self.D))
        return ks

    def total(self):
        return self.cost_of(self.all_keys())


def greedy_init(st, rnd, fixed):
    inst = st.inst
    for ui, (d, p) in fixed:
        st.add(ui, d, p)
    order = sorted(range(len(inst.units)),
                   key=lambda ui: (-len(inst.units[ui]["lessons"]) - len(st.coh[ui]), len(st.allowed[ui]),
                                   -inst.units[ui]["hours"], rnd.random()))
    for ui in order:
        while len(st.slots[ui]) < inst.units[ui]["hours"]:
            best, bv = None, None
            for d, p in st.allowed[ui]:
                if (d, p) in st.occ[ui]:
                    continue
                ks = st.keys(ui, [d])
                h0, s0 = st.cost_of(ks)
                st.place(ui, d, p, 1)
                st.slots[ui].append((d, p))
                h1, s1 = st.cost_of(ks)
                st.slots[ui].pop()
                st.place(ui, d, p, -1)
                v = st.hw * (h1 - h0) + (s1 - s0) + rnd.random() * 1e-3
                if bv is None or v < bv:
                    best, bv = (d, p), v
            st.add(ui, *best)


def init_from_file(st, path):
    with open(path, encoding="utf-8") as f:
        sol = json.load(f)
    seen = set()
    for e in sol["entries"]:
        ui = st.inst.unit_of[e["lesson"]]
        if (ui, e["day"], e["period"]) not in seen:
            seen.add((ui, e["day"], e["period"]))
            st.add(ui, e["day"], e["period"])


def anneal(st, rnd, fixed, limit, t0, tend, p_swap, log_every):
    inst = st.inst
    fixed_set = set(fixed)
    movable = [(ui, i) for ui, s in enumerate(st.slots) for i, sl in enumerate(s) if (ui, sl) not in fixed_set]
    h, s = st.total()
    cur = st.hw * h + s
    best = (h, s)
    best_slots = [list(x) for x in st.slots]
    hist = [(0.0, h, s)]
    t_start = time.time()
    it = acc = 0
    temp = t0
    ratio = tend / t0
    next_log = log_every

    def try_apply(ks, apply, revert):
        nonlocal cur, acc
        h0, s0 = st.cost_of(ks)
        apply()
        h1, s1 = st.cost_of(ks)
        dlt = st.hw * (h1 - h0) + (s1 - s0)
        if dlt <= 0 or rnd.random() < math.exp(-dlt / temp):
            cur += dlt
            acc += 1
            return True
        revert()
        return False

    while True:
        it += 1
        if it & 255 == 0:
            el = time.time() - t_start
            if el >= limit:
                break
            temp = t0 * ratio ** (el / limit)
            if log_every and el >= next_log:
                print(f"  t={el:6.1f}s  iter={it:>9}  T={temp:8.3f}  cur={cur:>8}  best=({best[0]},{best[1]})")
                next_log += log_every
        if len(movable) > 1 and rnd.random() < p_swap:
            (ua, ia), (ub, ib) = rnd.sample(movable, 2)
            if ua == ub:
                continue
            sa, sb = st.slots[ua][ia], st.slots[ub][ib]
            if sa == sb or sb not in st.allowed_set[ua] or sa not in st.allowed_set[ub]:
                continue
            if sb in st.occ[ua] or sa in st.occ[ub]:
                continue
            ks = st.keys(ua, {sa[0], sb[0]}) | st.keys(ub, {sa[0], sb[0]})

            def do(a=ua, i=ia, b=ub, j=ib, x=sa, y=sb):
                st.place(a, *x, -1); st.place(b, *y, -1)
                st.place(a, *y, 1); st.place(b, *x, 1)
                st.slots[a][i], st.slots[b][j] = y, x
                st.occ[a].discard(x); st.occ[a].add(y)
                st.occ[b].discard(y); st.occ[b].add(x)

            def undo(a=ua, i=ia, b=ub, j=ib, x=sa, y=sb):
                st.place(a, *y, -1); st.place(b, *x, -1)
                st.place(a, *x, 1); st.place(b, *y, 1)
                st.slots[a][i], st.slots[b][j] = x, y
                st.occ[a].discard(y); st.occ[a].add(x)
                st.occ[b].discard(x); st.occ[b].add(y)

            moved = try_apply(ks, do, undo)
        else:
            ui, i = rnd.choice(movable)
            x = st.slots[ui][i]
            y = rnd.choice(st.allowed[ui])
            if y in st.occ[ui]:
                continue
            ks = st.keys(ui, {x[0], y[0]})

            def do(a=ui, i=i, x=x, y=y):
                st.place(a, *x, -1); st.place(a, *y, 1)
                st.slots[a][i] = y
                st.occ[a].discard(x); st.occ[a].add(y)

            def undo(a=ui, i=i, x=x, y=y):
                st.place(a, *y, -1); st.place(a, *x, 1)
                st.slots[a][i] = x
                st.occ[a].discard(y); st.occ[a].add(x)

            moved = try_apply(ks, do, undo)
        if moved:
            if cur < st.hw * best[0] + best[1]:
                best = st.total()
                best_slots = [list(x) for x in st.slots]
                hist.append((round(time.time() - t_start, 3), best[0], best[1]))
    return best, best_slots, hist, it, acc


def estimate_t0(st, rnd, samples=2000):
    deltas = []
    for _ in range(samples):
        ui = rnd.randrange(len(st.slots))
        if not st.slots[ui]:
            continue
        i = rnd.randrange(len(st.slots[ui]))
        x, y = st.slots[ui][i], rnd.choice(st.allowed[ui])
        if y in st.occ[ui]:
            continue
        ks = st.keys(ui, {x[0], y[0]})
        h0, s0 = st.cost_of(ks)
        st.place(ui, *x, -1); st.place(ui, *y, 1); st.slots[ui][i] = y
        h1, s1 = st.cost_of(ks)
        st.place(ui, *y, -1); st.place(ui, *x, 1); st.slots[ui][i] = x
        if h1 == h0 and s1 > s0:
            deltas.append(s1 - s0)
    return (sum(deltas) / len(deltas)) / math.log(2) if deltas else 10.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--time", type=float, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--hw", type=int, default=1000)
    ap.add_argument("--t0", type=float, default=None)
    ap.add_argument("--tend", type=float, default=0.05)
    ap.add_argument("--swap", type=float, default=0.5)
    ap.add_argument("--init", default=None)
    ap.add_argument("--out", default="solution_sa.json")
    ap.add_argument("--teachers", action="store_true")
    ap.add_argument("--log", type=float, default=0)
    a = ap.parse_args()

    rnd = random.Random(a.seed)
    inst = Instance(load(a.instance))
    st = State(inst, a.hw)
    fixed = [(inst.unit_of[f["lesson"]], (f["day"], f["period"])) for f in inst.raw.get("fixed", [])]

    t0c = time.time()
    if a.init:
        init_from_file(st, a.init)
        method = "cp-sat+sa"
    else:
        greedy_init(st, rnd, fixed)
        method = "sa"
    init_s = time.time() - t0c
    h0, s0 = st.total()
    t0 = a.t0 if a.t0 else estimate_t0(st, rnd)

    print(f"instance: {inst.name}  units: {len(inst.units)}  cohorts: {len(inst.cohorts)}  method: {method}")
    print(f"init: hard={h0} soft={s0}  ({init_s:.2f}s)   T0={t0:.2f}  Tend={a.tend}")

    best, slots, hist, it, acc = anneal(st, rnd, fixed, a.time, t0, a.tend, a.swap, a.log)
    total_s = init_s + a.time
    print(f"iterations: {it}  accepted: {acc}  best: hard={best[0]} soft={best[1]}")

    sched = {ui: s for ui, s in enumerate(slots)}
    metrics = evaluate(inst, sched)
    print_metrics(metrics)
    if metrics["hard_violations"] != best[0] or metrics["penalty"] != best[1]:
        print("WARNING: evaluator != SA internal cost")

    entries = assign_rooms(inst, sched)
    if any(e["room"] is None for e in entries):
        print("WARNING: some lessons have no room")
    print_class_tables(inst, entries)
    if a.teachers:
        print_teacher_tables(inst, entries)

    tt_best = next((t for t, h, s in hist if (h, s) == best), 0.0)
    info = {"status": "FEASIBLE" if best[0] == 0 else "INFEASIBLE", "time_s": round(total_s, 2),
            "time_to_best_s": tt_best, "objective": best[1], "seed": a.seed, "time_limit": a.time,
            "iterations": it, "accepted": acc, "params": {"hw": a.hw, "t0": t0, "tend": a.tend, "swap": a.swap},
            "init": {"hard": h0, "soft": s0, "from": a.init or "greedy"}, "history": hist}
    save_solution(a.out, inst, method, info, metrics, entries)
    print(f"\nsaved: {a.out}")


if __name__ == "__main__":
    main()
