from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class CreditRequest(BaseModel):
    order_id: str
    customer_id: str
    order_value_eur: float
    payment_terms_days: int
    overdue_ratio: float = Field(ge=0, le=1)
    dso_proxy_days: int
    risk_class: Literal["A","B","C","D"]
    country_risk: int = Field(ge=1, le=5)
    incoterm: Literal["EXW","DDP","DAP","FCA","CPT"]
    is_new_customer: bool
    credit_limit_eur: float
    past_limit_breach: bool
    express_flag: bool
    data_version: str = "dv1.0"

class CreditResponse(BaseModel):
    decision_id: str
    score: int
    thresholds: dict
    decision: Literal["ALLOW","REVIEW","BLOCK"]
    rule_version: str
    data_version: str
    policy_rationale: str
    timestamp_utc: str
    service_version: str = "svc1.0.0"
