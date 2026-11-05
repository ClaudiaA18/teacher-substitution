import os, sys, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gen_scenarios import generate
T = [f"T{i}" for i in range(32)]
def share_any(p, L, seeds=200):
    tot = 0
    for s in range(1, seeds + 1):
        days = generate(T, 5, 190, p, L, s, 0.0)
        c = Counter(t for d in days for t in d["absent"])
        tot += sum(1 for t in T if c[t] > 0) / len(T)
    return tot / seeds
def calibrate(p, target):
    lo, hi = 1.0, 30.0
    for _ in range(18):
        mid = (lo + hi) / 2
        if share_any(p, mid, 60) > target: lo = mid
        else: hi = mid
    return round((lo + hi) / 2, 1)
C = {"England 2024/25": (5.0/190, 0.618), "Wales 2023/24": (12.2*0.606/190, 0.606),
     "Northern Ireland 2025/26": (10.2/190, 0.614), "Netherlands VO 2025": (0.059, 0.665)}
out = {}
for k, (p, s) in C.items():
    L = calibrate(p, s); out[k] = (p, L); print(k, round(p*100, 2), s, L, round(share_any(p, L), 3))
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "calib.json"), "w"))
