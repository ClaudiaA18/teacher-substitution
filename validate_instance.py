import json
import sys
from collections import Counter, defaultdict
from itertools import combinations


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seg_size(seg, classes):
    c = classes[seg["class"]]
    if "partition" not in seg:
        return c["size"]
    part = next(p for p in c["partitions"] if p["id"] == seg["partition"])
    return next(g["size"] for g in part["groups"] if g["id"] == seg["group"])


def segs_compatible(a, b):
    if a["class"] != b["class"]:
        return True
    if "partition" not in a or "partition" not in b:
        return False
    return a["partition"] == b["partition"] and a["group"] != b["group"]


def validate(inst):
    err, warn = [], []
    D = len(inst["calendar"]["days"])
    P = inst["calendar"]["periods_per_day"]
    slots = D * P

    subjects = {s["id"] for s in inst["subjects"]}
    rtypes = set(inst["room_types"])
    rooms = inst["rooms"]
    teachers = {t["id"]: t for t in inst["teachers"]}
    classes = {c["id"]: c for c in inst["classes"]}
    lessons = {l["id"]: l for l in inst["lessons"]}

    for r in rooms:
        if r["type"] not in rtypes:
            err.append(f"room {r['id']}: unknown type {r['type']}")

    for cid, c in classes.items():
        for p in c["partitions"]:
            s = sum(g["size"] for g in p["groups"])
            if s != c["size"]:
                warn.append(f"class {cid} partition {p['id']}: group sizes sum {s} != class size {c['size']}")

    valid_segs = {}
    for cid, c in classes.items():
        for p in c["partitions"]:
            for g in p["groups"]:
                valid_segs[(cid, p["id"], g["id"])] = True

    for lid, l in lessons.items():
        if l["subject"] not in subjects:
            err.append(f"lesson {lid}: unknown subject {l['subject']}")
        if l["teacher"] not in teachers:
            err.append(f"lesson {lid}: unknown teacher {l['teacher']}")
        if l["room_type"] not in rtypes:
            err.append(f"lesson {lid}: unknown room_type {l['room_type']}")
        if l["max_per_day"] * D < l["hours"]:
            err.append(f"lesson {lid}: hours {l['hours']} > max_per_day*days")
        for s in l["audience"]:
            if s["class"] not in classes:
                err.append(f"lesson {lid}: unknown class {s['class']}")
            elif "partition" in s and (s["class"], s["partition"], s["group"]) not in valid_segs:
                err.append(f"lesson {lid}: unknown group {s}")
        for a, b in combinations(l["audience"], 2):
            if not segs_compatible(a, b):
                err.append(f"lesson {lid}: overlapping audience segments {a} / {b}")
        if not err:
            size = sum(seg_size(s, classes) for s in l["audience"])
            if not any(r["type"] == l["room_type"] and r["capacity"] >= size for r in rooms):
                err.append(f"lesson {lid}: no {l['room_type']} room with capacity >= {size}")
    if err:
        return err, warn

    in_block = {}
    for b in inst["blocks"]:
        ls = [lessons[x] for x in b["lessons"] if x in lessons]
        if len(ls) != len(b["lessons"]):
            err.append(f"block {b['id']}: unknown lesson id")
            continue
        for x in b["lessons"]:
            if x in in_block:
                err.append(f"lesson {x} in blocks {in_block[x]} and {b['id']}")
            in_block[x] = b["id"]
        if len({l["hours"] for l in ls}) > 1:
            err.append(f"block {b['id']}: unequal hours {[l['hours'] for l in ls]}")
        tc = Counter(l["teacher"] for l in ls)
        for t, n in tc.items():
            if n > 1:
                err.append(f"block {b['id']}: teacher {t} appears {n} times")
        for la, lb in combinations(ls, 2):
            if any(not segs_compatible(a, c) for a in la["audience"] for c in lb["audience"]):
                err.append(f"block {b['id']}: student overlap between {la['id']} and {lb['id']}")
        need = Counter(l["room_type"] for l in ls)
        have = Counter(r["type"] for r in rooms)
        for rt, n in need.items():
            if n > have[rt]:
                err.append(f"block {b['id']}: needs {n} rooms of type {rt}, has {have[rt]}")

    load_cls = Counter()
    for cid in classes:
        units = set()
        h = 0
        for l in lessons.values():
            if not any(s["class"] == cid for s in l["audience"]):
                continue
            key = in_block.get(l["id"], l["id"])
            if key in units:
                continue
            units.add(key)
            h += l["hours"]
        load_cls[cid] = h
        if h > slots:
            err.append(f"class {cid}: load {h} > {slots} slots")

    tload = Counter()
    for l in lessons.values():
        tload[l["teacher"]] += l["hours"]
    for tid, t in teachers.items():
        unav = sum(len(u["periods"]) for u in t["unavailable"])
        avail = slots - unav
        if tload[tid] > avail:
            err.append(f"teacher {tid}: load {tload[tid]} > available {avail}")
        days_av = sum(1 for d in range(D) if not any(u["day"] == d and len(u["periods"]) == P for u in t["unavailable"]))
        if tload[tid] > days_av * t["max_per_day"]:
            err.append(f"teacher {tid}: load exceeds max_per_day * available days")

    partial = defaultdict(set)
    for l in lessons.values():
        if l["id"] in in_block:
            continue
        for s in l["audience"]:
            if "partition" in s:
                partial[(s["class"], s["partition"])].add(l["id"])
    for (cid, p), ids in partial.items():
        warn.append(f"class {cid} partition {p}: group lessons outside blocks {sorted(ids)} -> possible student gaps")

    for f in inst.get("fixed", []):
        if f["lesson"] not in lessons or not (0 <= f["day"] < D and 0 <= f["period"] < P):
            err.append(f"fixed: invalid entry {f}")

    stats = {
        "days x periods": f"{D} x {P}",
        "classes": len(classes), "teachers": len(teachers), "rooms": len(rooms),
        "lessons": len(lessons), "lesson-hours": sum(l["hours"] for l in lessons.values()),
        "blocks": len(inst["blocks"]),
        "class load": dict(load_cls), "teacher load": dict(sorted(tload.items())),
    }
    return err, warn, stats


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "ro_toy.json"
    res = validate(load(path))
    err, warn = res[0], res[1]
    for w in warn:
        print("WARN ", w)
    for e in err:
        print("ERROR", e)
    if len(res) == 3:
        for k, v in res[2].items():
            print(f"{k}: {v}")
    print("OK" if not err else f"{len(err)} error(s)")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
