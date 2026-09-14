#!/usr/bin/env python3
"""Predeclared silver weekly model research.

Purpose: search for a weekly/multi-week fair-value model that can beat a
persistence benchmark without contaminating the final out-of-sample test.

Protocol:
- Candidate horizons, feature sets and ridge penalties are fixed in code.
- First 260 samples = initial estimation window.
- Next 156 samples = model-selection validation window, using expanding
  walk-forward predictions only.
- Everything after that = untouched final out-of-sample evaluation.
- Selection uses validation MSE only; final OOS never participates in choice.
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
OUT = ROOT / "docs/silver/data/model_research.json"
START = 946684800
UA = "Mozilla/5.0 SilverEquilibriumResearch/1.0"
SYMBOLS = ["SI=F", "GC=F", "HG=F", "DX-Y.NYB", "^TNX", "^VIX"]
HORIZONS = [1, 4, 13]
LAMBDAS = [1.0, 5.0, 20.0, 100.0]
INITIAL_TRAIN = 260
VALIDATION = 156

FEATURE_SETS = {
    "AR_MOMENTUM": [
        "silver_ret_1", "silver_mom_4", "silver_mom_12",
    ],
    "CROSS_ASSET": [
        "silver_ret_1", "gold_ret_1", "copper_ret_1", "dxy_ret_1",
        "tnx_change_1", "vix_ret_1",
    ],
    "CROSS_MOMENTUM": [
        "silver_ret_1", "silver_mom_4", "silver_mom_12",
        "gold_ret_1", "gold_mom_4", "gold_mom_12",
        "copper_ret_1", "copper_mom_4", "dxy_ret_1", "dxy_mom_4",
        "tnx_change_1", "tnx_change_4", "vix_ret_1", "vix_ret_4",
    ],
    "VALUATION": [
        "silver_ret_1", "gold_ret_1", "copper_ret_1", "dxy_ret_1",
        "gold_silver_z52", "copper_silver_z52",
    ],
    "FULL": [
        "silver_ret_1", "silver_mom_4", "silver_mom_12",
        "gold_ret_1", "gold_mom_4", "gold_mom_12",
        "copper_ret_1", "copper_mom_4", "dxy_ret_1", "dxy_mom_4",
        "tnx_change_1", "tnx_change_4", "vix_ret_1", "vix_ret_4",
        "gold_silver_z52", "copper_silver_z52",
    ],
}


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
        raise RuntimeError(f"Yahoo returned no data for {symbol}")
    ts = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    out = {}
    for t, v in zip(ts, closes):
        if v is None:
            continue
        v = float(v)
        if v > 0 and math.isfinite(v):
            out[int(t) // 604800] = v
    return out, url


def solve(a, b):
    n = len(b)
    m = [a[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        z = m[c][c]
        if abs(z) < 1e-12:
            raise RuntimeError("singular matrix")
        m[c] = [x / z for x in m[c]]
        for r in range(n):
            if r == c:
                continue
            f = m[r][c]
            m[r] = [m[r][j] - f * m[c][j] for j in range(n + 1)]
    return [m[i][-1] for i in range(n)]


def standardize_fit(x_rows, y, lam):
    cols = list(zip(*x_rows))
    means = [statistics.fmean(c) for c in cols]
    sds = [statistics.pstdev(c) or 1.0 for c in cols]
    xz = [[1.0] + [(v - m) / s for v, m, s in zip(row, means, sds)] for row in x_rows]
    p = len(xz[0])
    a = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for x, target in zip(xz, y):
        for i in range(p):
            b[i] += x[i] * target
            for j in range(p):
                a[i][j] += x[i] * x[j]
    for i in range(1, p):
        a[i][i] += lam
    beta = solve(a, b)
    return beta, means, sds


def predict(beta, means, sds, row):
    x = [1.0] + [(v - m) / s for v, m, s in zip(row, means, sds)]
    return sum(a * b for a, b in zip(beta, x))


def zscore_last(values):
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values) or 1.0
    return (values[-1] - mean) / sd


def make_feature_map(series, i):
    s = series["SI=F"]
    g = series["GC=F"]
    c = series["HG=F"]
    d = series["DX-Y.NYB"]
    t = series["^TNX"]
    v = series["^VIX"]
    def lr(arr, a, b):
        return math.log(arr[a] / arr[b])
    gold_silver = [math.log(g[k] / s[k]) for k in range(i - 51, i + 1)]
    copper_silver = [math.log(c[k] / s[k]) for k in range(i - 51, i + 1)]
    return {
        "silver_ret_1": lr(s, i, i - 1),
        "silver_mom_4": lr(s, i, i - 4),
        "silver_mom_12": lr(s, i, i - 12),
        "gold_ret_1": lr(g, i, i - 1),
        "gold_mom_4": lr(g, i, i - 4),
        "gold_mom_12": lr(g, i, i - 12),
        "copper_ret_1": lr(c, i, i - 1),
        "copper_mom_4": lr(c, i, i - 4),
        "dxy_ret_1": lr(d, i, i - 1),
        "dxy_mom_4": lr(d, i, i - 4),
        "tnx_change_1": t[i] - t[i - 1],
        "tnx_change_4": t[i] - t[i - 4],
        "vix_ret_1": lr(v, i, i - 1),
        "vix_ret_4": lr(v, i, i - 4),
        "gold_silver_z52": zscore_last(gold_silver),
        "copper_silver_z52": zscore_last(copper_silver),
    }


def build_samples(data_by_week, horizon):
    weeks = sorted(data_by_week)
    series = {sym: [data_by_week[w][sym] for w in weeks] for sym in SYMBOLS}
    samples = []
    for i in range(52, len(weeks) - horizon):
        fmap = make_feature_map(series, i)
        anchor = series["SI=F"][i]
        future = series["SI=F"][i + horizon]
        target_return = math.log(future / anchor)
        samples.append({
            "week": weeks[i],
            "date": datetime.fromtimestamp(weeks[i] * 604800, tz=timezone.utc).date().isoformat(),
            "anchor": anchor,
            "future": future,
            "target_return": target_return,
            "features": fmap,
        })
    live = make_feature_map(series, len(weeks) - 1)
    return samples, live, series["SI=F"][-1], weeks[-1]


def walk_forward(samples, feature_names, lam, start, end):
    pred_prices, actual_prices, naive_prices = [], [], []
    for idx in range(start, end):
        train = samples[:idx]
        x = [[r["features"][k] for k in feature_names] for r in train]
        y = [r["target_return"] for r in train]
        beta, means, sds = standardize_fit(x, y, lam)
        row = samples[idx]
        x_live = [row["features"][k] for k in feature_names]
        ret = predict(beta, means, sds, x_live)
        pred_prices.append(row["anchor"] * math.exp(ret))
        actual_prices.append(row["future"])
        naive_prices.append(row["anchor"])
    return pred_prices, actual_prices, naive_prices


def metrics(pred, actual, naive):
    model_mse = statistics.fmean((a - p) ** 2 for a, p in zip(actual, pred))
    naive_mse = statistics.fmean((a - p) ** 2 for a, p in zip(actual, naive))
    model_mape = 100 * statistics.fmean(abs((a - p) / a) for a, p in zip(actual, pred))
    naive_mape = 100 * statistics.fmean(abs((a - p) / a) for a, p in zip(actual, naive))
    skill = 100 * (1 - model_mse / naive_mse) if naive_mse > 0 else float("-inf")
    return {
        "n": len(actual),
        "model_mape_pct": round(model_mape, 3),
        "naive_mape_pct": round(naive_mape, 3),
        "model_rmse_usd_oz": round(math.sqrt(model_mse), 3),
        "naive_rmse_usd_oz": round(math.sqrt(naive_mse), 3),
        "skill_vs_naive_mse_pct": round(skill, 3),
    }


def main():
    histories = {}
    sources = {}
    for sym in SYMBOLS:
        histories[sym], sources[sym] = chart(sym)
    common = sorted(set(histories[SYMBOLS[0]]).intersection(*[set(histories[s]) for s in SYMBOLS[1:]]))
    data_by_week = {w: {sym: histories[sym][w] for sym in SYMBOLS} for w in common}

    candidates = []
    prepared = {}
    for horizon in HORIZONS:
        samples, live_features, live_anchor, live_week = build_samples(data_by_week, horizon)
        prepared[horizon] = (samples, live_features, live_anchor, live_week)
        if len(samples) <= INITIAL_TRAIN + VALIDATION + 100:
            continue
        val_start = INITIAL_TRAIN
        val_end = INITIAL_TRAIN + VALIDATION
        for set_name, feature_names in FEATURE_SETS.items():
            for lam in LAMBDAS:
                pred, act, naive = walk_forward(samples, feature_names, lam, val_start, val_end)
                m = metrics(pred, act, naive)
                candidates.append({
                    "horizon_weeks": horizon,
                    "feature_set": set_name,
                    "features": feature_names,
                    "ridge_lambda": lam,
                    "validation": m,
                })

    if not candidates:
        raise RuntimeError("no candidate models")
    candidates.sort(key=lambda c: (-c["validation"]["skill_vs_naive_mse_pct"], c["validation"]["model_mape_pct"]))
    selected = candidates[0]
    horizon = selected["horizon_weeks"]
    samples, live_features, live_anchor, live_week = prepared[horizon]
    test_start = INITIAL_TRAIN + VALIDATION
    pred, act, naive = walk_forward(samples, selected["features"], selected["ridge_lambda"], test_start, len(samples))
    oos = metrics(pred, act, naive)

    x_all = [[r["features"][k] for k in selected["features"]] for r in samples]
    y_all = [r["target_return"] for r in samples]
    beta, means, sds = standardize_fit(x_all, y_all, selected["ridge_lambda"])
    live_x = [live_features[k] for k in selected["features"]]
    live_ret = predict(beta, means, sds, live_x)
    live_value = live_anchor * math.exp(live_ret)

    passed = (
        oos["n"] >= 260
        and oos["skill_vs_naive_mse_pct"] > 0
        and oos["model_mape_pct"] < oos["naive_mape_pct"]
    )
    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": "fixed candidate family; validation-only selection; untouched final OOS",
        "source_urls": sources,
        "candidate_count": len(candidates),
        "selection_windows": {
            "initial_train_samples": INITIAL_TRAIN,
            "validation_samples": VALIDATION,
            "final_oos_start_index": test_start,
        },
        "selected": selected,
        "final_oos": oos,
        "final_gate": "PASS" if passed else "FAIL",
        "live": {
            "as_of_week": datetime.fromtimestamp(live_week * 604800, tz=timezone.utc).date().isoformat(),
            "anchor_silver_usd_oz": round(live_anchor, 4),
            "predicted_horizon_weeks": horizon,
            "model_fair_value_usd_oz": round(live_value, 4),
            "predicted_return_pct": round(100 * (math.exp(live_ret) - 1), 3),
        },
        "top_validation_candidates": candidates[:10],
        "rules": {
            "naive_benchmark": "persistence at same forecast horizon",
            "selection_uses_final_oos": False,
            "pass_requires_positive_mse_skill": True,
            "pass_requires_lower_mape_than_naive": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
