"""
THE INSPECTOR — 7.2.2. A pattern-recognition auditor that reads the system the way the
operator does, every cycle, and writes down what it finds.

WHY. Every serious bug in this project's history was found by the operator's eye, not by the
tripwire battery. The battery answers "does each law still hold in isolation?" — 124 tests, all
green, while a sleeve took zero trades for three releases because it was wired to the wrong
candidate funnel. Nothing was *broken*; something was *disconnected*, and no unit test asks
that question. The operator asked for something that "combs through and checks for this type of
stuff... recognizes graph patterns, and starts to naturally steer the project towards the
profitable moves."

WHAT MAKES THIS DIFFERENT FROM THE BATTERY:
  selftest asks   "is this law still enforced?"            -> pass/fail, isolated, synthetic
  the INSPECTOR asks "does the RECORD look like a working system?" -> findings, on real data

It is a skeptic, not a cheerleader. Every check below exists because a real failure got past
everything else, and each one is written so that a green result is a claim it can be held to.

THE CHECKS, and the incident each one comes from:

  A. SILENT SLEEVES        a sleeve with zero trades AND zero vetoes is not picky, it is
                           disconnected (L/N/O/Q/R/S/T, three releases)
  B. GOAL MISSES           a position whose tape crossed its target while no trail armed
                           (the operator's "every reason for selling high is being ignored")
  C. LABEL INTEGRITY       an exit whose result contradicts its own name — a BREAKEVEN_LOCK
                           that books -3.64% is not a break-even lock (ONDO-USD)
  D. IMPOSSIBLE FILLS      a limit exit above its limit, the class that produced the
                           $242 PNUT windfall
  E. HEADLINE HONESTY      a sleeve whose reported return has the opposite sign to its
                           REALIZED P&L (six of them, and I repeated one to the operator)
  F. GIVE-BACK LEAK        winners that closed negative, and how much peak is surrendered
  G. FEED COMBS            V-shaped round trips to the identical price — the five-month
                           sawtooth, in both its crypto-grid and out-of-hours forms
  H. STRUCTURE AGREEMENT   did the graph say what the trade did? which structure states
                           preceded wins, and which preceded losses  <- THE STEERING PART
  I. STALE STORES          a panel reading a store nothing has written this cycle

Output: INSPECTOR.json — findings ranked by severity, each with the evidence that produced it
and, where the data supports one, a concrete next action. It changes no behaviour. It cannot:
an auditor that trades is not an auditor.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .atomic_io import write_json_atomic
except Exception:                                            # pragma: no cover
    def write_json_atomic(path, payload):                    # type: ignore
        Path(path).write_text(json.dumps(payload, indent=2))

SEV = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def _live(rows: List):
    out = []
    for r in (rows or []):
        try:
            if not r or len(r) < 2 or not r[1] or float(r[1]) <= 0:
                continue
            if "T00:00:00" in str(r[0]):
                continue
            out.append((str(r[0]), float(r[1])))
        except Exception:
            continue
    out.sort()
    return out


def _closed_trades(lab: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every closed sleeve trade, paired with its opening BUY so entry and hold are known."""
    rows = []
    for key, b in (lab.get("sleeves") or {}).items():
        opens: Dict[str, Any] = {}
        for t in (b.get("trades") or []):
            sym = t.get("sym")
            if not sym:
                continue
            if t.get("side") == "BUY":
                opens[sym] = t
            elif t.get("side") == "SELL":
                o = opens.pop(sym, None)
                rows.append({
                    "sleeve": key, "sym": sym,
                    "entry": t.get("entry") or (o or {}).get("entry"),
                    "exit": t.get("exit"), "why": str(t.get("why") or ""),
                    "net": t.get("realized_pct"),
                    "opened_t": t.get("opened_t") or (o or {}).get("t"),
                    "closed_t": t.get("t"),
                    "target_pct": (o or {}).get("target_pct"),
                    "fill_capped": bool(t.get("fill_capped")),
                })
    return rows


def build_inspector(out_dir, samples: Dict[str, List] = None) -> Dict[str, Any]:
    out = Path(out_dir)
    now = datetime.now(timezone.utc)
    if samples is None:
        try:
            from .canon_keys import canonical_samples
            samples = canonical_samples(out)
        except Exception:
            samples = {}
    tape = {s: _live(r) for s, r in (samples or {}).items()}

    lab = _load(out, "STRATEGY_LAB.json")
    vetoes = _load(out, "SLEEVE_VETOES.json")
    reads = (_load(out, "GRAPH_READ.json").get("by_symbol") or {})
    closed = _closed_trades(lab)
    findings: List[Dict[str, Any]] = []

    def add(sev, code, title, detail, evidence=None, action=None):
        findings.append({"severity": sev, "code": code, "title": title, "detail": detail,
                         "evidence": evidence or [], "action": action})

    # ── A. SILENT SLEEVES ─────────────────────────────────────────────────────────────
    veto_letters: Dict[str, int] = {}
    for v in (vetoes.get("vetoes") or []):
        k = str(v.get("sleeve") or "?")
        veto_letters[k] = veto_letters.get(k, 0) + 1
    silent = []
    for bk, rows in (lab.get("by_industry") or {}).items():
        for x in rows:
            slv = x.get("sleeve")
            if (x.get("closed") or 0) == 0 and (x.get("open") or 0) == 0:
                if veto_letters.get(slv, 0) == 0:
                    silent.append("%s:%s" % (bk, slv))
    if silent:
        add("HIGH", "SILENT_SLEEVE",
            "%d sleeve-books took no trades AND refused nothing" % len(silent),
            "A sleeve that is merely picky leaves refusals behind. Zero trades with zero "
            "refusals means it never saw a candidate — the disconnection pattern that hid "
            "L/N/O/Q/R/S/T for three releases.",
            sorted(silent)[:24],
            "Check what feeds this sleeve's candidate pool; a thesis sleeve should scan its own "
            "universe, not inherit the mean-reversion dip funnel.")

    # ── B. GOAL MISSES ────────────────────────────────────────────────────────────────
    misses = []
    for key, b in (lab.get("sleeves") or {}).items():
        for sym, p in (b.get("positions") or {}).items():
            e, tg, t0 = p.get("entry"), p.get("target"), str(p.get("t") or "")
            if not e or not tg:
                continue
            seg = [r for r in tape.get(sym, []) if r[0] >= t0]
            if len(seg) < 2:
                continue
            pk = max(r[1] for r in seg)
            if pk >= e * (1 + tg) and not p.get("peak_chg"):
                misses.append({"sleeve": key, "sym": sym,
                               "peak_pct": round((pk / e - 1) * 100, 2),
                               "target_pct": round(tg * 100, 2),
                               "now_pct": round((seg[-1][1] / e - 1) * 100, 2)})
    if misses:
        add("CRITICAL", "GOAL_MISS",
            "%d open positions crossed their target with no exit and no trail armed" % len(misses),
            "The tape shows price at or above the target while the position is still open and "
            "carries no high-water mark. Either the exit path did not run or the trail failed "
            "to arm.", misses[:12],
            "Trace the exit path for these symbols; a crossed target must either sell or arm a trail.")

    # ── C. LABEL INTEGRITY ────────────────────────────────────────────────────────────
    bad_labels = []
    for t in closed:
        n = t.get("net")
        if n is None:
            continue
        why = t["why"]
        if why == "BREAKEVEN_LOCK" and n < -0.75:
            bad_labels.append({**{k: t[k] for k in ("sleeve", "sym", "why")}, "net_pct": n,
                               "contradiction": "a break-even lock that books a real loss"})
        if why == "TARGET" and t.get("target_pct") and n > float(t["target_pct"]) + 0.6:
            bad_labels.append({**{k: t[k] for k in ("sleeve", "sym", "why")}, "net_pct": n,
                               "contradiction": "a limit exit above its own limit"})
        if why in ("CEILING_READ", "CEILING_SWEEP", "GIVEBACK_CAP") and n < -0.2:
            bad_labels.append({**{k: t[k] for k in ("sleeve", "sym", "why")}, "net_pct": n,
                               "contradiction": "a profit-taking exit that booked a loss"})
    if bad_labels:
        add("HIGH", "LABEL_CONTRADICTION",
            "%d exits contradict their own label" % len(bad_labels),
            "An exit reason is a claim about why we sold. When the number disagrees with the "
            "name, either the fill model or the label is wrong — and both mislead every audit "
            "downstream.", bad_labels[:12],
            "Model these as RESTING orders: fill where price crossed the level, taking the "
            "worse of level and observed print.")

    # ── D. IMPOSSIBLE FILLS ───────────────────────────────────────────────────────────
    impossible = [t for t in closed
                  if t.get("net") is not None and t["why"] in ("TARGET", "TAKE")
                  and float(t["net"]) > 8.0 and not t.get("fill_capped")]
    if impossible:
        add("CRITICAL", "IMPOSSIBLE_FILL",
            "%d limit-class exits far above any legal limit and NOT marked capped" % len(impossible),
            "A take-profit cannot fill above its limit. This is the class that produced the "
            "$242 PNUT windfall and poisoned the learning river.",
            [{k: t[k] for k in ("sleeve", "sym", "why", "net")} for t in impossible[:10]],
            "Run scripts/quarantine_bad_fills.py --apply and check the limit cap in _sell.")

    # ── E. HEADLINE HONESTY ───────────────────────────────────────────────────────────
    flips = []
    for bk, rows in (lab.get("by_industry") or {}).items():
        for x in rows:
            rep, rz = x.get("return_pct"), x.get("realized_pct")
            if rep is None or rz is None:
                continue
            if (rep > 0) != (rz > 0) and abs(rep) > 0.05:
                flips.append({"sleeve": "%s:%s" % (bk, x.get("sleeve")),
                              "headline_pct": rep, "realized_pct": rz,
                              "closed": x.get("closed")})
    if flips:
        add("MEDIUM", "HEADLINE_SIGN_FLIP",
            "%d sleeves show a headline with the opposite sign to realized P&L" % len(flips),
            "The headline is equity-based and includes unrealized marks. Law 1 says realized "
            "fee-paid P&L is the only score. Quoting the headline is how 'M FLOOR ARTIST is "
            "green in all four books' was said about a sleeve that was net negative.",
            flips[:10], "Judge sleeves on realized_pct. Treat the headline as mark-to-market only.")

    # ── F. GIVE-BACK LEAK ─────────────────────────────────────────────────────────────
    gave, turned = [], []
    for t in closed:
        if not (t.get("entry") and t.get("opened_t") and t.get("closed_t") and t.get("net") is not None):
            continue
        seg = [r for r in tape.get(t["sym"], []) if t["opened_t"] <= r[0] <= t["closed_t"]]
        if len(seg) < 3:
            continue
        pk = max(r[1] for r in seg) / t["entry"] - 1.0
        got = float(t["net"]) / 100.0
        gave.append(pk - got)
        if pk > 0.02 and got < 0:
            turned.append({"sleeve": t["sleeve"], "sym": t["sym"], "why": t["why"],
                           "peak_pct": round(pk * 100, 2), "closed_pct": round(got * 100, 2)})
    if gave:
        med = statistics.median(gave) * 100
        if turned:
            add("HIGH", "WINNER_TO_LOSER",
                "%d positions were up more than 2%% and still closed negative" % len(turned),
                "Median give-back across %d closed trades is %.2f%% of peak. A winner becoming "
                "a loser is not a market condition; it is a missing rail." % (len(gave), med),
                turned[:12],
                "Check the give-back governor is armed (giveback_arm_pct) and that its exits "
                "model a resting order rather than the next glance.")
        else:
            add("INFO", "GIVEBACK_OK",
                "no winner closed negative; median give-back %.2f%%" % med,
                "The give-back governor is holding.", [], None)

    # ── G. FEED COMBS ─────────────────────────────────────────────────────────────────
    combs = []
    for sym, rows in tape.items():
        if len(rows) < 60:
            continue
        v = sum(1 for i in range(2, len(rows))
                if rows[i - 2][1] == rows[i][1] and rows[i - 1][1] not in (0,)
                and abs(rows[i - 1][1] / rows[i - 2][1] - 1) > 0.01)
        if v >= 8:
            combs.append({"sym": sym, "v_round_trips": v, "prints": len(rows)})
    if combs:
        combs.sort(key=lambda c: -c["v_round_trips"])
        add("HIGH", "FEED_COMB",
            "%d symbols show repeated V-shaped round trips to the identical price" % len(combs),
            "Price leaving a level and returning to it EXACTLY, repeatedly, is not trading — it "
            "is two sources alternating or a stale cache being re-read. This is the five-month "
            "sawtooth in both its forms.", combs[:12],
            "Check canon_keys rejections (FROZEN/DEAD/OUT_OF_HOURS) for these symbols.")

    # ── H. STRUCTURE AGREEMENT — the steering part ────────────────────────────────────
    buckets: Dict[str, List[float]] = {}
    graded = 0
    for t in closed:
        r = reads.get(t["sym"])
        if not r or not r.get("ok") or t.get("net") is None:
            continue
        graded += 1
        net = float(t["net"])
        bp = r.get("band_pos")
        if bp is not None:
            k = "band_low" if bp <= 0.33 else ("band_mid" if bp <= 0.66 else "band_high")
            buckets.setdefault(k, []).append(net)
        nf = r.get("nearest_floor") or {}
        if nf.get("strength") is not None:
            k = "support_strong" if float(nf["strength"]) >= 3 else "support_weak"
            buckets.setdefault(k, []).append(net)
        if r.get("break_state"):
            buckets.setdefault("break_" + str(r["break_state"]).lower(), []).append(net)
        if r.get("approach"):
            buckets.setdefault("approach_" + str(r["approach"]).lower(), []).append(net)
    pattern = {k: {"n": len(v), "mean_net_pct": round(statistics.mean(v), 3),
                   "win_pct": round(sum(1 for x in v if x > 0) / len(v) * 100, 1)}
               for k, v in buckets.items() if len(v) >= 5}
    steer = []
    for a, b in (("band_low", "band_high"), ("support_strong", "support_weak"),
                 ("break_intact", "break_broken"),
                 ("approach_lifting_off", "approach_falling_into")):
        if a in pattern and b in pattern:
            d = pattern[a]["mean_net_pct"] - pattern[b]["mean_net_pct"]
            if abs(d) >= 0.5:
                better, worse = (a, b) if d > 0 else (b, a)
                steer.append("entries at %s averaged %+.2f%% vs %+.2f%% at %s (n=%d/%d)"
                             % (better, pattern[better]["mean_net_pct"],
                                pattern[worse]["mean_net_pct"], worse,
                                pattern[better]["n"], pattern[worse]["n"]))
    if pattern:
        add("INFO" if not steer else "MEDIUM", "STRUCTURE_PATTERN",
            ("graded %d closed trades against the structure at their symbol" % graded)
            + ("; %d readable separations" % len(steer) if steer else "; no separation yet"),
            "This is the steering signal: which chart states preceded winners and which "
            "preceded losers. It is a CURRENT-structure approximation, not an entry-time "
            "reconstruction, so treat it as a direction to investigate rather than proof.",
            steer or [pattern], 
            ("Consider tightening the sleeves toward the better bucket, with a knob and an A/B."
             if steer else "Keep collecting; no bucket separates yet."))

    # ── I. STALE STORES ───────────────────────────────────────────────────────────────
    stale = []
    for name in ("GRAPH_READ.json", "PRICE_TRUTH.json", "STRATEGY_LAB.json",
                 "SLEEVE_VETOES.json", "paper_sim_live.json", "SOURCE_OVERLAY.json"):
        d = _load(out, name)
        ts = d.get("generated_at") if isinstance(d, dict) else None
        if not ts:
            stale.append({"store": name, "age": "no generated_at"})
            continue
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if not t.tzinfo:
                t = t.replace(tzinfo=timezone.utc)
            age_h = (now - t).total_seconds() / 3600.0
            limit = 6.0 if name != "SOURCE_OVERLAY.json" else 26.0
            if age_h > limit:
                stale.append({"store": name, "age_h": round(age_h, 1)})
        except Exception:
            stale.append({"store": name, "age": "unparseable"})
    if stale:
        add("MEDIUM", "STALE_STORE", "%d stores are older than expected" % len(stale),
            "A panel reading a store nothing has written this cycle shows yesterday's truth "
            "with today's confidence.", stale, "Check the cycle wiring for these builders.")

    findings.sort(key=lambda f: (SEV.get(f["severity"], 9), f["code"]))
    counts: Dict[str, int] = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    payload = {
        "generated_at": now.isoformat(),
        "what": ("a skeptic that reads the RECORD rather than the laws. selftest asks 'is each "
                 "law still enforced?'; the inspector asks 'does this look like a working "
                 "system?' — on real data, every cycle."),
        "closed_trades_examined": len(closed),
        "symbols_with_structure": len(reads),
        "counts": counts,
        "verdict": ("CLEAN — nothing above INFO" if not any(
            f["severity"] in ("CRITICAL", "HIGH") for f in findings)
            else "ATTENTION — %d critical/high finding(s)" % sum(
                1 for f in findings if f["severity"] in ("CRITICAL", "HIGH"))),
        "structure_pattern": pattern,
        "findings": findings,
        "honesty": ("this auditor changes no behaviour and takes no trade. Its structure "
                    "patterns use CURRENT structure, not the structure at entry time, so they "
                    "point at questions rather than answering them."),
    }
    write_json_atomic(out / "INSPECTOR.json", payload)
    return payload


if __name__ == "__main__":                                   # pragma: no cover
    import sys
    p = build_inspector(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("INSPECTOR: %s" % p["verdict"])
    print("  examined %d closed trades, %d symbols with structure"
          % (p["closed_trades_examined"], p["symbols_with_structure"]))
    for f in p["findings"]:
        print("\n  [%s] %s" % (f["severity"], f["title"]))
        print("      %s" % f["detail"][:200])
        for e in (f["evidence"] or [])[:4]:
            print("        - %s" % (json.dumps(e)[:150] if not isinstance(e, str) else e[:150]))
        if f.get("action"):
            print("      -> %s" % f["action"][:160])
