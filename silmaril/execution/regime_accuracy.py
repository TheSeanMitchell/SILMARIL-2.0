"""
REGIME ACCURACY AUDIT (4.0 Movement I — Verification) — every regime call is graded against what
the market actually did 24h later. The classifier stops being trusted by default and starts
EARNING trust (Notes #1). Deterministic; honest below sample.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _median(v):
    v = sorted(v)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def build_regime_accuracy(out_dir):
    out = Path(out_dir)
    try:
        rows = [json.loads(l) for l in (out / "REGIME_COMBOS.jsonl").read_text().splitlines() if l.strip()]
        samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
        from .paper_sim import asset_class
    except Exception:
        rows, samples = [], {}
    now = datetime.now(timezone.utc)
    books = {b: {"graded": 0, "correct": 0, "by_label": {}} for b in ("crypto", "stock", "metal", "energy")}
    for r in rows[-200:]:
        try:
            t0 = datetime.fromisoformat(r["t"])
        except Exception:
            continue
        t1 = t0 + timedelta(hours=24)
        if now < t1 + timedelta(minutes=30):
            continue
        for bk in books:
            label = r.get(bk)
            if label in (None, "NO DATA"):
                continue
            moves = []
            for sym, sr in samples.items():
                if asset_class(sym) != bk:
                    continue
                w = []
                for t, p in sr:
                    if not p or p <= 0 or "T00:00:00" in t:
                        continue
                    try:
                        dt = datetime.fromisoformat(t)
                    except Exception:
                        continue
                    if t0 <= dt <= t1:
                        w.append(p)
                if len(w) >= 2 and w[0] > 0:
                    moves.append(w[-1] / w[0] - 1)
            m = _median(moves)
            if m is None:
                continue
            realized = "UPTREND" if m > 0.01 else "DOWNTREND" if m < -0.01 else "SIDEWAYS"
            b = books[bk]
            b["graded"] += 1
            b["correct"] += int(label == realized)
            key = "%s->%s" % (label[0], realized[0])
            b["by_label"][key] = b["by_label"].get(key, 0) + 1
    for bk, b in books.items():
        b["accuracy_pct"] = round(b["correct"] / b["graded"] * 100, 1) if b["graded"] else None
        b["status"] = ("insufficient — each call grades 24h later; keep collecting"
                       if b["graded"] < 5 else "earning trust")
    payload = {"generated_at": now.isoformat(), "books": books,
               "what": ("Every regime call graded vs the market 24h later (median book move, +/-1% "
                        "bands). Trust is EARNED, never assumed — Notes #1 made real.")}
    (out / "REGIME_ACCURACY.json").write_text(json.dumps(payload, indent=1))
    return payload
