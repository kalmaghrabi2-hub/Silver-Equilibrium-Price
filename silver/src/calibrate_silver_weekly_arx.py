#!/usr/bin/env python3
"""Weekly ARX fair-value model for silver.

Target: next-week log COMEX silver close (SI=F).
Features available at t only: lagged silver, gold, USD index, 10Y yield,
VIX and copper. Expanding one-step-ahead walk-forward; no look-ahead and
no missing-value imputation. Publication also requires positive MSE skill
against a persistence benchmark (next week = previous observed silver price).
"""
from __future__ import annotations

import json
import math
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/silver/data/weekly_calibration.json"
TARGET = "SI=F"
MACRO = ["GC=F", "DX-Y.NYB", "^TNX", "^VIX", "HG=F"]
SERIES = ["LAG_SILVER_LOG"] + MACRO
START = 946684800  # 2000-01-01 UTC
RIDGE_LAMBDA = 3.0
MIN_TRAIN = 156
MIN_OOS = 260
MIN_R2 = 0.60
MAX_MAPE = 15.0
MIN_SKILL_VS_NAIVE_MSE_PCT = 0.0
UA = "Mozilla/5.0 SilverEquilibriumPrice/2.0"


def chart(symbol: str):
    q = urllib.parse.quote(symbol, safe="")
    now = int(datetime.now(timezone.utc).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{q}"
        f"?period1={START}&period2={now}&interval=1wk&events=history"
        "&includeAdjustedClose=true"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(f"Yahoo returned no result for {symbol}")
    timestamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    out = {}
    for ts, value in zip(timestamps, closes):
        if value is None:
            continue
        value = float(value)
        if value > 0 and math.isfinite(value):
            out[int(ts) // 604800] = value
    if len(out) < 200:
        raise RuntimeError(f"Insufficient Yahoo weekly data for {symbol}: {len(out)}")
    return out, url


def solve(matrix, rhs):
    n = len(rhs)
    aug = [matrix[i][:] + [rhs[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(aug[row][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        z = aug[col][col]
        if abs(z) < 1e-12:
            raise RuntimeError("Singular matrix")
        aug[col] = [v / z for v in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [aug[row][j] - factor * aug[col][j] for j in range(n + 1)]
    return [aug[i][-1] for i in range(n)]


def fit(x_rows, y, lam=RIDGE_LAMBDA):
    p = len(x_rows[0])
    a = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for x, target in zip(x_rows, y):
        for i in range(p):
            b[i] += x[i] * target
            for j in range(p):
                a[i][j] += x[i] * x[j]
    for i in range(1, p):
        a[i][i] += lam
    return solve(a, b)


def design(rows):
    columns = list(zip(*[row[2] for row in rows]))
    means = [statistics.fmean(col) for col in columns]
    sds = [statistics.pstdev(col) or 1.0 for col in columns]
    x = [[1.0] + [(v - m) / s for v, m, s in zip(row[2], means, sds)] for row in rows]
    return x, means, sds


def main():
    silver, silver_url = chart(TARGET)
    factors = {}
    urls = {}
    for symbol in MACRO:
        factors[symbol], urls[symbol] = chart(symbol)

    common_weeks = sorted(set(silver).intersection(*[set(factors[s]) for s in MACRO]))
    raw = [(w, silver[w], [factors[s][w] for s in MACRO]) for w in common_weeks]

    rows = []
    for i in range(1, len(raw)):
        prev_week, prev_silver, prev_factors = raw[i - 1]
        week, current_silver, _ = raw[i]
        if week - prev_week == 1:
            rows.append((week, current_silver, [math.log(prev_silver)] + prev_factors))

    if len(rows) < MIN_TRAIN + MIN_OOS:
        raise RuntimeError(f"Insufficient complete weekly history: {len(rows)}")

    predictions = []
    naive_predictions = []
    actuals = []
    dates = []
    for i in range(MIN_TRAIN, len(rows)):
        train = rows[:i]
        x_train, means, sds = design(train)
        beta = fit(x_train, [math.log(r[1]) for r in train])
        live_x = [1.0] + [(v - m) / s for v, m, s in zip(rows[i][2], means, sds)]
        predictions.append(math.exp(sum(a * b for a, b in zip(live_x, beta))))
        naive_predictions.append(math.exp(rows[i][2][0]))
        actuals.append(rows[i][1])
        dates.append(datetime.fromtimestamp(rows[i][0] * 604800, tz=timezone.utc).date().isoformat())

    x_all, means, sds = design(rows)
    beta = fit(x_all, [math.log(r[1]) for r in rows])

    avg = statistics.fmean(actuals)
    total_ss = sum((a - avg) ** 2 for a in actuals)
    model_sq_errors = [(a - p) ** 2 for a, p in zip(actuals, predictions)]
    naive_sq_errors = [(a - p) ** 2 for a, p in zip(actuals, naive_predictions)]
    model_mse = statistics.fmean(model_sq_errors)
    naive_mse = statistics.fmean(naive_sq_errors)
    r2 = 1.0 - sum(model_sq_errors) / total_ss
    mape = 100.0 * statistics.fmean(abs((a - p) / a) for a, p in zip(actuals, predictions))
    naive_mape = 100.0 * statistics.fmean(abs((a - p) / a) for a, p in zip(actuals, naive_predictions))
    rmse = math.sqrt(model_mse)
    naive_rmse = math.sqrt(naive_mse)
    skill_vs_naive_mse = 100.0 * (1.0 - model_mse / naive_mse) if naive_mse > 0 else float("-inf")

    direction_hits = 0
    direction_n = 0
    for actual, predicted, baseline in zip(actuals, predictions, naive_predictions):
        actual_move = actual - baseline
        predicted_move = predicted - baseline
        if actual_move != 0:
            direction_n += 1
            direction_hits += int((actual_move > 0) == (predicted_move > 0))
    direction_accuracy = 100.0 * direction_hits / direction_n if direction_n else None

    passed = (
        len(predictions) >= MIN_OOS
        and r2 >= MIN_R2
        and mape <= MAX_MAPE
        and skill_vs_naive_mse > MIN_SKILL_VS_NAIVE_MSE_PCT
        and mape < naive_mape
    )
    metrics = {
        "n_weeks_total": len(rows),
        "walk_forward_n": len(predictions),
        "walk_forward_start": dates[0],
        "walk_forward_end": dates[-1],
        "r2": round(r2, 4),
        "mape_pct": round(mape, 3),
        "rmse_usd_oz": round(rmse, 3),
        "naive_mape_pct": round(naive_mape, 3),
        "naive_rmse_usd_oz": round(naive_rmse, 3),
        "skill_vs_naive_mse_pct": round(skill_vs_naive_mse, 3),
        "direction_accuracy_pct": None if direction_accuracy is None else round(direction_accuracy, 2),
    }

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "silver-weekly-arx-ridge-v2",
        "frequency": "weekly",
        "target": TARGET,
        "target_source": silver_url,
        "series": SERIES,
        "predictor_sources": {"LAG_SILVER_LOG": silver_url, **urls},
        "beta": beta,
        "means": means,
        "sds": sds,
        "ridge_lambda": RIDGE_LAMBDA,
        "metrics": metrics,
        "walk_forward_gate": "PASS" if passed else "FAIL",
        "publication_status": "CALIBRATED" if passed else "PROVISIONAL",
        "rules": {
            "min_training_weeks": MIN_TRAIN,
            "min_oos_weeks": MIN_OOS,
            "max_mape_pct": MAX_MAPE,
            "min_r2": MIN_R2,
            "min_skill_vs_naive_mse_pct": MIN_SKILL_VS_NAIVE_MSE_PCT,
            "must_beat_naive_mape": True,
            "naive_benchmark": "persistence: next weekly close equals previous observed weekly close",
            "lookahead": "none; lagged silver and predictors are from the prior observed week",
            "missing_data": "complete-case only; no imputation",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
