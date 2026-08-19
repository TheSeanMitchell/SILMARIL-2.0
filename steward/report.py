"""steward.report — one page, one hierarchy: DELTA-VS-HOLD above equity, always.

The last dashboard led with equity, and equity flatters — a book that made +5% in a
market that made +10% looks green while losing. This page's biggest number, per
book, is the dollars gained or lost AGAINST doing nothing, because that is the only
number that says whether any of this is worth the effort.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import prices as P
from .book import bench_equity, equity, universe_of
from .config import (BASELINE_FILE, EQUITY_FILE, REGISTERED, REPORT_FILE,
                     registration_hash)
from .util import read_json


# ── the weekly paired t against the benchmark ─────────────────────────────────────

def weekly_t(rows: List) -> Tuple[Optional[float], int]:
    """rows = [[date, equity, bench_equity], ...] -> (one-sided paired t, n_weeks)."""
    by_week = {}
    for d, eq, be in rows:
        y, w, _ = datetime.strptime(d, "%Y-%m-%d").isocalendar()
        by_week[(y, w)] = (eq, be)
    pts = [by_week[k] for k in sorted(by_week)]
    if len(pts) < 4:
        return None, max(0, len(pts) - 1)
    diffs = []
    for i in range(1, len(pts)):
        r_book = pts[i][0] / pts[i - 1][0] - 1 if pts[i - 1][0] else 0
        r_bench = pts[i][1] / pts[i - 1][1] - 1 if pts[i - 1][1] else 0
        diffs.append(r_book - r_bench)
    n = len(diffs)
    m = sum(diffs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in diffs) / n)
    return (m / (sd / math.sqrt(n)) if sd > 1e-12 else None), n


# ── html assembly ─────────────────────────────────────────────────────────────────

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0E1116;color:#E7EBF0;font:15px/1.55 -apple-system,'Segoe UI',Roboto,sans-serif;padding:28px 16px 80px}
.wrap{max-width:1100px;margin:0 auto}
.mono{font-family:'Cascadia Code','SF Mono',Consolas,monospace}
header{border-bottom:2px solid #E7EBF0;padding-bottom:18px;margin-bottom:26px}
h1{font-size:26px;letter-spacing:.04em} h1 small{color:#D2A64A;font-size:14px;letter-spacing:.14em}
.sub{color:#8B95A2;font-size:13px;margin-top:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-bottom:26px}
.card{background:#161B22;border:1px solid #262D36;border-radius:6px;padding:18px 20px}
.card h2{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#8B95A2;display:flex;justify-content:space-between}
.delta{font-size:34px;font-weight:700;margin:10px 0 2px;font-variant-numeric:tabular-nums}
.dlabel{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8B95A2;margin-bottom:12px}
.pos{color:#6FBF97}.neg{color:#E0837A}.dim{color:#8B95A2}
.kv{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-top:1px solid #1D242D}
.kv b{font-weight:500;color:#C4CCD6;font-variant-numeric:tabular-nums}
.light{display:inline-block;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700;letter-spacing:.08em}
.ACTIVE{background:#12291F;color:#6FBF97}.KILLED{background:#2E1917;color:#E0837A}
.HALTED,.COLLECTING{background:#2E2716;color:#D2A64A}.PASSED{background:#12291F;color:#6FBF97}
section{margin-bottom:26px}
section>h3{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#D2A64A;margin-bottom:10px;border-bottom:1px solid #262D36;padding-bottom:6px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{color:#8B95A2;font-size:10px;letter-spacing:.12em;text-transform:uppercase;text-align:left;padding:7px 10px;border-bottom:1px solid #262D36}
td{padding:7px 10px;border-bottom:1px solid #1D242D;font-variant-numeric:tabular-nums}
.tw{overflow-x:auto;background:#161B22;border:1px solid #262D36;border-radius:6px}
.note{color:#8B95A2;font-size:12px;margin-top:8px}
footer{color:#8B95A2;font-size:12px;border-top:1px solid #262D36;padding-top:14px;line-height:1.8}
"""


def _money(v: float) -> str:
    return ("+" if v >= 0 else "−") + "$%s" % format(abs(round(v)), ",")


def _book_card(name: str, bk: Dict, store: Dict, eq_rows: List) -> str:
    eq = equity(bk, store)
    be = bench_equity(bk, store)
    delta = eq - be
    cls = "pos" if delta >= 0 else "neg"
    t, nweeks = weekly_t(eq_rows)
    bench_names = "+".join(REGISTERED["books"][name]["bench"])
    positions = ", ".join(
        "%s %s" % (s, ("%+.1f%%" % ((P.latest_bar(store, s)[1] / p["entry_eff"] - 1) * 100))
                   if P.latest_bar(store, s) else s)
        for s, p in bk["positions"].items()) or "cash"
    kill = ('<div class="note neg">%s</div>' % bk["kill_reason"]) if bk.get("kill_reason") else ""
    ttxt = ("t=%+.2f · wk %d/104" % (t, nweeks)) if t is not None else ("wk %d/104" % nweeks)
    return f"""
    <div class="card">
      <h2>{name} <span class="light {bk['status']}">{bk['status']}</span></h2>
      <div class="delta {cls}">{_money(delta)}</div>
      <div class="dlabel">vs holding {bench_names} — the number that matters</div>
      <div class="kv"><span>equity</span><b>${eq:,.0f}</b></div>
      <div class="kv"><span>hold twin</span><b>${be:,.0f}</b></div>
      <div class="kv"><span>holding</span><b>{positions}</b></div>
      <div class="kv"><span>primary hypothesis</span><b class="mono">{ttxt}</b></div>
      {kill}
    </div>"""


def _shadow_rows(shadow: Dict) -> str:
    rows = []
    for key in ("newsfade", "form4", "congress"):
        s = (shadow.get("summary") or {}).get(key, {})
        spec = REGISTERED["shadows"][key]
        status = s.get("status", spec.get("status", "COLLECTING"))
        rows.append(
            "<tr><td class='mono'>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td><span class='light %s'>%s</span></td><td class='dim'>%s</td></tr>" % (
                key.upper(),
                str(s.get("n", "—")) + "/" + str(s.get("need_n", "—")) if "n" in s else "—",
                ("%+.3f%%" % s["mean_pct"]) if s.get("mean_pct") is not None else "—",
                ("%+.2f" % s["t"]) if s.get("t") is not None else "—",
                status if status in ("PASSED", "KILLED") else "COLLECTING", status,
                spec.get("pass", spec.get("activation", ""))[:70]))
    return "".join(rows)


def _baseline_rows(base: Dict) -> str:
    rows = []
    for name, r in (base.get("books") or {}).items():
        if r.get("skipped"):
            rows.append("<tr><td class='mono'>%s</td><td colspan='5' class='dim'>%s</td></tr>"
                        % (name, r["skipped"]))
            continue
        d = r.get("delta_usd")
        cls = "pos" if (d or 0) >= 0 else "neg"
        rows.append("<tr><td class='mono'>%s</td><td>%s → %s</td><td>$%s</td><td>$%s</td>"
                    "<td class='%s'>%s</td><td>%s · DD %s%%</td></tr>" % (
                        name, r["window"][0], r["window"][1],
                        format(round(r["final_equity"]), ","),
                        format(round(r["bench_equity"] or 0), ","),
                        cls, _money(d or 0), r["round_trips"], r["max_dd_pct"]))
    return "".join(rows)


def build(state: Dict, store: Dict, data_dir: Path, docs_dir: Path) -> Path:
    eq_hist = read_json(Path(data_dir) / EQUITY_FILE, {})
    shadow = read_json(Path(data_dir) / "steward_shadow.json", {})
    base = read_json(Path(data_dir) / BASELINE_FILE, {})
    rh = registration_hash()
    epoch = state.get("epoch", "—")
    days = ((datetime.now(timezone.utc) - datetime.fromisoformat(epoch)).days
            if epoch not in (None, "—") else 0)
    cards = "".join(_book_card(n, bk, store, eq_hist.get(n, []))
                    for n, bk in state["books"].items())
    exp = REGISTERED["expected"]
    kills = REGISTERED["kills"]
    dd_kills = " / ".join("%s %.0f%%" % (k, v)
                          for k, v in kills["max_drawdown_pct"].items())
    next_cp = next((c for c in (91, 182, 273) if days < c), None)
    cp_txt = ("day %d of %d — execution audit only, no verdict" % (days, next_cp)
              if next_cp else "checkpoints complete — verdict at week 104")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>STEWARD — SILMARIL 8.0</title><style>{_CSS}</style></head><body><div class="wrap">
<header>
  <h1>STEWARD <small>SILMARIL 8.0 · registration {rh}</small></h1>
  <div class="sub mono">epoch {str(epoch)[:10]} · day {days} · {cp_txt} · updated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>
</header>

<div class="grid">{cards}</div>

<section><h3>The registered experiment</h3>
<div class="card" style="font-size:13.5px;line-height:1.7">
  <b>{REGISTERED['strategy_family']}</b> — signal at bar D, fills at the first bar after D;
  monthly seats with a {REGISTERED['hysteresis']:.0%} hysteresis; absolute gate at
  {REGISTERED['abs_gate']:.2%} (cash is a position); both-sides fees
  {REGISTERED['round_trip_cost']['stock']:.1%}/{REGISTERED['round_trip_cost']['crypto']:.1%} equity/crypto.<br>
  <span class="dim">PASS (week 104): delta &gt; $0 and one-sided paired weekly t ≥ 1.7.
  EXITS check the gate daily (fast out, slow in); entries wait for the month.
  KILLS (per class): drawdown −{dd_kills} · week-52 delta ≤ ${kills['week52_delta_usd']:.0f} ·
  stale tape &gt; {kills['stale_data_days']}d halts buys.
  Registered expectation: {exp['central_estimate_pct'][0]}–{exp['central_estimate_pct'][1]}%/yr central,
  {exp['annual_net_range_pct'][0]}%…{exp['annual_net_range_pct'][1]}% range,
  P(beat hold) {exp['p_beat_hold_104wk']} — and P($1k/mo on $10k): {exp['p_1000_per_month_on_10k'].split(' — ')[0]}.</span>
</div></section>

<section><h3>Shadow hypotheses — graded, never funded</h3>
<div class="tw"><table>
<tr><th>hypothesis</th><th>n / needed</th><th>mean</th><th>t</th><th>status</th><th>pass mark</th></tr>
{_shadow_rows(shadow)}
</table></div>
<div class="note">NEWSFADE was found in-sample and owes the data-mining debt (t ≤ −3.0 to replicate).
FORM4 is a filing-count proxy, stated plainly. CONGRESS is registered so the hypothesis predates the data.</div>
</section>

<section><h3>Design check — the rules replayed on the warmup tape</h3>
<div class="tw"><table>
<tr><th>book</th><th>window</th><th>final</th><th>hold</th><th>delta</th><th>trips · max DD</th></tr>
{_baseline_rows(base)}
</table></div>
<div class="note">{base.get('label', 'IN_DESIGN_CHECK')} — context, never proof. The forward window above is the experiment.</div>
</section>

<footer class="mono">
registration {rh} · parameters frozen in steward/config.py · any edit is a visible re-registration event<br>
delta-vs-hold sits above equity by design: a book that made +5% while its market made +10% lost money.<br>
paper simulation · not investment advice · wipes are not a feature of this system
</footer>
</div></body></html>"""
    out = Path(docs_dir) / REPORT_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
