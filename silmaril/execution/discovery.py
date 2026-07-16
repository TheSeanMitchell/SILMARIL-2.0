"""silmaril.execution.discovery — 5.3 THE DISCOVERY LAYER.

The system stops learning only from what it did. Two instruments:

· OPPORTUNITY GRAVEYARD — every near-miss the funnel saw but did not buy is
  buried with its price and reason; the resolver exhumes each at +24h/+7d and
  records what WOULD have happened. "Rejected by X, avg missed +Y%" becomes a
  measured sentence instead of a mystery.
· COUNTERFACTUAL ENGINE — every closed trade spawns deterministic alternates
  from the recorded tape: never_bought · limit_at_target · held_+4h · half_size.
  The Master learns POLICY, not trades.

Emits DISCOVERY.json (+ append-only OPPORTUNITY_GRAVEYARD.jsonl, CF_LEDGER.jsonl).
KILL: discovery.mode:"off". Deterministic; no synthetic prices — only the tape.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic
from .paper_sim import load_all_samples

GY = "OPPORTUNITY_GRAVEYARD.jsonl"
CF = "CF_LEDGER.jsonl"


def _now():
    return datetime.now(timezone.utc)


def _parse(t) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def _series(samples, sym):
    out = []
    for t, p in samples.get(sym) or []:
        if not p or "T00:00:00" in str(t):
            continue
        d = _parse(t)
        if d:
            out.append((d, float(p)))
    out.sort()
    return out


def _px_at(ser, when, fwd_ok=True):
    if not ser:
        return None
    after = [p for d, p in ser if d >= when]
    return (after[0] if after else (ser[-1][1] if fwd_ok else None))


def _read_jsonl(path: Path) -> List[dict]:
    try:
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    except Exception:
        return []


def _write_jsonl(path: Path, rows: List[dict]):
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))


def build_discovery(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cat = _load(out, "PARAM_CATALOG.json")
    kb = cat.get("discovery") or {}
    if str(kb.get("mode", "auto")).lower() != "auto":
        return {"summary": "discovery: off"}
    cap = int(kb.get("graveyard_cap", 5000))
    samples = load_all_samples(out)
    live = _load(out, "paper_sim_live.json")
    now = _now()

    # ── 1 · bury this cycle's near-misses ────────────────────────────────────
    rows = _read_jsonl(out / GY)
    recent_syms = {(r.get("sym"), r.get("book")) for r in rows
                   if (_parse(r.get("t")) or now) > now - timedelta(hours=6)}
    buried = 0
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        b = (live or {}).get(bk) or {}
        held = {p.get("sym") for p in (b.get("positions") or [])}
        for d in (b.get("decision_trace_live") or [])[:12]:
            sym = d.get("sym")
            if not sym or sym in held or (sym, bk) in recent_syms:
                continue
            ser = _series(samples, sym)
            px = ser[-1][1] if ser else None
            if not px:
                continue
            rows.append({"t": now.isoformat(), "sym": sym, "book": bk, "px": px,
                         "dip_pct": d.get("dip_pct"), "conviction": d.get("conviction"),
                         "reason": d.get("why") or d.get("blocked") or "not_selected",
                         "resolved": {}})
            buried += 1

    # ── 2 · exhume: resolve +24h / +7d outcomes ──────────────────────────────
    resolved = 0
    for r in rows:
        t0 = _parse(r.get("t"))
        if not t0 or not r.get("px"):
            continue
        res = r.setdefault("resolved", {})
        ser = _series(samples, r["sym"])
        for tag, dt in (("h24", timedelta(hours=24)), ("d7", timedelta(days=7))):
            if tag in res or now < t0 + dt:
                continue
            pxf = _px_at(ser, t0 + dt)
            win = [p for d, p in ser if t0 <= d <= t0 + dt]
            if pxf:
                res[tag] = {"px": pxf,
                            "would_gross_pct": round((pxf / r["px"] - 1) * 100, 2),
                            "max_gross_pct": (round((max(win) / r["px"] - 1) * 100, 2)
                                              if win else None)}
                resolved += 1
    rows = rows[-cap:]
    _write_jsonl(out / GY, rows)

    # ── 3 · counterfactuals on newly closed trades ───────────────────────────
    disc = _load(out, "DISCOVERY.json", {})
    seen = set(disc.get("cf_seen") or [])
    cf_rows = _read_jsonl(out / CF)
    new_cf = 0
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        d = _load(out, f"paper_book_{bk}.json")
        buys = {}
        for t in d.get("trades") or []:
            if t.get("side") == "BUY":
                buys[t.get("sym")] = t
            if t.get("side") != "SELL":
                continue
            key = f"{bk}:{t.get('sym')}:{t.get('t')}"
            if key in seen:
                continue
            seen.add(key)
            b0 = buys.get(t.get("sym")) or {}
            et, xt = _parse(b0.get("t")), _parse(t.get("t"))
            ser = _series(samples, t.get("sym"))
            if not (et and xt and ser):
                continue
            fee = float(t.get("fee_pct") or 0.5)
            raw_entry = None
            if b0.get("price"):
                raw_entry = float(b0["price"]) / (1 + fee / 200.0)
            best = t.get("best_pct")
            tgt = t.get("target_pct")
            held4 = _px_at(ser, xt + timedelta(hours=4))
            alts = {"never_bought": 0.0,
                    "limit_at_target": (round(float(tgt) - fee, 3)
                                        if (tgt is not None and best is not None
                                            and best >= tgt) else t.get("realized_pct")),
                    "held_4h_more": (round((held4 / raw_entry - 1) * 100 - fee, 3)
                                     if (held4 and raw_entry) else None),
                    "half_size": round(float(t.get("realized_pct") or 0) / 2.0, 3)}
            cf_rows.append({"t": t.get("t"), "sym": t.get("sym"), "book": bk,
                            "actual_net_pct": t.get("realized_pct"),
                            "exit_reason": t.get("exit_reason"), "alts": alts})
            new_cf += 1
    cf_rows = cf_rows[-cap:]
    _write_jsonl(out / CF, cf_rows)

    # ── 4 · aggregates the BRAIN can read ────────────────────────────────────
    by_reason: Dict[str, List[float]] = {}
    for r in rows:
        g = (r.get("resolved") or {}).get("h24", {}).get("would_gross_pct")
        if g is not None:
            by_reason.setdefault(str(r.get("reason"))[:60], []).append(g)
    top_missed = sorted(
        ({"reason": k, "n": len(v), "avg_would_gross_pct": round(sum(v) / len(v), 2)}
         for k, v in by_reason.items() if len(v) >= 3),
        key=lambda x: -x["avg_would_gross_pct"])[:6]
    deltas_l = [c["alts"]["limit_at_target"] - (c.get("actual_net_pct") or 0)
                for c in cf_rows if c["alts"].get("limit_at_target") is not None
                and c.get("actual_net_pct") is not None]
    deltas_h = [c["alts"]["held_4h_more"] - (c.get("actual_net_pct") or 0)
                for c in cf_rows if c["alts"].get("held_4h_more") is not None
                and c.get("actual_net_pct") is not None]
    payload = {"generated_at": now.isoformat(),
               "graveyard": {"buried_total": len(rows), "buried_this_cycle": buried,
                             "resolved_this_cycle": resolved, "top_missed_by_reason": top_missed},
               "counterfactual": {"trades_analyzed": len(cf_rows), "new_this_cycle": new_cf,
                                  "avg_delta_limit_vs_actual_pct": (round(sum(deltas_l) / len(deltas_l), 3)
                                                                    if deltas_l else None),
                                  "avg_delta_held4h_vs_actual_pct": (round(sum(deltas_h) / len(deltas_h), 3)
                                                                     if deltas_h else None)},
               "cf_seen": sorted(seen)[-4000:],
               "what": ("the system learns from what it did NOT do: every rejection resolved "
                        "forward, every trade shadowed by its alternates — policy evidence, "
                        "not vibes")}
    write_json_atomic(out / "DISCOVERY.json", payload)
    return {"summary": f"discovery: graveyard {len(rows)} (+{buried}, resolved {resolved}) · "
                       f"cf {len(cf_rows)} (+{new_cf})"}
