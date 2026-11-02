import argparse
import logging
import warnings

import numpy as np
import pandas as pd
import sqlalchemy as sa

import db

Y = "average_number_of_days_all_teachers"
warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("prophet").setLevel(logging.ERROR)


def series(eng, scope):
    df = pd.read_sql_table("dfe_absence", eng)
    if scope == "secondary":
        df = df[df.school_type.str.contains("econdary", na=False)]
    s = df.groupby(df.time_period // 100)[Y].median()
    return s.reindex(range(s.index.min(), s.index.max() + 1))


def f_naive(s, h):
    v = s.dropna().iloc[-1]
    return np.full(h, v), None, None


def f_arima(s, h):
    from statsmodels.tsa.arima.model import ARIMA
    r = ARIMA(s.interpolate().values, order=(1, 0, 0)).fit().get_forecast(h)
    ci = r.conf_int(alpha=0.2)
    return r.predicted_mean, ci[:, 0], ci[:, 1]


def f_holt(s, h):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    m = ExponentialSmoothing(s.interpolate().values, trend="add", damped_trend=True).fit()
    return m.forecast(h), None, None


def f_prophet(s, h):
    from prophet import Prophet
    logging.getLogger("cmdstanpy").disabled = True
    d = s.dropna().reset_index()
    d.columns = ["ds", "y"]
    d["ds"] = pd.to_datetime(d["ds"].astype(str) + "-09-01")
    d["covid"] = d["ds"].dt.year.isin([2020, 2021]).astype(float)
    m = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False,
                changepoint_prior_scale=0.1, interval_width=0.8)
    m.add_regressor("covid")
    m.fit(d)
    last = d["ds"].dt.year.max()
    fut = pd.DataFrame({"ds": pd.to_datetime([f"{last + k}-09-01" for k in range(1, h + 1)]), "covid": 0.0})
    fc = m.predict(fut)
    return fc["yhat"].values, fc["yhat_lower"].values, fc["yhat_upper"].values


MODELS = {"naive": f_naive, "arima": f_arima, "holt": f_holt, "prophet": f_prophet}


def backtest(s, fn, start):
    err = []
    for t in range(start, int(s.index.max()) + 1):
        if np.isnan(s.get(t, np.nan)):
            continue
        tr = s[s.index < t]
        yhat = fn(tr.loc[:tr.last_valid_index()], 1)[0][0]
        err.append(abs(yhat - s[t]))
    return float(np.mean(err)), len(err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--horizon", type=int, default=2)
    ap.add_argument("--backtest-from", type=int, default=2016)
    a = ap.parse_args()
    eng = db.engine(a.db)
    db.init(eng)
    rows, mrows = [], []
    for scope in ("secondary", "all"):
        s = series(eng, scope)
        last = int(s.last_valid_index())
        print(f"\n[{scope}] {int(s.index.min())}/{(int(s.index.min()) + 1) % 100:02d} - {last}/{(last + 1) % 100:02d}  "
              f"(missing: {[int(y) for y in s.index[s.isna()]]})")
        print(f"  {'model':<8} {'backtest MAE':>12}   " +
              "   ".join(f"{last + k}/{(last + k + 1) % 100:02d} [80% interval]" for k in range(1, a.horizon + 1)))
        for name, fn in MODELS.items():
            try:
                mae, n = backtest(s, fn, a.backtest_from)
                yhat, lo, hi = fn(s.loc[:last], a.horizon)
            except Exception as e:
                print(f"  {name:<8} skipped ({type(e).__name__}: {str(e)[:60]})")
                continue
            mrows.append({"model": name, "scope": scope, "mae": mae, "n": n})
            cells = []
            for k in range(a.horizon):
                y0 = last + k + 1
                l_, h_ = (float(lo[k]), float(hi[k])) if lo is not None else (None, None)
                rows.append({"model": name, "scope": scope, "time_period": y0 * 100 + (y0 + 1) % 100,
                             "yhat": float(yhat[k]), "lo": l_, "hi": h_})
                cells.append(f"{yhat[k]:5.2f}" + (f" [{l_:.2f}-{h_:.2f}]" if l_ is not None else " " * 14))
            print(f"  {name:<8} {mae:12.3f}   " + "   ".join(f"{c:<26}" for c in cells))
    with eng.begin() as c:
        c.execute(sa.delete(db.forecast_series))
        c.execute(sa.delete(db.forecast_series_metrics))
        c.execute(sa.insert(db.forecast_series), rows)
        c.execute(sa.insert(db.forecast_series_metrics), mrows)
    print("\nsaved: forecast_series, forecast_series_metrics")


if __name__ == "__main__":
    main()
