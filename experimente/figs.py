import json
import math
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False})

HERE = os.path.dirname(os.path.abspath(__file__))
d = pd.DataFrame(json.load(open(os.path.join(HERE, "results.json"))))
d["rec"] = d["instr_hours_recovered"]

lam = d[d.tag == "lambda"].groupby("fair")[["rec", "gini"]].agg(["mean", "std"])
ref = d[d.tag == "lambda_ref"][["rec", "gini"]].agg(["mean", "std"])

fig, ax = plt.subplots(figsize=(4.8, 2.5))
ax.grid(True, color=GRID, lw=0.6)
ax.set_axisbelow(True)
x, y = lam[("gini", "mean")], lam[("rec", "mean")]
ax.errorbar(x, y, xerr=lam[("gini", "std")], yerr=lam[("rec", "std")], color=BLUE, lw=2,
            marker="o", ms=5, mec="white", mew=1, ecolor=BLUE, elinewidth=0.8, capsize=2,
            label=r"CP-SAT, fairness weight $\lambda$")
off = {0.0: (-4, 10), 0.5: (-8, 8), 1.0: (-6, -14), 2.0: (-6, 7), 3.0: (-6, 7), 5.0: (-6, 7)}
for l, xi, yi in zip(lam.index, x, y):
    ax.annotate(rf"$\lambda$={l:g}", (xi, yi), textcoords="offset points", xytext=off[l],
                ha="right", fontsize=7, color=INK)
ax.errorbar(ref.loc["mean", "gini"], ref.loc["mean", "rec"], xerr=ref.loc["std", "gini"],
            yerr=ref.loc["std", "rec"], color=ORANGE, marker="s", ms=6, mec="white", mew=1,
            ls="none", elinewidth=0.8, capsize=2, label="Greedy")
ax.set_xlabel("Gini coefficient of the substitution load (lower = fairer)")
ax.set_ylabel("Recovered hours per year")
ax.legend(frameon=False, loc="lower right")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "fig_tradeoff.pdf"))
fig.savefig(os.path.join(HERE, "fig_tradeoff.png"), dpi=200)

months = ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
ms = list(range(9, 19))
n, h = 32, 380 / 32 / 5


def series(p, a):
    f = [1 + a * math.cos(2 * math.pi * (m - 13) / 12) for m in ms]
    mean = sum(f) / len(f)
    return [n * p * v / mean * h for v in f]


fig, ax = plt.subplots(figsize=(4.8, 2.2))
ax.grid(True, axis="y", color=GRID, lw=0.6)
ax.set_axisbelow(True)
lines = [(series(0.026, 0.6), BLUE, "o", "England, median, winter peak"),
         (series(0.026, 0.0), ORANGE, "s", "England, median, constant"),
         (series(0.026 * 0.342, 0.6), AQUA, "^", "Romanian rules, winter peak")]
for ys, c, mk, lab in lines:
    ax.plot(months, ys, color=c, lw=2, marker=mk, ms=5, mec="white", mew=1, label=lab)
ax.set_ylim(0, 3.9)
ax.set_ylabel("Lessons to cover per day")
ax.legend(frameon=False, loc="upper left", fontsize=7)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "fig_monthly.pdf"))
fig.savefig(os.path.join(HERE, "fig_monthly.png"), dpi=200)
print(lam.round(3))
print([round(v, 2) for v in series(0.026 * 0.342, 0.6)])
