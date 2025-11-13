from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import hashlib
import json
import os
from schemas import CreditRequest, CreditResponse
from rules import score_and_decision, RULE_VERSION
from db import log_decision, fetch_base_decision, existing_override
from auth import require_role, TOKENS
import time
from starlette.responses import PlainTextResponse

SERVICE_VERSION = "svc1.0.0"

app = FastAPI(title="Credit Decision Service")

# Simple content-length limit and token-bucket rate limiting
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "65536"))  # 64KB default
RATE_LIMIT_RATE = float(os.getenv("RATE_LIMIT_RATE", "5"))  # tokens per second
RATE_LIMIT_BURST = float(os.getenv("RATE_LIMIT_BURST", "10"))
_buckets = {}

def _key_for_request(request: Request):
    token = request.headers.get("X-Auth-Token")
    return token or request.client.host if request.client else "anon"

@app.middleware("http")
async def security_limits(request: Request, call_next):
    # Skip health
    if request.url.path == "/health":
        return await call_next(request)
    # Content-Length check
    cl = request.headers.get("content-length")
    try:
        if cl is not None and int(cl) > MAX_BODY_BYTES:
            return PlainTextResponse("Payload too large", status_code=413)
    except Exception:
        pass
    # Rate limiting
    now = time.monotonic()
    key = _key_for_request(request)
    bucket = _buckets.get(key, {"tokens": RATE_LIMIT_BURST, "ts": now})
    # refill
    elapsed = max(0.0, now - bucket["ts"])
    bucket["tokens"] = min(RATE_LIMIT_BURST, bucket["tokens"] + elapsed * RATE_LIMIT_RATE)
    bucket["ts"] = now
    if bucket["tokens"] < 1.0:
        _buckets[key] = bucket
        return PlainTextResponse("Too Many Requests", status_code=429)
    bucket["tokens"] -= 1.0
    _buckets[key] = bucket
    return await call_next(request)

@app.get("/health")
def health():
    auth_state = "configured" if TOKENS else "misconfigured"
    return {"status": "ok", "service_version": SERVICE_VERSION, "rules_version": RULE_VERSION, "auth": auth_state}

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


class OverridePayload(BaseModel):
    decision_id: str
    new_decision: str = Field(pattern="^(ALLOW|BLOCK)$")
    override_reason: str
    actor_ux: str | None = None  # ignored for auth-lite; actor derived from token

class OverrideResponse(BaseModel):
    decision_id: str
    original_decision: str
    new_decision: str
    score: int
    second_approval: int
    override_reason: str
    timestamp_utc: str
    rule_version: str
    data_version: str
    service_version: str = SERVICE_VERSION

@app.post("/v1/credit/override", response_model=OverrideResponse)
def override_decision(payload: OverridePayload, auth=Depends(require_role("reviewer"))):
    # Validate reason length
    if len(payload.override_reason.strip()) < 15:
        raise HTTPException(status_code=400, detail="override_reason must be at least 15 characters")
    # Fetch base (non-overridden) decision
    base = fetch_base_decision(payload.decision_id)
    if not base:
        raise HTTPException(status_code=404, detail="decision_id not found or already overridden base missing")
    # Idempotence guard (optional 409)
    if existing_override(payload.decision_id, payload.new_decision, payload.override_reason.strip()):
        raise HTTPException(status_code=409, detail="Identical override already exists")
    # Extract fields from base row (row is a Row object)
    base_map = dict(base._mapping)
    score = base_map["score"]
    original_decision = base_map["decision"]
    rule_version = base_map["rule_version"]
    data_version = base_map["data_version"]
    input_json = base_map["input_json"]
    try:
        parsed = json.loads(input_json)
    except Exception:
        parsed = {}
    order_value_eur = parsed.get("order_value_eur", 0)
    country_risk = parsed.get("country_risk", 0)
    second_approval = 1 if (order_value_eur >= 50000 or country_risk >= 4) else 0
    # Enforce admin for second approval cases
    if second_approval == 1 and auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required for second approval")
    ts_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Insert override log row (append-only)
    log_decision({
        "decision_id": payload.decision_id,
        "ts_utc": ts_utc,
        "order_id": base_map.get("order_id"),
        "customer_id": base_map.get("customer_id"),
        "input_json": input_json,  # keep original canonical request
        "score": score,
        "thresholds_json": base_map.get("thresholds_json"),
        "decision": payload.new_decision,
        "rule_version": rule_version,
        "data_version": data_version,
        "actor_sys": "oversight_ui",
        "actor_ux": auth.get("user"),
        "overridden": 1,
        "override_reason": payload.override_reason.strip(),
        "second_approval": second_approval
    })

    return OverrideResponse(
        decision_id=payload.decision_id,
        original_decision=original_decision,
        new_decision=payload.new_decision,
        score=score,
        second_approval=second_approval,
        override_reason=payload.override_reason.strip(),
        timestamp_utc=ts_utc,
        rule_version=rule_version,
        data_version=data_version,
        service_version=SERVICE_VERSION
    )


class LoginPayload(BaseModel):
    token: str

@app.post("/v1/auth/login")
def login(payload: LoginPayload):
    # Validate token from body against token store; no header required here
    role = TOKENS.get(payload.token)
    if not role:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"user": payload.token, "role": role}

@app.post("/v1/auth/logout")
def logout():
    # Stateless logout: always OK to simplify client UX
    return {"ok": True}
