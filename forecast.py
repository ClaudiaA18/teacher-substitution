import argparse
import warnings

import numpy as np
import pandas as pd
import sqlalchemy as sa

import db

SCHOOL_DAYS = 190
Y = "average_number_of_days_all_teachers"
CAT = ["school_type", "region_name"]
warnings.filterwarnings("ignore")


def load(eng):
    df = pd.read_sql_table("dfe_absence", eng)
    df["year"] = df["time_period"] // 100
    return df.dropna(subset=[Y])


def panel(df):
    w = df.pivot_table(index="school_urn", columns="year", values=Y)
    pct = df.pivot_table(index="school_urn", columns="year", values="percentage_taking_absence")
    info = df.sort_values("year").groupby("school_urn")[CAT].last()
    nat = df.groupby("year")[Y].median()
    years = sorted(df["year"].unique())
    rows = []
    for y in range(years[0] + 1, years[-1] + 2):
        prev = [c for c in w.columns if c < y]
        if not prev:
            continue
        f = pd.DataFrame(index=w.index)
        for k in (1, 2, 3):
            f[f"lag{k}"] = w[y - k] if (y - k) in w.columns else np.nan
        f["mean_prev"] = w[prev].mean(axis=1)
        f["std_prev"] = w[prev].std(axis=1)
        f["n_prev"] = w[prev].notna().sum(axis=1)
        f["pct_lag1"] = pct[y - 1] if (y - 1) in pct.columns else np.nan
        f["nat_lag1"] = nat.get(y - 1, np.nan)
        f["covid_prev"] = float(y - 1 in (2020, 2021))
        f["year"] = y
        f["target"] = w[y] if y in w.columns else np.nan
        f = f.join(info)
        f = f[f["n_prev"] > 0]
        rows.append(f.reset_index())
    p = pd.concat(rows, ignore_index=True)
    for c in CAT:
        p[c] = p[c].astype("category")
    return p


FEATS = ["lag1", "lag2", "lag3", "mean_prev", "std_prev", "n_prev", "pct_lag1", "nat_lag1", "covid_prev",
         "school_type", "region_name"]


def fit_predict(name, tr, te):
    if name == "naive_last":
        return te["lag1"].fillna(te["mean_prev"]).values
    if name == "school_mean":
        return te["mean_prev"].values
    X, y = tr[FEATS], tr["target"]
    if name == "lightgbm":
        import lightgbm as lgb
        m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=50,
                              objective="l1", verbose=-1, random_state=0)
        m.fit(X, y)
        return m.predict(te[FEATS])
    if name == "xgboost":
        import xgboost as xgb
        m = xgb.XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=6, min_child_weight=50,
                             objective="reg:absoluteerror", tree_method="hist", enable_categorical=True,
                             random_state=0)
        m.fit(X, y)
        return m.predict(te[FEATS])
    if name == "hist_gb":
        from sklearn.ensemble import HistGradientBoostingRegressor

        def arr(D):
            D = D.copy()
            for c in CAT:
                D[c] = D[c].cat.codes.astype(float).where(D[c].cat.codes >= 0)
            return D.to_numpy(dtype=float)
        m = HistGradientBoostingRegressor(loss="absolute_error", max_iter=400, learning_rate=0.05,
                                          min_samples_leaf=50, categorical_features=[FEATS.index(c) for c in CAT],
                                          random_state=0)
        m.fit(arr(X), y.to_numpy(dtype=float))
        return m.predict(arr(te[FEATS]))
    raise ValueError(name)


def national_arima(df, test_year):
    from statsmodels.tsa.arima.model import ARIMA
    s = df[df["school_type"].str.contains("econdary", na=False)].groupby("year")[Y].median()
    s = s.reindex(range(s.index.min(), s.index.max() + 1)).interpolate()
    tr = s[s.index < test_year]
    fc = ARIMA(tr.values, order=(1, 0, 0)).fit().forecast(1)[0]
    return fc, s.get(test_year, np.nan)


def metrics(y, p):
    e = np.asarray(p) - np.asarray(y)
    return float(np.mean(np.abs(e))), float(np.sqrt(np.mean(e ** 2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--horizon", type=int, default=2)
    ap.add_argument("--models", default="naive_last,school_mean,hist_gb,lightgbm,xgboost")
    a = ap.parse_args()
    eng = db.engine(a.db)
    db.init(eng)
    df = load(eng)
    p = panel(df)
    last = int(df["year"].max())
    models = a.models.split(",")
    mrows = []
    print(f"panel rows: {len(p)}  years: {int(p.year.min())}-{last + 1}")

    for test_year in (last - 1, last):
        tr = p[(p.year < test_year) & p.target.notna()]
        te = p[(p.year == test_year) & p.target.notna()]
        sec = te["school_type"].astype(str).str.contains("econdary").values
        print(f"\ntest {test_year}/{(test_year + 1) % 100:02d}: train={len(tr)} test={len(te)} (secondary={sec.sum()})")
        print(f"  {'model':<12} {'MAE all':>8} {'RMSE all':>9} {'MAE sec':>8} {'RMSE sec':>9}")
        for mname in models:
            try:
                pred = fit_predict(mname, tr, te)
            except Exception as e:
                print(f"  {mname:<12} skipped ({type(e).__name__}: {str(e)[:80]})")
                continue
            ma, ra = metrics(te.target, pred)
            ms, rs = metrics(te.target[sec], pred[sec])
            print(f"  {mname:<12} {ma:8.3f} {ra:9.3f} {ms:8.3f} {rs:9.3f}")
            mrows += [{"model": mname, "test_year": test_year, "scope": "all", "mae": ma, "rmse": ra, "n": len(te)},
                      {"model": mname, "test_year": test_year, "scope": "secondary", "mae": ms, "rmse": rs,
                       "n": int(sec.sum())}]
        try:
            fc, act = national_arima(df, test_year)
            print(f"  national secondary median, ARIMA(1,0,0): forecast={fc:.2f} actual={act:.2f}")
            mrows.append({"model": "arima_national", "test_year": test_year, "scope": "secondary_median",
                          "mae": abs(fc - act), "rmse": abs(fc - act), "n": 1})
        except Exception as e:
            print(f"  ARIMA skipped ({type(e).__name__})")

    best = min((r for r in mrows if r["scope"] == "secondary" and r["test_year"] == last),
               key=lambda r: r["mae"])["model"]
    tr = p[p.target.notna()]
    outs, hist = [], df.copy()
    for step in range(1, a.horizon + 1):
        yr = last + step
        pp = p if step == 1 else panel(hist)
        fut = pp[(pp.year == yr) & pp.lag1.notna()].copy()
        fut["pred_days"] = fit_predict(best, tr, fut)
        fut["pred_days"] = fut["pred_days"].clip(lower=0)
        fut["p_daily"] = fut["pred_days"] / SCHOOL_DAYS
        out = pd.DataFrame({"model": best, "time_period": yr * 100 + (yr + 1) % 100,
                            "school_urn": fut["school_urn"], "school_type": fut["school_type"].astype(str),
                            "region_name": fut["region_name"].astype(str), "pred_days": fut["pred_days"],
                            "p_daily": fut["p_daily"]})
        outs.append(out)
        add = out[["school_urn", "school_type", "region_name"]].copy()
        add["time_period"] = out["time_period"]
        add["year"] = yr
        add[Y] = out["pred_days"]
        add["percentage_taking_absence"] = np.nan
        hist = pd.concat([hist, add], ignore_index=True)
        s = out[out.school_type.str.contains("econdary")]
        print(f"\nforecast {yr}/{(yr + 1) % 100:02d} with {best}: {len(out)} schools")
        print(f"  secondary: median days={s.pred_days.median():.2f}  p_daily median={s.p_daily.median():.4f}  "
              f"p90={s.p_daily.quantile(.9):.4f}")
    with eng.begin() as c:
        c.execute(sa.delete(db.forecast))
        c.execute(sa.delete(db.forecast_metrics))
    pd.concat(outs).to_sql("forecast", eng, if_exists="append", index=False, chunksize=20000, method="multi")
    pd.DataFrame(mrows).to_sql("forecast_metrics", eng, if_exists="append", index=False)

if __name__ == "__main__":
    main()
