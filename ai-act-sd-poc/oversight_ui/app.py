import json
import os
import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st
from sqlalchemy import create_engine


BASE_DIR = Path(__file__).resolve().parents[1]


def _has_table(db_path: Path, table: str) -> bool:
	try:
		if not db_path.exists():
			return False
		with sqlite3.connect(str(db_path)) as con:
			cur = con.cursor()
			cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
			return cur.fetchone() is not None
	except Exception:
		return False


def _resolve_db_path() -> Path:
	env_db_url = os.getenv("DB_URL")
	if env_db_url and env_db_url.startswith("sqlite:///"):
		env_path = Path(env_db_url.replace("sqlite:///", ""))
		if env_path.exists():
			return env_path
	candidates = [
		BASE_DIR / "backend" / "governance.db",
		BASE_DIR / "governance.db",
	]
	for candidate in candidates:
		if _has_table(candidate, "decision_logs"):
			return candidate
	for candidate in candidates:
		if candidate.exists():
			return candidate
	return candidates[0]


def _attempt_login(token: str) -> tuple[bool, dict | None, str]:
	token = (token or "").strip()
	if not token:
		return False, None, "Bitte Token eingeben."
	backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
	try:
		resp = requests.post(f"{backend_url}/v1/auth/login", json={"token": token}, timeout=10)
	except Exception as exc:
		return False, None, f"Login-Request fehlgeschlagen: {exc}"
	if resp.status_code == 200:
		return True, resp.json(), ""
	if resp.status_code in (401, 404):
		return False, None, "Login fehlgeschlagen: Token ungültig (401/404)."
	return False, None, f"Login fehlgeschlagen: {resp.status_code}"


def _logout() -> None:
	st.session_state.pop("auth", None)
	st.session_state["login_token"] = ""
	for key in list(st.session_state.keys()):
		if key.startswith("override_reason_") or key.startswith("override_decision_"):
			st.session_state.pop(key)


def _render_sidebar_auth() -> None:
	st.sidebar.header("Zugang")
	auth_state = st.session_state.get("auth")
	if auth_state:
		st.sidebar.success(
			f"Angemeldet als {auth_state.get('user')} ({auth_state.get('role')})",
			icon="✅",
		)
		st.sidebar.button(
			"Abmelden",
			type="primary",
			use_container_width=True,
			on_click=_logout,
			key="sidebar_logout_btn",
		)
	else:
		token_value = st.sidebar.text_input("X-Auth-Token", type="password", key="login_token")
		if st.sidebar.button("Anmelden", type="primary", use_container_width=True, key="sidebar_login_btn"):
			ok, data, message = _attempt_login(token_value)
			if ok and data:
				st.session_state["auth"] = {
					"user": data.get("user"),
					"role": data.get("role"),
					"token": token_value,
				}
				st.session_state["login_token"] = ""
				st.sidebar.success(f"Angemeldet als {data.get('user')} ({data.get('role')})")
			else:
				st.sidebar.error(message)


st.set_page_config(page_title="Oversight Dashboard", layout="wide")

if "auth" not in st.session_state:
	st.session_state["auth"] = None
if "login_token" not in st.session_state:
	st.session_state["login_token"] = ""

header = st.container()
with header:
	left, right = st.columns([7, 3], gap="large")
	with left:
		st.title("REVIEW Queue – Credit Decisions")
		st.caption("Oversight Dashboard für Kreditentscheidungen")
	with right:
		st.markdown("#### Zugang")
		auth_state = st.session_state.get("auth")
		if auth_state:
			st.success(f"Aktiv: {auth_state.get('user')} ({auth_state.get('role')})")
		else:
			st.info("Bitte in der Sidebar anmelden.")

_render_sidebar_auth()

auth = st.session_state.get("auth")
if not auth:
	st.info("Bitte anmelden, um die Oversight-Daten einzusehen.")
	st.stop()

db_path = _resolve_db_path()
engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
query = """
	SELECT id, ts_utc, order_id, customer_id, score, decision,
		   overridden, second_approval, rule_version, data_version,
		   decision_id, thresholds_json, input_json
	FROM decision_logs
	ORDER BY ts_utc DESC
"""

try:
	df = pd.read_sql(query, engine)
except Exception as exc:
	st.error(f"Daten konnten nicht geladen werden: {exc}")
	st.stop()

df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce")
resolved = str(db_path.resolve())
try:
	rel = str(db_path.relative_to(BASE_DIR))
except ValueError:
	rel = str(db_path)
env_caption = os.getenv("DB_URL") or "(default)"
st.caption(
	f"DB: {rel} (resolved: {resolved}) | DB_URL: {env_caption} | User: {auth.get('user')} ({auth.get('role')})"
)

st.sidebar.header("Filter")
review_only = st.sidebar.toggle("Nur REVIEW-Fälle", value=True, key="filter_review")
decision_options = sorted(df["decision"].dropna().unique().tolist())
decision_filter = st.sidebar.multiselect(
	"Entscheidungen",
	decision_options,
	default=decision_options,
	key="filter_decisions",
)
search_text = st.sidebar.text_input("Suche (Order ID oder Kunde)", key="filter_search")
date_from = date_to = None
date_bounds = df["ts_utc"].dropna()
if not date_bounds.empty:
	min_date = date_bounds.min().date()
	max_date = date_bounds.max().date()
	range_value = st.sidebar.date_input(
		"Zeitraum",
		value=(min_date, max_date),
		key="filter_date",
	)
	if isinstance(range_value, (list, tuple)) and len(range_value) == 2:
		date_from, date_to = range_value
	elif range_value:
		date_from = range_value
		date_to = range_value

filtered_df = df.copy()
if review_only:
	filtered_df = filtered_df[filtered_df["decision"] == "REVIEW"]
if decision_filter:
	filtered_df = filtered_df[filtered_df["decision"].isin(decision_filter)]
if search_text:
	term = search_text.strip()
	if term:
		mask = (
			filtered_df["order_id"].fillna("").str.contains(term, case=False)
			| filtered_df["customer_id"].fillna("").str.contains(term, case=False)
		)
		filtered_df = filtered_df[mask]
if date_from and date_to:
	filtered_df = filtered_df[
		(filtered_df["ts_utc"].dt.date >= date_from)
		& (filtered_df["ts_utc"].dt.date <= date_to)
	]

st.subheader("Arbeitsüberblick")
summary_cols = st.columns(4)
summary_cols[0].metric("Fälle (gefiltert)", int(len(filtered_df)))
summary_cols[1].metric("Review offen", int((filtered_df["decision"] == "REVIEW").sum()))
summary_cols[2].metric(
	"Übersteuert",
	int(filtered_df["overridden"].fillna(0).astype(int).sum()),
)
latest_ts = filtered_df["ts_utc"].dropna().max()
if pd.notna(latest_ts):
	latest_val = latest_ts.tz_convert("UTC") if latest_ts.tzinfo else latest_ts.tz_localize("UTC")
	latest_str = latest_val.strftime("%Y-%m-%d %H:%M")
else:
	latest_str = "-"
summary_cols[3].metric("Letztes Update (UTC)", latest_str)

if not filtered_df.empty:
	timeline_source = filtered_df.dropna(subset=["ts_utc"]).copy()
	timeline_source["ts_day"] = timeline_source["ts_utc"].dt.floor("D")
	timeline_counts = (
		timeline_source.groupby(["ts_day", "decision"])
		.size()
		.reset_index(name="count")
	)
	if not timeline_counts.empty:
		chart = alt.Chart(timeline_counts).mark_area(opacity=0.6).encode(
			x=alt.X("ts_day:T", title="Datum"),
			y=alt.Y("count:Q", title="Fälle"),
			color=alt.Color("decision:N", title="Entscheidung"),
			tooltip=[
				alt.Tooltip("ts_day:T", title="Datum"),
				alt.Tooltip("decision:N", title="Entscheidung"),
				alt.Tooltip("count:Q", title="Anzahl"),
			],
		).properties(height=260)
		st.altair_chart(chart, use_container_width=True)

table_col, detail_col = st.columns([3, 2], gap="large")

with table_col:
	st.subheader("Fälle")
	visible_cols = [
		"ts_utc",
		"order_id",
		"customer_id",
		"decision",
		"score",
		"overridden",
		"second_approval",
		"rule_version",
		"data_version",
	]
	table_df = filtered_df[visible_cols].copy() if not filtered_df.empty else filtered_df
	if not table_df.empty:
		table_df["ts_utc"] = table_df["ts_utc"].dt.strftime("%Y-%m-%d %H:%M")
	st.dataframe(table_df, use_container_width=True, height=420)

with detail_col:
	st.subheader("Details & Override")
	if filtered_df.empty:
		st.info("Keine Einträge für die aktuellen Filter.")
	else:
		selection = st.selectbox(
			"Fall auswählen",
			filtered_df["id"].tolist(),
			key="selected_case",
		)
		selected_id = int(selection)
		detail_row = filtered_df[filtered_df["id"] == selected_id].iloc[0]
		ts_info = detail_row["ts_utc"]
		if pd.notna(ts_info):
			ts_display = ts_info.tz_convert("UTC") if ts_info.tzinfo else ts_info.tz_localize("UTC")
			ts_string = ts_display.strftime("%Y-%m-%d %H:%M:%S")
		else:
			ts_string = "-"
		st.markdown(
			f"**decision_id:** `{detail_row.get('decision_id')}`  "+
			f"**Entscheidung:** {detail_row.get('decision')} (Score: {detail_row.get('score')})"
		)
		st.markdown(
			f"**Zeitpunkt (UTC):** {ts_string}  |  **Übersteuert:** {'Ja' if detail_row.get('overridden') else 'Nein'}"
		)
		if detail_row.get("second_approval"):
			st.info("Eintrag mit Vier-Augen-Freigabe markiert.")

		try:
			thresholds_obj = json.loads(detail_row.get("thresholds_json") or "{}")
		except json.JSONDecodeError:
			thresholds_obj = {}
		try:
			input_obj = json.loads(detail_row.get("input_json") or "{}")
		except json.JSONDecodeError:
			input_obj = {}

		tabs = st.tabs(["Inputdaten", "Thresholds", "Verlauf"])
		with tabs[0]:
			st.json(input_obj)
		with tabs[1]:
			st.json(thresholds_obj)
		with tabs[2]:
			history = df[df["decision_id"] == detail_row.get("decision_id")].copy()
			if history.empty:
				st.info("Keine Historie gefunden.")
			else:
				history["ts_utc"] = history["ts_utc"].dt.strftime("%Y-%m-%d %H:%M")
				hist_cols = [
					"ts_utc",
					"decision",
					"overridden",
					"second_approval",
					"score",
				]
				st.dataframe(history[hist_cols], use_container_width=True, height=220)

		base_review = (
			detail_row.get("decision") == "REVIEW"
			and int(detail_row.get("overridden") or 0) == 0
		)
		if base_review:
			order_value = float(input_obj.get("order_value_eur", 0) or 0)
			country_risk = float(input_obj.get("country_risk", 0) or 0)
			needs_four_eyes = order_value >= 50000 or country_risk >= 4
			if needs_four_eyes:
				st.warning("Vier-Augen erforderlich (order_value_eur ≥ 50000 oder country_risk ≥ 4)")
			decision_key = f"override_decision_{selected_id}"
			reason_key = f"override_reason_{selected_id}"
			new_decision = st.radio(
				"Neue Entscheidung",
				options=("ALLOW", "BLOCK"),
				horizontal=True,
				key=decision_key,
			)
			override_reason = st.text_area(
				"Begründung (Pflicht, ≥15 Zeichen)",
				key=reason_key,
				height=120,
			)
			need_admin = needs_four_eyes and auth.get("role") == "reviewer"
			if need_admin:
				st.error("Admin benötigt für Vier-Augen-Fälle.")
			btn_disabled = len(override_reason.strip()) < 15 or need_admin
			if st.button(
				"Override speichern",
				type="primary",
				use_container_width=True,
				disabled=btn_disabled,
				key=f"override_submit_{selected_id}",
			):
				payload = {
					"decision_id": detail_row.get("decision_id"),
					"new_decision": new_decision,
					"override_reason": override_reason.strip(),
				}
				backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
				headers = {"X-Auth-Token": auth.get("token")}
				try:
					resp = requests.post(
						f"{backend_url}/v1/credit/override",
						json=payload,
						headers=headers,
						timeout=10,
					)
				except Exception as exc:
					st.error(f"Request fehlgeschlagen: {exc}")
				else:
					if resp.status_code == 200:
						st.success("Override gespeichert – Dashboard wird aktualisiert.")
						st.session_state.pop(reason_key, None)
						st.session_state.pop(decision_key, None)
						st.experimental_rerun()
					elif resp.status_code in (400, 403, 404, 409):
						content_type = resp.headers.get("content-type", "")
						if content_type.startswith("application/json"):
							detail_msg = resp.json().get("detail", resp.text)
						else:
							detail_msg = resp.text
						st.error(f"Fehler {resp.status_code}: {detail_msg}")
					else:
						st.error(f"Fehler {resp.status_code}: {resp.text}")
		else:
			st.info("Overrides sind nur für offene REVIEW-Basisfälle möglich.")
