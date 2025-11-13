import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path
import sqlite3
import os

# Robust absolute path to governance.db regardless of launch directory
BASE_DIR = Path(__file__).resolve().parents[1]

# Allow explicit override via environment (e.g. DB_URL=sqlite:///C:/.../backend/governance.db)
env_db_url = os.getenv("DB_URL")
if env_db_url and env_db_url.startswith("sqlite:///"):
    # Strip prefix and treat remainder as path
    override_path = Path(env_db_url.replace("sqlite:///", ""))
else:
    override_path = None

_candidates = [
    BASE_DIR / "backend" / "governance.db",  # preferred canonical location
    BASE_DIR / "governance.db",                # legacy root location
]

def _has_table(db_path: Path, table: str) -> bool:
    try:
        if not db_path.exists():
            return False
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        ok = cur.fetchone() is not None
        con.close()
        return ok
    except Exception:
        return False

if override_path:
    DB_PATH = override_path
else:
    # Choose DB: prefer backend file if it exists or has table, else fallback
    ordered = sorted(_candidates, key=lambda p: 0 if p.parent.name=="backend" else 1)
    DB_PATH = next((p for p in ordered if _has_table(p, "decision_logs")), None)
    if DB_PATH is None:
        DB_PATH = next((p for p in ordered if p.exists()), ordered[0])
engine = create_engine(f"sqlite:///{DB_PATH}")

st.set_page_config(page_title="Oversight", layout="wide")
st.title("REVIEW Queue – Credit Decisions")
# Caption: show source DB path and resolved absolute path
resolved = str(DB_PATH.resolve())
try:
    rel = str(DB_PATH.relative_to(BASE_DIR))
except Exception:
    rel = str(DB_PATH)
env_caption = os.getenv("DB_URL") or "(default)"
st.caption(f"DB: {rel} (resolved: {resolved}) | DB_URL: {env_caption}")

df = pd.read_sql(
    """
    SELECT id, ts_utc, order_id, customer_id, score, decision, rule_version,
        data_version, decision_id, thresholds_json
    FROM decision_logs
    ORDER BY ts_utc DESC
    """,
    engine,
)

# Filter auf REVIEW-Fälle
review_only = st.toggle("Nur REVIEW-Fälle zeigen", value=True)
if review_only:
    df = df[df["decision"]=="REVIEW"]

visible_cols = [
    "ts_utc",
    "order_id",
    "customer_id",
    "score",
    "decision",
    "rule_version",
    "data_version",
]
st.dataframe(df[visible_cols] if not df.empty else df, use_container_width=True, height=360)

row = st.selectbox("Fall wählen (id)", df["id"]) if not df.empty else None
if row:
    detail = pd.read_sql(f"SELECT * FROM decision_logs WHERE id={int(row)}", engine).iloc[0]
    st.subheader(f"Fall #{row} – Entscheidung: {detail['decision']} – Score: {detail['score']}")
    with st.expander("Details", expanded=True):
        st.markdown("- decision_id: `" + str(detail.get("decision_id", "")) + "`")
        st.markdown("- thresholds_json:")
        st.code(detail.get("thresholds_json", "{}"), language="json")
        st.markdown("- input_json:")
        st.code(detail.get("input_json", "{}"), language="json")
