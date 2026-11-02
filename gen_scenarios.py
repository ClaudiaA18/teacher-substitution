import argparse
import json
import math
import random

from tt_core import Instance, load

LEVELS = {"median": 0.026, "p90": 0.045, "peak": 0.033, "pre_covid": 0.021}


def seasonal(n_days, amp=0.0, peak_month=1.0):
    month = [9 + 10 * i / n_days for i in range(n_days)]
    raw = [1 + amp * math.cos(2 * math.pi * (m - 12 - peak_month) / 12) for m in month]
    mean = sum(raw) / n_days
    return [r / mean for r in raw]


def generate(teachers, D, n_days, p, spell=1.0, seed=1, amp=0.0):
    L = max(1.0, spell)
    prof = seasonal(n_days, amp)
    rnd = random.Random(seed)
    left = {t: 0 for t in teachers}
    days = []
    for i in range(n_days):
        pi = min(0.99, p * prof[i])
        q = pi / (L * (1 - pi) + pi)
        absent = []
        for t in teachers:
            if left[t] == 0 and rnd.random() < q:
                n = 1
                while rnd.random() > 1 / L:
                    n += 1
                left[t] = n
            if left[t] > 0:
                absent.append(t)
                left[t] -= 1
        days.append({"i": i, "day": i % D, "absent": absent})
    return days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--days", type=int, default=190)
    ap.add_argument("--level", choices=LEVELS, default="median")
    ap.add_argument("--p", type=float, default=None)
    ap.add_argument("--spell", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--season", type=float, default=0.0)
    ap.add_argument("--out", default="scenarios.json")
    a = ap.parse_args()

    inst = Instance(load(a.instance))
    p = a.p if a.p is not None else LEVELS[a.level]
    L = max(1.0, a.spell)
    days = generate(list(inst.teachers), inst.D, a.days, p, L, a.seed, a.season)

    n = [len(d["absent"]) for d in days]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"instance": inst.name, "p": p, "spell": L, "seed": a.seed, "days": days}, f, indent=1)
    print(f"p={p} spell={L} days={a.days}  absent/day: mean={sum(n) / len(n):.2f} max={max(n)}  "
          f"days with 0 absent: {n.count(0)}")
    print(f"saved: {a.out}")


if __name__ == "__main__":
    main()
