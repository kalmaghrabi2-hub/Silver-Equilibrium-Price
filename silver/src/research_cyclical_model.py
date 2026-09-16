#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, math, statistics, urllib.parse, urllib.request
from bisect import bisect_right
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/silver/data/cyclical_research.json"
TARGET = "SI=F"
FRED = ["DFII10", "DTWEXBGS", "VIXCLS", "T10YIE"]
FEATURE_SETS = [
    ["RET1", "GOLD_RET1", "COPPER_RET1", "D_DFII10", "D_DTWEXBGS", "D_VIXCLS"],
    ["RET1", "RET4", "GOLD_RET1", "COPPER_RET1", "D_DFII10", "D_DTWEXBGS", "D_VIXCLS", "D_T10YIE"],
    ["RET1", "RET4", "GOLD_RET1", "COPPER_RET1", "DFII10", "DTWEXBGS", "VIXCLS", "T10YIE", "D_DFII10", "D_DTWEXBGS"],
]
LAMBDAS = [0.5, 2.0, 10.0, 50.0]
WEIGHTS = [0.25, 0.50, 0.75, 1.0]
MIN_TRAIN, VALIDATION_WEEKS, FINAL_OOS_WEEKS = 156, 156, 260
UA = "Mozilla/5.0 SilverCyclicalResearch/1.0"


def yahoo(symbol: str):
    q = urllib.parse.quote(symbol, safe="")
    now = int(datetime.now(timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?period1=946684800&period2={now}&interval=1wk&events=history&includeAdjustedClose=true"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    out = []
    for t, v in zip(result["timestamp"], result["indicators"]["quote"][0]["close"]):
        if v is not None and float(v) > 0:
            out.append((datetime.fromtimestamp(t, tz=timezone.utc).date(), float(v)))
    return out, url


def fred(series_id: str):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8-sig")
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        raw = (row.get(series_id) or "").strip()
        if raw and raw != ".":
            rows.append((date.fromisoformat(row.get("DATE") or row["observation_date"]), float(raw)))
    return rows, url


def asof(rows, d, max_age=14):
    dates = [x[0] for x in rows]
    i = bisect_right(dates, d) - 1
    if i < 0 or (d - dates[i]).days > max_age:
        return None
    return rows[i][1]


def market_asof(rows, d, max_age=10):
    dates = [x[0] for x in rows]
    i = bisect_right(dates, d) - 1
    if i < 0 or (d - dates[i]).days > max_age:
        return None
    return rows[i][1]


def solve(a, b):
    n = len(b)
    aug = [a[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(aug[r][c]))
        aug[c], aug[p] = aug[p], aug[c]
        z = aug[c][c]
        if abs(z) < 1e-12:
            raise RuntimeError("singular matrix")
        aug[c] = [v / z for v in aug[c]]
        for r in range(n):
            if r == c:
                continue
            f = aug[r][c]
            aug[r] = [aug[r][j] - f * aug[c][j] for j in range(n + 1)]
    return [aug[i][-1] for i in range(n)]


def fit_predict(train, row, features, lam):
    xs = [[r["x"][f] for f in features] for r in train]
    cols = list(zip(*xs))
    means = [statistics.fmean(c) for c in cols]
    sds = [statistics.pstdev(c) or 1.0 for c in cols]
    X = [[1.0] + [(v - m) / s for v, m, s in zip(x, means, sds)] for x in xs]
    y = [r["ret"] for r in train]
    p = len(X[0])
    A, b = [[0.0] * p for _ in range(p)], [0.0] * p
    for x, target in zip(X, y):
        for i in range(p):
            b[i] += x[i] * target
            for j in range(p):
                A[i][j] += x[i] * x[j]
    for i in range(1, p):
        A[i][i] += lam
    beta = solve(A, b)
    live = [1.0] + [(row["x"][f] - m) / s for f, m, s in zip(features, means, sds)]
    return sum(a * b for a, b in zip(live, beta))


def metrics(pred, actual, anchor):
    mse = statistics.fmean((a - p) ** 2 for a, p in zip(actual, pred))
    nmse = statistics.fmean((a - n) ** 2 for a, n in zip(actual, anchor))
    mape = 100 * statistics.fmean(abs((a - p) / a) for a, p in zip(actual, pred))
    nmape = 100 * statistics.fmean(abs((a - n) / a) for a, n in zip(actual, anchor))
    direction = 100 * sum(((a - n) > 0) == ((p - n) > 0) for a, p, n in zip(actual, pred, anchor)) / len(actual)
    return {"mse": mse, "naive_mse": nmse, "mape_pct": mape, "naive_mape_pct": nmape, "mse_skill_pct": 100 * (1 - mse / nmse), "relative_mape_improvement_pct": 100 * (nmape - mape) / nmape, "direction_accuracy_pct": direction}


def dm(pred, actual, anchor, lag=4):
    d = [(a - n) ** 2 - (a - p) ** 2 for a, p, n in zip(actual, pred, anchor)]
    n = len(d)
    mu = statistics.fmean(d)
    cen = [x - mu for x in d]
    hac = sum(x * x for x in cen) / n
    for k in range(1, lag + 1):
        g = sum(cen[t] * cen[t - k] for t in range(k, n)) / n
        hac += 2 * (1 - k / (lag + 1)) * g
    if hac <= 0:
        return 0.0, 1.0
    stat = mu / math.sqrt(hac / n)
    return stat, 0.5 * math.erfc(stat / math.sqrt(2))


def main():
    metal, target_url = yahoo(TARGET)
    gold_factor, gold_url = yahoo("GC=F")
    copper_factor, copper_url = yahoo("HG=F")
    frows, sources = {}, {"target": target_url, "GC=F": gold_url, "HG=F": copper_url}
    for s in FRED:
        frows[s], sources[s] = fred(s)
    rows = []
    for i in range(5, len(metal) - 1):
        d0, p0 = metal[i]
        d1, p1 = metal[i + 1]
        if (d1 - d0).days > 10:
            continue
        x = {"RET1": math.log(p0 / metal[i - 1][1]), "RET4": math.log(p0 / metal[i - 4][1])}
        g0, gm = market_asof(gold_factor, d0), market_asof(gold_factor, metal[i - 1][0])
        c0, cm = market_asof(copper_factor, d0), market_asof(copper_factor, metal[i - 1][0])
        if None in (g0, gm, c0, cm) or min(g0, gm, c0, cm) <= 0:
            continue
        x["GOLD_RET1"] = math.log(g0 / gm)
        x["COPPER_RET1"] = math.log(c0 / cm)
        ok = True
        for s in FRED:
            v0, vm = asof(frows[s], d0), asof(frows[s], metal[i - 1][0])
            if v0 is None or vm is None:
                ok = False
                break
            x[s], x["D_" + s] = v0, v0 - vm
        if ok:
            rows.append({"date": d1.isoformat(), "anchor": p0, "actual": p1, "ret": math.log(p1 / p0), "x": x})
    required = MIN_TRAIN + VALIDATION_WEEKS + FINAL_OOS_WEEKS
    if len(rows) < required:
        raise RuntimeError(f"insufficient complete rows: {len(rows)} < {required}")
    test0 = len(rows) - FINAL_OOS_WEEKS
    val0 = test0 - VALIDATION_WEEKS
    candidates = []
    for features in FEATURE_SETS:
        for lam in LAMBDAS:
            raw = {i: fit_predict(rows[:i], rows[i], features, lam) for i in range(val0, test0)}
            for w in WEIGHTS:
                pred = [rows[i]["anchor"] * math.exp(w * raw[i]) for i in range(val0, test0)]
                actual = [rows[i]["actual"] for i in range(val0, test0)]
                anchor = [rows[i]["anchor"] for i in range(val0, test0)]
                m = metrics(pred, actual, anchor)
                candidates.append((m["mse"], m["mape_pct"], features, lam, w, m))
    _, _, features, lam, weight, validation_metrics = min(candidates, key=lambda z: (z[0], z[1]))
    pred, actual, anchor, dates = [], [], [], []
    for i in range(test0, len(rows)):
        r = fit_predict(rows[:i], rows[i], features, lam)
        pred.append(rows[i]["anchor"] * math.exp(weight * r))
        actual.append(rows[i]["actual"])
        anchor.append(rows[i]["anchor"])
        dates.append(rows[i]["date"])
    m = metrics(pred, actual, anchor)
    dm_stat, dm_p = dm(pred, actual, anchor)
    windows = []
    for k in range(5):
        a, b = k * 52, (k + 1) * 52
        mm = metrics(pred[a:b], actual[a:b], anchor[a:b])
        windows.append({"window": k + 1, "mse_skill_pct": mm["mse_skill_pct"], "positive": mm["mse_skill_pct"] > 0})
    checks = {"nonzero_model_weight": weight > 0, "min_mse_skill": m["mse_skill_pct"] >= 2.0, "min_relative_mape_improvement": m["relative_mape_improvement_pct"] >= 1.0, "dm_significance": dm_p <= 0.05, "regime_stability": sum(x["positive"] for x in windows) >= 4, "directional_information": m["direction_accuracy_pct"] >= 52.5}
    statistical_pass = all(checks.values())
    payload = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "model": "silver-cyclical-return-ridge-research-v1", "status": "RESEARCH_ONLY", "promotion_eligible": False, "promotion_blocker": "Historical FRED CSV is current-vintage. ALFRED point-in-time vintages or a sufficiently long committed forward archive are required before publication promotion.", "data_sources": sources, "selected": {"features": features, "ridge_lambda": lam, "model_weight": weight, "validation_metrics": validation_metrics}, "final_oos": {"start": dates[0], "end": dates[-1], "n": len(pred), **m, "dm_stat": dm_stat, "dm_one_sided_p_value": dm_p, "positive_52w_windows": sum(x["positive"] for x in windows), "windows": windows, "checks": checks, "statistical_gate": "PASS" if statistical_pass else "FAIL"}, "policy": {"final_oos_untouched": True, "selection_window_weeks": VALIDATION_WEEKS, "final_oos_weeks": FINAL_OOS_WEEKS, "no_price_clipping": True, "current_published_price_unchanged": True}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
