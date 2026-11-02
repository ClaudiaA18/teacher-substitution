import os
import datetime as dt

import sqlalchemy as sa

URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://localhost/orar")
meta = sa.MetaData()

instances = sa.Table(
    "instances", meta,
    sa.Column("name", sa.String, primary_key=True),
    sa.Column("raw", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime, default=dt.datetime.now),
)
teachers = sa.Table(
    "teachers", meta,
    sa.Column("instance", sa.String, sa.ForeignKey("instances.name", ondelete="CASCADE"), primary_key=True),
    sa.Column("teacher_id", sa.String, primary_key=True),
    sa.Column("name", sa.String),
    sa.Column("subjects", sa.JSON),
    sa.Column("related", sa.JSON),
    sa.Column("max_per_day", sa.Integer),
)
timetable = sa.Table(
    "timetable", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("instance", sa.String, sa.ForeignKey("instances.name", ondelete="CASCADE"), index=True),
    sa.Column("lesson_id", sa.String),
    sa.Column("subject", sa.String),
    sa.Column("teacher_id", sa.String),
    sa.Column("day", sa.Integer),
    sa.Column("period", sa.Integer),
    sa.Column("room", sa.String),
)
absences = sa.Table(
    "absences", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("instance", sa.String, sa.ForeignKey("instances.name", ondelete="CASCADE"), index=True),
    sa.Column("date", sa.Date, index=True),
    sa.Column("teacher_id", sa.String),
    sa.Column("created_at", sa.DateTime, default=dt.datetime.now),
    sa.UniqueConstraint("instance", "date", "teacher_id"),
)
substitutions = sa.Table(
    "substitutions", meta,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("instance", sa.String, sa.ForeignKey("instances.name", ondelete="CASCADE"), index=True),
    sa.Column("date", sa.Date, index=True),
    sa.Column("period", sa.Integer),
    sa.Column("lesson_id", sa.String),
    sa.Column("absent_teacher", sa.String),
    sa.Column("substitute", sa.String),
    sa.Column("kind", sa.String),
    sa.Column("score", sa.Float),
    sa.Column("method", sa.String),
    sa.Column("created_at", sa.DateTime, default=dt.datetime.now),
    sa.UniqueConstraint("instance", "date", "lesson_id", "period"),
)
dfe_absence = sa.Table(
    "dfe_absence", meta,
    sa.Column("time_period", sa.Integer, primary_key=True),
    sa.Column("school_urn", sa.BigInteger, primary_key=True),
    sa.Column("school_name", sa.String),
    sa.Column("la_name", sa.String),
    sa.Column("region_name", sa.String),
    sa.Column("school_type", sa.String, index=True),
    sa.Column("total_teachers_taking_absence", sa.Float),
    sa.Column("percentage_taking_absence", sa.Float),
    sa.Column("total_number_of_days_lost", sa.Float),
    sa.Column("average_number_of_days_taken", sa.Float),
    sa.Column("average_number_of_days_all_teachers", sa.Float),
)
forecast = sa.Table(
    "forecast", meta,
    sa.Column("model", sa.String, primary_key=True),
    sa.Column("time_period", sa.Integer, primary_key=True),
    sa.Column("school_urn", sa.BigInteger, primary_key=True),
    sa.Column("school_type", sa.String, index=True),
    sa.Column("region_name", sa.String),
    sa.Column("pred_days", sa.Float),
    sa.Column("p_daily", sa.Float),
)
forecast_metrics = sa.Table(
    "forecast_metrics", meta,
    sa.Column("model", sa.String, primary_key=True),
    sa.Column("test_year", sa.Integer, primary_key=True),
    sa.Column("scope", sa.String, primary_key=True),
    sa.Column("mae", sa.Float),
    sa.Column("rmse", sa.Float),
    sa.Column("n", sa.Integer),
)
forecast_series = sa.Table(
    "forecast_series", meta,
    sa.Column("model", sa.String, primary_key=True),
    sa.Column("scope", sa.String, primary_key=True),
    sa.Column("time_period", sa.Integer, primary_key=True),
    sa.Column("yhat", sa.Float),
    sa.Column("lo", sa.Float),
    sa.Column("hi", sa.Float),
)
forecast_series_metrics = sa.Table(
    "forecast_series_metrics", meta,
    sa.Column("model", sa.String, primary_key=True),
    sa.Column("scope", sa.String, primary_key=True),
    sa.Column("mae", sa.Float),
    sa.Column("n", sa.Integer),
)


def engine(url=None):
    return sa.create_engine(url or URL, future=True)


def init(eng):
    meta.create_all(eng)
