#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / "docs/silver/data/latest.json"
CAL = ROOT / "docs/silver/data/weekly_calibration.json"
INST = ROOT / "docs/silver/data/institutional_inputs.json"


def dt(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(text[:10]), datetime.min.time(), tzinfo=timezone.utc)
        except ValueError:
            return None


def age_days(value, now):
    x = dt(value)
    if x is None:
        return 10**6
    if x.tzinfo is None:
        x = x.replace(tzinfo=timezone.utc)
    return (now - x.astimezone(timezone.utc)).total_seconds() / 86400.0


def main():
    now = datetime.now(timezone.utc)
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    cal = json.loads(CAL.read_text(encoding="utf-8"))
    inst = json.loads(INST.read_text(encoding="utf-8"))
    failures = []
    market_age = age_days((latest.get("market") or {}).get("as_of"), now)
    cal_age = age_days(cal.get("generated_at_utc"), now)
    if market_age > 5.0:
        failures.append(f"market stale: {market_age:.2f} days")
    if cal_age > 3.0:
        failures.append(f"weekly calibration stale: {cal_age:.2f} days")
    if inst.get("status") != "PASS":
        failures.append("institutional collector status not PASS")
    observations = inst.get("observations") or {}
    for key in ("real_yield_10y", "broad_usd", "vix", "breakeven_10y"):
        obs = observations.get(key) or {}
        a = age_days(obs.get("observation_date"), now)
        if a > 10.0:
            failures.append(f"institutional {key} stale: {a:.2f} days")
    # INDPRO is monthly and is research-only; it is intentionally not a daily fail-closed input.
    result = {"checked_at_utc": now.isoformat(), "market_age_days": round(market_age, 3), "calibration_age_days": round(cal_age, 3), "failures": failures, "status": "FAIL" if failures else "PASS"}
    print(json.dumps(result, ensure_ascii=False))
    if failures:
        raise SystemExit("data freshness gate failed")


if __name__ == "__main__":
    main()
