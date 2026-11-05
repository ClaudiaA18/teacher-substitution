import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
RELATED = {'MAT': ['INFO', 'FIZ'], 'INFO': ['MAT', 'TIC', 'TEH'], 'TIC': ['INFO', 'TEH'], 'TEH': ['TIC', 'INFO', 'FIZ'], 'FIZ': ['MAT', 'CHI'], 'CHI': ['BIO', 'FIZ'], 'BIO': ['CHI', 'GEO'], 'ROM': ['LOG'], 'ENG': ['FR', 'ES'], 'FR': ['ENG', 'ES'], 'ES': ['ENG', 'FR'], 'IST': ['GEO', 'SOC', 'ECO'], 'SOC': ['IST', 'PSI', 'LOG'], 'GEO': ['IST', 'BIO'], 'LOG': ['PSI', 'SOC', 'ROM'], 'PSI': ['SOC', 'LOG'], 'ECO': ['SOC', 'IST'], 'ART': [], 'EFS': [], 'DIR': [], 'LAT': ['ROM', 'FR'], 'REL': ['IST'], 'PST': ['EFS']}
d = json.load(open(os.path.join(HERE, "traian_entries.json")))
T, L, E, seen = {}, {}, [], set()
for e in d["entries"]:
    key = (e["teacher"], e["day"], e["period"])
    if key in seen: continue
    seen.add(key)
    lid = f"{e['teacher']}-{e['subject']}-{'+'.join(e['classes'])}-{e['day']}-{e['period']}"
    L[lid] = {"subject": e["subject"], "audience": [{"class": c, "group": ""} for c in e["classes"]], "teacher": e["teacher"]}
    E.append({"teacher": e["teacher"], "day": e["day"], "period": e["period"], "lesson": lid})
for t in d["teachers"]:
    subj = sorted({L[x["lesson"]]["subject"] for x in E if x["teacher"] == t})
    rel = sorted({r for s in subj for r in RELATED.get(s, []) if r not in subj})
    T[t] = {"subjects": subj, "related": rel, "max_per_day": 8}
json.dump({"teachers": T, "lessons": L, "entries": E}, open(os.path.join(os.path.dirname(HERE), "traian_anon.json"), "w"), ensure_ascii=False, indent=1)
print(len(T), "teachers", len(E), "lessons/week", len({a["class"] for l in L.values() for a in l["audience"]}), "classes")
