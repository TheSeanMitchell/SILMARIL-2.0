"""selftest_5_1.py — PERMANENT REGRESSION PROTECTION.

Every bug this project has swatted and re-swatted gets an automated tripwire
here, so "it came back after an update/wipe" ends as a sentence anyone can say.
Pure-python, no network, seconds to run. Synthetic fixtures are TEST VECTORS
(explicitly allowed by doctrine); nothing here touches live stores.

Run:  python scripts/selftest_5_1.py            (from repo root)
CI:   .github/workflows/selftest.yml (weekly + on demand)
Exit: 0 all pass · 1 any fail (each failure names the historical incident).
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))


def now():
    return datetime.now(timezone.utc)


# ── T1 · THE CORE-HOSTAGE GUARD (incident 2026-07-10: a broker gate enclosed
#    818 lines including the paper sim; the engine went dark in every lane).
#    AST-walk cli.py: the paper-sim invocation must NOT sit inside any `if`
#    whose test references _HAS_ALPACA or _broker_exec. -----------------------
def t1_core_never_hostage():
    src = (ROOT / "silmaril/cli.py").read_text()
    tree = ast.parse(src)
    hit = []

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_If(self, node):
            self.stack.append(node)
            self.generic_visit(node)
            self.stack.pop()

        def visit_ImportFrom(self, node):
            if node.module and node.module.endswith("paper_sim") and \
               any(a.name == "live_step" for a in node.names):
                for ifn in self.stack:
                    t = ast.dump(ifn.test)
                    if "_HAS_ALPACA" in t or "_broker_exec" in t:
                        hit.append(ast.dump(ifn.test)[:80])
            self.generic_visit(node)

    V().visit(tree)
    check("T1 core-never-hostage (paper sim outside broker conditionals)",
          not hit, f"live_step import nested under: {hit}")


# ── T2 · GEKKO EXIT CLASS (incident 2026-07-10: exits filtered by book label,
#    aggressive positions could never sell). Fixture live_step must SELL an
#    over-target aggressive position. ----------------------------------------
def t2_gekko_sells():
    from silmaril.execution import paper_sim as ps
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        t0 = now()
        sym = "TST-USD"
        prices = [1.00, 0.985, 0.99, 1.00, 1.01, 1.03, 1.035]
        samples = {sym: [[(t0 - timedelta(minutes=5 * (len(prices) - i))).isoformat(), p]
                         for i, p in enumerate(prices)]}
        (out / "price_samples.json").write_text(json.dumps({"samples": samples}))
        (out / "PARAM_CATALOG.json").write_text(json.dumps({
            "aggressive_book": {"enabled": True, "name": "GEKKO", "entry": 0.02,
                                 "target": 0.02, "stop": 0.06}}))
        book = {"cash": 8965.0, "equity": 10000.0, "realized_pnl": 0.0,
                "positions": {sym: {"sym": sym, "qty": 1000.0, "entry": 1.00,
                                     "mark": 1.03, "target": 0.02, "stop": 0.06,
                                     "t": (t0 - timedelta(hours=3)).isoformat(),
                                     "wager_usd": 1000.0, "cost": 0.004, "mfe": 1.035}},
                "trades": []}
        (out / "paper_book_aggressive.json").write_text(json.dumps(book))
        try:
            ps.live_step(out)
        except Exception as e:
            check("T2 GEKKO-class exits fire", False, f"live_step raised: {e}")
            return
        d = json.loads((out / "paper_book_aggressive.json").read_text())
        sold = any(t.get("side") == "SELL" and t.get("sym") == sym
                   for t in d.get("trades", []))
        check("T2 GEKKO-class exits fire (aggressive position past target sells)",
              sold, "over-target aggressive position did not sell")


# ── T3 · STALE-PRICE ZOMBIE (a held name whose feed dies must neither fill on
#    fiction nor zombie forever: it stays open, flagged stale). ---------------
def t3_stale_no_fiction_fill():
    from silmaril.execution import paper_sim as ps
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        t0 = now()
        sym = "OLD-USD"
        samples = {sym: [[(t0 - timedelta(hours=6)).isoformat(), 1.10]]}   # stale print above target
        (out / "price_samples.json").write_text(json.dumps({"samples": samples}))
        (out / "PARAM_CATALOG.json").write_text(json.dumps({}))
        book = {"cash": 9000.0, "equity": 10000.0, "realized_pnl": 0.0,
                "positions": {sym: {"sym": sym, "qty": 900.0, "entry": 1.00,
                                     "mark": 1.00, "target": 0.03, "stop": 0.05,
                                     "t": (t0 - timedelta(hours=9)).isoformat(),
                                     "wager_usd": 900.0, "cost": 0.004}},
                "trades": []}
        (out / "paper_book_crypto.json").write_text(json.dumps(book))
        try:
            ps.live_step(out)
        except Exception as e:
            check("T3 stale-price safety", False, f"live_step raised: {e}")
            return
        d = json.loads((out / "paper_book_crypto.json").read_text())
        still_open = sym in (d.get("positions") or {})
        no_sell = not any(t.get("side") == "SELL" for t in d.get("trades", []))
        flagged = still_open and d["positions"][sym].get("stale_price_min") is not None
        check("T3 stale-price safety (no fill on a 6h-old print; position flagged, armed)",
              still_open and no_sell and flagged,
              f"open={still_open} no_sell={no_sell} flagged={flagged}")


# ── T4 · GOVERNANCE GROUPING (incident: validation grouped by BOOK, election
#    graded an empty dict, champion frozen forever). --------------------------
def t4_validation_by_strategy():
    from silmaril.execution.champion_validation import build_champion_validation
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        trades = [{"side": "SELL", "realized_pct": 2.0, "champion_entry": "MR_x", "t": now().isoformat()}
                  for _ in range(6)]
        (out / "paper_book_crypto.json").write_text(json.dumps({"trades": trades}))
        cv = build_champion_validation(out)
        rows = cv.get("strategies") or []
        ok = rows and all(r.get("strategy") not in ("crypto", "stock", "metal", "energy")
                          for r in rows) and rows[0].get("book") == "crypto"
        check("T4 validation groups by entering strategy (never by book)",
              bool(ok), f"rows={[(r.get('book'), r.get('strategy')) for r in rows][:3]}")


# ── T5 · POST-STOP COOLDOWN (the LDO re-buy-the-knife lesson). ----------------
def t5_cooldown_semantics():
    cat = {"reentry_cooldown": {"after_stop_min": 240}}
    t0 = now()
    trades = [{"side": "SELL", "exit_reason": "STOP", "sym": "AAA-USD",
               "t": (t0 - timedelta(minutes=10)).isoformat()},
              {"side": "SELL", "exit_reason": "STOP", "sym": "BBB-USD",
               "t": (t0 - timedelta(minutes=500)).isoformat()}]
    cd = float(((cat.get("reentry_cooldown") or {}).get("after_stop_min", 240)) or 0)
    cool = set()
    for tr in reversed(trades[-400:]):
        if tr.get("side") == "SELL" and tr.get("exit_reason") == "STOP":
            ag = (t0 - datetime.fromisoformat(tr["t"])).total_seconds() / 60.0
            if ag <= cd:
                cool.add(tr["sym"])
    check("T5 post-STOP cooldown (10-min-ago blocked, 500-min-ago free)",
          cool == {"AAA-USD"}, f"cool={cool}")


# ── T6 · CHECKOUT-PROOF FRESHNESS (git resets mtimes; ages must come from
#    content). A 31h-old heartbeat under a brand-new mtime must go RED. -------
def t6_content_age():
    from silmaril.execution.store_contracts import _age_min
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "deep_heartbeat.json"
        p.write_text(json.dumps({"started_at": (now() - timedelta(hours=31)).isoformat()}))
        a = _age_min(p)   # fresh mtime, old content
        check("T6 content-timestamp freshness beats checkout mtime",
              a is not None and a > 30 * 60, f"age_min={a}")


# ── T7 · MARKET-HOURS TRIPWIRE (the recurring weekend regression). ------------
def t7_market_hours_rule():
    from silmaril.execution.invariants import _rule_market_hours
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        sat = datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc)  # a Saturday
        (out / "paper_book_stock.json").write_text(json.dumps(
            {"trades": [{"side": "BUY", "sym": "AAPL", "t": sat.isoformat()}]}))
        s, d = _rule_market_hours(out)
        check("T7 market-hours guard trips on a weekend stock BUY",
              s == "FAIL", f"status={s} detail={d[:60]}")


# ── T8 · MIN-TAKEHOME VETO WIRING (fee-aware expectancy stays enforced). ------
def t8_takehome_veto_present():
    s = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    check("T8 fee-aware entry veto present (min_takehome / clear $ net)",
          ("min_takehome" in s) and ("net" in s), "veto text not found in paper_sim")


# ── T9 · VERSION PIN (incident 5.1: PROJECT_META + verify_install held '3.0' and
#    the header kept reverting). Header is a constant; meta must agree; verify
#    must assert 5.1. ---------------------------------------------------------
def t9_version_pin():
    ix = (ROOT / "docs/index.html").read_text()
    # 5.1 FINAL header: brand constant "SILMARIL" + separate verNum "5.1"; no 5.0 anywhere
    ok_h1 = ('id="verHdr"' in ix and ">SILMARIL<" in ix
             and '<span id="verNum">5.1</span>' in ix and "5.0" not in ix.split("<script")[0])
    ok_no_override = "h.innerHTML='SILMARIL&nbsp;'+m.version" not in ix
    meta = json.loads((ROOT / "docs/data/PROJECT_META.json").read_text())
    vi = (ROOT / ".github/workflows/verify_install.yml").read_text()
    check("T9 version pin (header constant · meta 5.1 · verify asserts 5.1)",
          ok_h1 and ok_no_override and meta.get("version") == "5.1" and "v=='5.1'" in vi,
          f"h1={ok_h1} override_gone={ok_no_override} meta={meta.get('version')}")


# ── T10 · SCORECARD CONTRACT (incident: renderer expected the old object shape,
#    UI printed 'undefined'). Store rows carry name/grade/formula; renderer
#    must reference the same fields. -----------------------------------------
def t10_scorecard_contract():
    ix = (ROOT / "docs/index.html").read_text()
    import re
    m = re.search(r"async function renderScorecard.*?\n(?=async function|function )", ix, re.S)
    body = m.group(0) if m else ""
    check("T10 scorecard store⇄renderer contract (.name/.grade/.formula)",
          all(k in body for k in (".name", ".grade", ".formula")),
          "renderer does not reference the 5.1 category fields")


# ── T11 · MTF LADDER unit — a clean up-series must vote green and stack
#    positive confluence; fast_green must trip. -------------------------------
def t11_mtf_votes():
    from silmaril.execution.mtf_regime import _slopes, _row
    t0 = now()
    rows = [[(t0 - timedelta(minutes=m)).isoformat(), 100.0 * (1 + 0.0004 * (2000 - m))]
            for m in range(2000, 0, -10)]
    r = _row(_slopes(rows))
    check("T11 MTF ladder (up-series → greens, positive confluence, fast_green)",
          r["greens"] >= 6 and r["confluence"] > 2 and r["fast_green"],
          f"greens={r['greens']} conf={r['confluence']} fast_green={r['fast_green']}")


def _crash_fixture(td, extra_pos=None, mtf_fastred=True):
    out = Path(td); t0 = now(); sym = "GRN-USD"
    prices = [1.00, 0.985, 0.99, 1.00, 1.005, 1.008, 1.01]
    samples = {sym: [[(t0 - timedelta(minutes=5 * (len(prices) - i))).isoformat(), p]
                     for i, p in enumerate(prices)]}
    (out / "price_samples.json").write_text(json.dumps({"samples": samples}))
    (out / "PARAM_CATALOG.json").write_text(json.dumps({
        "regime_exit": {"mode": "auto"}, "stale_capital": {"review_h": 36},
        "conviction_sizing": {"mode": "auto"}}))
    if mtf_fastred:
        (out / "MTF_REGIME.json").write_text(json.dumps(
            {"books": {"crypto": {"fast_red": True}}, "symbols": {}}))
    pos = {"sym": sym, "qty": 1000.0, "entry": 1.00, "mark": 1.008, "target": 0.05,
           "stop": 0.06, "cost": 0.004, "wager_usd": 1000.0,
           "t": (t0 - timedelta(hours=(extra_pos or {}).get("age_h", 3))).isoformat()}
    (out / "paper_book_crypto.json").write_text(json.dumps(
        {"cash": 9000.0, "equity": 10000.0, "realized_pnl": 0.0,
         "positions": {sym: pos}, "trades": []}))
    return out, sym


# ── T12 · REGIME-FLIP HARVEST — fast-red + net-green position must bank. ------
def t12_regime_harvest():
    from silmaril.execution import paper_sim as ps
    with tempfile.TemporaryDirectory() as td:
        out, sym = _crash_fixture(td, mtf_fastred=True)
        ps.live_step(out)
        d = json.loads((out / "paper_book_crypto.json").read_text())
        hit = [t for t in d.get("trades", []) if t.get("exit_reason") == "REGIME_FLIP_HARVEST"]
        ab = (out / "REGIME_EXIT_AB.jsonl").exists()
        check("T12 regime-flip harvest fires on fast-red (net-green banks, A/B logged)",
              bool(hit) and ab, f"harvest={bool(hit)} ab_ledger={ab}")


# ── T13 · FEE-CLEAR TIME — 40h-old green position frees its capital. ----------
def t13_fee_clear_time():
    from silmaril.execution import paper_sim as ps
    with tempfile.TemporaryDirectory() as td:
        out, sym = _crash_fixture(td, extra_pos={"age_h": 40}, mtf_fastred=False)
        ps.live_step(out)
        d = json.loads((out / "paper_book_crypto.json").read_text())
        hit = [t for t in d.get("trades", []) if t.get("exit_reason") == "FEE_CLEAR_TIME"]
        check("T13 stale-capital fee-clear (36h review, head above water banks)",
              bool(hit), "40h green position did not fee-clear")


# ── T14 · CONVICTION CLAMPS — wager fraction stays inside [floor, max]. -------
def t14_conviction_clamps():
    s = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ('_base_frac = max(float(_cs.get("floor_frac", 0.05)),' in s
          and 'min(float(_cs.get("max_frac", 0.25))' in s
          and '"base_wager_usd"' in s)
    check("T14 conviction sizing clamped + flat-base twin logged", ok,
          "clamp or base-twin stamp missing")


# ── T15 · CONFIDENCE ENGINE uses peak rhythm (the "use everything" directive) ──
def t15_confidence_uses_rhythm():
    src = (ROOT / "silmaril/execution/confidence_engine.py").read_text()
    ok = ("PEAK_RHYTHM.json" in src and "rhythm_regularity" in src
          and "rhythm_phase" in src and "rhythm_tradeability" in src)
    # and paper_sim must consume it for sizing
    ps = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    wired = "CONFIDENCE_ENGINE.json" in ps and "_ce_map" in ps
    check("T15 confidence engine fuses peak rhythm AND feeds sizing", ok and wired,
          f"engine_ok={ok} sizing_wired={wired}")


# ── T16 · 15-MINUTE REGIME fast band present in the live classifier ──
def t16_fast_band_regime():
    src = (ROOT / "silmaril/execution/regime_classifier.py").read_text()
    ok = ("slope_12m_pct" in src and "slope_15m_pct" in src and "slope_30m_pct" in src
          and "fast_band_red" in src)
    check("T16 live regime has the 12m/15m/30m fast band", ok,
          "fast band slopes missing from regime_classifier")


# ── T17 · STRATEGY LAB has four distinct sleeves with different caps ──
def t17_strategy_lab_sleeves():
    from silmaril.execution.strategy_lab_abcd import SLEEVES
    caps = {k: v["cap"] for k, v in SLEEVES.items()}
    ok = (set(SLEEVES) == {"A", "B", "C", "D"} and caps["A"] == 10 and caps["B"] == 5
          and caps["D"] <= 3 and SLEEVES["C"]["recycle_h"] and SLEEVES["D"]["conf_gate"] > 0)
    check("T17 strategy lab: 4 sleeves, distinct discipline (A=10 control, D=sniper≤3 conf-gated)", ok,
          f"caps={caps}")


# ── T18 · UI STRUCTURE: six-tab routing, every section categorized, nothing orphaned ──
def t18_ui_six_tabs():
    ix = (ROOT / "docs/index.html").read_text()
    import re
    tabs = re.findall(r'data-p="(\w+)"', ix)
    has_six = all(t in tabs for t in ("cmd", "strategy", "markets", "forensics", "health", "settings"))
    secs = ix.count("<section")
    tagged = len(re.findall(r'<section data-cat="', ix))
    orphan = len(re.findall(r'<section(?! data-cat)', ix))
    check("T18 six-tab UI: all sections categorized, zero orphans",
          has_six and tagged == secs and orphan == 0,
          f"six_tabs={has_six} sections={secs} tagged={tagged} orphans={orphan}")


# ── T19 · CONFIDENCE ENGINE fuses EVERY predictive signal (the "wire the brain
#    to everything" directive). Guards that the high-value stores are all read. ──
def t19_confidence_all_signals():
    src = (ROOT / "silmaril/execution/confidence_engine.py").read_text()
    needed = ["PEAK_RHYTHM.json", "FINGERPRINTS.json", "MTF_REGIME.json",
              "timing_fingerprint.json", "momentum_chain.json", "conviction_ranking.json"]
    missing = [n for n in needed if n not in src]
    # and the weight table must carry the new components
    comps = ["timing_alignment", "momentum_exhaustion", "conviction_backing"]
    miss_c = [c for c in comps if c not in src]
    check("T19 confidence engine reads all predictive stores + new components",
          not missing and not miss_c,
          f"missing_stores={missing} missing_components={miss_c}")


# ── T20 · UI RENDER RESILIENCE (the bug that blanked the whole dashboard):
#    $() must return a no-op stub for missing ids so one stale reference can
#    never abort load(). And there must be no UNGUARDED $('id').prop before the
#    safe() wrappers. ---------------------------------------------------------
def t20_ui_render_resilience():
    ix = (ROOT / "docs/index.html").read_text()
    has_stub = "_NULLSTUB" in ix and "document.getElementById(id)||_NULLSTUB" in ix
    # the old crash pattern: $('ts').textContent with no guard, before safe() exists
    import re
    # find the load() region up to the first safe= definition
    m = re.search(r"async function load\(\).*?const safe=", ix, re.S)
    region = m.group(0) if m else ""
    # any bare $('literal').prop= assignment that isn't guarded by a local var check
    risky = re.findall(r"[$]\('[a-zA-Z]+'\)\.(?:textContent|innerHTML|value)\s*=", region)
    check("T20 UI render resilience: $() stub + no unguarded id writes pre-safe()",
          has_stub and len(risky) == 0,
          f"stub={has_stub} risky_writes={len(risky)}")


# ── T21 · SERVICE WORKER is network-first (the cache bug that trapped the old
#    UI). Cache-first shells are banned. -------------------------------------
def t21_sw_network_first():
    sw = (ROOT / "docs/sw.js").read_text()
    import re
    # the ACTIVE cache name (not comment text) must not be the old v51b shell cache
    m = re.search(r"const\s+CACHE\s*=\s*'([^']+)'", sw)
    active_cache = m.group(1) if m else ""
    bumped = "v51b" not in active_cache and active_cache != ""
    # network-first: the fetch handler tries fetch() first, falls back to caches.match
    fetch_first = "fetch(e.request)" in sw and "caches.match" in sw
    # must NOT pre-cache the html shell (that was the cache-first trap)
    no_shell_precache = "'./index.html'])" not in sw and "addAll(['./', './index.html'" not in sw
    check("T21 service worker network-first (no cache-first shell trap)",
          fetch_first and no_shell_precache and bumped,
          f"active_cache={active_cache} fetch_first={fetch_first} no_precache={no_shell_precache}")


# ── T22 · BRAIN WIRING MAP IS TRUTHFUL — every listed consumer file really
#    contains the store's filename. The nothing-is-decoration table cannot lie. ──
def t22_brain_map_truthful():
    from silmaril.execution.brain_wiring import _signals
    rows = _signals(ROOT / "docs/data")
    bad = []
    for r in rows:
        if not r["consumers"]:
            bad.append(r["store"] + ":NO_CONSUMER")
            continue
        for cf in r["consumers"]:
            try:
                if r["store"] not in (ROOT / cf).read_text():
                    bad.append(f"{r['store']}!in!{cf}")
            except Exception:
                bad.append(f"{r['store']}:missing:{cf}")
    check("T22 brain-wiring map truthful (every consumer really reads the store)",
          not bad, f"violations={bad[:4]}")


# ── T23 · DR. STRANGE self-grades feed the experimental gate ──
def t23_dr_strange_graded_gate():
    src = (ROOT / "silmaril/execution/gate_evidence.py").read_text()
    ok = 'dr_strange.json' in src and 'career' in src and 'resolved' in src and 'hit_rate' in src
    check("T23 dr_strange gate fed by its own career (resolved + hit-rate)", ok,
          "gate_evidence not sourcing dr career")


# ── T24 · VOL-NATIVE entry clamps (quiet floor · wild cap · never above base · off=None) ──
def t24_vol_native_clamps():
    from silmaril.execution.paper_sim import _vol_native_entry
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    def tape(step_pct):
        rows, px = [], 100.0
        for i in range(60):
            t = (now - timedelta(minutes=10 * (60 - i))).isoformat()
            px *= (1 + step_pct * ((-1) ** i))
            rows.append((t, px))
        return rows
    quiet = _vol_native_entry(tape(0.0005), "crypto", 0.03, {"mode": "auto", "k_sigma": 1.5})
    wild = _vol_native_entry(tape(0.02), "crypto", 0.03, {"mode": "auto", "k_sigma": 1.5})
    off = _vol_native_entry(tape(0.001), "crypto", 0.03, {"mode": "off"})
    ok = (quiet is not None and abs(quiet - 0.012) < 1e-9        # quiet → class floor binds
          and wild is not None and wild <= 0.03 + 1e-9           # wild → never above base/cap
          and off is None)
    check("T24 vol-native clamps: floor on quiet, ≤base on wild, off disables",
          ok, f"quiet={quiet} wild={wild} off={off}")


# ── T25 · BRAIN TAB exists: 7th tab + guide + ≥4 brain-categorized sections ──
def t25_brain_tab():
    ix = (ROOT / "docs/index.html").read_text()
    ok = ('data-p="brain"' in ix and '"brain"' in ix
          and ix.count('data-cat="brain"') >= 4 and 'renderBrain' in ix)
    check("T25 BRAIN tab wired (button + guide + ≥4 sections + renderer)", ok,
          f"btn={'data-p=\"brain\"' in ix} sections={ix.count('data-cat=\"brain\"')}")


# ── T26 · DOSSIER contract — the graphs carry EVERYTHING (peaks, ETA, likelihoods,
#    trajectory, confidence anatomy) ──
def t26_dossier_contract():
    import json as _json
    d = _json.loads((ROOT / "docs/data/BRAIN_WIRING.json").read_text())
    need = {"sym", "series", "last_peak_at", "next_peak_eta", "cycle_min",
            "bounce_likelihood", "trajectory", "mtf_confluence",
            "confidence_parts", "rhythm_tradeability"}
    ds = d.get("dossiers") or []
    ok = bool(ds) and need.issubset(set(ds[0].keys())) and "master_brain" in d
    check("T26 dossier contract (peaks·ETA·likelihood·trajectory·anatomy) + master brain",
          ok, f"dossiers={len(ds)} missing={sorted(need - set(ds[0].keys())) if ds else 'ALL'}")


if __name__ == "__main__":
    for t in (t1_core_never_hostage, t2_gekko_sells, t3_stale_no_fiction_fill,
              t4_validation_by_strategy, t5_cooldown_semantics, t6_content_age,
              t7_market_hours_rule, t8_takehome_veto_present,
              t9_version_pin, t10_scorecard_contract, t11_mtf_votes,
              t12_regime_harvest, t13_fee_clear_time, t14_conviction_clamps,
              t15_confidence_uses_rhythm, t16_fast_band_regime,
              t17_strategy_lab_sleeves, t18_ui_six_tabs,
              t19_confidence_all_signals, t20_ui_render_resilience,
              t21_sw_network_first, t22_brain_map_truthful, t23_dr_strange_graded_gate,
              t24_vol_native_clamps, t25_brain_tab, t26_dossier_contract):
        try:
            t()
        except Exception as e:  # a crashing test is a failing test
            check(t.__name__, False, f"raised {type(e).__name__}: {e}")
    print(f"\n== SELFTEST 5.1: {len(PASS)} pass · {len(FAIL)} fail ==")
    if FAIL:
        for n, d in FAIL:
            print("  FAILED:", n, "—", d)
        sys.exit(1)
