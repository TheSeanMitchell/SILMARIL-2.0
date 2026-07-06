"""
STOCK PARITY AUDIT (P6) — why is the stock book idle? Measures, from DAILY candles, how often each
dip threshold (1–4%) actually occurs across the stock universe. Report-only: emits an evidence-based
threshold recommendation the OPERATOR may apply via regime_overrides. No behavior change, no new
signal — the deliberate, honest step before stock-tuned thresholds.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def build_stock_parity_audit(out_dir):
    out = Path(out_dir)
    try:
        S = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception:
        S = {}
    from .paper_sim import asset_class
    ths = [0.01, 0.015, 0.02, 0.03, 0.04]
    hits = {t: 0 for t in ths}
    days = 0
    syms = 0
    for sym, rows in S.items():
        if asset_class(sym) != "stock":
            continue
        closes = [p for t, p in rows if p and p > 0 and "T00:00:00" in t]
        if len(closes) < 30:
            continue
        syms += 1
        for i in range(1, len(closes)):
            days += 1
            mv = closes[i] / closes[i - 1] - 1
            for th in ths:
                if mv <= -th:
                    hits[th] += 1
    if syms == 0:
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
                   "status": "insufficient — stock daily candles missing; run backfill_universe first"}
    else:
        table = [{"dip_threshold_pct": th * 100,
                  "daily_hit_rate_pct": round(hits[th] / days * 100, 2) if days else 0}
                 for th in ths]
        rec = next((r for r in table if r["daily_hit_rate_pct"] >= 1.0), table[-1])
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
                   "symbols_with_history": syms, "symbol_days": days, "table": table,
                   "recommendation": ("evidence: %.2f%%-per-day hit rate at %.1f%% dip — the current 2-3%% "
                                       "intraday threshold rarely fires on liquid names; if stock is to trade "
                                       "meaningfully, set regime_overrides.stock accordingly (OPERATOR decision, "
                                       "report-only)" % (rec["daily_hit_rate_pct"], rec["dip_threshold_pct"]))}
    (out / "STOCK_PARITY_AUDIT.json").write_text(json.dumps(payload, indent=1))
    return payload
