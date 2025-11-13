import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path


def canonical_json(d: dict) -> str:
    return json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_row_hash(prev_hash: str, payload: dict, ts_utc: str) -> str:
    h = hashlib.sha256()
    h.update((prev_hash or '').encode('utf-8'))
    payload_json = canonical_json({k: v for k, v in payload.items() if k not in ('prev_hash', 'row_hash')})
    h.update(payload_json.encode('utf-8'))
    h.update((ts_utc or '').encode('utf-8'))
    return h.hexdigest()


def verify_db(db_path: Path) -> tuple[bool, str, int]:
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    q = (
        "SELECT id, ts_utc, decision_id, order_id, customer_id, input_json, score, thresholds_json, "
        "decision, rule_version, data_version, actor_sys, actor_ux, overridden, override_reason, second_approval, prev_hash, row_hash "
        "FROM decision_logs ORDER BY id"
    )
    rows = list(cur.execute(q))
    con.close()
    prev = ''
    count = 0
    for r in rows:
        (id_, ts_utc, decision_id, order_id, customer_id, input_json, score, thresholds_json,
         decision, rule_version, data_version, actor_sys, actor_ux, overridden, override_reason, second_approval, prev_hash, row_hash) = r
        payload = {
            'decision_id': decision_id,
            'ts_utc': ts_utc,
            'order_id': order_id,
            'customer_id': customer_id,
            'input_json': input_json,
            'score': score,
            'thresholds_json': thresholds_json,
            'decision': decision,
            'rule_version': rule_version,
            'data_version': data_version,
            'actor_sys': actor_sys,
            'actor_ux': actor_ux,
            'overridden': overridden,
            'override_reason': override_reason,
            'second_approval': second_approval,
        }
        calc = compute_row_hash(prev_hash or prev, payload, ts_utc)
        if calc != row_hash:
            return False, f"Mismatch at row id={id_} expected {row_hash} got {calc}", count
        prev = row_hash
        count += 1
    return True, f"OK ({count} rows)", count


essential_fields = [
    'id','ts_utc','decision_id','order_id','customer_id','input_json','score','thresholds_json','decision','rule_version','data_version','overridden','second_approval','actor_sys','actor_ux','override_reason','prev_hash','row_hash'
]

def verify_csv(csv_path: Path) -> tuple[bool, str, int]:
    # Read all lines; ignore trailing hash footer starting with '# SHA256='
    text = csv_path.read_text(encoding='utf-8').splitlines()
    data_lines = [ln for ln in text if not ln.startswith('# SHA256=')]
    from io import StringIO
    sio = StringIO('\n'.join(data_lines) + '\n')
    rdr = csv.DictReader(sio)
    prev = ''
    count = 0
    for row in rdr:
        for f in essential_fields:
            if f not in row:
                return False, f"CSV missing field {f}", count
        ts_utc = row['ts_utc']
        payload = {
            'decision_id': row['decision_id'],
            'ts_utc': ts_utc,
            'order_id': row['order_id'],
            'customer_id': row['customer_id'],
            'input_json': row['input_json'],
            'score': int(row['score']) if row['score'] else 0,
            'thresholds_json': row['thresholds_json'],
            'decision': row['decision'],
            'rule_version': row['rule_version'],
            'data_version': row['data_version'],
            'actor_sys': row['actor_sys'],
            'actor_ux': row['actor_ux'],
            'overridden': int(row['overridden']) if row['overridden'] else 0,
            'override_reason': row['override_reason'],
            'second_approval': int(row['second_approval']) if row['second_approval'] else 0,
        }
        prev_hash = row['prev_hash']
        row_hash = row['row_hash']
        calc = compute_row_hash(prev_hash or prev, payload, ts_utc)
        if calc != row_hash:
            return False, f"Mismatch at CSV row id={row['id']} expected {row_hash} got {calc}", count
        prev = row_hash
        count += 1
    return True, f"OK ({count} rows)", count


def main():
    ap = argparse.ArgumentParser(description='Verify audit log hash chain (db or csv)')
    ap.add_argument('--source', choices=['db','csv'], required=True)
    ap.add_argument('--db')
    ap.add_argument('--csv')
    args = ap.parse_args()
    if args.source == 'db':
        if not args.db:
            print('Missing --db path')
            raise SystemExit(2)
        ok, msg, _ = verify_db(Path(args.db))
    else:
        if not args.csv:
            print('Missing --csv path')
            raise SystemExit(2)
        ok, msg, _ = verify_csv(Path(args.csv))
    print(msg)
    raise SystemExit(0 if ok else 1)

if __name__ == '__main__':
    main()
