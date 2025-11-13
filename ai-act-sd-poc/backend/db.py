from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
import hashlib
import json as _json
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
  second_approval INTEGER DEFAULT 0,
  prev_hash TEXT,
  row_hash TEXT
);
"""

def ensure_schema():
  with engine.begin() as cx:
    cx.exec_driver_sql(DDL)
    # Ensure unique index for base rows ONLY (overridden=0) to allow overrides
    try:
      cx.exec_driver_sql("DROP INDEX IF EXISTS ux_decision_logs_decision_id")
    except Exception:
      pass
    try:
      cx.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_decision_logs_decision_id_base ON decision_logs(decision_id) WHERE overridden=0"
      )
    except Exception:
      # In very old SQLite versions without partial indexes, fall back to application-level check
      pass
    # Ensure second_approval column (legacy safety)
    cols = [r[1] for r in cx.exec_driver_sql("PRAGMA table_info('decision_logs')").fetchall()]
    if 'second_approval' not in cols:
      cx.exec_driver_sql("ALTER TABLE decision_logs ADD COLUMN second_approval INTEGER DEFAULT 0")
    if 'prev_hash' not in cols:
      cx.exec_driver_sql("ALTER TABLE decision_logs ADD COLUMN prev_hash TEXT")
    if 'row_hash' not in cols:
      cx.exec_driver_sql("ALTER TABLE decision_logs ADD COLUMN row_hash TEXT")
    # Immutable log via triggers (block UPDATE/DELETE)
    try:
      cx.exec_driver_sql("""
        CREATE TRIGGER deny_update BEFORE UPDATE ON decision_logs BEGIN
          SELECT RAISE(ABORT, 'immutable log');
        END;
      """)
    except Exception:
      pass
    try:
      cx.exec_driver_sql("""
        CREATE TRIGGER deny_delete BEFORE DELETE ON decision_logs BEGIN
          SELECT RAISE(ABORT, 'immutable log');
        END;
      """)
    except Exception:
      pass

ensure_schema()
def _last_row_hash():
  with engine.begin() as cx:
    row = cx.execute(text("SELECT row_hash FROM decision_logs ORDER BY id DESC LIMIT 1")).fetchone()
    return row[0] if row and row[0] else ""

def _compute_hash(prev_hash: str, payload: dict, ts_utc: str) -> str:
  # Create canonical JSON of payload (excluding prev_hash/row_hash) with sorted keys
  data = {k: v for k, v in payload.items() if k not in ("prev_hash", "row_hash")}
  payload_json = _json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
  h = hashlib.sha256()
  h.update((prev_hash or "").encode("utf-8"))
  h.update(payload_json.encode("utf-8"))
  h.update((ts_utc or "").encode("utf-8"))
  return h.hexdigest()


def log_decision(payload):
  """Insert base decision row (overridden=0) append-only; skip if base already exists."""
  decision_id = payload.get("decision_id")
  ts_utc = payload.get("ts_utc")
  overridden = payload.get("overridden", 0)
  if overridden == 0:
    # Skip if a non-overridden row already exists
    with engine.begin() as cx:
      exists = cx.execute(text("SELECT 1 FROM decision_logs WHERE decision_id=:d AND overridden=0 LIMIT 1"),
                {"d": decision_id}).fetchone()
      if exists:
        return
  # Compute hash chain values
  prev_hash = _last_row_hash()
  row_hash = _compute_hash(prev_hash, payload, ts_utc)
  payload = dict(payload)
  payload["prev_hash"] = prev_hash
  payload["row_hash"] = row_hash
  if overridden == 0:
    with engine.begin() as cx:
      try:
        cx.execute(text(
          """
          INSERT INTO decision_logs
          (decision_id, ts_utc, order_id, customer_id, input_json, score, thresholds_json,
           decision, rule_version, data_version, actor_sys, actor_ux, overridden, override_reason, second_approval,
           prev_hash, row_hash)
          VALUES
          (:decision_id, :ts_utc, :order_id, :customer_id, :input_json, :score, :thresholds_json,
           :decision, :rule_version, :data_version, :actor_sys, :actor_ux, :overridden, :override_reason, :second_approval,
           :prev_hash, :row_hash)
          """
        ), payload)
      except IntegrityError:
        return
  else:
    with engine.begin() as cx:
      cx.execute(text(
        """
        INSERT INTO decision_logs
        (decision_id, ts_utc, order_id, customer_id, input_json, score, thresholds_json,
         decision, rule_version, data_version, actor_sys, actor_ux, overridden, override_reason, second_approval,
         prev_hash, row_hash)
        VALUES
        (:decision_id, :ts_utc, :order_id, :customer_id, :input_json, :score, :thresholds_json,
         :decision, :rule_version, :data_version, :actor_sys, :actor_ux, :overridden, :override_reason, :second_approval,
         :prev_hash, :row_hash)
        """
      ), payload)
    return

def existing_override(decision_id: str, new_decision: str, override_reason: str):
  with engine.begin() as cx:
    row = cx.execute(text(
      """
      SELECT 1 FROM decision_logs
      WHERE decision_id=:d AND overridden=1 AND decision=:dec AND override_reason=:r LIMIT 1
      """
    ), {"d": decision_id, "dec": new_decision, "r": override_reason}).fetchone()
    return row is not None

def fetch_base_decision(decision_id: str):
  """Fetch the base (overridden=0) decision row for a given decision_id.
  Returns a SQLAlchemy Row or None.
  """
  with engine.begin() as cx:
    row = cx.execute(text(
      """
      SELECT id, decision_id, ts_utc, order_id, customer_id,
             input_json, score, thresholds_json,
             decision, rule_version, data_version,
             actor_sys, actor_ux, overridden, override_reason,
             second_approval, prev_hash, row_hash
        FROM decision_logs
       WHERE decision_id = :did AND overridden = 0
       ORDER BY id ASC
       LIMIT 1
      """
    ), {"did": decision_id}).fetchone()
    return row
