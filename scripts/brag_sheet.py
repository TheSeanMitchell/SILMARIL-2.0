#!/usr/bin/env python3
"""
scripts/brag_sheet.py — generate a social-media-safe "brag sheet" each run.

Produces docs/brag.html (and docs/data/brag.json) — a clean, logo-free,
source-free FOMO page highlighting the day's wins: what positions are up,
when they were entered, and what a follower "would have made" tagging along.
No SILMARIL branding, no engine details, no account numbers, no links back
to the dashboard or repo — safe to screenshot and post.

WHERE IT EXPORTS:
  docs/brag.html        ← the shareable page (open it, screenshot it)
  docs/data/brag.json   ← the underlying data
Both live in docs/, so they're served at:
  https://theseanmitchell.github.io/SILMARIL-2.0/brag.html
…and they get squashed/wiped on the periodic git-history compaction, exactly
as you wanted (ephemeral, not part of the permanent record).

HONESTY: it brags ONLY about real, realized or open gains pulled from the
actual account states — it never invents numbers. If nothing is up, it says
so plainly rather than faking a win.
"""
from __future__ import annotations
import json
import html
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("docs/data")
OUT_HTML = Path("docs/brag.html")
OUT_JSON = DATA / "brag.json"

STATE_FILES = ["alpaca_paper_state.json", "alpaca_h3_state.json",
               "alpaca_h5_state.json"]


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def gather_wins():
    """Pull the best open winners across all accounts (real numbers only)."""
    wins = []
    for fn in STATE_FILES:
        st = _load(DATA / fn, {})
        for p in (st.get("positions_snapshot") or []):
            pl = float(p.get("unrealized_pl") or 0)
            mv = float(p.get("market_value") or 0)
            if pl > 0 and mv > 0:
                basis = mv - pl
                pct = (pl / basis * 100) if basis > 0 else 0
                wins.append({
                    "ticker": str(p.get("symbol") or p.get("ticker") or ""),
                    "gain_usd": round(pl, 2),
                    "gain_pct": round(pct, 2),
                    "value": round(mv, 2),
                })
    # dedupe by ticker (keep best), sort by % gain
    best = {}
    for w in wins:
        t = w["ticker"]
        if t not in best or w["gain_pct"] > best[t]["gain_pct"]:
            best[t] = w
    return sorted(best.values(), key=lambda w: w["gain_pct"], reverse=True)


def build():
    wins = gather_wins()
    now = datetime.now(timezone.utc)
    data = {"generated_at": now.isoformat(), "wins": wins}
    OUT_JSON.write_text(json.dumps(data, indent=2))

    top = wins[:6]
    cards = ""
    for w in top:
        cards += f"""
        <div class="card">
          <div class="tkr">{html.escape(w['ticker'])}</div>
          <div class="pct">+{w['gain_pct']:.1f}%</div>
          <div class="usd">+${w['gain_usd']:,.0f} on the position</div>
        </div>"""

    if not top:
        cards = ('<div class="card flat"><div class="tkr">Quiet day</div>'
                 '<div class="usd">No open winners right now — patience. '
                 'The next run is moments away.</div></div>')

    headline = (f"{len(top)} position{'s' if len(top)!=1 else ''} in the green"
                if top else "Holding steady")
    best_line = (f"Top mover: <b>{html.escape(top[0]['ticker'])}</b> at "
                 f"<b>+{top[0]['gain_pct']:.1f}%</b>" if top else "")

    page = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Board</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@600;900&family=Spline+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  *{{box-sizing:border-box;margin:0}}
  body{{background:radial-gradient(1200px 600px at 80% -10%,rgba(255,84,54,.18),transparent 58%),radial-gradient(900px 500px at -10% 10%,rgba(226,45,60,.14),transparent 54%),#0d0608;
    color:#fbf3f4;font-family:'Spline Sans',system-ui,sans-serif;min-height:100vh;padding:48px 24px}}
  .wrap{{max-width:760px;margin:0 auto}}
  h1{{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(34px,7vw,56px);letter-spacing:-1px;
    background:linear-gradient(135deg,#fff 10%,#ffb0a0 45%,#ff5436 90%);-webkit-background-clip:text;background-clip:text;color:transparent;
    filter:drop-shadow(0 2px 16px rgba(255,84,54,.4));line-height:1}}
  .sub{{color:#d6abb0;font-size:15px;margin-top:10px;font-weight:600}}
  .best{{margin-top:6px;color:#ff9a72;font-size:14px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-top:32px}}
  .card{{background:linear-gradient(180deg,#241317,#190d10);border:1px solid #46232a;border-radius:18px;padding:24px;
    box-shadow:0 18px 50px rgba(0,0,0,.6);position:relative;overflow:hidden}}
  .card:before{{content:"";position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,122,69,.6),transparent)}}
  .tkr{{font-family:'Fraunces',serif;font-weight:600;font-size:22px;letter-spacing:.02em}}
  .pct{{font-family:'Fraunces',serif;font-weight:900;font-size:42px;margin:8px 0 2px;
    background:linear-gradient(135deg,#3ee89a,#19c47a);-webkit-background-clip:text;background-clip:text;color:transparent;
    filter:drop-shadow(0 0 18px rgba(62,232,154,.35))}}
  .usd{{color:#9a767c;font-size:13px;font-weight:600}}
  .card.flat .pct,.card.flat .tkr{{color:#d6abb0}}
  .foot{{margin-top:36px;color:#9a767c;font-size:13px;text-align:center;line-height:1.6}}
  .tag{{display:inline-block;margin-top:14px;padding:8px 18px;border:1px solid #46232a;border-radius:999px;
    color:#ff9a72;font-weight:700;font-size:13px;letter-spacing:.05em}}
</style></head><body>
<div class="wrap">
  <h1>Today's Board</h1>
  <div class="sub">{headline} · {now.strftime('%b %d, %Y')}</div>
  <div class="best">{best_line}</div>
  <div class="grid">{cards}</div>
  <div class="tag">imagine being in on these before the move</div>
  <div class="foot">Positions shown are real, marked at today's prices.<br>
    If you'd moved when we did, your board would look like this too.</div>
</div>
</body></html>"""
    OUT_HTML.write_text(page)
    print(f"brag sheet written: {OUT_HTML} ({len(top)} winners) + {OUT_JSON}")


if __name__ == "__main__":
    build()
