import json
import os
import sqlite3
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st
from sqlalchemy import create_engine


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
	sys.path.append(str(BASE_DIR))

from tools.classifier_metrics import (
	compute_calibration_bins,
	compute_classifier_metrics,
	load_classifier_csv,
)


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


def _compute_governance_overview(log_df: pd.DataFrame) -> dict:
	if log_df.empty:
		return {
			"mix_counts": {},
			"mix_pct": {},
			"base_total": 0,
			"override_pct": 0.0,
			"four_eyes_pct": 0.0,
			"queue_mean_min": None,
			"queue_p95_min": None,
		}

	work = log_df.copy()
	work["overridden_flag"] = work["overridden"].fillna(0).astype(int)
	base = work[work["overridden_flag"] == 0]
	total_base = len(base)
	mix_counts = base["decision"].value_counts().to_dict()
	mix_pct = {k: (v / total_base * 100.0) if total_base else 0.0 for k, v in mix_counts.items()}
	overrides = work[work["overridden_flag"] == 1]
	override_pct = (len(overrides) / total_base * 100.0) if total_base else 0.0
	four_eyes_pct = (
		overrides["second_approval"].fillna(0).astype(int).mean() * 100.0
		if not overrides.empty
		else 0.0
	)
	review_base = base[base["decision"] == "REVIEW"].rename(columns={"ts_utc": "ts_base"})
	queue_mean_min = None
	queue_p95_min = None
	if not review_base.empty and not overrides.empty:
		override_times = (
			overrides.sort_values("ts_utc")
			.drop_duplicates("decision_id", keep="last")
			.rename(columns={"ts_utc": "ts_override"})[["decision_id", "ts_override"]]
		)
		merged = review_base.merge(override_times, on="decision_id", how="left")
		merged = merged.dropna(subset=["ts_override"])
		if not merged.empty:
			durations = (merged["ts_override"] - merged["ts_base"]).dt.total_seconds() / 60.0
			queue_mean_min = float(durations.mean())
			queue_p95_min = float(durations.quantile(0.95))

	return {
		"mix_counts": mix_counts,
		"mix_pct": mix_pct,
		"base_total": total_base,
		"override_pct": override_pct,
		"four_eyes_pct": four_eyes_pct,
		"queue_mean_min": queue_mean_min,
		"queue_p95_min": queue_p95_min,
	}


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
	st.session_state["clear_login_token"] = True
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
		if st.session_state.get("clear_login_token"):
			st.session_state["login_token"] = ""
			st.session_state["clear_login_token"] = False
		with st.sidebar.form("login_form", clear_on_submit=False):
			token_value = st.text_input("X-Auth-Token", type="password", key="login_token")
			submitted = st.form_submit_button(
				"Anmelden",
				type="primary",
				use_container_width=True,
			)
		if submitted:
			ok, data, message = _attempt_login(token_value)
			if ok and data:
				st.session_state["auth"] = {
					"user": data.get("user"),
					"role": data.get("role"),
					"token": token_value,
				}
				st.session_state["clear_login_token"] = True
				st.sidebar.success(f"Angemeldet als {data.get('user')} ({data.get('role')})")
			else:
				st.sidebar.error(message)


st.set_page_config(page_title="Oversight Dashboard", layout="wide")

if "auth" not in st.session_state:
	st.session_state["auth"] = None
if "login_token" not in st.session_state:
	st.session_state["login_token"] = ""
if "clear_login_token" not in st.session_state:
	st.session_state["clear_login_token"] = False

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
st.markdown("🧭 **Navigation:** Oversight › Review Queue › Audit Logs › Scores & Metrics › API Input")

export_target = BASE_DIR / "data" / "abb_6_1_decision_logs.csv"
DEFAULT_CLASSIFIER_CSV = BASE_DIR / "data" / "classifier_results_demo.csv"
classifier_demo_csv = BASE_DIR / "docs" / "examples" / "classifier_output_example.csv"
st.sidebar.markdown("---")
st.sidebar.subheader("Audit Log Snapshot")
if export_target.exists():
	st.sidebar.success("CSV geladen – Ansicht im Tab 'Audit Logs'.")
else:
	st.sidebar.warning("Export noch nicht vorhanden. Bitte tools/export_log.py ausführen.")

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

# Audit-CSV einlesen (Anzeige erfolgt später im Tab)
audit_df = None
if export_target.exists():
	try:
		audit_df = pd.read_csv(export_target, comment="#")
		if "ts_utc" in audit_df.columns:
			audit_df["ts_utc"] = pd.to_datetime(audit_df["ts_utc"], errors="coerce")
	except Exception as exc:
		audit_df = None
		st.warning(f"Export konnte nicht geladen werden: {exc}")

review_tab, audit_tab, metrics_tab, api_tab = st.tabs([
	"Review Queue",
	"Audit Logs",
	"Scores & Metrics",
	"API Input",
])

with review_tab:
	st.subheader("Arbeitsüberblick")
	overview_df = filtered_df if not filtered_df.empty else df
	overview_scope = "Filter" if not filtered_df.empty else "Gesamtbestand"
	if filtered_df.empty and not df.empty:
		st.caption("Keine Treffer für die aktuellen Filter – zeige Gesamtbestand.")
	summary_cols = st.columns(4)
	overview_len = int(len(overview_df))
	summary_cols[0].metric(f"Fälle ({overview_scope})", overview_len)
	if overview_len:
		review_open = int((overview_df["decision"] == "REVIEW").sum())
		override_cnt = int(overview_df["overridden"].fillna(0).astype(int).sum())
		latest_ts = overview_df["ts_utc"].dropna().max()
		if pd.notna(latest_ts):
			latest_val = latest_ts.tz_convert("UTC") if latest_ts.tzinfo else latest_ts.tz_localize("UTC")
			latest_str = latest_val.strftime("%Y-%m-%d %H:%M")
		else:
			latest_str = "-"
	else:
		review_open = 0
		override_cnt = 0
		latest_str = "-"
	summary_cols[1].metric("Review offen", review_open)
	summary_cols[2].metric("Übersteuert", override_cnt)
	summary_cols[3].metric("Letztes Update (UTC)", latest_str)

	if not overview_df.empty:
		timeline_source = overview_df.dropna(subset=["ts_utc"]).copy()
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
	else:
		st.info("Keine Einträge im aktuellen Datenbestand.")

	st.markdown("### Arbeitsliste")
	table_col, detail_col = st.columns([3, 2], gap="large")

	with table_col:
		st.caption("Fokus auf REVIEW-Fälle – sortiert nach Zeit")
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
		st.caption("Details & Override-Workflow")
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
				f"**decision_id:** `{detail_row.get('decision_id')}`  "
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

			with audit_tab:
				st.subheader("Audit Logs – CSV Snapshot")
				if audit_df is None:
					st.info("Kein Export geladen. Bitte tools/export_log.py ausführen und Seite neu laden.")
				elif audit_df.empty:
					st.warning("CSV vorhanden, aber ohne Einträge.")
				else:
					col_a, col_b, col_c, col_d = st.columns(4)
					col_a.metric("Einträge", len(audit_df))
					if "overridden" in audit_df.columns:
						col_b.metric("Overrides", int(audit_df["overridden"].fillna(0).astype(int).sum()))
					if "decision" in audit_df.columns:
						review_share = (
							(audit_df["decision"] == "REVIEW").mean() * 100
							if len(audit_df)
							else 0
						)
						col_c.metric("Review-Anteil", f"{review_share:.1f}%")
					if "ts_utc" in audit_df.columns and audit_df["ts_utc"].notna().any():
						last_ts = audit_df["ts_utc"].dropna().max()
						if isinstance(last_ts, pd.Timestamp):
							col_d.metric("Letzter Eintrag", last_ts.strftime("%Y-%m-%d %H:%M"))

					view_cols = [
						"ts_utc",
						"decision_id",
						"decision",
						"overridden",
						"second_approval",
						"actor_sys",
						"actor_ux",
						"override_reason",
					]
					available_cols = [c for c in view_cols if c in audit_df.columns]
					view_df = audit_df[available_cols].copy() if available_cols else audit_df.copy()
					if "ts_utc" in view_df.columns:
						view_df["ts_utc"] = view_df["ts_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")
					for text_col in ["actor_sys", "actor_ux", "override_reason"]:
						if text_col in view_df.columns:
							view_df[text_col] = view_df[text_col].fillna("")
					if "overridden" in view_df.columns:
						view_df["overridden"] = (
							view_df["overridden"].fillna(0).astype(int).map({0: "Nein", 1: "Ja"}).fillna("")
						)
					if "second_approval" in view_df.columns:
						view_df["second_approval"] = (
							view_df["second_approval"].fillna(0).astype(int).map({0: "Nein", 1: "Ja"}).fillna("")
						)
					view_df = view_df.rename(
						columns={
							"ts_utc": "Zeit (UTC)",
							"decision_id": "decision_id",
							"decision": "Entscheidung",
							"overridden": "Override",
							"second_approval": "Vier-Augen",
							"actor_sys": "System",
							"actor_ux": "Bearbeiter",
							"override_reason": "Begründung",
						}
					)
					view_df = view_df.reset_index(drop=True)
					st.dataframe(view_df.head(150), use_container_width=True, height=420)
					st.caption("Quelle: data/abb_6_1_decision_logs.csv – Ansicht für Audits & Screenshots")

			with metrics_tab:
				st.subheader("Scores & Metrics Evaluation")
				st.caption("Klassifikator unterstützt die deterministische Logik – Upload möglich, Standard-Datei als Fallback.")
				classifier_file = st.file_uploader(
					"Classifier-Output als CSV laden (optional)",
					type=["csv"],
					key="classifier_output_upload",
					help="Wenn nichts hochgeladen wird, wird die Standard-Datei aus data/ verwendet.",
				)

				classifier_records: list = []
				classifier_source = None
				if classifier_file is not None:
					try:
						classifier_records = load_classifier_csv(classifier_file)
						classifier_source = "Upload"
					except Exception as exc:
						st.error(f"Upload konnte nicht verarbeitet werden: {exc}")
				elif DEFAULT_CLASSIFIER_CSV.exists():
					try:
						classifier_records = load_classifier_csv(DEFAULT_CLASSIFIER_CSV)
						classifier_source = f"Default: {DEFAULT_CLASSIFIER_CSV.name}"
					except Exception as exc:
						st.warning(f"Default-CSV konnte nicht geladen werden: {exc}")
				elif classifier_demo_csv.exists():
					try:
						classifier_records = load_classifier_csv(classifier_demo_csv)
						classifier_source = f"Demo: {classifier_demo_csv.name}"
					except Exception as exc:
						st.warning(f"Demo-CSV konnte nicht geladen werden: {exc}")
				else:
					st.info("Noch keine Klassifizierer-Ergebnisse vorhanden. Zeige nur deterministische KPIs.")

				if classifier_records and classifier_source:
					st.caption(f"Quelle: {classifier_source} – Samples: {len(classifier_records)}")

				if classifier_records:
					metrics_bundle = compute_classifier_metrics(classifier_records, positive_label="REVIEW")
					review_metrics = metrics_bundle["per_class"].get("REVIEW")
					binary_metrics = metrics_bundle.get("binary", {})
					summary_cols = st.columns(4)
					summary_cols[0].metric("Samples", metrics_bundle["total"])
					summary_cols[1].metric("Macro F1", f"{metrics_bundle['macro_f1']*100:.1f}%")
					if review_metrics:
						summary_cols[2].metric("Precision REVIEW", f"{review_metrics['precision']*100:.1f}%")
						summary_cols[3].metric("Recall REVIEW", f"{review_metrics['recall']*100:.1f}%")
					else:
						summary_cols[2].metric("Precision REVIEW", "n/a")
						summary_cols[3].metric("Recall REVIEW", "n/a")

					class_rows = []
					for label in metrics_bundle["labels"]:
						count = metrics_bundle["class_distribution"].get(label, 0)
						share = (count / metrics_bundle["total"] * 100.0) if metrics_bundle["total"] else 0.0
						class_rows.append({"Klasse": label, "Anzahl": count, "Anteil %": f"{share:.1f}"})
					if class_rows:
						st.dataframe(pd.DataFrame(class_rows), use_container_width=True, height=220)

					matrix_df = pd.DataFrame.from_dict(metrics_bundle["matrix"], orient="index")
					matrix_df = matrix_df.reindex(index=metrics_bundle["labels"], columns=metrics_bundle["labels"]).fillna(0).astype(int)
					st.markdown("#### Confusion Matrix")
					st.dataframe(matrix_df, use_container_width=True, height=260)

					per_class_df = pd.DataFrame.from_dict(metrics_bundle["per_class"], orient="index")
					if not per_class_df.empty:
						per_class_df = per_class_df.loc[metrics_bundle["labels"]]
						for col in ["precision", "recall", "f1"]:
							per_class_df[col] = per_class_df[col] * 100.0
						per_class_df = per_class_df.rename(columns={
							"precision": "Precision %",
							"recall": "Recall %",
							"f1": "F1 %",
						})
						per_class_df = per_class_df.reset_index().rename(columns={"index": "Klasse"})
						st.dataframe(per_class_df, use_container_width=True, height=260)

					if binary_metrics:
						binary_cols = st.columns(3)
						binary_cols[0].metric("Accuracy", f"{binary_metrics.get('accuracy', 0.0)*100:.1f}%")
						binary_cols[1].metric("F1 REVIEW", f"{binary_metrics.get('f1', 0.0)*100:.1f}%")
						binary_cols[2].metric(
							"TP/FP",
							f"{binary_metrics.get('tp', 0)}/{binary_metrics.get('fp', 0)}",
						)

					calibration_bins = compute_calibration_bins(classifier_records, positive_label="REVIEW")
					if calibration_bins:
						st.markdown("#### Calibration (Review Probability)")
						calib_df = pd.DataFrame(calibration_bins)
						calib_long = calib_df.melt(
							id_vars=["bin_label", "count"],
							value_vars=["predicted_rate", "observed_rate"],
							var_name="Serie",
							value_name="Rate",
						)
						calib_chart = alt.Chart(calib_long).mark_line(point=True).encode(
							x=alt.X("bin_label:N", title="Wahrscheinlichkeits-Bin"),
							y=alt.Y("Rate:Q", title="Review-Rate (%)"),
							color=alt.Color("Serie:N", title=""),
							tooltip=["bin_label", "Rate", "Serie", "count"],
						).properties(height=280)
						st.altair_chart(calib_chart, use_container_width=True)
						st.dataframe(
							calib_df[["bin_label", "count", "predicted_rate", "observed_rate"]],
							use_container_width=True,
							height=220,
						)
					else:
						st.info("Keine review_probability-Spalte gefunden – Kalibrierung übersprungen.")
				else:
					st.info("Noch keine Klassifizierer-Ergebnisse vorhanden. Zeige nur deterministische KPIs.")

				st.markdown("#### Governance-KPIs (Oversight)")
				gov = _compute_governance_overview(df)
				mix_rows = []
				for label in ["ALLOW", "REVIEW", "BLOCK"]:
					mix_rows.append(
						{
							"Entscheidung": label,
							"Anzahl": gov["mix_counts"].get(label, 0),
							"Anteil %": f"{gov['mix_pct'].get(label, 0.0):.1f}",
						}
					)
				st.dataframe(pd.DataFrame(mix_rows), use_container_width=True, height=200)
				g_cols = st.columns(4)
				g_cols[0].metric("Base-Fälle", gov["base_total"])
				g_cols[1].metric("Override-Rate", f"{gov['override_pct']:.1f}%")
				g_cols[2].metric("Vier-Augen", f"{gov['four_eyes_pct']:.1f}%")
				queue_p95 = f"{gov['queue_p95_min']:.1f} Min" if gov["queue_p95_min"] is not None else "n/a"
				g_cols[3].metric("Review-Zeit p95", queue_p95)
				queue_mean = f"{gov['queue_mean_min']:.1f} Min" if gov["queue_mean_min"] is not None else "n/a"
				st.caption(f"Ø Review-Zeit: {queue_mean}")

	with api_tab:
		st.subheader("API Input & Thresholds")
		selected_case_id = st.session_state.get("selected_case")
		if not selected_case_id:
			st.info("Bitte zuerst im Tab 'Review Queue' einen Fall auswählen.")
		else:
			try:
				selected_case_id = int(selected_case_id)
			except (TypeError, ValueError):
				st.error("Ausgewählte Fall-ID ist ungültig. Bitte erneut wählen.")
			else:
				case_df = df[df["id"] == selected_case_id]
				if case_df.empty:
					st.warning("Fall nicht mehr im aktuellen Datensatz. Bitte Ansicht aktualisieren.")
				else:
					case_row = case_df.iloc[0]
					try:
						api_input = json.loads(case_row.get("input_json") or "{}")
					except json.JSONDecodeError:
						api_input = {}
					try:
						thresholds_data = json.loads(case_row.get("thresholds_json") or "{}")
					except json.JSONDecodeError:
						thresholds_data = {}

					st.markdown("#### Request Body (POST /v1/credit/decision)")
					st.caption("Payload inklusive aller Attribute, die vom Backend verarbeitet wurden.")
					if api_input:
						st.json(api_input)
					else:
						st.info("Keine Inputdaten im Log gespeichert.")

					st.markdown("#### Thresholds & Regelparameter")
					st.caption("Konfigurationswerte, die bei der Bewertung dieses Falls aktiv waren.")
					if thresholds_data:
						st.json(thresholds_data)
					else:
						st.info("Keine Threshold-Daten für diesen Fall vorhanden.")

