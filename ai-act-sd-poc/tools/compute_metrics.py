"""Compute metrics snapshot from an audit log (JSONL).
Stdlib only. Default input: docs/examples/audit_log_example.jsonl
Output: data/metrics_snapshot.csv with required columns.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG = BASE_DIR/"docs"/"examples"/"audit_log_example.jsonl"
OUT_FILE = BASE_DIR/"data"/"metrics_snapshot.csv"

COLUMNS = [
    "batch_id","total","allow","review","block","allow_pct","review_pct","block_pct",
    "override_total","override_pct","second_approval_pct",
    "log_completeness_pct","determinism_consistency_pct",
    "p50_latency_ms","p95_latency_ms",
    "violations_monotonicity","violations_threshold_coherence",
    "edge_band_pct","notes"
]

REQUIRED_COMMON = [
    "event","decision_id","request","response","rule_version","data_version","service_version","timestamp_utc","actor_sys"
]
REQUIRED_RESPONSE_CREDIT = ["decision","score","thresholds"]
REQ_THRESH_KEYS = ["allow_max","review_range","block_min"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--log", type=str, default=str(DEFAULT_LOG), help="Path to JSONL audit log")
    p.add_argument("--batch", type=str, default="demo1")
    p.add_argument("--out", type=str, default=str(OUT_FILE))
    return p.parse_args()


def load_log(path: Path) -> List[Dict[str, Any]]:
    events = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def pct(num: int, den: int) -> float:
    return (num/den*100.0) if den else 0.0


def latency_percentiles(values: List[float]) -> Tuple[str,str]:
    if not values:
        return ("NA","NA")
    values = sorted(values)
    p50 = values[int(0.5*(len(values)-1))]
    p95 = values[int(0.95*(len(values)-1))]
    return (f"{p50:.0f}", f"{p95:.0f}")


def check_completeness(ev: Dict[str, Any]) -> bool:
    # Check required keys
    for k in REQUIRED_COMMON:
        if k not in ev:
            return False
    if ev["event"] == "credit.decision":
        for k in REQUIRED_RESPONSE_CREDIT:
            if k not in ev["response"]:
                return False
        th = ev["response"].get("thresholds", {})
        if not all(k in th for k in REQ_THRESH_KEYS):
            return False
    if ev["event"] == "override.apply":
        if not ev.get("override_reason") or len(str(ev.get("override_reason"))) < 15:
            return False
        if not ev.get("actor_ux"):
            return False
        if ev.get("second_approval") is not True:
            return False
    return True


def decision_from_score(score: float, th: Dict[str, Any]) -> str:
    allow_max = th.get("allow_max")
    review_lo, review_hi = th.get("review_range", [None, None])
    block_min = th.get("block_min")
    if score <= allow_max:
        return "ALLOW"
    if review_lo is not None and review_lo <= score <= review_hi:
        return "REVIEW"
    if score >= block_min:
        return "BLOCK"
    # fallback
    return "ALLOW"


def main():
    args = parse_args()
    log_path = Path(args.log)
    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True)

    events = load_log(log_path)

    credit_events = [e for e in events if e.get("event") == "credit.decision"]
    override_events = [e for e in events if e.get("event") == "override.apply"]

    total = len(credit_events)
    allow = sum(1 for e in credit_events if e.get("response",{}).get("decision") == "ALLOW")
    review = sum(1 for e in credit_events if e.get("response",{}).get("decision") == "REVIEW")
    block = sum(1 for e in credit_events if e.get("response",{}).get("decision") == "BLOCK")

    allow_pct = pct(allow,total)
    review_pct = pct(review,total)
    block_pct = pct(block,total)

    override_total = len(override_events)
    override_pct = pct(override_total,total)
    second_approval_true = sum(1 for e in override_events if e.get("second_approval") is True)
    second_approval_pct = pct(second_approval_true, override_total) if override_total else 0.0

    compl = sum(1 for e in (credit_events + override_events) if check_completeness(e))
    denom = len(credit_events) + len(override_events)
    log_completeness_pct = pct(compl, denom) if denom else 0.0

    # Determinism: same request JSON should yield same decision
    decisions_by_req = {}
    inconsistent = 0
    for e in credit_events:
        req = e.get("request", {})
        req_key = json.dumps(req, sort_keys=True)
        dec = e.get("response",{}).get("decision")
        prev = decisions_by_req.setdefault(req_key, dec)
        if prev != dec:
            inconsistent += 1
    determinism_consistency_pct = 100.0 if inconsistent == 0 else max(0.0, 100.0 - 100.0*inconsistent/ max(1,total))

    # Latencies
    lat = [float(e.get("duration_ms")) for e in credit_events if isinstance(e.get("duration_ms"), (int,float))]
    p50_latency_ms, p95_latency_ms = latency_percentiles(lat)

    # Violations: threshold coherence
    violations_threshold_coherence = 0
    for e in credit_events:
        resp = e.get("response", {})
        score = resp.get("score")
        th = resp.get("thresholds", {})
        dec = resp.get("decision")
        expected = decision_from_score(score, th)
        if expected != dec:
            violations_threshold_coherence += 1

    # Monotonicity heuristic (no strict check in MVP)
    violations_monotonicity = 0

    # Edge band: within ±5 around lower boundary of review_range
    edge_cnt = 0
    for e in credit_events:
        resp = e.get("response", {})
        score = resp.get("score")
        th = resp.get("thresholds", {})
        review_lo = th.get("review_range", [None, None])[0]
        if review_lo is None:
            continue
        if (review_lo - 5) <= float(score) <= (review_lo + 5):
            edge_cnt += 1
    edge_band_pct = pct(edge_cnt, total)

    notes = []
    if override_pct < 10:
        notes.append("override_pct<10")
    if log_completeness_pct == 100.0:
        notes.append("log_complete")
    if second_approval_pct == 100.0 and override_total>0:
        notes.append("four_eyes_ok")
    if violations_threshold_coherence == 0:
        notes.append("coherence_ok")
    try:
        if p95_latency_ms != "NA" and float(p95_latency_ms) < 150:
            notes.append("p95<150ms")
    except Exception:
        pass

    row = {
        "batch_id": args.batch,
        "total": total,
        "allow": allow,
        "review": review,
        "block": block,
        "allow_pct": f"{allow_pct:.2f}",
        "review_pct": f"{review_pct:.2f}",
        "block_pct": f"{block_pct:.2f}",
        "override_total": override_total,
        "override_pct": f"{override_pct:.2f}",
        "second_approval_pct": f"{second_approval_pct:.2f}",
        "log_completeness_pct": f"{log_completeness_pct:.2f}",
        "determinism_consistency_pct": f"{determinism_consistency_pct:.2f}",
        "p50_latency_ms": p50_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "violations_monotonicity": violations_monotonicity,
        "violations_threshold_coherence": violations_threshold_coherence,
        "edge_band_pct": f"{edge_band_pct:.2f}",
        "notes": ",".join(notes) or "artefact-run"
    }

    with OUT_FILE.open("w", newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerow(row)
    print(f"Wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
