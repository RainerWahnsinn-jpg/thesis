from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
import hashlib
import json
from schemas import CreditRequest, CreditResponse
from rules import score_and_decision, RULE_VERSION
from db import log_decision

SERVICE_VERSION = "svc1.0.0"

app = FastAPI(title="Credit Decision Service")

@app.get("/health")
def health():
    return {"status": "ok", "service_version": SERVICE_VERSION, "rules_version": RULE_VERSION}

@app.post("/v1/credit/decision", response_model=CreditResponse)
def decide(req: CreditRequest):
    try:
        # Deterministic scoring / decision
        score, decision, rationale = score_and_decision(req)
        thresholds = {"allow_max": 59, "review_range": [60, 79], "block_min": 80}

        # Deterministic decision_id from canonical JSON (sorted keys)
        canonical_dict = req.model_dump()
        canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        decision_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        decision_id = f"dec-{decision_hash}"

        # ISO8601 with trailing Z
        ts_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        # Append-only log insert (idempotent on same decision_id)
        log_decision({
            "decision_id": decision_id,
            "ts_utc": ts_utc,
            "order_id": req.order_id,
            "customer_id": req.customer_id,
            "input_json": canonical_json,
            "score": score,
            "thresholds_json": json.dumps(thresholds, separators=(",", ":")),
            "decision": decision,
            "rule_version": RULE_VERSION,
            "data_version": req.data_version,
            "actor_sys": "credit_decision_api",
            "actor_ux": None,
            "overridden": 0,
            "override_reason": None
        })

        return CreditResponse(
            decision_id=decision_id,
            score=score,
            thresholds=thresholds,
            decision=decision,
            rule_version=RULE_VERSION,
            data_version=req.data_version,
            policy_rationale=rationale,
            timestamp_utc=ts_utc,
            service_version=SERVICE_VERSION
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
