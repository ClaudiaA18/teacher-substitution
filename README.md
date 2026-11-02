# Every Lesson Covered, but by Whom?

Code and data for the paper *Every Lesson Covered, but by Whom? Fair Teacher Substitution in High Schools with Constraint Programming* (A.-C. Gîrniță, P. Mihai, U.P.B. Scientific Bulletin, submitted).

## Install
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Files
| File | Role |
|---|---|
| `ro_toy.json`, `ro_school.json` | instances (2 and 12 classes) |
| `gen_school.py` | generates RO-school instances |
| `validate_instance.py` | checks an instance |
| `tt_core.py` | loading, evaluation, output (shared) |
| `solve_cpsat.py`, `solve_sa.py` | weekly timetable: CP-SAT, simulated annealing |
| `gen_scenarios.py` | absence scenarios calibrated on DfE data |
| `substitute.py`, `simulate.py` | daily substitute assignment: greedy, Hungarian, CP-SAT |
| `fetch_dfe.py`, `forecast.py`, `forecast_trend.py` | DfE data, absence forecasts |
| `app.py`, `db.py`, `import_data.py` | Streamlit app + PostgreSQL |
| `experimente/` | scripts and raw results of the paper |

## Run
```
python3 solve_cpsat.py ro_school.json --time 600 --out sol_school.json
python3 gen_scenarios.py ro_school.json --level median --spell 2 --seed 1 --out sc.json
python3 simulate.py ro_school.json sol_school.json sc.json --outdir results
```

## Reproduce the paper
```
python3 experimente/exp_paper.py
python3 experimente/figs.py
```
`exp_paper.py` runs 775 simulations (20 seeds, English and Romanian scenarios, λ curve, sensitivity) and writes `experimente/results.json`. `figs.py` draws Fig. 1 and Fig. 2.

## Data
Teacher sickness absence, School Workforce in England, reporting year 2025, Department for Education, Open Government Licence v3.0:
https://explore-education-statistics.service.gov.uk/find-statistics/school-workforce-in-england/2025
Download with `python3 fetch_dfe.py`. The raw files are not included.

## License
Code: MIT.
