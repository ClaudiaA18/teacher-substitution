import argparse
import json

import pandas as pd
import sqlalchemy as sa

import db

DFE_COLS = ["time_period", "school_urn", "school_name", "la_name", "region_name", "school_type",
            "total_teachers_taking_absence", "percentage_taking_absence", "total_number_of_days_lost",
            "average_number_of_days_taken", "average_number_of_days_all_teachers"]


def import_instance(eng, inst_path, sol_path):
    raw = json.load(open(inst_path, encoding="utf-8"))
    entries = json.load(open(sol_path, encoding="utf-8"))["entries"]
    name = raw["meta"]["name"]
    with eng.begin() as c:
        c.execute(sa.delete(db.instances).where(db.instances.c.name == name))
        c.execute(sa.insert(db.instances), [{"name": name, "raw": raw}])
        own = {}
        for l in raw["lessons"]:
            own.setdefault(l["teacher"], set()).add(l["subject"])
        c.execute(sa.insert(db.teachers), [{
            "instance": name, "teacher_id": t["id"], "name": t.get("name", t["id"]),
            "subjects": t.get("subjects", sorted(own.get(t["id"], []))), "related": t.get("related", []),
            "max_per_day": t["max_per_day"]} for t in raw["teachers"]])
        c.execute(sa.insert(db.timetable), [{
            "instance": name, "lesson_id": e["lesson"], "subject": e["subject"], "teacher_id": e["teacher"],
            "day": e["day"], "period": e["period"], "room": e["room"]} for e in entries])
    print(f"instance '{name}': {len(raw['teachers'])} teachers, {len(entries)} timetable entries")


def import_dfe(eng, csv_path):
    df = pd.read_csv(csv_path, low_memory=False)
    if "geographic_level" in df.columns:
        df = df[df["geographic_level"] == "School"]
    df = df[DFE_COLS].copy()
    for col in DFE_COLS[6:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["school_urn"]).drop_duplicates(["time_period", "school_urn"])
    with eng.begin() as c:
        c.execute(sa.delete(db.dfe_absence))
    df.to_sql("dfe_absence", eng, if_exists="append", index=False, chunksize=20000, method="multi")
    print(f"dfe_absence: {len(df)} rows, years {df.time_period.min()}-{df.time_period.max()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance")
    ap.add_argument("--solution")
    ap.add_argument("--dfe")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    eng = db.engine(a.db)
    db.init(eng)
    if a.instance:
        import_instance(eng, a.instance, a.solution)
    if a.dfe:
        import_dfe(eng, a.dfe)


if __name__ == "__main__":
    main()
