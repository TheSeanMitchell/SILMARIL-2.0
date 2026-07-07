"""
SELF-CALIBRATION (Movement V, Phase 24 foundation) — predicted vs realized, per book.
Every BUY records its expected move + conviction; every SELL records what actually happened. This
builder measures the gap. With thin data it says so honestly ("insufficient") instead of fabricating
trust. Changes CONFIDENCE displays only — never behavior (Law 5).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def build_calibration(out_dir):
    out = Path(out_dir)
    books = {}
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        try:
            trs = json.loads((out / f"paper_book_{bk}.json").read_text()).get("trades", [])
        except Exception:
            trs = []
        buys = {t.get("sym"): t for t in trs if t.get("side") == "BUY"}
        pairs = []
        for t in trs:
            if t.get("side") == "SELL" and t.get("realized_pct") is not None:
                b = buys.get(t.get("sym")) or {}
                exp = b.get("expected_move")
                if exp is not None:
                    pairs.append((exp * 100, t["realized_pct"]))
        n = len(pairs)
        if n < 5:
            books[bk] = {"n": n, "status": "insufficient — needs ≥5 closed predicted trades",
                         "trust": "unrated"}
            continue
        pe = sum(p for p, r in pairs) / n
        re_ = sum(r for p, r in pairs) / n
        gap = re_ - pe
        books[bk] = {"n": n, "predicted_edge_pct": round(pe, 3), "realized_edge_pct": round(re_, 3),
                     "gap_pct": round(gap, 3),
                     "verdict": ("well-calibrated" if abs(gap) < 0.5 else
                                 "OVERCONFIDENT — realized under prediction" if gap < 0 else
                                 "underconfident — beating its own estimates"),
                     "trust": "earning"}
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "books": books,
               "what": ("Confidence must earn confidence. Predicted edge vs realized edge per book. "
                        "Adjusts trust displays only — never behavior directly (Law 5).")}
    (out / "CALIBRATION.json").write_text(json.dumps(payload, indent=1))
    return payload
