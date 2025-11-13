from typing import Tuple

RULE_VERSION = "rules_v1.2"

def score_and_decision(req) -> Tuple[int, str, str]:
    # einfache Scoring-Heuristik (0..100)
    score = 50
    if req.overdue_ratio >= 0.25: score += 20
    if req.order_value_eur >= 50000: score += 15
    if req.risk_class in ["C","D"]: score += 10
    if req.country_risk >= 4: score += 10
    if req.is_new_customer: score += 5
    if req.past_limit_breach: score += 15
    if req.incoterm == "EXW": score += 5

    # Schwellenregime
    thresholds = {"allow_max": 59, "review_range": [60, 79], "block_min": 80}

    if score >= thresholds["block_min"]:
        decision, rationale = "BLOCK", "High risk: overdue/amount/risk signals"
    elif thresholds["review_range"][0] <= score <= thresholds["review_range"][1]:
        decision, rationale = "REVIEW", "Medium risk: manual check required"
    else:
        # Zusatzbedingung: DSO-Proxy darf Ziel +10 nicht überschreiten
        if req.dso_proxy_days <= (req.payment_terms_days + 10) and not req.past_limit_breach:
            decision, rationale = "ALLOW", "Low risk within terms"
        else:
            decision, rationale = "REVIEW", "DSO near/over target or history flag"

    return score, decision, rationale
