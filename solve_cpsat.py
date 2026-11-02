import argparse
import time

from ortools.sat.python import cp_model

from tt_core import (Instance, load, evaluate, assign_rooms, print_class_tables,
                     print_teacher_tables, print_metrics, save_solution)


def gap_count(m, busy_exprs, P):
    b = []
    for e in busy_exprs:
        v = m.new_bool_var("")
        m.add(v == e)
        b.append(v)
    before = [m.new_constant(0)]
    for p in range(1, P):
        v = m.new_bool_var("")
        m.add_max_equality(v, [before[-1], b[p - 1]])
        before.append(v)
    after = [None] * P
    after[P - 1] = m.new_constant(0)
    for p in range(P - 2, -1, -1):
        v = m.new_bool_var("")
        m.add_max_equality(v, [after[p + 1], b[p + 1]])
        after[p] = v
    gaps = []
    for p in range(1, P - 1):
        g = m.new_bool_var("")
        m.add(g >= before[p] + after[p] - b[p] - 1)
        gaps.append(g)
    return sum(gaps)


def build(inst):
    m = cp_model.CpModel()
    D, P, U = inst.D, inst.P, inst.units
    rng = [(d, p) for d in range(D) for p in range(P)]
    x = {(ui, d, p): m.new_bool_var(f"x_{ui}_{d}_{p}") for ui in range(len(U)) for d, p in rng}

    for ui, u in enumerate(U):
        m.add(sum(x[ui, d, p] for d, p in rng) == u["hours"])
        for d in range(D):
            m.add(sum(x[ui, d, p] for p in range(P)) <= u["max_per_day"])
        for d, p in rng:
            if any((d, p) in inst.unavail[t] for t in u["teachers"]):
                m.add(x[ui, d, p] == 0)

    for f in inst.raw.get("fixed", []):
        m.add(x[inst.unit_of[f["lesson"]], f["day"], f["period"]] == 1)

    for t, us in inst.units_of_teacher.items():
        for d in range(D):
            for p in range(P):
                m.add(sum(x[ui, d, p] for ui in us) <= 1)
            m.add(sum(x[ui, d, p] for ui in us for p in range(P)) <= inst.teachers[t]["max_per_day"])

    for ki, us in inst.units_of_cohort.items():
        cid = inst.cohorts[ki][0]
        cmax = inst.classes[cid].get("max_per_day", P)
        for d in range(D):
            for p in range(P):
                m.add(sum(x[ui, d, p] for ui in us) <= 1)
            m.add(sum(x[ui, d, p] for ui in us for p in range(P)) <= cmax)

    for rt, n in inst.room_count.items():
        users = [ui for ui, u in enumerate(U) if u["rooms"][rt]]
        for d, p in rng:
            m.add(sum(U[ui]["rooms"][rt] * x[ui, d, p] for ui in users) <= n)

    terms = {k: [] for k in inst.w}
    for ki, us in inst.units_of_cohort.items():
        for d in range(D):
            terms["student_gap"].append(gap_count(m, [sum(x[ui, d, p] for ui in us) for p in range(P)], P))
    for t, us in inst.units_of_teacher.items():
        for d in range(D):
            terms["teacher_gap"].append(gap_count(m, [sum(x[ui, d, p] for ui in us) for p in range(P)], P))
    for ui, u in enumerate(U):
        if u["max_per_day"] > 1:
            for d in range(D):
                e = m.new_int_var(0, u["max_per_day"] - 1, "")
                m.add(e >= sum(x[ui, d, p] for p in range(P)) - 1)
                terms["same_subject_same_day"].append(e)
    for c, us in inst.units_of_class.items():
        hi, lo = m.new_int_var(0, P * len(us), ""), m.new_int_var(0, P * len(us), "")
        for d in range(D):
            load = sum(x[ui, d, p] for ui in us for p in range(P))
            m.add(hi >= load)
            m.add(lo <= load)
        terms["day_imbalance"].append(hi - lo)
    late = inst.soft["late_period_from"]
    terms["hard_subject_late"] = [x[ui, d, p] for ui, u in enumerate(U) if u["hard"]
                                  for d in range(D) for p in range(late, P)]

    m.minimize(sum(inst.w[k] * sum(v) for k, v in terms.items()))
    return m, x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--time", type=float, default=60)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="solution_cpsat.json")
    ap.add_argument("--teachers", action="store_true")
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()

    inst = Instance(load(a.instance))
    t0 = time.time()
    m, x = build(inst)
    build_s = time.time() - t0

    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = a.time
    s.parameters.num_workers = a.workers
    s.parameters.random_seed = a.seed
    s.parameters.log_search_progress = a.log
    st = s.solve(m)
    status = s.status_name(st)

    print(f"instance: {inst.name}  units: {len(inst.units)}  cohorts: {len(inst.cohorts)}  "
          f"vars: {len(m.proto.variables)}  constraints: {len(m.proto.constraints)}")
    print(f"status: {status}  build: {build_s:.2f}s  solve: {s.wall_time:.2f}s")
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return

    sched = {}
    for (ui, d, p), v in x.items():
        if s.value(v):
            sched.setdefault(ui, []).append((d, p))
    metrics = evaluate(inst, sched)
    print(f"objective: {s.objective_value:.0f}  bound: {s.best_objective_bound:.0f}")
    print_metrics(metrics)
    if abs(metrics["penalty"] - s.objective_value) > 1e-6:
        print("WARNING: evaluator penalty != solver objective")

    entries = assign_rooms(inst, sched)
    if any(e["room"] is None for e in entries):
        print("WARNING: some lessons have no room")
    print_class_tables(inst, entries)
    if a.teachers:
        print_teacher_tables(inst, entries)

    info = {"status": status, "time_s": round(s.wall_time, 2), "objective": s.objective_value,
            "bound": s.best_objective_bound, "seed": a.seed, "time_limit": a.time}
    save_solution(a.out, inst, "cp-sat", info, metrics, entries)
    print(f"\nsaved: {a.out}")


if __name__ == "__main__":
    main()
