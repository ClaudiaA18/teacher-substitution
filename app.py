import copy
import datetime as dt
from collections import defaultdict

import pandas as pd
import sqlalchemy as sa
import streamlit as st

import db
from tt_core import Instance
from substitute import Context, run_day, DEFAULT_WEIGHTS, METHODS
from gen_scenarios import generate
from simulate import run_simulation, gini

st.set_page_config(page_title="Suplinire profesori", layout="wide")
KIND = {"same": "aceeași specialitate", "related": "disciplină înrudită", "sup": "supraveghere"}
NONE = "— neacoperită —"


@st.cache_resource
def get_engine():
    eng = db.engine()
    db.init(eng)
    return eng


try:
    eng = get_engine()
except sa.exc.OperationalError as e:
    st.error("Nu mă pot conecta la PostgreSQL.")
    st.markdown("- Deschide **Postgres.app** și verifică să scrie *Running* (dacă nu, apasă **Start**).\n"
                "- Prima dată: **Initialize**, apoi în terminal `createdb orar`.\n"
                f"- Adresa folosită: `{db.URL}`")
    st.code(str(e.orig).strip())
    st.stop()


def q(sql, **kw):
    with eng.connect() as c:
        return pd.read_sql(sa.text(sql), c, params=kw)


def load_instance(name):
    with eng.connect() as c:
        raw = c.execute(sa.select(db.instances.c.raw).where(db.instances.c.name == name)).scalar_one()
        tdf = pd.read_sql(sa.select(db.teachers).where(db.teachers.c.instance == name), c)
        ent = pd.read_sql(sa.select(db.timetable).where(db.timetable.c.instance == name), c)
    raw = copy.deepcopy(raw)
    by_id = tdf.set_index("teacher_id")
    known = {t["id"] for t in raw["teachers"]}
    for r in tdf.itertuples():
        if r.teacher_id not in known:
            raw["teachers"].append({"id": r.teacher_id, "max_per_day": int(r.max_per_day), "unavailable": []})
    for t in raw["teachers"]:
        if t["id"] in by_id.index:
            r = by_id.loc[t["id"]]
            t["subjects"], t["related"], t["max_per_day"] = list(r.subjects or []), list(r.related or []), int(r.max_per_day)
            t["name"] = r["name"]
    entries = [{"lesson": r.lesson_id, "subject": r.subject, "teacher": r.teacher_id, "day": int(r.day),
                "period": int(r.period), "room": r.room} for r in ent.itertuples()]
    inst = Instance(raw)
    return inst, Context(inst, entries), entries, tdf


def cum_subs(name, before):
    df = q("select substitute, count(*) n from substitutions where instance=:i and date < :d group by 1",
           i=name, d=before)
    return dict(zip(df.substitute, df.n))


def kind_of(f):
    return "same" if f["same_subject"] else "related" if f["related"] else "sup"


names = q("select name from instances order by name")["name"].tolist()
if not names:
    st.error("Baza de date e goală. Rulează întâi: python3 import_data.py --instance ... --solution ...")
    st.stop()

with st.sidebar:
    st.header("Setări")
    name = st.selectbox("Instanță (școală)", names)
    method = st.radio("Metodă de alocare", list(METHODS), index=2,
                      format_func={"greedy": "Greedy", "hungarian": "Algoritmul ungar", "cpsat": "CP-SAT"}.get)
    fair = st.slider("Pondere echitate (CP-SAT)", 0.0, 5.0, 1.0, 0.5)

inst, ctx, entries, tdf = load_instance(name)
tname = dict(zip(tdf.teacher_id, tdf["name"]))
lab = lambda t: f"{t} – {tname.get(t, t)}" if tname.get(t, t) != t else t

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Suplinire", "Orar", "Profesori", "Istoric", "Prognoză și simulare (DfE)"])

def page_suplinire():
    c1, c2 = st.columns([1, 3])
    date = c1.date_input("Data", dt.date.today())
    d = date.weekday()
    if d >= inst.D:
        st.warning("Zi fără cursuri în orar.")
        return
    c1.caption(f"Ziua din orar: **{inst.days[d]}**")
    saved = q("select teacher_id from absences where instance=:i and date=:d", i=name, d=date)["teacher_id"].tolist()
    absent = c2.multiselect("Profesori absenți", list(inst.teachers), default=saved, format_func=lab)

    key = (name, str(date), tuple(sorted(absent)), method, fair)
    if st.button("Calculează înlocuitorii", type="primary") and absent:
        cum = cum_subs(name, date)
        res, plan, _ = run_day(ctx, method, d, absent, cum, DEFAULT_WEIGHTS, fair)
        tasks = ctx.tasks(d, absent)
        rows, alts = [], {}
        for tk in tasks:
            cands = sorted(ctx.candidates(tk, d, absent, cum, DEFAULT_WEIGHTS), key=lambda x: -x[1])
            pick = next((x["substitute"] for x in plan if x["lesson"] == tk["lesson"] and x["period"] == tk["period"]), None)
            f = next((f for t, s, f in cands if t == pick), None)
            sc = next((s for t, s, f in cands if t == pick), None)
            rows.append({"Ora": inst.labels[tk["period"]], "period": tk["period"], "Lecție": tk["lesson"],
                         "Disciplină": tk["subject"], "Clase": ", ".join(sorted(tk["classes"])),
                         "Absent": tk["absent"], "Înlocuitor": pick or NONE,
                         "Tip": KIND[kind_of(f)] if f else "", "Scor": round(sc, 2) if sc is not None else None})
            alts[(tk["lesson"], tk["period"])] = [(t, round(s, 2), kind_of(f)) for t, s, f in cands[:5]]
        st.session_state["plan"] = {"key": key, "rows": rows, "alts": alts, "res": res}

    plan = st.session_state.get("plan")
    if plan and plan["key"] == key:
        r = plan["res"]
        m = st.columns(5)
        m[0].metric("Ore de acoperit", r["tasks"])
        m[1].metric("Acoperite", int(r["covered"]))
        m[2].metric("Aceeași specialitate", int(r["same_subject"]))
        m[3].metric("Înrudită", int(r["related"]))
        m[4].metric("Supraveghere", int(r["supervision"]))
        df = pd.DataFrame(plan["rows"])
        opts = [NONE] + [t for t in inst.teachers if t not in absent]
        ed = st.data_editor(
            df.drop(columns=["period"]), hide_index=True, use_container_width=True,
            disabled=["Ora", "Lecție", "Disciplină", "Clase", "Absent", "Tip", "Scor"],
            column_config={"Înlocuitor": st.column_config.SelectboxColumn("Înlocuitor (modificabil)", options=opts)})
        with st.expander("Alternative (top 5 candidați pe oră)"):
            for (les, p), al in plan["alts"].items():
                st.write(f"**{inst.labels[p]} {les}**: " + "; ".join(f"{t} ({KIND[k]}, {s})" for t, s, k in al))

        if st.button("Salvează în baza de date"):
            errs, used = [], defaultdict(int)
            for row, p in zip(ed.itertuples(), df["period"]):
                t = row.Înlocuitor
                if t == NONE:
                    continue
                if p in ctx.busy[(t, d)] or (d, p) in inst.unavail[t]:
                    errs.append(f"{t} nu e liber la {inst.labels[p]}")
                used[(t, p)] += 1
                if used[(t, p)] > 1:
                    errs.append(f"{t} apare de două ori la {inst.labels[p]}")
            if errs:
                st.error("Nu am salvat:\n- " + "\n- ".join(errs))
            else:
                cand = {(tk_les, p): {t: (s, k) for t, s, k in al} for (tk_les, p), al in plan["alts"].items()}
                with eng.begin() as c:
                    c.execute(sa.delete(db.absences).where((db.absences.c.instance == name) & (db.absences.c.date == date)))
                    c.execute(sa.delete(db.substitutions).where((db.substitutions.c.instance == name) & (db.substitutions.c.date == date)))
                    if absent:
                        c.execute(sa.insert(db.absences), [{"instance": name, "date": date, "teacher_id": t} for t in absent])
                    subs = []
                    for row, p in zip(ed.itertuples(), df["period"]):
                        if row.Înlocuitor == NONE:
                            continue
                        s, k = cand.get((row.Lecție, p), {}).get(row.Înlocuitor, (None, "manual"))
                        subs.append({"instance": name, "date": date, "period": int(p), "lesson_id": row.Lecție,
                                     "absent_teacher": row.Absent, "substitute": row.Înlocuitor, "kind": k,
                                     "score": s, "method": method})
                    if subs:
                        c.execute(sa.insert(db.substitutions), subs)
                st.success(f"Salvat: {len(absent)} absențe, {len(subs)} supliniri pentru {date}.")


with tab1:
    page_suplinire()

with tab2:
    mode = st.radio("Afișează orarul pentru", ["Clasă", "Profesor"], horizontal=True)
    if mode == "Clasă":
        who = st.selectbox("Clasa", list(inst.classes))
        sel = [e for e in entries if any(s["class"] == who for s in inst.lessons[e["lesson"]]["audience"])]
        cell = lambda e: f"{e['subject']} ({e['teacher']})"
    else:
        who = st.selectbox("Profesorul", list(inst.teachers), format_func=lab)
        sel = [e for e in entries if e["teacher"] == who]
        cell = lambda e: f"{e['lesson']} [{e['room']}]"
    grid = pd.DataFrame("", index=inst.labels, columns=inst.days)
    for e in sel:
        cur = grid.iat[e["period"], e["day"]]
        grid.iat[e["period"], e["day"]] = (cur + " / " if cur else "") + cell(e)
    st.dataframe(grid, use_container_width=True)

with tab3:
    subj_name = {x["id"]: x.get("name", x["id"]) for x in inst.raw["subjects"]}
    sname = lambda x: f"{x} – {subj_name.get(x, x)}"
    over = tdf[["teacher_id", "name", "subjects", "related", "max_per_day"]].copy()
    over["subjects"] = over["subjects"].map(lambda x: ", ".join(x or []))
    over["related"] = over["related"].map(lambda x: ", ".join(x or []))
    st.dataframe(over.rename(columns={"teacher_id": "Cod", "name": "Nume", "subjects": "Specialitate",
                                      "related": "Discipline înrudite", "max_per_day": "Max. ore/zi"}),
                 hide_index=True, use_container_width=True)

    if "teacher_msg" in st.session_state:
        st.success(st.session_state.pop("teacher_msg"))
    st.subheader("Editează sau adaugă profesor")
    NEW = "+ profesor nou"
    pick = st.selectbox("Profesor", [NEW] + tdf.teacher_id.tolist(), format_func=lambda t: t if t == NEW else lab(t))
    row = tdf.set_index("teacher_id").loc[pick] if pick != NEW else None
    with st.form("teacher_form"):
        c1, c2, c3 = st.columns([1, 2, 1])
        tid = c1.text_input("Cod", value=pick if row is not None else "", disabled=row is not None)
        tnm = c2.text_input("Nume", value=row["name"] if row is not None else "")
        mpd = c3.number_input("Max. ore/zi", 1, 12, int(row["max_per_day"]) if row is not None else inst.P)
        subs = st.multiselect("Specialitate (discipline predate)", list(subj_name),
                              default=[x for x in (row["subjects"] or []) if x in subj_name] if row is not None else [],
                              format_func=sname)
        rel = st.multiselect("Discipline înrudite (poate suplini)", list(subj_name),
                             default=[x for x in (row["related"] or []) if x in subj_name] if row is not None else [],
                             format_func=sname)
        ok = st.form_submit_button("Salvează")
    if ok:
        tid = (tid or "").strip()
        if not tid:
            st.error("Completează codul profesorului.")
        elif row is None and tid in tdf.teacher_id.tolist():
            st.error(f"Codul {tid} există deja.")
        else:
            vals = {"name": tnm or tid, "subjects": subs, "related": [x for x in rel if x not in subs],
                    "max_per_day": int(mpd)}
            with eng.begin() as c:
                if row is None:
                    c.execute(sa.insert(db.teachers).values(instance=name, teacher_id=tid, **vals))
                else:
                    c.execute(sa.update(db.teachers).where((db.teachers.c.instance == name) &
                                                           (db.teachers.c.teacher_id == tid)).values(**vals))
            st.session_state["teacher_msg"] = f"Profesor {tid} salvat."
            st.rerun()

    if pick != NEW:
        own = sorted({e["lesson"] for e in entries if e["teacher"] == pick})
        st.caption("Lecții în orar: " + (", ".join(own) if own else "niciuna (poate fi doar înlocuitor)"))

with tab4:
    c1, c2 = st.columns(2)
    d1 = c1.date_input("De la", dt.date(dt.date.today().year if dt.date.today().month >= 9 else dt.date.today().year - 1, 9, 1))
    d2 = c2.date_input("Până la", dt.date.today())
    h = q("select date, period, lesson_id, absent_teacher, substitute, kind, score, method from substitutions "
          "where instance=:i and date between :a and :b order by date, period", i=name, a=d1, b=d2)
    if h.empty:
        st.info("Nicio suplinire salvată în interval.")
    else:
        m = st.columns(4)
        m[0].metric("Supliniri", len(h))
        m[1].metric("Aceeași specialitate", f"{100 * (h.kind == 'same').mean():.0f}%")
        loads = h.substitute.value_counts().reindex(list(inst.teachers), fill_value=0)
        m[2].metric("Gini (echitate)", f"{gini(loads.tolist()):.3f}")
        m[3].metric("Max. / profesor", int(loads.max()))
        st.bar_chart(loads.rename("supliniri"))
        h["kind"] = h["kind"].map(KIND).fillna(h["kind"])
        st.dataframe(h, hide_index=True, use_container_width=True)
        st.download_button("Descarcă CSV", h.to_csv(index=False).encode(), f"supliniri_{name}.csv")

def page_prognoza():
    if q("select count(*) n from dfe_absence")["n"][0] == 0:
        st.info("Nu există date DfE în bază. Rulează: python3 import_data.py --dfe <fișier _sch.csv>")
        return
    yl = lambda tp: f"{str(tp)[:4]}/{str(tp)[4:]}"
    scope = st.radio("Serie", ["secondary", "all"], horizontal=True,
                     format_func={"secondary": "școli secundare", "all": "toate școlile"}.get)
    cond = "where school_type ilike '%secondary%'" if scope == "secondary" else ""
    nat = q("select time_period, percentile_cont(0.5) within group (order by average_number_of_days_all_teachers) med "
            f"from dfe_absence {cond} group by 1 order by 1")
    st.subheader("Absențe medicale ale profesorilor (Anglia, DfE) și prognoză")
    chart = pd.DataFrame({"real": nat.set_index("time_period")["med"]})
    fs = q("select model, time_period, yhat, lo, hi from forecast_series where scope=:s", s=scope)
    if not fs.empty:
        lastp = int(nat.time_period.max())
        for mdl, g in fs.groupby("model"):
            col = pd.concat([pd.Series({lastp: float(chart.loc[lastp, "real"])}), g.set_index("time_period")["yhat"]])
            chart = chart.join(col.rename(mdl), how="outer")
    chart.index = [yl(i) for i in chart.index]
    st.line_chart(chart)
    if not fs.empty:
        sm = q("select model, mae from forecast_series_metrics where scope=:s order by mae", s=scope)
        tab = fs.assign(an=fs.time_period.map(yl)).pivot_table(index="model", columns="an", values="yhat").round(2)
        tab = tab.join(sm.set_index("model")["mae"].round(3).rename("MAE backtest"))
        pr = fs[fs.model == "prophet"]
        st.dataframe(tab.sort_values("MAE backtest"), use_container_width=True)
        if not pr.empty:
            st.caption("Prophet, interval 80%: " + "; ".join(f"{yl(r.time_period)}: {r.yhat:.2f} [{r.lo:.2f}–{r.hi:.2f}]"
                                                               for r in pr.itertuples()))
    else:
        st.info("Pentru prognoza seriei (Prophet, ARIMA, Holt) rulează: python3 forecast_trend.py")

    mt = q("select * from forecast_metrics order by test_year, scope, mae")
    if mt.empty:
        st.info("Rulează: python3 forecast.py")
        return
    st.subheader("Evaluarea modelelor de predicție (MAE, zile/profesor/an)")
    st.dataframe(mt.pivot_table(index="model", columns=["test_year", "scope"], values="mae").round(3),
                 use_container_width=True)

    fc = q("select school_type, region_name, pred_days, p_daily, model, time_period from forecast")
    yrs = sorted(int(x) for x in fc.time_period.unique())
    yr = st.selectbox("An școlar prognozat (pe școli)", yrs, index=len(yrs) - 1, format_func=yl)
    fc = fc[fc.time_period == yr]
    st.subheader(f"Prognoză pe școli {yl(yr)} (model: {fc.model.iloc[0]})")
    c1, c2 = st.columns(2)
    types = sorted(fc.school_type.unique())
    stype = c1.multiselect("Tip de școală", types, default=[t for t in types if "econdary" in t])
    regs = c2.multiselect("Regiune", sorted(fc.region_name.unique()))
    s = fc[fc.school_type.isin(stype)] if stype else fc
    s = s[s.region_name.isin(regs)] if regs else s
    if s.empty:
        return
    lvl = st.radio("Nivel folosit", ["mediană", "p75", "p90"], horizontal=True)
    p = float({"mediană": s.p_daily.median(), "p75": s.p_daily.quantile(.75), "p90": s.p_daily.quantile(.9)}[lvl])
    n_t = len(inst.teachers)
    m = st.columns(3)
    m[0].metric("Școli în selecție", len(s))
    m[1].metric("Probabilitate zilnică de absență", f"{100 * p:.2f}%")
    m[2].metric(f"Absenți/zi așteptați ({n_t} profesori)", f"{n_t * p:.2f}")

    st.subheader("Simulare an școlar cu probabilitatea prognozată")
    c1, c2, c3 = st.columns(3)
    days_n = c1.number_input("Zile", 20, 400, 190)
    spell = c2.number_input("Durata medie a unei absențe (zile)", 1.0, 10.0, 2.0, 0.5)
    seed = c3.number_input("Seed", 0, 10_000, 1)
    if st.button("Rulează simularea"):
        days = generate(list(inst.teachers), inst.D, int(days_n), p, spell, int(seed))
        with st.spinner("Simulez..."):
            _, summ = run_simulation(ctx, days, list(METHODS), DEFAULT_WEIGHTS, fair)
        st.dataframe(pd.DataFrame(summ), hide_index=True, use_container_width=True)


with tab5:
    page_prognoza()
