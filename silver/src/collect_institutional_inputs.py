#!/usr/bin/env python3
"""Collect auditable institutional macro inputs for silver research.

Research/data layer only. It does not change the published price. Daily
snapshots establish a forward point-in-time record for future validation.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/silver/data/institutional_inputs.json"
UA = "Mozilla/5.0 SilverEquilibriumInstitutionalCollector/1.0"

SERIES = {
    "real_yield_10y": {"id": "DFII10", "source": "Federal Reserve/FRED", "role": "precious-metals real-yield channel"},
    "broad_usd": {"id": "DTWEXBGS", "source": "Federal Reserve/FRED", "role": "broad USD valuation channel"},
    "vix": {"id": "VIXCLS", "source": "CBOE via FRED", "role": "risk regime"},
    "breakeven_10y": {"id": "T10YIE", "source": "FRED", "role": "inflation expectations"},
    "industrial_production": {"id": "INDPRO", "source": "Federal Reserve/FRED", "role": "industrial-cycle context; release-lag control required"},
}


def fetch_series(series_id: str):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise RuntimeError(f"No FRED rows for {series_id}")
    value_col = series_id if series_id in rows[0] else list(rows[0].keys())[-1]
    for row in reversed(rows):
        raw = (row.get(value_col) or "").strip()
        if raw and raw != ".":
            return {
                "observation_date": row.get("DATE") or row.get("observation_date"),
                "value": float(raw),
                "url": url,
            }
    raise RuntimeError(f"No valid FRED observations for {series_id}")


def main():
    now = datetime.now(timezone.utc).isoformat()
    observations = {}
    errors = {}
    for name, meta in SERIES.items():
        try:
            obs = fetch_series(meta["id"])
            observations[name] = {**meta, **obs}
        except Exception as exc:
            errors[name] = str(exc)

    status = "PASS" if not errors and len(observations) == len(SERIES) else "PARTIAL"
    payload = {
        "generated_at_utc": now,
        "status": status,
        "purpose": "institutional research inputs; not authorized to change published equilibrium/reference price",
        "point_in_time_policy": {
            "forecast_use": "only observations available before forecast week may be used",
            "release_lag": "monthly/annual series require explicit publication-lag mapping before backtest use",
            "retroactive_revision_policy": "do not treat later revisions as historically known",
            "archive_policy": "daily committed snapshots establish forward point-in-time evidence from activation date",
        },
        "observations": observations,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if status != "PASS":
        raise SystemExit("institutional input collection incomplete")


if __name__ == "__main__":
    main()
