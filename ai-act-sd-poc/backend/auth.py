import os
import json
from fastapi import HTTPException, Header, Depends

STRICT_AUTH = os.getenv("STRICT_AUTH", "0") in ("1", "true", "True")

def _load_tokens():
    # Prefer explicit JSON string
    raw = os.getenv("TOKENS_JSON")
    # Or load from file path if provided
    if not raw and os.getenv("TOKENS_FILE"):
        try:
            with open(os.getenv("TOKENS_FILE"), "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            raw = None
    if not raw:
        if STRICT_AUTH:
            # No tokens configured in strict mode: fail fast
            raise RuntimeError("Auth misconfigured: set TOKENS_JSON or TOKENS_FILE")
        # Demo fallback for non-strict mode
        return {
            "reviewer@rittal": "reviewer",
            "admin@rittal": "admin",
        }
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            if STRICT_AUTH:
                raise RuntimeError("TOKENS_JSON must be a JSON object")
            return {
                "reviewer@rittal": "reviewer",
                "admin@rittal": "admin",
            }
        # normalize roles
        norm = {}
        for k, v in data.items():
            role = str(v).lower()
            if role not in ("reviewer", "admin"):
                continue
            norm[str(k)] = role
        if norm:
            return norm
        if STRICT_AUTH:
            raise RuntimeError("TOKENS_JSON must contain at least one valid token")
        return {
            "reviewer@rittal": "reviewer",
            "admin@rittal": "admin",
        }
    except Exception:
        if STRICT_AUTH:
            raise
        return {
            "reviewer@rittal": "reviewer",
            "admin@rittal": "admin",
        }

TOKENS = _load_tokens()

def role_rank(role: str) -> int:
    return {"reviewer": 1, "admin": 2}.get(role, 0)

def require_role(min_role: str):
    required_rank = role_rank(min_role)
    async def _dep(x_auth_token: str | None = Header(None, alias="X-Auth-Token")):
        if not x_auth_token:
            raise HTTPException(status_code=401, detail="Missing X-Auth-Token")
        role = TOKENS.get(x_auth_token)
        if not role:
            raise HTTPException(status_code=401, detail="Invalid token")
        if role_rank(role) < required_rank:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return {"user": x_auth_token, "role": role, "token": x_auth_token}
    return _dep
