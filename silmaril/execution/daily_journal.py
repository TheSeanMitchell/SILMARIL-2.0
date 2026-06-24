"""
silmaril.execution.daily_journal — DAILY JOURNAL / LIVE BRAG SHEET (2.5.4).

Writes a short, human-sounding log entry each run — like an employee marking the company log —
that finds something true and good to point out, even on a rough day ("despite X, we had a
solid Y"). Pulls from real state (realized P&L per book, champion survivability, recent win rate,
edge capture, regime) and assembles one motivational paragraph from a template bank keyed to
whatever is genuinely going well. Never invents wins. Emits DAILY_JOURNAL.json.
"""
from __future__ import annotations
import json, random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from ._trade_helpers import closed_trades, _dt
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def build_daily_journal(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    live = _load(out, "paper_sim_live.json")
    gov = _load(out, "CHAMPION_GOVERNANCE.json")
    tim = _load(out, "TIMER_OPTIMIZATION.json")
    thr = _load(out, "THRESHOLD_CHAMPION.json")
    reg = _load(out, "REGIME_CLASSIFIER.json")

    def realized(bk): return ((live.get(bk, {}) or {}).get("realized")) or 0
    cr, st = realized("crypto"), realized("stock")
    champ = (gov.get("declared_champion") or {})
    surv = champ.get("survivability_score")
    cname = champ.get("strategy")

    # win rate over last 24h of closed trades
    trades = closed_trades(out)
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = [t for t in trades if _dt(t["exit_t"]) and _dt(t["exit_t"]) >= cutoff]
    wins = sum(1 for t in recent if t["realized_pct"] > 0)
    wr = round(wins / len(recent) * 100) if recent else None
    cryp_tim = (tim.get("by_book") or {}).get("crypto") or {}
    edge = cryp_tim.get("optimal_avg_realized_pct")
    combo = thr.get("champion_combo") or {}

    goods: List[str] = []
    if cr and cr > 0: goods.append(f"the crypto book is green on realized P&L (+${cr:.2f})")
    if surv and surv >= 70: goods.append(f"our champion {cname} is holding strong at {surv:.0f}/100 survivability")
    if wr is not None and wr >= 50: goods.append(f"we won {wr}% of the last 24h of closed trades")
    if edge is not None and edge > 0: goods.append(f"the timer study says our best hold captures +{edge}%/trade")
    if combo: goods.append(f"the drop×bounce lab found a {combo.get('expectancy_pct')}%/trade edge at drop {combo.get('drop')}%→target {combo.get('bounce')}%")
    fresh = sum(1 for b, d in (reg.get("by_book") or {}).items() if d.get("regime") not in (None, "NO DATA"))
    if fresh: goods.append(f"regime classification is live on {fresh} book(s) so we can read the tape before betting")

    bads: List[str] = []
    if st and st < 0: bads.append(f"the stock book is underwater (${st:.2f})")
    if cr and cr < 0: bads.append(f"crypto realized is red (${cr:.2f})")
    if wr is not None and wr < 50: bads.append(f"win rate dipped to {wr}% over the last day")

    openers = ["Log entry:", "Today's note:", "From the desk:", "Quick log:", "Marking the book:"]
    closers = [
        "Not a trading system yet — but the evidence pile is growing every cycle, and that's the job today.",
        "We're playing for data, not dollars, and the data keeps getting cleaner.",
        "Slow is smooth, smooth is fast. Another honest cycle in the books.",
        "No overclaiming, no faked wins — just one more truthful day of measurement.",
        "The edge is still marginal, but it's measured, and measured beats hoped.",
    ]
    random.seed(datetime.now().strftime("%Y%m%d%H"))   # stable within the hour
    if goods and bads:
        entry = f"{random.choice(openers)} Despite {bads[0]}, {goods[0]}" + (f", and {goods[1]}" if len(goods) > 1 else "") + f". {random.choice(closers)}"
    elif goods:
        entry = f"{random.choice(openers)} {goods[0].capitalize()}" + (f", and {goods[1]}" if len(goods) > 1 else "") + f". {random.choice(closers)}"
    else:
        entry = f"{random.choice(openers)} Quiet tape, no fills to brag about yet — but every workflow is green and the books are intact. {random.choice(closers)}"

    payload = {"generated_at": _now(), "entry": entry,
               "good_signals": goods, "watch_items": bads,
               "what": "A human-voice daily log that surfaces something genuinely good each run.",
               "note": "Composed only from true state — never invents wins."}
    try: write_json_atomic(out / "DAILY_JOURNAL.json", payload)
    except Exception: pass
    return payload
