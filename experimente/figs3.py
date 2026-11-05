import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "serif", "font.size": 7.5, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6})

a = pd.DataFrame(json.load(open(os.path.join(HERE, "results_countries2_all_5.json"))))
b = pd.DataFrame(json.load(open(os.path.join(HERE, "results_countries2_3_10.json"))))
d = pd.concat([a, b])
d = d[d.method == "greedy"]
order = list(dict.fromkeys(a.country))
m = d.groupby(["country", "rule"])["mean_load"].mean().unstack()
m = m.loc[order[::-1]]
labels = [c.replace("Northern Ireland", "N. Ireland") for c in m.index]

fig, ax = plt.subplots(figsize=(3.4, 2.35))
ax.grid(True, axis="x", color=GRID, lw=0.5)
ax.set_axisbelow(True)
y = range(len(m))
ax.hlines(list(y), m["3"], m["all"], color=GRID, lw=2.5, zorder=1)
for rule, c, mk, lab in (("all", BLUE, "o", "colleagues cover all days"),
                         ("5", ORANGE, "s", "hired from day 6"),
                         ("10", YELLOW, "D", "hired from day 11"),
                         ("3", AQUA, "^", "hired from day 4")):
    ax.scatter(m[rule], list(y), color=c, marker=mk, s=16, edgecolor="white", linewidth=0.5, zorder=3, label=lab)
ax.set_yticks(list(y))
ax.set_yticklabels(labels)
ax.set_xlabel("Lessons covered per teacher per year")
ax.set_xlim(0, 32)
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.38, 1.0), ncol=2, fontsize=6.2, handletextpad=0.2, columnspacing=0.8)
fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(HERE, "fig_countries.pdf"))
fig.savefig(os.path.join(HERE, "fig_countries.png"), dpi=250)

e = pd.DataFrame(json.load(open(os.path.join(HERE, "results_england.json"))))
e = e[e.kind != "weights"]
g = e.groupby(["kind", "par"])[["rec", "gini"]].agg(["mean", "sem"])
fig, ax = plt.subplots(figsize=(3.4, 1.85))
ax.grid(True, color=GRID, lw=0.5)
ax.set_axisbelow(True)
for k, c, mk, lab in (("cpsat_l", BLUE, "o", r"CP-SAT, $\lambda$ = 0 to 5"),
                      ("greedy_w", ORANGE, "s", "Greedy, load weight 0.3 to 2")):
    x = g.loc[k].sort_values(("gini", "mean"))
    ax.errorbar(x[("gini", "mean")], x[("rec", "mean")], xerr=x[("gini", "sem")], yerr=x[("rec", "sem")],
                color=c, lw=1.4, marker=mk, ms=3.5, mec="white", mew=0.6, elinewidth=0.6, capsize=1.5, label=lab)
ax.set_xlabel("Gini coefficient of the substitution load")
ax.set_ylabel("Recovered hours / year")
ax.legend(frameon=False, loc="lower right", fontsize=7)
fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(HERE, "fig_tradeoff.pdf"))
fig.savefig(os.path.join(HERE, "fig_tradeoff.png"), dpi=250)
