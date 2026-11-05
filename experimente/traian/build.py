import json, re, sys, difflib
from collections import Counter, defaultdict

SUBJ = {"ROM": "ROM", "RomCDS": "ROM", "Rom Aprof": "ROM", "L.Univ": "ROM", "ENG": "ENG", "Engleza CDS": "ENG",
        "FR": "FR", "LAT": "LAT", "MAT": "MAT", "MatCDS": "MAT", "FIZ": "FIZ", "CHIM": "CHI", "ChCDS": "CHI",
        "BIO": "BIO", "BioCDS": "BIO", "Stiinte": "BIO", "IST": "IST", "IstCDS": "IST", "Istoria Holocaustului": "IST",
        "GEO": "GEO", "GeoCDS": "GEO", "LOG": "LOG", "Filos": "LOG", "PSIHO": "PSI", "SOCIO": "SOC", "CDS socio": "SOC",
        "Stud.Soc": "SOC", "CDS studii": "SOC", "ECO": "ECO", "Economie CDS": "ECO", "CDS Ed. antr": "ECO",
        "REL": "REL", "TIC": "TIC", "INF": "INFO", "EF": "EFS", "EPS": "EFS", "PSP": "EFS", "MUZ": "ART", "DES": "ART",
        "Muz/ Des": "ART", "EdA": "ART", "Ed. artistica": "ART", "DIRIG": "DIR", "PST": "PST"}
KEYS = list(SUBJ)
NONCURR = re.compile(r"cerc|club|handbal|baschet|volei", re.I)
CLS = re.compile(r"(9|10|11|12)[A-H]")

def fix_cls(tok):
    t = re.sub(r"[^0-9A-Za-z]", "", tok)
    t = re.sub(r"^[OoSs](?=[A-H]$)", "9", t)
    t = t.replace("R", "B") if re.fullmatch(r"(9|10|11|12)R", t) else t
    for k in range(len(t)):
        if CLS.fullmatch(t[k:]): return t[k:]
    return None

def classes(txt):
    out = []
    for part in re.split(r"[/\s]+", txt):
        if not part: continue
        c = fix_cls(part)
        if c: out.append(c)
    return list(dict.fromkeys(out))

def subject(txt):
    lines = [l.strip(" '_.") for l in txt.split("\n") if l.strip(" '_.|")]
    if not lines: return None
    cand = " ".join(lines[-2:]) if "Holocaust" in txt else lines[-1]
    up = [k.upper() for k in KEYS]
    m = difflib.get_close_matches(cand.upper(), up, n=1, cutoff=0.5)
    if not m: return None
    k = KEYS[up.index(m[0])]
    return SUBJ[k]

def main(raw, out):
    d = json.load(open(raw))
    pages = sorted(d, key=lambda p: p["page"])
    tid = lambda g, r: f"T{sum(len(pages[i]['names']) for i in range(g)) + r + 1:02d}"
    entries, skipped, unk = [], Counter(), []
    for i, p in enumerate(pages):
        g, blk = i % 5, i // 5
        for c in p["cells"]:
            top, bot = c["text"].split(" || ")
            if NONCURR.search(c["text"]): skipped["club"] += 1; continue
            cl = classes(top) or classes(bot)
            sj = subject(bot)
            for r in c["rows"]:
                for col in c["cols"]:
                    day = 2 * blk + col // 8 if blk < 2 else 4
                    entries.append(dict(teacher=tid(g, r), day=day, period=col % 8, classes=cl, subject=sj))
    main_subj = {}
    for t in {e["teacher"] for e in entries}:
        cnt = Counter(e["subject"] for e in entries if e["teacher"] == t and e["subject"] not in (None, "DIR", "PST"))
        main_subj[t] = cnt.most_common(1)[0][0] if cnt else None
    for e in entries:
        t = e["teacher"]
        n = sum(1 for x in entries if x["teacher"] == t and x["subject"] == e["subject"])
        if e["subject"] not in (main_subj[t], "DIR") and n <= 2 and main_subj[t]: e["subject"] = main_subj[t]; skipped["subject_fixed"] += 1
        if e["subject"] is None: e["subject"] = main_subj[e["teacher"]]; skipped["subject_imputed"] += 1
        if not e["classes"]: unk.append(e)
    entries = [e for e in entries if e["classes"]]
    teachers = sorted({tid(g, r) for g in range(5) for r in range(len(pages[g]["names"]))})
    return entries, teachers, main_subj, skipped, unk

if __name__ == "__main__":
    entries, teachers, ms, sk, unk = main(sys.argv[1], None)
    print(len(teachers), "teachers;", len(entries), "lesson-slots;", dict(sk), "no class:", len(unk))
    print(Counter(e["subject"] for e in entries))
    print(Counter(c for e in entries for c in e["classes"]))
    load = Counter(e["teacher"] for e in entries)
    print(sorted(load.values()))
    print({t: ms.get(t) for t in teachers})
    json.dump(dict(entries=entries, teachers=teachers), open("traian_entries.json", "w"))
