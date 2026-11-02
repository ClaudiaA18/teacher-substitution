# HSTT – CP-SAT (terminal)

## Instalare
```
pip install ortools
```

## Fișiere
| Fișier | Rol |
|---|---|
| `ro_toy.json` | instanța (format JSON) |
| `validate_instance.py` | verifică datele înainte de rezolvare |
| `tt_core.py` | încărcare, evaluare, alocare săli, afișare (comun pentru CP-SAT și SA) |
| `solve_cpsat.py` | modelul CP-SAT |

## Rulare
```
python3 validate_instance.py ro_toy.json
python3 solve_cpsat.py ro_toy.json
python3 solve_cpsat.py ro_toy.json --time 120 --seed 1 --teachers --out sol.json
```

| Opțiune | Implicit | Rol |
|---|---|---|
| `--time` | 60 | limită de timp (s) |
| `--workers` | 8 | fire de execuție |
| `--seed` | 42 | reproductibilitate |
| `--teachers` | – | afișează și orarul profesorilor |
| `--log` | – | log-ul solverului |
| `--out` | `solution_cpsat.json` | soluția salvată |

## Ieșire
Status, obiectiv și bound, încălcări tari (trebuie să fie 0), componentele penalizării, orarul pe clase, plus fișierul JSON cu soluția.

## Simulated annealing
```
python3 solve_sa.py ro_toy.json
python3 solve_sa.py ro_toy.json --time 60 --seed 3 --log 5
python3 solve_sa.py ro_toy.json --init solution_cpsat.json --out sol_hybrid.json
```

| Opțiune | Implicit | Rol |
|---|---|---|
| `--time` | 60 | limită de timp (s) |
| `--seed` | 42 | reproductibilitate |
| `--init` | – | pornește din soluția CP-SAT (hibrid) |
| `--hw` | 1000 | pondere încălcări tari |
| `--t0` / `--tend` | auto / 0.05 | temperatura inițială / finală |
| `--swap` | 0.5 | probabilitatea mutării de tip swap |
| `--log` | 0 | afișează progresul la fiecare N secunde |
| `--out` | `solution_sa.json` | soluția + istoric convergență |

Inițializare greedy, mutări move/swap, răcire geometrică pe timp. Același evaluator ca CP-SAT.

## Suplinire (scenarii + alocare)
```
pip install scipy
python3 gen_scenarios.py ro_toy.json --level median --spell 2
python3 simulate.py ro_toy.json solution_cpsat.json scenarios.json --show-day 5
```

| Script | Rol |
|---|---|
| `gen_scenarios.py` | zile de absență calibrate pe DfE: `--level median/p90/peak/pre_covid` sau `--p`, `--spell` (durata medie, zile), `--days` |
| `substitute.py` | candidați, scor de potrivire, metode: `greedy`, `hungarian`, `cpsat` |
| `simulate.py` | rulează metodele pe toate zilele; `--fair` (pondere echitate CP-SAT), `--weights` (JSON cu ponderi), `--show-day` |

Ieșire: `results/sim_summary.csv` (acoperire, aceeași specialitate, înrudită, supraveghere, ore de predare recuperate, deplasări, ferestre, Gini, timp) și `results/sim_days.csv`.

Calificări în instanță: `teachers[].subjects`, `teachers[].related`; `substitution.max_subs_per_day`.

## Aplicație grafică + PostgreSQL

### 1. PostgreSQL (o singură dată)
Postgres.app: postgresapp.com → descarcă → mută în Applications → deschide → **Initialize**.
```
echo 'export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile
createdb orar
```

### 2. Pachete
```
pip install -r requirements.txt
```
Dacă `lightgbm`/`xgboost` dau eroare `libomp`: `brew install libomp` (modelul `hist_gb` din scikit-learn merge oricum).

### 3. Import date + modele
```
python3 import_data.py --instance ro_toy.json --solution solution_cpsat.json
python3 import_data.py --dfe data/dfe/2025/data/sickness_absence_teachers_2010_2025_sch.csv
python3 forecast.py
```

### 4. Pornire
```
streamlit run app.py
```

| Tab | Ce face |
|---|---|
| Suplinire | alegi data și profesorii absenți → înlocuitori propuși (modificabili) → salvare în bază |
| Orar | orarul pe clasă sau profesor |
| Profesori | editare specialitate / discipline înrudite / max. ore |
| Istoric | supliniri salvate, echitate (Gini), export CSV |
| Prognoză și simulare | date DfE, evaluarea modelelor, probabilitate de absență prognozată, simulare an școlar |

Altă bază: `export DATABASE_URL="postgresql+psycopg2://user:parola@host/orar"`.

## Școală mare (12 clase) + prognoză 2025/26 – 2026/27
```
pip install prophet
python3 gen_school.py --per-profile 1          # 12 clase (IX–XII × mate-info/științe/filologie), ~32 profesori
python3 solve_cpsat.py ro_school.json --time 120 --out sol_school.json
python3 import_data.py --instance ro_school.json --solution sol_school.json
python3 forecast.py                            # pe școli, LightGBM/XGBoost/HistGB, 2 ani înainte
python3 forecast_trend.py                      # serie: Prophet, ARIMA, Holt, naive (backtest + interval 80%)
streamlit run app.py
```
`gen_school.py --per-profile 2` → 24 clase. Orele pe discipline sunt aproximative (structura planurilor-cadru), de verificat cu planurile oficiale.
