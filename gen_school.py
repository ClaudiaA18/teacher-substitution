import argparse
import json
import math
import random
from collections import defaultdict

SUBJECTS = {
    "ROM": ("Limba si literatura romana", 2), "MAT": ("Matematica", 3), "ENG": ("Limba engleza", 1),
    "FR": ("Limba franceza", 1), "DE": ("Limba germana", 1), "LAT": ("Limba latina", 1),
    "INFO": ("Informatica", 2), "TIC": ("TIC", 1), "FIZ": ("Fizica", 3), "CHI": ("Chimie", 3),
    "BIO": ("Biologie", 2), "IST": ("Istorie", 1), "GEO": ("Geografie", 1), "SOC": ("Stiinte socio-umane", 1),
    "REL": ("Religie", 1), "EFS": ("Educatie fizica", 1), "ART": ("Educatie artistica", 1),
}
PROFILES = {
    "mate-info": {"ROM": 4, "MAT": 4, "ENG": 2, "L2": 2, "INFO": 4, "TIC": 1, "FIZ": 2, "CHI": 1, "BIO": 1,
                  "IST": 1, "GEO": 1, "SOC": 1, "REL": 1, "EFS": 1, "ART": 1},
    "stiinte": {"ROM": 4, "MAT": 3, "ENG": 2, "L2": 2, "TIC": 1, "FIZ": 2, "CHI": 3, "BIO": 3,
                "IST": 1, "GEO": 1, "SOC": 1, "REL": 1, "EFS": 1, "ART": 1},
    "filologie": {"ROM": 5, "MAT": 2, "ENG": 3, "L2": 3, "LAT": 1, "TIC": 1, "FIZ": 1, "CHI": 1, "BIO": 1,
                  "IST": 3, "GEO": 1, "SOC": 2, "REL": 1, "EFS": 1, "ART": 1},
}
RELATED = {"ROM": ["LAT"], "LAT": ["ROM"], "MAT": ["INFO", "FIZ"], "INFO": ["MAT", "TIC"], "TIC": ["INFO"],
           "FIZ": ["MAT", "CHI"], "CHI": ["BIO", "FIZ"], "BIO": ["CHI", "GEO"], "ENG": ["FR", "DE"],
           "FR": ["ENG"], "DE": ["ENG"], "IST": ["SOC", "GEO"], "GEO": ["IST", "BIO"], "SOC": ["IST"],
           "REL": ["IST", "SOC"], "EFS": [], "ART": []}
POOL = {"TIC": "INFO"}
LAB = {"INFO": "lab_info", "TIC": "lab_info", "EFS": "gym"}
NORM = 18


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-profile", type=int, default=1)
    ap.add_argument("--profiles", default="mate-info,stiinte,filologie")
    ap.add_argument("--periods", type=int, default=7)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default="ro_school.json")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    profiles = a.profiles.split(",")
    grades = ["9", "10", "11", "12"]

    classes, lessons, blocks = [], [], []
    demand = defaultdict(list)
    letters = "ABCDEFGHIJ"
    for g in grades:
        cat_members = []
        for k, prof in enumerate(profiles * a.per_profile):
            cid = f"{g}{letters[k]}"
            size = rnd.randint(25, 30)
            l2a = rnd.randint(size // 2 - 3, size // 2 + 3)
            cat = rnd.randint(2, 4)
            g1 = size // 2
            classes.append({"id": cid, "profile": prof, "size": size, "partitions": [
                {"id": "grp", "groups": [{"id": "G1", "size": g1}, {"id": "G2", "size": size - g1}]},
                {"id": "L2", "groups": [{"id": "FR", "size": l2a}, {"id": "DE", "size": size - l2a}]},
                {"id": "rel", "groups": [{"id": "ORT", "size": size - cat}, {"id": "CAT", "size": cat}]}]})
            cat_members.append(cid)
            for subj, h in PROFILES[prof].items():
                if subj == "L2":
                    ids = []
                    for lang in ("FR", "DE"):
                        lid = f"{cid}-{lang}"
                        lessons.append({"id": lid, "subject": lang, "audience": [{"class": cid, "partition": "L2", "group": lang}],
                                        "hours": h, "room_type": "standard", "max_per_day": 1})
                        demand[lang].append((lid, h, None))
                        ids.append(lid)
                    blocks.append({"id": f"B-{cid}-L2", "lessons": ids})
                elif subj in ("INFO", "TIC"):
                    ids = []
                    for gr in ("G1", "G2"):
                        lid = f"{cid}-{subj}-{gr}"
                        lessons.append({"id": lid, "subject": subj, "audience": [{"class": cid, "partition": "grp", "group": gr}],
                                        "hours": h, "room_type": "lab_info", "max_per_day": 2 if h > 2 else 1})
                        ids.append(lid)
                    demand["INFO"].append((ids, h, "pair"))
                    blocks.append({"id": f"B-{cid}-{subj}", "lessons": ids})
                elif subj == "REL":
                    lid = f"{cid}-REL-ORT"
                    lessons.append({"id": lid, "subject": "REL", "audience": [{"class": cid, "partition": "rel", "group": "ORT"}],
                                    "hours": 1, "room_type": "standard", "max_per_day": 1})
                else:
                    room = LAB.get(subj, "lab_sci" if subj in ("CHI", "BIO") and prof == "stiinte" else "standard")
                    lid = f"{cid}-{subj}"
                    lessons.append({"id": lid, "subject": subj, "audience": [{"class": cid}], "hours": h,
                                    "room_type": room, "max_per_day": 1})
                    demand[subj].append((lid, h, None))
        cat_id = f"{g}-REL-CAT"
        lessons.append({"id": cat_id, "subject": "REL", "audience": [{"class": c, "partition": "rel", "group": "CAT"} for c in cat_members],
                        "hours": 1, "room_type": "standard", "max_per_day": 1})
        rel_ids = [f"{c}-REL-ORT" for c in cat_members] + [cat_id]
        blocks.append({"id": f"B-{g}-REL", "lessons": rel_ids})
        demand["REL"].append((rel_ids, 1, "grade"))

    by_id = {l["id"]: l for l in lessons}
    teachers, tcount = [], 0

    def new_teacher(spec):
        nonlocal tcount
        tcount += 1
        t = {"id": f"T{tcount:02d}", "spec": spec, "load": 0}
        teachers.append(t)
        return t

    for spec, items in sorted(demand.items()):
        total = sum(h * (len(x) if isinstance(x, list) else 1) for x, h, _ in items)
        width = max((len(x) for x, _, _ in items if isinstance(x, list)), default=1)
        n = max(width, math.ceil(total / NORM))
        pool = [new_teacher(spec) for _ in range(n)]
        for x, h, kind in sorted(items, key=lambda it: -it[1]):
            ids = x if isinstance(x, list) else [x]
            chosen = sorted(pool, key=lambda t: (t["load"], rnd.random()))[:len(ids)]
            for lid, t in zip(ids, chosen):
                by_id[lid]["teacher"] = t["id"]
                t["load"] += h

    tlist = []
    for t in teachers:
        own = sorted({l["subject"] for l in lessons if l.get("teacher") == t["id"]})
        rel = sorted({r for s in own for r in RELATED.get(s, []) if r not in own})
        un = []
        if t["load"] <= 10 and rnd.random() < 0.6:
            un = [{"day": rnd.randrange(5), "periods": list(range(a.periods))}]
        tlist.append({"id": t["id"], "max_per_day": a.periods, "unavailable": un, "subjects": own, "related": rel})

    n_cls = len(classes)
    slots = 5 * a.periods
    need = defaultdict(int)
    for l in lessons:
        need[l["room_type"]] += l["hours"]
    cnt = lambda rt, lo: max(lo, math.ceil(need[rt] / (0.6 * slots)))
    rooms = [{"id": f"R{i + 1:02d}", "type": "standard", "capacity": 32} for i in range(n_cls + 2)]
    rooms += [{"id": f"LINF{i + 1}", "type": "lab_info", "capacity": 16} for i in range(cnt("lab_info", 2))]
    rooms += [{"id": f"LSCI{i + 1}", "type": "lab_sci", "capacity": 32} for i in range(cnt("lab_sci", 1))]
    rooms += [{"id": f"GYM{i + 1}", "type": "gym", "capacity": 60} for i in range(cnt("gym", 1))]

    labels = [f"{8 + p:02d}-{9 + p:02d}" for p in range(a.periods)]
    name = a.name or f"RO-school-{n_cls}cls"
    inst = {
        "meta": {"name": name, "description": "Generated Romanian theoretical high school (hours approximate plan-cadru)",
                 "anonymized": True, "format_version": "1.0", "seed": a.seed},
        "calendar": {"days": ["Lu", "Ma", "Mi", "Jo", "Vi"], "periods_per_day": a.periods, "period_labels": labels},
        "subjects": [{"id": k, "name": v[0], "difficulty": v[1]} for k, v in SUBJECTS.items()],
        "room_types": ["standard", "lab_info", "lab_sci", "gym"],
        "rooms": rooms, "teachers": tlist, "classes": classes, "lessons": lessons, "blocks": blocks,
        "fixed": [], "soft": {"late_period_from": 5, "hard_difficulty": 3},
        "weights": {"student_gap": 10, "teacher_gap": 3, "same_subject_same_day": 5, "day_imbalance": 1,
                    "hard_subject_late": 2},
        "substitution": {"max_subs_per_day": 2},
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(inst, f, ensure_ascii=False, indent=1)
    loads = sorted(t["load"] for t in teachers)
    print(f"{name}: {n_cls} classes, {len(tlist)} teachers (load {loads[0]}-{loads[-1]} h), "
          f"{len(lessons)} lessons, {len(blocks)} blocks, {len(rooms)} rooms -> {a.out}")


if __name__ == "__main__":
    main()
