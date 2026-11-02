import pathlib
import sys
import pandas as pd

SCHOOL_DAYS = 190
NUM = ["average_number_of_days_all_teachers", "average_number_of_days_taken", "percentage_taking_absence"]
ID_COLS = ["school_urn", "urn", "school_laestab", "laestab"]


def pick(year):
    files = [p for p in pathlib.Path("data/dfe", year).rglob("*.csv") if "absence" in p.name.lower()]
    found = []
    for p in files:
        cols = pd.read_csv(p, nrows=0).columns
        if all(c in cols for c in NUM):
            found.append((any(c in cols for c in ID_COLS), p))
    if not found:
        return None, False
    school_level, p = max(found, key=lambda x: x[0])
    return p, school_level


def load(year):
    p, school_level = pick(year)
    if p is None:
        print(f"[{year}] no usable absence CSV in data/dfe/{year}")
        return None
    df = pd.read_csv(p, low_memory=False)
    if "geographic_level" in df.columns:
        df = df[df["geographic_level"] == "School"]
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    print(f"[{year}] {p}  rows={len(df)}  school-level={school_level}")
    return df


def summary(df):
    g = df.groupby("time_period")[NUM].median()
    g["p_daily"] = g[NUM[0]] / SCHOOL_DAYS
    return g


def main():
    a, b = load("2024"), load("2025")
    if a is None and b is None:
        sys.exit(1)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    if a is not None and b is not None:
        sa, sb = summary(a), summary(b)
        both = sa.join(sb, lsuffix="_2024", rsuffix="_2025", how="outer").round(3)
        print("\nmedian per school, by year (2024 release vs 2025 release):\n", both)
        common = sa.index.intersection(sb.index)
        diff = (sb.loc[common, NUM] - sa.loc[common, NUM]).abs().max().max()
        print(f"\noverlapping years: {len(common)}  max revision in medians: {diff:.3f}")
        new = sb.index.difference(sa.index)
        print(f"new years in 2025 release: {list(new)}")
    else:
        df = a if a is not None else b
        print("\nmedian per school, by year:\n", summary(df).round(3))

    df = b if b is not None else a
    last = df["time_period"].max()
    d = df.loc[df["time_period"] == last, NUM[0]].dropna()
    print(f"\nlatest year {last}: days lost / teacher (per school)")
    print(d.describe(percentiles=[.1, .25, .5, .75, .9]).round(2))
    print(f"daily absence probability: median={d.median() / SCHOOL_DAYS:.4f}  "
          f"p90={d.quantile(.9) / SCHOOL_DAYS:.4f}")
    if "school_type" in df.columns:
        sec = df[df["school_type"].astype(str).str.contains("secondary", case=False)]
        s = sec.groupby("time_period")[NUM[0]].agg(["median", lambda x: x.quantile(.9)])
        s.columns = ["days_median", "days_p90"]
        s["p_daily_median"] = s["days_median"] / SCHOOL_DAYS
        s["p_daily_p90"] = s["days_p90"] / SCHOOL_DAYS
        print("\nsecondary schools only, by year:\n", s.round(4))
        print("\nby school type (latest year):\n",
              df[df["time_period"] == last].groupby("school_type")[NUM].median().round(2))


if __name__ == "__main__":
    main()
