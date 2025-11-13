import argparse
import csv
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "backend" / "governance.db"


def export_csv(out_path: Path, db_path: Path, ts_from: str | None, ts_to: str | None):
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    q = "SELECT id, ts_utc, decision_id, order_id, customer_id, input_json, score, thresholds_json, decision, rule_version, data_version, overridden, second_approval, actor_sys, actor_ux, override_reason, prev_hash, row_hash FROM decision_logs"
    clauses = []
    params = []
    if ts_from:
        clauses.append("ts_utc >= ?")
        params.append(ts_from)
    if ts_to:
        clauses.append("ts_utc <= ?")
        params.append(ts_to)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY id"
    rows = list(cur.execute(q, params))
    con.close()

    # write to a temp buffer to compute hash, then append footer line
    lines = []
    header = [
        "id","ts_utc","decision_id","order_id","customer_id","input_json","score","thresholds_json",
        "decision","rule_version","data_version","overridden","second_approval","actor_sys","actor_ux",
        "override_reason","prev_hash","row_hash"
    ]
    lines.append(",".join(header) + "\n")
    for r in rows:
        # simple CSV with basic escaping by csv module
        # we'll build rows via writer for correctness, then collect as string
        pass

    # Use csv module to generate content reliably
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(header)
    for r in rows:
        w.writerow([*r])
    content = buf.getvalue()
    buf.close()

    sha = hashlib.sha256(content.encode('utf-8')).hexdigest()
    content_with_footer = content + f"# SHA256={sha}\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content_with_footer, encoding='utf-8')
    return sha, len(rows)


def main():
    p = argparse.ArgumentParser(description="Export decision_logs to signed CSV")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Path to governance.db")
    p.add_argument("--out", default="data/decision_logs_export.csv", help="Output CSV path")
    p.add_argument("--from", dest="ts_from", help="Start timestamp (inclusive, ISO UTC '...Z')")
    p.add_argument("--to", dest="ts_to", help="End timestamp (inclusive, ISO UTC '...Z')")
    args = p.parse_args()

    sha, n = export_csv(Path(args.out), Path(args.db), args.ts_from, args.ts_to)
    print(f"Exported {n} rows to {args.out}")
    print(f"SHA256={sha}")

if __name__ == "__main__":
    main()
