import sys
import glob
import pandas as pd

SCHOOL_DAYS = 190

files = sorted(f for f in glob.glob("data/dfe/**/*.csv", recursive=True)
               if "absence" in f.lower() and "school" in f.lower())
if len(sys.argv) > 1:
    path = sys.argv[1]
elif files:
    path = files[-1]
else:
    sys.exit("no school-level absence CSV in data/dfe; run: ls -R data/dfe")
print("candidates:", *files, sep="\n  ")
df = pd.read_csv(path, low_memory=False)
print(f"file: {path}\nrows: {len(df)}\ncolumns: {list(df.columns)}\n")

num = ["average_number_of_days_all_teachers", "average_number_of_days_taken",
       "percentage_taking_absence", "total_number_of_days_lost", "total_teachers_taking_absence"]
for c in num:
    df[c] = pd.to_numeric(df[c], errors="coerce")

year = "time_period" if "time_period" in df.columns else None
if year:
    g = df.groupby(year)[num[:3]].median().round(2)
    print("median per school, by year:\n", g, "\n")

if "school_type" in df.columns:
    print("median by school type:\n", df.groupby("school_type")[num[:3]].median().round(2), "\n")

d = df["average_number_of_days_all_teachers"].dropna()
print("days lost / teacher / year:")
print(d.describe(percentiles=[.1, .25, .5, .75, .9]).round(2), "\n")

p = (d / SCHOOL_DAYS).describe(percentiles=[.1, .5, .9]).round(4)
print(f"daily absence probability per teacher (days / {SCHOOL_DAYS}):")
print(p)
