import json
from collections import Counter, defaultdict
from itertools import product


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def covers(seg, cid, sel):
    return seg["class"] == cid and ("partition" not in seg or sel.get(seg["partition"]) == seg["group"])


class Instance:
    def __init__(self, raw):
        self.raw = raw
        cal = raw["calendar"]
        self.name = raw["meta"]["name"]
        self.days = cal["days"]
        self.D = len(self.days)
        self.P = cal["periods_per_day"]
        self.labels = cal.get("period_labels", [str(p + 1) for p in range(self.P)])
        self.subj = {s["id"]: s for s in raw["subjects"]}
        self.teachers = {t["id"]: t for t in raw["teachers"]}
        self.classes = {c["id"]: c for c in raw["classes"]}
        self.lessons = {l["id"]: l for l in raw["lessons"]}
        self.rooms = raw["rooms"]
        self.room_count = Counter(r["type"] for r in self.rooms)
        self.w = raw["weights"]
        self.soft = raw["soft"]
        self.unavail = {
            tid: {(u["day"], p) for u in t["unavailable"] for p in u["periods"]}
            for tid, t in self.teachers.items()
        }
        self._build_units()
        self._build_cohorts()

    def _build_units(self):
        in_block = set()
        self.units = []
        for b in self.raw["blocks"]:
            in_block.update(b["lessons"])
            self.units.append({"id": b["id"], "lessons": list(b["lessons"])})
        for lid in self.lessons:
            if lid not in in_block:
                self.units.append({"id": lid, "lessons": [lid]})
        self.unit_of = {}
        hard = self.soft["hard_difficulty"]
        for ui, u in enumerate(self.units):
            L = [self.lessons[x] for x in u["lessons"]]
            for x in u["lessons"]:
                self.unit_of[x] = ui
            u["hours"] = L[0]["hours"]
            u["max_per_day"] = min(l["max_per_day"] for l in L)
            u["teachers"] = sorted({l["teacher"] for l in L})
            u["classes"] = sorted({s["class"] for l in L for s in l["audience"]})
            u["hard"] = any(self.subj[l["subject"]]["difficulty"] >= hard for l in L)
            u["rooms"] = Counter(l["room_type"] for l in L)
        self.units_of_teacher = defaultdict(list)
        self.units_of_class = defaultdict(list)
        for ui, u in enumerate(self.units):
            for t in u["teachers"]:
                self.units_of_teacher[t].append(ui)
            for c in u["classes"]:
                self.units_of_class[c].append(ui)

    def _build_cohorts(self):
        self.cohorts = []
        for cid, c in self.classes.items():
            parts = c["partitions"]
            for combo in product(*[[g["id"] for g in p["groups"]] for p in parts]):
                self.cohorts.append((cid, {p["id"]: g for p, g in zip(parts, combo)}))
        self.units_of_cohort = defaultdict(list)
        for ki, (cid, sel) in enumerate(self.cohorts):
            for ui, u in enumerate(self.units):
                if any(covers(s, cid, sel) for x in u["lessons"] for s in self.lessons[x]["audience"]):
                    self.units_of_cohort[ki].append(ui)

    def seg_size(self, seg):
        c = self.classes[seg["class"]]
        if "partition" not in seg:
            return c["size"]
        part = next(p for p in c["partitions"] if p["id"] == seg["partition"])
        return next(g["size"] for g in part["groups"] if g["id"] == seg["group"])

    def lesson_size(self, lid):
        return sum(self.seg_size(s) for s in self.lessons[lid]["audience"])


def day_gaps(busy):
    idx = [p for p, b in enumerate(busy) if b]
    return (idx[-1] - idx[0] + 1 - len(idx)) if idx else 0


def evaluate(inst, sched):
    D, P = inst.D, inst.P
    occ = {(ui, d, p): 1 for ui, slots in sched.items() for d, p in slots}
    o = lambda ui, d, p: occ.get((ui, d, p), 0)
    hard = Counter()

    for ui, u in enumerate(inst.units):
        s = sched.get(ui, [])
        if len(set(s)) != u["hours"]:
            hard["hours"] += abs(len(set(s)) - u["hours"])
        for d in range(D):
            hard["unit_per_day"] += max(0, sum(o(ui, d, p) for p in range(P)) - u["max_per_day"])
        for d, p in s:
            hard["unavailable"] += sum((d, p) in inst.unavail[t] for t in u["teachers"])

    for t, us in inst.units_of_teacher.items():
        mpd = inst.teachers[t]["max_per_day"]
        for d in range(D):
            load = 0
            for p in range(P):
                n = sum(o(ui, d, p) for ui in us)
                hard["teacher_clash"] += max(0, n - 1)
                load += n
            hard["teacher_per_day"] += max(0, load - mpd)

    for ki, us in inst.units_of_cohort.items():
        cmax = inst.classes[inst.cohorts[ki][0]].get("max_per_day", P)
        for d in range(D):
            load = 0
            for p in range(P):
                n = sum(o(ui, d, p) for ui in us)
                hard["student_clash"] += max(0, n - 1)
                load += n
            hard["class_per_day"] += max(0, load - cmax)

    for rt, n in inst.room_count.items():
        for d in range(D):
            for p in range(P):
                need = sum(u["rooms"][rt] * o(ui, d, p) for ui, u in enumerate(inst.units))
                hard["rooms"] += max(0, need - n)

    soft = Counter()
    for ki, us in inst.units_of_cohort.items():
        for d in range(D):
            soft["student_gap"] += day_gaps([sum(o(ui, d, p) for ui in us) for p in range(P)])
    for t, us in inst.units_of_teacher.items():
        for d in range(D):
            soft["teacher_gap"] += day_gaps([sum(o(ui, d, p) for ui in us) for p in range(P)])
    for ui, u in enumerate(inst.units):
        for d in range(D):
            soft["same_subject_same_day"] += max(0, sum(o(ui, d, p) for p in range(P)) - 1)
    for c, us in inst.units_of_class.items():
        loads = [sum(o(ui, d, p) for ui in us for p in range(P)) for d in range(D)]
        soft["day_imbalance"] += max(loads) - min(loads)
    late = inst.soft["late_period_from"]
    for ui, u in enumerate(inst.units):
        if u["hard"]:
            soft["hard_subject_late"] += sum(o(ui, d, p) for d in range(D) for p in range(late, P))

    total = sum(inst.w[k] * soft[k] for k in inst.w)
    return {
        "hard_violations": sum(hard.values()),
        "hard": {k: v for k, v in hard.items() if v},
        "soft": {k: soft[k] for k in inst.w},
        "penalty": total,
    }


def assign_rooms(inst, sched):
    by_slot = defaultdict(list)
    for ui, slots in sched.items():
        for d, p in slots:
            for lid in inst.units[ui]["lessons"]:
                by_slot[(d, p)].append(lid)
    out = []
    for (d, p), lids in sorted(by_slot.items()):
        free = sorted(inst.rooms, key=lambda r: r["capacity"])
        for lid in sorted(lids, key=inst.lesson_size, reverse=True):
            l = inst.lessons[lid]
            size = inst.lesson_size(lid)
            room = next((r for r in free if r["type"] == l["room_type"] and r["capacity"] >= size), None)
            if room:
                free.remove(room)
            out.append({"lesson": lid, "subject": l["subject"], "teacher": l["teacher"],
                        "day": d, "period": p, "room": room["id"] if room else None})
    return out


def _label(inst, e, cid):
    l = inst.lessons[e["lesson"]]
    segs = [s for s in l["audience"] if s["class"] == cid]
    grp = segs[0].get("group") if segs and "group" in segs[0] else None
    return f"{l['subject']}({grp})" if grp else l["subject"]


def print_class_tables(inst, entries):
    w = 20
    for cid in inst.classes:
        print(f"\n== {cid} ==")
        print(" " * 7 + "".join(d.ljust(w) for d in inst.days))
        for p in range(inst.P):
            row = []
            for d in range(inst.D):
                cell = [_label(inst, e, cid) for e in entries
                        if e["day"] == d and e["period"] == p
                        and any(s["class"] == cid for s in inst.lessons[e["lesson"]]["audience"])]
                row.append("/".join(cell)[: w - 1].ljust(w) if cell else "-".ljust(w))
            print(inst.labels[p].ljust(7) + "".join(row))


def print_teacher_tables(inst, entries):
    w = 10
    for t in inst.teachers:
        mine = [e for e in entries if e["teacher"] == t]
        if not mine:
            continue
        print(f"\n== {t} ==")
        print(" " * 7 + "".join(d.ljust(w) for d in inst.days))
        for p in range(inst.P):
            row = []
            for d in range(inst.D):
                e = next((e for e in mine if e["day"] == d and e["period"] == p), None)
                row.append(((e["lesson"].split("-")[0] + " " + (e["room"] or "?"))[: w - 1] if e else "-").ljust(w))
            print(inst.labels[p].ljust(7) + "".join(row))


def print_metrics(m):
    print(f"\nhard violations: {m['hard_violations']} {m['hard'] or ''}")
    for k, v in m["soft"].items():
        print(f"  {k:<22}{v}")
    print(f"penalty: {m['penalty']}")


def save_solution(path, inst, solver, info, metrics, entries):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"instance": inst.name, "solver": solver, **info, "metrics": metrics, "entries": entries},
                  f, ensure_ascii=False, indent=1)
