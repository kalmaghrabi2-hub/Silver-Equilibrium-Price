#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/silver/data/latest.json"
CAL = ROOT / "docs/silver/data/weekly_calibration.json"
FUND = ROOT / "docs/silver/data/fundamentals.json"
UA = "Mozilla/5.0 SilverEquilibriumPrice/1.0"
MACRO_SERIES = ["GC=F", "DX-Y.NYB", "^TNX", "^VIX", "HG=F"]


def get_text(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_json(url):
    return json.loads(get_text(url))


def yahoo_quote(symbol):
    q = urllib.parse.quote(symbol, safe="")
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - 21 * 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{q}"
        f"?period1={start}&period2={now}&interval=1d&events=history"
    )
    payload = get_json(url)
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(f"Yahoo empty result for {symbol}")
    timestamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    for ts, value in reversed(list(zip(timestamps, closes))):
        if value is not None and math.isfinite(float(value)) and float(value) > 0:
            return {
                "series": symbol,
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                "value": float(value),
                "source": url,
            }
    raise RuntimeError(f"Yahoo has no valid close for {symbol}")


def fetch_market():
    try:
        quote = yahoo_quote("SI=F")
        return {
            "usd_oz": quote["value"],
            "as_of": quote["date"],
            "freshness_status": "latest_daily_close",
            "provider": "Yahoo COMEX Silver Futures SI=F",
            "benchmark_type": "futures",
            "source": quote["source"],
        }
    except Exception as yahoo_error:
        payload = get_json("https://api.gold-api.com/price/XAG")
        value = payload.get("price")
        if value is None:
            raise RuntimeError(f"Market feeds failed; Yahoo error: {yahoo_error}")
        return {
            "usd_oz": float(value),
            "as_of": payload.get("updatedAt") or payload.get("updated_at"),
            "freshness_status": "fallback",
            "provider": "Gold API XAG",
            "benchmark_type": "spot_fallback",
            "source": "https://api.gold-api.com/price/XAG",
        }


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def weekly_fair_value(macro, calibration, silver_anchor):
    if not calibration:
        return None
    series = calibration.get("series") or []
    beta = calibration.get("beta") or []
    means = calibration.get("means") or []
    sds = calibration.get("sds") or []
    if len(beta) != len(series) + 1 or len(means) != len(series) or len(sds) != len(series):
        return None
    values = []
    for key in series:
        if key == "LAG_SILVER_LOG":
            values.append(math.log(silver_anchor))
        elif key in macro:
            values.append(macro[key]["value"])
        else:
            return None
    x = [1.0] + [(v - mean) / sd for v, mean, sd in zip(values, means, sds)]
    return math.exp(sum(a * b for a, b in zip(x, beta)))


def select_physical_snapshot(fundamentals, current_year):
    forecast = fundamentals.get("forecast") or {}
    actual = fundamentals.get("actual") or {}
    if forecast.get("year") and int(forecast["year"]) >= current_year:
        return forecast, "FORECAST"
    return actual, "ACTUAL_STALE"


def physical_overlay(fundamentals, current_year):
    snapshot, vintage_type = select_physical_snapshot(fundamentals, current_year)
    supply = float(snapshot["total_supply_moz"])
    demand = float(snapshot["total_demand_moz"])
    elasticity_supply = float(fundamentals["elasticities"]["supply"])
    elasticity_demand = float(fundamentals["elasticities"]["demand"])
    denominator = elasticity_supply - elasticity_demand
    if supply <= 0 or demand <= 0 or denominator <= 0:
        raise RuntimeError("Invalid physical-equilibrium inputs")
    demand_supply_ratio = demand / supply
    exponent = 1.0 / denominator
    raw_multiplier = demand_supply_ratio ** exponent
    multiplier = min(max(raw_multiplier, 0.80), 1.25)
    survey_year = int(fundamentals.get("survey_year") or 0)
    snapshot_year = int(snapshot.get("year") or 0)
    source_gate = fundamentals.get("physical_source_gate") == "PASS"
    freshness_gate = snapshot_year >= current_year
    gate = "PASS" if source_gate and freshness_gate else "STALE"
    return {
        "vintage_type": vintage_type,
        "snapshot_year": snapshot_year,
        "survey_year": survey_year,
        "total_supply_moz": supply,
        "total_demand_moz": demand,
        "market_balance_moz": float(snapshot.get("market_balance_moz", supply - demand)),
        "mine_production_moz": float(snapshot.get("mine_production_moz", 0.0)),
        "recycling_moz": float(snapshot.get("recycling_moz", 0.0)),
        "industrial_demand_moz": float(snapshot.get("industrial_demand_moz", 0.0)),
        "coin_net_bar_demand_moz": float(snapshot.get("coin_net_bar_demand_moz", 0.0)),
        "net_etp_investment_moz": float(snapshot.get("net_etp_investment_moz", 0.0)),
        "demand_supply_ratio": demand_supply_ratio,
        "elasticity_supply": elasticity_supply,
        "elasticity_demand": elasticity_demand,
        "equilibrium_exponent": exponent,
        "raw_multiplier": raw_multiplier,
        "multiplier": multiplier,
        "guardrail_active": multiplier != raw_multiplier,
        "physical_source_gate": gate,
        "source": fundamentals.get("source_url"),
        "elasticity_source": (fundamentals.get("elasticities") or {}).get("source_url"),
    }


def main():
    now = datetime.now(timezone.utc)
    errors = []
    payload = {
        "as_of_date": now.date().isoformat(),
        "generated_at_utc": now.isoformat(),
        "model_version": "silver-weekly-arx-physical-equilibrium-v1.0",
    }

    try:
        market = fetch_market()
        payload["market"] = market
    except Exception as exc:
        errors.append(f"market: {exc}")
        market = None

    macro = {}
    for symbol in MACRO_SERIES:
        try:
            macro[symbol] = yahoo_quote(symbol)
        except Exception as exc:
            errors.append(f"Yahoo {symbol}: {exc}")
    payload["macro"] = macro

    try:
        calibration = load_json(CAL)
    except Exception as exc:
        calibration = None
        errors.append(f"calibration: {exc}")
    payload["calibration"] = calibration

    try:
        fundamentals = load_json(FUND)
        physical = physical_overlay(fundamentals, now.year)
    except Exception as exc:
        fundamentals = None
        physical = None
        errors.append(f"fundamentals: {exc}")
    payload["fundamentals_reference"] = fundamentals

    macro_value = weekly_fair_value(macro, calibration, market["usd_oz"]) if market else None

    if market and macro_value and physical:
        raw_pstar = macro_value * physical["multiplier"]
        low = 0.50 * market["usd_oz"]
        high = 1.60 * market["usd_oz"]
        pstar = min(max(raw_pstar, low), high)
        weekly_gate = (calibration or {}).get("walk_forward_gate") or "PENDING"
        physical_gate = physical.get("physical_source_gate") or "PENDING"
        critical_errors = [e for e in errors if e.startswith("market:") or e.startswith("calibration:") or e.startswith("fundamentals:")]
        fully_valid = weekly_gate == "PASS" and physical_gate == "PASS" and not critical_errors
        status = "VALID" if fully_valid else "PROVISIONAL"
        confidence = "HIGH" if fully_valid else ("MEDIUM" if weekly_gate == "PASS" else "LOW")
        payload["model"] = {
            "weekly_fair_value_usd_oz": round(macro_value, 4),
            "physical_overlay": {
                k: (round(v, 8) if isinstance(v, float) else v) for k, v in physical.items()
            },
            "raw_combined_p_star_usd_oz": round(raw_pstar, 4),
            "fundamental_p_star_usd_oz": round(pstar, 4),
            "market_vs_pstar_pct": round((market["usd_oz"] / pstar - 1.0) * 100.0, 3),
            "guardrail_active": pstar != raw_pstar or bool(physical.get("guardrail_active")),
            "status": status,
            "confidence": confidence,
            "governance": {
                "weekly_walk_forward": weekly_gate,
                "physical_source_gate": physical_gate,
                "no_imputation": True,
                "publication_gate": "VALID" if fully_valid else "PROVISIONAL_ONLY",
            },
        }
        payload["model_status"] = status
    else:
        payload["model"] = None
        payload["model_status"] = "UNAVAILABLE"

    payload["errors"] = errors
    payload["data_quality"] = "OK" if not errors else "DEGRADED"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
