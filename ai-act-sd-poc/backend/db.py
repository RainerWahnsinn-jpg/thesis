from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
import os

DB_URL = os.getenv("DB_URL", "sqlite:///./governance.db")
engine = create_engine(DB_URL, future=True)

DDL = """
CREATE TABLE IF NOT EXISTS decision_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  decision_id TEXT NOT NULL,
  ts_utc TEXT NOT NULL,
  order_id TEXT, customer_id TEXT,
  input_json TEXT NOT NULL,
  score INTEGER NOT NULL,
  thresholds_json TEXT NOT NULL,
  decision TEXT NOT NULL,
  rule_version TEXT NOT NULL,
  data_version TEXT NOT NULL,
  actor_sys TEXT NOT NULL,
  actor_ux TEXT,
  overridden INTEGER DEFAULT 0,
  override_reason TEXT,
  second_approval INTEGER DEFAULT 0
);
"""

def ensure_schema():
    with engine.begin() as cx:
        cx.exec_driver_sql(DDL)
        # Unique constraint on decision_id via index (idempotent)
        cx.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_decision_logs_decision_id ON decision_logs(decision_id)"
        )
        # Add column second_approval if missing (SQLite: check pragma, then alter)
        cols = [r[1] for r in cx.exec_driver_sql("PRAGMA table_info('decision_logs')").fetchall()]
        if 'second_approval' not in cols:
            cx.exec_driver_sql("ALTER TABLE decision_logs ADD COLUMN second_approval INTEGER DEFAULT 0")

ensure_schema()

def log_decision(payload):
  try:
    with engine.begin() as cx:
      cx.execute(text(
        """
        INSERT INTO decision_logs
        (decision_id, ts_utc, order_id, customer_id, input_json, score, thresholds_json,
         decision, rule_version, data_version, actor_sys, actor_ux, overridden, override_reason)
        VALUES
        (:decision_id, :ts_utc, :order_id, :customer_id, :input_json, :score, :thresholds_json,
         :decision, :rule_version, :data_version, :actor_sys, :actor_ux, :overridden, :override_reason)
        """
      ), payload)
  except IntegrityError:
    # Append-only: if the same decision_id already exists, do nothing
    pass
