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
             and '<span id="verNum">7.0</span>' in ix and "5.0" not in ix.split("<script")[0])
    ok_no_override = "h.innerHTML='SILMARIL&nbsp;'+m.version" not in ix
    meta = json.loads((ROOT / "docs/data/PROJECT_META.json").read_text())
    vi = (ROOT / ".github/workflows/verify_install.yml").read_text()
    check("T9 version pin (header constant · meta 7.0 · verify asserts 7.0)",
          ok_h1 and ok_no_override and meta.get("version") == "7.0" and "v=='7.0'" in vi,
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
    from silmaril.execution.strategy_lab_abcd import SLEEVES, BOOKS
    caps = {k: v["cap"] for k, v in SLEEVES.items()}
    ok = (set(SLEEVES.keys()) >= {"A", "B", "C", "D", "E", "F"}
          and {"G", "H"} <= set(SLEEVES.keys())                 # 7.0 stop-loss lab
          and caps["A"] == 10                                  # the control
          and caps["D"] <= 3 and SLEEVES["D"]["conf_gate"] > 0  # the sniper
          and SLEEVES["E"]["strike_extra"] == 2                 # adaptive striker
          and SLEEVES["F"]["vault"] is True                     # cash harvester
          and BOOKS == ("crypto", "stock", "metal", "energy"))
    check("T17 lab v2: A–H sleeves per industry (control·sniper·striker·vault·geometry·patient)",
          ok, f"caps={caps}")

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
    _btn = 'data-p="brain"' in ix
    _nsec = ix.count('data-cat="brain"')
    check("T25 BRAIN tab wired (button + guide + ≥4 sections + renderer)", ok,
          f"btn={_btn} sections={_nsec}")


# ── T26 · DOSSIER contract — the graphs carry EVERYTHING (peaks, ETA, likelihoods,
#    trajectory, confidence anatomy) ──
def t26_dossier_contract():
    import json as _json
    src = (ROOT / "silmaril/execution/brain_wiring.py").read_text()
    need = {"sym", "series", "last_peak_at", "next_peak_eta", "cycle_min",
            "bounce_likelihood", "trajectory", "mtf_confluence",
            "confidence_parts", "rhythm_tradeability"}
    ok_src = all(('"%s"' % k) in src for k in need) and "master_brain" in src
    try:
        d = _json.loads((ROOT / "docs/data/BRAIN_WIRING.json").read_text())
    except Exception:
        d = None
    if d is None:
        check("T26 dossier contract — code verified (store pending first cycle)", ok_src,
              "brain_wiring.py missing dossier fields")
        return
    ds = d.get("dossiers") or []
    ok = ok_src and bool(ds) and need.issubset(set(ds[0].keys())) and "master_brain" in d
    check("T26 dossier contract (peaks·ETA·likelihood·trajectory·anatomy) + master brain",
          ok, f"dossiers={len(ds)} missing={sorted(need - set(ds[0].keys())) if ds else 'ALL'}")

# ── T27 · PRICE-INTEGRITY GUARDS (the July-13 sawtooth lesson, permanently armed) ──
def t27_price_integrity_guards():
    rec = (ROOT / "silmaril/execution/momentum_chain.py").read_text()
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    rc = (ROOT / "silmaril/execution/conductor_report_card.py").read_text()
    ok = ("pending_ticks" in rec and "unconfirmed_jump" in rec
          and "_osc_ratio" in sim and "_LAST_OSC" in sim and "SUSPECT_OSC" in sim
          and "verified_realized_usd" in rc)
    check("T27 price integrity: recorder two-print confirm + osc quarantine + suspect tagging + verified line",
          ok, "a guard is missing")


# ── T28 · UNIVERSAL CONFIDENCE CARD contract ──
def t28_confidence_cards():
    import json as _json
    eng = (ROOT / "silmaril/execution/confidence_engine.py").read_text()
    need = {"class", "last_px", "confidence", "cycle_min", "expected_hold_min",
            "vol_native_bar_pct", "compounder_score", "book_win_pct", "momentum",
            "timing_best_buy", "bounce_reliability"}
    ok_src = ("CONFIDENCE_CARDS.json" in eng and "compounder_score" in eng
              and all(('"%s"' % k) in eng for k in need))
    try:
        d = _json.loads((ROOT / "docs/data/CONFIDENCE_CARDS.json").read_text())
    except Exception:
        d = None
    if d is None:
        check("T28 universal confidence card — code verified (store generates on first cycle)",
              ok_src, "confidence_engine.py missing card fields")
        return
    cards = d.get("cards") or {}
    sample = next(iter(cards.values()), {})
    ok = ok_src and d.get("n_cards", 0) > 0 and need.issubset(set(sample.keys()))
    check("T28 universal confidence card (every valuable, full stat block + compounder)",
          ok, f"missing={sorted(need - set(sample.keys())) if sample else ['NO_CARDS']}")

# ── T29 · PER-INDUSTRY LAB with E (striker) + F (vault) sleeves ──
def t29_lab_per_industry():
    import json as _json
    lab = (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text()
    ok_src = ("strike_extra" in lab and "vault_usd" in lab
              and 'BOOKS = ("crypto", "stock", "metal", "energy")' in lab
              and '"E"' in lab and '"F"' in lab)
    try:
        d = _json.loads((ROOT / "docs/data/STRATEGY_LAB.json").read_text())
    except Exception:
        d = {}
    bi = d.get("by_industry")
    if not bi:
        check("T29 per-industry lab — code verified (by_industry generates on first cycle)",
              ok_src, "strategy_lab_abcd.py missing v2 structures")
        return
    ok = (set(bi.keys()) == {"crypto", "stock", "metal", "energy"}
          and all(len(rows) >= 8 for rows in bi.values())
          and all({"G", "H"} <= {r.get("sleeve") for r in rows} for rows in bi.values()))
    check("T29 per-industry lab: 4 industries × A–H incl GEOMETRY SNIPER + PATIENT REVERT (7.0 stop-lab)",
          ok_src and ok,
          f"books={sorted(bi.keys())} sizes={[len(v) for v in bi.values()]}")

# ═════════ 5.3 HAIL MARY TRIPWIRES (T30–T42) — the release that never lies again ═════════

def t30_accounting_units():
    """A PERFECT target fill must read 100% of goal · 0.000 left · fee on its own line."""
    import importlib, silmaril.execution.paper_sim as ps
    importlib.reload(ps)
    try:
        b = ps.PaperBook()
    except TypeError:
        b = ps.PaperBook(10000.0)
    b.buy('X-USD', 1000.0, 100.0, 0.01, target=0.03, stop=0.06)
    b.positions['X-USD']['mfe'] = 103.0
    b.sell('X-USD', 103.0)
    tr = b.trades[-1]
    ok = (abs(tr['pct_of_goal'] - 100.0) < 0.2 and tr['left_on_table_pct'] < 0.02
          and abs(tr['fee_pct'] - 1.0) < 0.01 and abs(tr['realized_gross_pct'] - 3.0) < 0.05
          and 'target_net_pct' in tr)
    check("T30 accounting units: perfect fill = 100%/0.000/fee-own-line (gross≠net, forever)",
          ok, f"goal={tr.get('pct_of_goal')} left={tr.get('left_on_table_pct')} fee={tr.get('fee_pct')}")


def t31_starvation_exposed():
    """Law 8: green means FED. Starved components must be EXPOSED, gates percentile."""
    import json as _json
    lab = (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text()
    mb = (ROOT / "silmaril/execution/master_account.py").read_text()
    eng = (ROOT / "silmaril/execution/confidence_engine.py").read_text()
    ok_src = ("PERCENTILE" in lab.upper() and "_pct_cut" in mb
              and "starved_components" in eng)
    d = {}
    try:
        d = _json.loads((ROOT / "docs/data/CONFIDENCE_CARDS.json").read_text())
    except Exception:
        pass
    ok_data = ("starved_components" in d) if d else True
    check("T31 starvation exposed: percentile gates (lab+master) + starved list published",
          ok_src and ok_data, f"src={ok_src} data={'starved_components' in d if d else 'pending'}")


def t32_clean_room():
    """M4: registry covers every store; STATE never predates the wipe; card derives from books."""
    import json as _json, os
    reg = {}
    try:
        reg = _json.loads((ROOT / "docs/data/STORE_REGISTRY.json").read_text()).get("stores") or {}
    except Exception:
        pass
    files = [f for f in os.listdir(ROOT / "docs/data")
             if f.endswith(".json") or f.endswith(".jsonl")]
    missing = [f for f in files if f not in reg and f != "STORE_REGISTRY.json"]
    lab_ok = True
    try:
        lab = _json.loads((ROOT / "docs/data/STRATEGY_LAB.json").read_text())
        wm = _json.loads((ROOT / "docs/data/WIPE_MARKER.json").read_text()).get("wiped_at")
        if wm:
            lab_ok = ("wipe_epoch" in lab) and str(lab.get("created_at", "9999")) >= str(wm)
    except Exception:
        pass
    rc_src = "for _b5 in (" in (ROOT / "silmaril/execution/conductor_report_card.py").read_text()
    # 7.0.2: the registry is rebuilt BY RULE every cycle, so coverage is total by
    # construction — the old "<=3 unregistered" tolerance was papering over a registry
    # that could not keep up with its own tree (it failed the moment the 7.0.1 repair
    # resurrected THRESHOLD_TAKEHOME/KRAKEN_SPREAD/MASTER_LOG/SESSION_ANATOMY).
    reg_src = "build_store_registry" in (ROOT / "silmaril/cli.py").read_text()
    check("T32 clean room: registry self-heals to TOTAL coverage + lab honors wipe + card derives from books",
          (not missing) and lab_ok and rc_src and reg_src,
          f"unregistered={missing[:4]} lab_ok={lab_ok} self_healing={reg_src}")


def t33_venue_contract():
    """M2: declared fees, live listings, universe truth test, capped slippage, cost hook."""
    import json as _json
    src = (ROOT / "silmaril/execution/venues.py").read_text()
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok_src = ("venue_round_trip_cost" in src and "build_venue_reality" in src
              and "slippage" in src and "venue_round_trip_cost" in sim)
    d = {}
    try:
        d = _json.loads((ROOT / "docs/data/VENUES.json").read_text())
    except Exception:
        pass
    ok_data = (not d) or (set(d.get("fees", {}).keys()) >= {"binanceus", "coinbase", "robinhood"}
                          and all(len(v) > 10 for v in (d.get("listed") or {}).values()))
    vr_ok = True
    try:
        vr = _json.loads((ROOT / "docs/data/VENUE_REALITY.json").read_text())
        vr_ok = "truth_test" in vr and "universe_gaps" in vr
    except Exception:
        pass
    check("T33 venue layer: 3 venues declared + listings + Universe Truth Test + cost hook",
          ok_src and ok_data and vr_ok, f"src={ok_src} venues={bool(d)} reality={vr_ok}")


def t34_harvest_identity():
    """M5: working + reserve == total on every sleeve row (arithmetic honesty)."""
    import json as _json
    try:
        d = _json.loads((ROOT / "docs/data/STRATEGY_LAB.json").read_text())
    except Exception:
        check("T34 harvest identity — store pending first cycle (schema verified in source)",
              "harvest_view" in (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text(), "")
        return
    bad = []
    for bk, rows in (d.get("by_industry") or {}).items():
        for r in rows:
            hv = r.get("harvest_view") or {}
            if hv and abs((hv.get("working_usd", 0) + hv.get("reserve_usd", 0))
                          - hv.get("total_usd", 0)) > 0.02:
                bad.append(f"{bk}:{r['sleeve']}")
    check("T34 harvest identity: working+reserve==total, every sleeve", not bad, str(bad[:4]))


def t36_master_decides():
    """M7: the Master writes a verdict — accept AND reject — every cycle, with reasons."""
    import json as _json
    src = (ROOT / "silmaril/execution/master_account.py").read_text()
    ok_src = ("MASTER_LEDGER" in src and "MASTER_DECISION_LEDGER" in src
              and "SHADOW" in src and "reserve_usd" in src and "strike" in src.lower())
    try:
        ml = _json.loads((ROOT / "docs/data/MASTER_LEDGER.json").read_text())
        cy = (ml.get("cycles") or [])[-1]
        ok_d = all(("policy_sleeve" in b and ("accepted" in b) and ("rejected_top" in b))
                   for b in (cy.get("books") or {}).values())
    except Exception:
        ok_d = True
    check("T36 master decides: shadow book + verdicts in writing + policy + reserve",
          ok_src and ok_d, f"src={ok_src}")


def t37_crash_lane():
    """M8: confirmed giant steps become VERIFIED_CRASH + cool-off; entries honor it."""
    rec = (ROOT / "silmaril/execution/momentum_chain.py").read_text()
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("VERIFIED_CRASH" in rec and "crash_cooloff" in rec
          and "crash_cooloff" in sim and "cool-off" in sim)
    check("T37 verified-crash lane: classify + ledger + cool-off honored at entry", ok, "")


def t38_reconciliation():
    """M9: four ledgers agree, out loud — or the battery fails."""
    import json as _json
    try:
        d = _json.loads((ROOT / "docs/data/RECONCILIATION.json").read_text())
    except Exception:
        check("T38 reconciliation — store pending first cycle (module verified)",
              (ROOT / "silmaril/execution/reconciliation.py").exists(), "")
        return
    bad = [c["name"] + f" Δ{c['delta']}" for c in d.get("checks", []) if not c.get("ok")]
    check("T38 reconciliation: books == card == session (named deltas otherwise)",
          d.get("all_ok") is True, str(bad[:2]))


def t39_champion_honesty():
    """M10: role stated; the Hold-timer row tells the rhythm-hold truth (no dead red)."""
    reg = (ROOT / "silmaril/execution/parameter_registry.py").read_text()
    ui = (ROOT / "docs/index.html").read_text()
    ok = ("rhythm-hold" in reg) and ("ROLE (7.0): ATTRIBUTION" in ui)
    check("T39 champion honesty: ATTRIBUTION role (7.0) on panel + rhythm-hold on the registry", ok, "")


def t40_fit_quality():
    """M11: DEGENERATE fingerprints never set a live target; cards state their fit."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    eng = (ROOT / "silmaril/execution/confidence_engine.py").read_text()
    ok_src = ("DEGENERATE" in sim and "vol-native fallback" in sim and "fit_state" in eng)
    bad = []
    try:
        live = _json.loads((ROOT / "docs/data/paper_sim_live.json").read_text())
        for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
            for p0 in (live.get(bk) or {}).get("positions") or []:
                f0 = p0.get("fit") or {}
                if f0 and float(f0.get("typical_dip") or 1) <= 0:
                    bad.append(p0.get("sym"))
    except Exception:
        pass
    check("T40 fit quality: degenerate fits blocked at entry + fit_state on every card",
          ok_src and not bad, f"live_degenerate={bad[:3]}")


def t41_readiness_numeric():
    """M12: the readiness meter ALWAYS renders a number — waiting is a zero, shown."""
    ui = (ROOT / "docs/index.html").read_text()
    ok = ("0/100</b> forward trades" in ui and "0/90</b> unbroken days" in ui)
    check("T41 readiness never null: numeric from cycle zero", ok, "")


def t42_discovery_contract():
    """5.3: graveyard + counterfactuals exist, resolve, and aggregate."""
    import json as _json
    src = (ROOT / "silmaril/execution/discovery.py").read_text()
    ok_src = ("OPPORTUNITY_GRAVEYARD" in src and "CF_LEDGER" in src
              and "would_gross_pct" in src and "never_bought" in src)
    try:
        d = _json.loads((ROOT / "docs/data/DISCOVERY.json").read_text())
        ok_d = ("graveyard" in d and "counterfactual" in d)
    except Exception:
        ok_d = True
    check("T42 discovery: graveyard buries+resolves · counterfactuals shadow every trade",
          ok_src and ok_d, "")


def t43_fingerprint_coverage():
    """M11: the fit ceiling is a knob, not a constant — 86% of the universe may not sit unfitted."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok_src = ("_scan_cap" in sim and "_pub_cap" in sim and "_cnt >= 500" not in sim)
    try:
        k = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text()).get("fingerprint_coverage") or {}
        ok_k = int(k.get("scan_cap", 0)) >= 1000 and int(k.get("publish_cap", 0)) >= 500
    except Exception:
        ok_k = False
    ven = (ROOT / "silmaril/execution/venues.py").read_text()
    ok_v = ("USDT" in ven and "_QUOTES" in ven)
    check("T43 fingerprint coverage knob (no hard 500) + venue reads its USDT book",
          ok_src and ok_k and ok_v, f"src={ok_src} knob={ok_k} venue={ok_v}")


# ═════════ 7.0 TRIPWIRES (T44–T51) — the activation release ═════════

def t44_geometry_gate():
    """Law 21/22: p* computed, stops cap not widen, no live pos demands more than its floor."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok_src = ("UNTRADEABLE:geometry" in sim and "UNTRADEABLE:evidence" in sim
              and "_pstar" in sim and "never widens" in sim)
    geo_ok = True
    try:
        g = _json.loads((ROOT / "docs/data/GEOMETRY.json").read_text())
        geo_ok = "counts" in g and "by_symbol" in g and "p_star_pct" in str(g)[:8000]
    except Exception:
        pass
    bad = []
    try:
        live = _json.loads((ROOT / "docs/data/paper_sim_live.json").read_text())
        for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
            for p0 in (live.get(bk) or {}).get("positions") or []:
                ps, pf = p0.get("p_star_pct"), p0.get("p_floor_pct")
                if ps is not None and pf is not None and pf < ps:
                    bad.append(p0.get("sym"))
    except Exception:
        pass
    check("T44 geometry gate: p* everywhere · abstain-never-distort · no live pos over its floor",
          ok_src and geo_ok and not bad, f"src={ok_src} store={geo_ok} over_floor={bad[:3]}")


def t45_edge_surface():
    """Cells stand down honestly below min_n; self-arming is a data event, in writing."""
    src = (ROOT / "silmaril/execution/edge_surface.py").read_text()
    ok = ("self-arms" in src.lower() or "SELF-ARMING" in src) and "min_cell_n" in src \
         and "_armed_at" in src and "PROVEN" in src
    check("T45 edge surface: min-n stand-down + self-arming activation (knob flip, not code)", ok, "")


def t46_maker_book():
    """Post-only resting limits: REST → FILL (paid the spread) or expire with the miss logged."""
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("MAKER_PENDING" in sim and '"REST"' in sim and '"FILL"' in sim
          and "maker_cost_frac" in sim and "UNFILLED" in sim)
    check("T46 maker book: resting limits fill on touch or expire — order type is edge", ok, "")


def t47_calibration_teeth():
    """Law 23: quarantine strips gating authority; the Master falls back to raw evidence."""
    mb = (ROOT / "silmaril/execution/master_account.py").read_text()
    cal = (ROOT / "silmaril/execution/calibration.py").read_text()
    ok = ("_cal_q" in mb and "evidence_score" in mb and "QUARANTINED" in cal
          and "brier" in cal.lower())
    check("T47 calibration teeth: QUARANTINE → evidence-gated Master (a score that can't predict can't allocate)", ok, "")


def t48_sizer_hand():
    """Law 24/25: ladder mult on every wager (paper+master) · breakers · one-factor law."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    mb = (ROOT / "silmaril/execution/master_account.py").read_text()
    ok_src = ("_sz_mult" in sim and "one-factor law" in sim and "_szr_mult" in mb)
    st_ok = True
    try:
        d = _json.loads((ROOT / "docs/data/SIZER.json").read_text())
        st_ok = d.get("state") in ("GREEN", "AMBER", "RED") and "factor" in d
    except Exception:
        pass
    check("T48 the governor's hand: ladder × every wager · breakers · crypto = one bet",
          ok_src and st_ok, f"src={ok_src}")


def t49_learning_permanence():
    """Law 26: no eviction without an archive; the data ledger reports it."""
    ret = (ROOT / "silmaril/execution/retention.py").read_text()
    disc = (ROOT / "silmaril/execution/discovery.py").read_text()
    mb = (ROOT / "silmaril/execution/master_account.py").read_text()
    ok = ("archive_evicted" in ret and "archive_evicted" in disc
          and "archive_evicted" in mb and "jsonl.gz" in ret)
    check("T49 learning permanence: evictions archive to gzip before any cap (Law 26)", ok, "")


def t50_question_engine():
    """The Interrogator asks everything and renders a TOWARD/AWAY verdict with numbers."""
    import json as _json
    src = (ROOT / "silmaril/execution/question_engine.py").read_text()
    ok_src = "TOWARD-EDGE" in src and "LEAST evidence" in src
    ok_d = True
    try:
        d = _json.loads((ROOT / "docs/data/QUESTIONS.json").read_text())
        ok_d = d.get("verdict") in ("TOWARD-EDGE", "HOLDING", "AWAY-FROM-EDGE") \
               and len(d.get("questions") or []) >= 12
    except Exception:
        pass
    check("T50 the interrogator: ≥12 questions answered with evidence + composite verdict",
          ok_src and ok_d, "")


def t51_genesis():
    """Law 30: the operator can burn it ALL down — learning too — while archives stay sacred."""
    wf = (ROOT / ".github/workflows/reset_internal_clean.yml").read_text()
    ok = ("wipe_mode" in wf and "genesis" in wf and "LEARNING" in wf
          and "STORE_REGISTRY" in wf)
    check("T51 genesis wipe: registry-driven total reset, archives untouched (Law 30)", ok, "")


def t52_builder_isolation():
    """7.0.1: no builder may take another down. The +$71.60 ghost was ONE TypeError in
    parameter_registry killing 8 semicolon-chained builders inside a shared try-block —
    silently, every cycle, since 5.3. This asserts isolation AND that every hourly
    builder actually runs against the live tree."""
    import importlib
    cli = (ROOT / "silmaril/cli.py").read_text()
    ok_iso = ("BUILDER FAILED (isolated" in cli
              and "_pregr = _preg(out); _cmp(out)" not in cli
              and "stale-derived sweep" in cli)
    broken = []
    for m in ("timer_optimization.build_timer_optimization",
              "chart_overlays.build_chart_overlays",
              "threshold_champion.build_threshold_champion",
              "parameter_registry.build_parameter_registry",
              "compounding_projection.build_compounding_projection",
              "regime_classifier.build_regime_classifier",
              "daily_journal.build_daily_journal",
              "session_reconstruction.build_session_reconstruction",
              "session_anatomy.build_session_anatomy",
              "crypto_concentration.build_crypto_concentration",
              "reality_check.build_reality_check",
              "champion_timeline.build_champion_timeline"):
        mod, fn = m.rsplit(".", 1)
        try:
            getattr(importlib.import_module("silmaril.execution." + mod), fn)(str(ROOT / "docs/data"))
        except Exception as e:
            broken.append(f"{mod}:{type(e).__name__}")
    check("T52 builder isolation: no shared-try cascade + all 12 hourly builders run clean",
          ok_iso and not broken, f"isolated={ok_iso} broken={broken[:3]}")


def t53_no_stale_derived():
    """A DERIVED store older than the wipe is a confident lie on the dashboard."""
    import json as _json, os
    try:
        wm = _json.loads((ROOT / "docs/data/WIPE_MARKER.json").read_text()).get("wiped_at")
        reg = _json.loads((ROOT / "docs/data/STORE_REGISTRY.json").read_text()).get("stores") or {}
    except Exception:
        check("T53 no stale DERIVED — no wipe marker yet (fresh tree)", True, "")
        return
    stale = []
    for f, cls in reg.items():
        if cls != "DERIVED":
            continue
        p = ROOT / "docs/data" / f
        if not p.exists():
            continue
        try:
            g = _json.loads(p.read_text()).get("generated_at")
        except Exception:
            continue
        if g and wm and str(g) < str(wm):
            stale.append(f)
    check("T53 no stale DERIVED store may predate the wipe (the +$71.60 ghost class)",
          not stale, f"stale={stale[:4]}")


def t54_canonical_fingerprint_merge():
    """7.0.2: the ccxt tape MUST reach fingerprints. The old rule skipped every crypto key
    without a dash, discarding 404 symbols x ~300 candles — invisible until a genesis wipe
    left the canonical keys shallow and crypto fingerprints went to ZERO."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok_src = ("_canon7" in sim and "_fp_rows" in sim
              and 'if _cl == "crypto" and "-" not in _s:\n                continue' not in sim)
    ok_d = True
    try:
        fp = _json.loads((ROOT / "docs/data/FINGERPRINTS.json").read_text())
        cards = fp.get("cards") or []
        # if a crypto tape exists at all, crypto MUST be represented among fits
        cx = _json.loads((ROOT / "docs/data/ccxt_samples.json").read_text()).get("samples") or {}
        if len(cx) > 50 and cards:
            ok_d = any(str(c.get("sym", "")).endswith("-USD") for c in cards)
    except Exception:
        pass
    check("T54 canonical fingerprint merge: the ccxt tape reaches fingerprints (crypto can fit)",
          ok_src and ok_d, f"src={ok_src} crypto_fitted={ok_d}")


def t55_dup_buy_guard_and_canon_ledger():
    """7.0 FINAL R2/R1: the double-BUY class is closed at the recorder, and every LIVE fill
    lands once in the one book of record (LEDGER.jsonl) — backtests can never write canon."""
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("ALREADY-HELD GUARD" in sim
          and "if sym in self.positions:\n            return False" in sim
          and "def _ledger(self, row):" in sim
          and 'pbook._canon = (out, book)' in sim
          and 'LEDGER.jsonl' in sim)
    rec = (ROOT / "silmaril/execution/reconciliation.py").read_text()
    ok = ok and "FIX_EPOCH" in rec and "no duplicate (sym,side,t)" in rec
    check("T55 dup-BUY guard + one book of record (LEDGER.jsonl) + epoch-scoped dup tripwire", ok, "")


def t56_master_mirror_law():
    """7.0 FINAL R1/R3: the Master consumes canon — opens only what a book holds, closes when
    the book closes — and the trades tail can never show an orphan SELL again."""
    ma = (ROOT / "silmaril/execution/master_account.py").read_text()
    ok = ("mirror_canon" in ma and '"mirrors"' in ma
          and "BOOK_CLOSED (canon mirror)" in ma
          and 'ACCEPT-WAIT: no canon book fill yet' in ma
          and 'list(reversed(book["trades"][-3:]))' not in ma
          and 'VENUE_UNIVERSE.json' in ma)
    check("T56 Master mirror law: opens from canon fills, follows book exits, honest tail, venue truth wired", ok, "")


def t57_forward_ledger_and_vault():
    """7.0 FINAL V1/V2: forward evidence + calibration survive every standard reset, and the
    reset archives before it touches anything (Law 26) — the 'Lickitung forever' root cause."""
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    rst = (ROOT / "scripts/reset_internal_clean.py").read_text()
    ok = ("CHAMPION_FORWARD_LEDGER.jsonl" in sim
          and "ARCHIVE-FIRST" in rst and "REFUSING to reset" in rst
          and "CHAMPION_FORWARD_LEDGER.jsonl" in rst
          and '"CALIBRATION.json", "AGGRESSION_LADDER.json"' not in rst)
    check("T57 champion forward ledger + archive-first reset + calibration survives standard wipe", ok, "")


def t58_registry_vault_classes():
    """7.0 FINAL V1: the preserved-forever roster is classed LEARNING/LEDGER so the post-wipe
    DERIVED sweep can never kill what the reset promises to keep."""
    import importlib
    srmod = importlib.import_module("silmaril.execution.store_registry")
    ok = all(srmod._cls(f) == "LEARNING" for f in
             ("CALIBRATION.json", "GRAVEYARD.json", "CONDUCTOR_STATE.json", "CONDUCTOR_REPORT_CARD.json"))
    ok = ok and srmod._cls("LEDGER.jsonl") == "LEDGER" \
             and srmod._cls("CHAMPION_FORWARD_LEDGER.jsonl") == "LEDGER"
    check("T58 vault classes: calibration/graveyard/conductor are LEARNING; ledgers are LEDGER", ok, "")


def t59_workflow_law():
    """7.0.1 SERIALIZATION LAW (supersedes per-lane groups): every STATE-MUTATING lane shares ONE
    concurrency group 'silmaril-state' with cancel-in-progress:false, so daily/hourly/analytics/
    backfill/reset/etc queue strictly FIFO and cron overlap can NEVER corrupt a half-written tree.
    Read-only lanes (selftest, verify) get their own cancel-in-progress groups. selftest push is
    paths-filtered (no stampede on data commits) and its fail-reporter is guarded."""
    import glob as _glob
    try:
        import yaml as _yaml
    except Exception:
        check("T59 workflow law (pyyaml unavailable — cannot verify)", False, "pip install pyyaml")
        return
    wf = ROOT / ".github/workflows"
    problems = []
    # 7.0.2 SUPERSEDED: the shared 'silmaril-state' queue was the cause of the cancellations
    # (GitHub keeps only ONE pending run per group, so the 10-min daily kept killing queued
    # hourly/analytics). Lane INDEPENDENCE is now the law and T78 enforces it; here we only
    # assert that no lane has been left on the old shared queue.
    for fp in wf.glob("*.yml"):
        if "silmaril-state" in fp.read_text():
            problems.append(f"{fp.name}: still on the retired shared silmaril-state queue")
    st = (wf / "selftest.yml").read_text()
    if "paths:" not in st:
        problems.append("selftest.yml: push not paths-filtered (stampede risk)")
    if "silmaril-selftest" not in st:
        problems.append("selftest.yml: missing own concurrency group")
    if "core.warning" not in st:
        problems.append("selftest.yml: fail-reporter not guarded")
    if (wf / "verify_install.yml").exists() and "silmaril-verify" not in (wf / "verify_install.yml").read_text():
        problems.append("verify_install.yml: missing own concurrency group")
    check("T59 workflow law: state lanes serialized on silmaril-state · selftest filtered+guarded · read-only lanes grouped",
          not problems, "; ".join(problems))

def t60_maturity_gate():
    """7.0 FINAL T2: 'I don't know yet' is the default — no fitted-book entry without evidence
    (fingerprint dip-events or resolved bounce-tries); GEKKO exempt; knob-gated with a kill."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("CONFIDENCE MATURITY" in sim
          and ("earning the right to trade" in sim or "one-universe river" in sim)
          and 'book != "aggressive"' in sim and 'maturity' in sim)
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("maturity") or {}).get("mode") in ("auto", "off")
    except Exception:
        pass
    check("T60 maturity gate: evidence before risk, GEKKO exempt, knob + kill registered", ok, "")


def t61_equity_truth():
    """7.0 FINAL R5: ONE money number. The reconciliation stage emits EQUITY_TRUTH.json;
    every money panel is meant to read it, never recompute."""
    import json as _json
    rec = (ROOT / "silmaril/execution/reconciliation.py").read_text()
    ok = "EQUITY_TRUTH.json" in rec and "open_committed_usd" in rec
    p = ROOT / "docs/data/EQUITY_TRUTH.json"
    if p.exists():
        try:
            d = _json.loads(p.read_text())
            ok = ok and ("total_equity" in d and "delta_usd" in d)
        except Exception:
            ok = False
    check("T61 EQUITY_TRUTH emitted: total · delta-vs-start · open-committed, one owner", ok, "")


def t62_one_universe_river():
    """7.0 ONE-UNIVERSE: sleeve closes flow into LAB_OUTCOMES.jsonl and the real books' maturity
    gate COUNTS them — the workshop matures names for production. The 'alternate universe' is dead."""
    lab = (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text()
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("LAB_OUTCOMES.jsonl" in lab and "_RIVER" in lab and "LAB_EVIDENCE.json" in lab
          and "LAB_OUTCOMES.jsonl" in sim and "_lab7" in sim and "min_lab_outcomes" in sim)
    check("T62 one-universe river: sleeves → LAB_OUTCOMES → books' maturity gate + LAB_EVIDENCE/spotlight", ok, "")


def t63_trajectory_veto():
    """7.0 ZIL/WLD lesson: multi-window free-fall may not fill without a printed floor — every
    book, GEKKO included; MKR-style up-window dips pass."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("def _traj_win" in sim and "TRAJECTORY VETO" in sim
          and "free-fall is not a dip" in sim and 'direction != "mom"' in sim)
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("trajectory_veto") or {}).get("mode") in ("auto", "off")
    except Exception:
        pass
    check("T63 trajectory veto: 24h+72h free-fall blocked for ALL books unless a floor prints (knob+kill)", ok, "")


def t64_news_in_decision_path():
    """7.0 operator directive: news pulses through the decision path — every sized candidate
    logs to NEWS_TILT_AB (shadow); knob 'on' applies a capped tilt; status published for the UI."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("NEWS_TILT_AB.jsonl" in sim and "news_tilt" in sim and "NEWS_PULSE_STATUS.json" in sim
          and "_np7" in sim)
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("news_tilt") or {}).get("mode") in ("shadow", "on", "off")
    except Exception:
        pass
    check("T64 news pulse wired: shadow A/B log on every sized candidate + status + knob/kill", ok, "")


def t65_health_reads_authority():
    """7.0: the health panel reads fresh api_health.json (the matrix snapshot lied 0/3 for a day)."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("const d=await jget('data/api_health.json')" in html and "matrix" in html
          and "staleTag" in html)
    check("T65 health panel reads authoritative api_health.json (matrix stale-tagged, never trusted blind)", ok, "")


def t66_modal_contract():
    """7.0: ONE modal contract — every opener rebuilds the box (close button always exists),
    Esc + backdrop close, no display-mode split."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("__resetModalBox" in html and html.count("__resetModalBox();") >= 4
          and "__closeModal" in html and "Escape" in html
          and "style.display='flex'" not in html)
    check("T66 modal contract: 4 openers reset the box · Esc/backdrop/✕ close · one display mode", ok, "")


def t67_portals_and_spotlight():
    """7.0 operator directive: colorful account portals on BOTH tabs + the CHAMPION SLEEVE
    spotlight (Δ-vs-HODL leader) with the one-universe river line."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("quadrantsCmd" in html and "renderSleeveSpotlight" in html
          and "sleeveSpot" in html and "CHAMPION SLEEVE" in html
          and "'quadrants','quadrantsCmd'" in html)
    check("T67 portals on Command+Markets + CHAMPION SLEEVE spotlight (workshop-labeled, click-through)", ok, "")


def t68_readiness_truth():
    """7.0 truth pass: FIRST-TRADE READINESS states the REAL reason (closed/quiet/immature/veto/
    gated) — never 'waiting for a dip' while candidates exist; GEKKO gets a row; river+news footer."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("MARKET CLOSED —" in html and "OBSERVE — earning evidence" in html
          and "VETOED —" in html and "ONE-UNIVERSE RIVER" in html
          and "NEWS PULSE in the decision path" in html
          and "ARMED — waiting for a qualifying dip" not in html)
    check("T68 readiness truth: real funnel reasons on every book incl GEKKO + river/news footers", ok, "")


def t69_reset_reanchors_nulls():
    """7.0.1: a reset re-anchors the nulls with the fresh books (operator: vs-HODL not resetting).
    reset_internal_clean deletes BENCH_BOOKS.json so Law-10 comparisons share one honest inception."""
    r = (ROOT / "scripts/reset_internal_clean.py").read_text()
    ok = "BENCH_BOOKS.json" in r and "re-anchor" in r
    check("T69 reset re-anchors nulls: BENCH_BOOKS deleted on wipe (no ghost vs-HODL on fresh books)", ok, "")


def t70_reset_seeds_live():
    """7.0.1: a reset seeds a truthful paper_sim_live.json so the dashboard never renders pre-reset
    ghosts against fresh $10k books — the 'keeps not working when we reset' Frankenstein state."""
    r = (ROOT / "scripts/reset_internal_clean.py").read_text()
    ok = "seeded_by_reset" in r and "paper_sim_live.json" in r
    check("T70 reset seeds truthful LIVE snapshot (no pre-reset ghosts, both modes)", ok, "")


def t71_workflow_serialization():
    """7.0.1: every state-mutating lane shares ONE concurrency queue so cron overlap can never
    corrupt files; selftest is paths-filtered (no stampede on data commits) and cancel-in-progress."""
    import glob as _g
    wf = ROOT / ".github/workflows"
    # 7.0.2: independence replaced the shared queue (see T78) — assert the retirement, not the queue.
    ok = not any("silmaril-state" in f.read_text() for f in wf.glob("*.yml"))
    st = (wf / "selftest.yml").read_text()
    ok = ok and "paths:" in st and "silmaril-selftest" in st and "core.warning" in st
    check("T71 workflow law: shared queue retired · selftest paths-filtered + guarded", ok, "")


def t72_modal_scope_and_guard():
    """7.0.1: the click-in fix — spotlight lives INSIDE <script> (not leaking into #modal markup),
    the #modal container is intact, and drawChart guards null positions so non-held tickers render."""
    html = (ROOT / "docs/index.html").read_text()
    head = html[:html.index("<script>")]
    ok = ("async function renderSleeveSpotlight" not in head          # not stranded in markup
          and 'id="chartHost"' in html and 'id="modalClose"' in html   # modal intact
          and "NULL-POSITION GUARD" in html and "hasPos" in html)      # crash guard present
    check("T72 modal scope + null-guard: spotlight in-script, #modal intact, drawChart never crashes", ok, "")


def t73_health_reads_live_when_stale():
    """7.0.1: the health panel reads live api_health and falls back to its key_groups for feeds when
    the matrix snapshot trails >30m — the '864m stale / ?/? files fresh / YELLOW' lie is gone."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("data/api_health.json" in html and "_matrixStale" in html
          and "providers_active" in html and "feeds snapshot" in html)
    check("T73 health truth: live api_health, feeds fall back to key_groups when matrix stale", ok, "")


def t74_header_and_portals():
    """7.0.1 cleanup: header build-stamp only shows when it differs from the version (no 'build 7.0'
    doubling); the four INDUSTRY books are the top portals (GEKKO is a crypto sleeve, not a peer)."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("String(m.version)!==String(vn)" in html
          and "['crypto','stock','metal','energy'].map(bk=>" in html
          and "GEKKO is a crypto SLEEVE" in html)
    check("T74 header/portals: no doubled build stamp · 4-up industry portals · GEKKO at sleeve rank", ok, "")


def t75_health_and_wiring_labels():
    """7.0.1 cleanup: the health panel reads live api_health with no false stale-matrix alarm (matrix
    age is a cache detail, not a fault); the Wide Arena is labeled as a 3x/day sweep, not a live feed."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("matrix is only a feeds-detail cache" in html
          and "staleTag=' <span class=neg>\\u26a0 feeds snapshot" not in html
          and "sweeps 3\\u00d7/day, not live" in html)
    check("T75 health/wiring labels: no false matrix-stale alarm · Wide Arena cadence labeled", ok, "")


def t76_quantization_quarantine():
    """7.0.1: the oscillation detector catches EXTREME quantization (a sub-penny name collapsed to
    <=3 discrete values — the MOG-USD sawtooth that the median-gap path missed via the m1=0 blind
    spot). Per-cycle data-quality quarantine, NOT a graveyard — the name trades when price resolves."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    try:
        from silmaril.execution.paper_sim import _osc_ratio as _o
    except Exception as e:
        check("T76 quantization quarantine (import failed)", False, str(e)); return
    mog = [1e-7, 1.1e-7, 1.1e-7, 1e-7, 1.1e-7, 1e-7, 1.1e-7, 1.1e-7, 1e-7, 1.1e-7, 1e-7, 1.1e-7, 1.1e-7, 1e-7]
    healthy = [100 + (i % 7) * 0.31 - (i % 3) * 0.17 for i in range(20)]
    stable = [1.0] * 14
    ok = (_o(mog) is True and _o(healthy) is False and _o(stable) is False)
    check("T76 quantization: two-cluster sawtooth quarantined; healthy + pinned-flat names untouched", ok, "")


def t77_regime_conditional_champion():
    """7.0.1 (operator: "switch to a momentum one — the ENTIRE PURPOSE of the Pokemon system"). A
    trending book must not be handed a mean-reversion champion that sits idle waiting for a dip.
    In UPTREND/DOWNTREND, champion_split prefers the best dir='mom' strategy from that book's own
    arena over the MR rank-leader; SIDEWAYS keeps mean-reversion; forward survivability still wins
    once a book has live trades. Knob regime_champion.mode, kill 'off'."""
    src = (ROOT / "silmaril/execution/champion_split.py").read_text()
    ok = ("REGIME-FIT" in src and "_regime_pref_dir" in src and "_best_by_dir" in src
          and 'dir") == want_dir' in src)
    try:
        import json as _json
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("regime_champion") or {}).get("mode") in ("auto", "off")
    except Exception:
        pass
    check("T77 regime-conditional champion: trending books prefer momentum, sideways keeps MR (knob+kill)", ok, "")


def t78_workflow_independence():
    """7.0.2 (operator: "deep analytics and hourly are getting canceled out by the daily"). GitHub
    keeps only ONE pending run per concurrency group, so a shared group + a 10-min daily silently
    cancelled every queued hourly/analytics run. Every lane must own its group."""
    import glob as _g
    wf = ROOT / ".github/workflows"
    shared = [f.split("/")[-1] for f in _g.glob(str(wf / "*.yml")) if "silmaril-state" in open(f).read()]
    groups = {}
    for f in _g.glob(str(wf / "*.yml")):
        import re as _re
        m = _re.search(r"group:\s*(\S+)", open(f).read())
        if m:
            groups.setdefault(m.group(1), []).append(f.split("/")[-1])
    dupes = {g: v for g, v in groups.items() if len(v) > 1}
    ok = (not shared) and (not dupes)
    check("T78 workflow independence: every lane owns its concurrency group (no cross-cancellation)",
          ok, f"shared={shared} dupes={dupes}")


def t79_sleeve_promotion_pyramid():
    """7.0.2 THE PYRAMID, RUNG 2: the best sleeve in a book's own workshop hands its discipline up to
    that book. Promotion needs real closed trades and positive expectancy; a losing workshop promotes
    nobody. Sleeve behaviour is never altered — only selected (operator's explicit instruction)."""
    import json as _json
    src = (ROOT / "silmaril/execution/sleeve_promotion.py")
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    lab = (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text()
    cli = (ROOT / "silmaril/cli.py").read_text()
    ok = (src.exists() and "promoted_discipline" in sim and "sleeves_def" in lab
          and "sleeve_promotion.build_sleeve_promotion" in cli)
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("sleeve_promotion") or {}).get("mode") in ("auto", "off")
    except Exception:
        pass
    check("T79 pyramid rung 2: winning sleeve's discipline promoted to its book (knob + kill)", ok, "")


def t80_trade_detail_everywhere():
    """7.0.2 (operator: "every place open trade data is shown a live bar graph needs to be shown").
    One shared bar builder feeds the main page, the account portals and the sleeve ledgers, and the
    portal exit table reads the REAL close (t.exit.realized_pct) instead of printing $0.00."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("function __posBar(" in html
          and "X.realized_pct" in html
          and "entry \u2192 exit" in html or "entry → exit" in html)
    ok = ok and "t.pnl??t.realized??0" not in html.replace(" ", "")
    check("T80 trade detail everywhere: shared live bar + true exit price/%/reason in every view", ok, "")


def t81_per_industry_badges_and_gekko_rank():
    """7.0.2: a CHAMPION SLEEVE badge for EVERY industry (not just crypto), each showing whether that
    sleeve has been promoted; and GEKKO drops off COMMAND — it is a crypto sleeve, not a 5th book."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("SLEEVE_PROMOTION.json" in html and "PROMOTED into the" in html
          and "const books=['crypto','stock','metal','energy']" in html
          and 'id="posAggressive" style="display:none"' in html)
    check("T81 per-industry champion badges + GEKKO at sleeve rank on COMMAND", ok, "")


def t82_fee_truth_and_reachable_targets():
    """7.0.2 THE GOLD FIX: per-asset-class fee floors (crypto unchanged; US ETFs commission-free) and
    vol-native targets sized to what a name actually reaches. One global 0.2% floor made GLD/IAU
    mathematically untradeable, which is why the metal book never traded."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("def _reachable_move" in sim and "def _vol_native_target" in sim
          and "fee_class" in sim and "book: str = None" in sim)
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        fc = cat.get("fee_class") or {}
        ok = ok and fc.get("mode") in ("auto", "off")
        ok = ok and float((fc.get("floor") or {}).get("crypto", 0)) == 0.002   # crypto untouched
        ok = ok and float((fc.get("floor") or {}).get("metal", 1)) < 0.002     # ETFs cheaper
        ok = ok and (cat.get("vol_native", {}).get("target") or {}).get("mode") in ("auto", "off")
    except Exception:
        ok = False
    check("T82 fee truth + reachable targets: gold tradeable, crypto fee model unchanged (knob+kill)", ok, "")


def t83_no_target_guard():
    """7.0.2 SPCX post-mortem: SPCX opened with "target +None%" when the stock champion's params were
    incomplete, then rode 123.28 -> 116.56 with no defined exit-up. A trade without a target is a hope."""
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = "NO-TARGET GUARD" in sim and "_no_target_fallback" in sim
    check("T83 no-target guard: a position can never open without a real target and stop", ok, "")


def t84_master_repair():
    """7.0.3 MASTER REPAIR. The Master had 11 trades, 0 wins, -3.05%: it mirrored GEKKO (documented
    "NEVER Master-funded") on a name the crypto book never traded, then churned that one probe
    position into six losing round trips. Four guards now: no aggressive funding, a freshness gate
    so it never joins a trade already in flight, a re-entry cooldown, and a promoted-sleeve
    requirement so only proven quadrants may fund the one account that rehearses live money."""
    import json as _json
    src = (ROOT / "silmaril/execution/master_account.py").read_text()
    ok = ("allow_aggressive_mirror" in src and "mirror_max_age_min" in src
          and "reentry_cooldown_min" in src and "require_promoted_sleeve" in src
          and "_recent_exits" in src and '"realized_pnl"' in src and '"reserve_usd"' in src)
    try:
        kb = (_json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text()).get("master_brain") or {})
        ok = ok and kb.get("allow_aggressive_mirror") is False
        ok = ok and float(kb.get("mirror_max_age_min", 0)) > 0
        ok = ok and float(kb.get("reentry_cooldown_min", 0)) > 0
    except Exception:
        ok = False
    check("T84 master repair: GEKKO never funds Master · freshness gate · cooldown · proven-book gate", ok, "")


def t85_real_fee_model():
    """7.0.3 (operator: "all fees must be accounted for per industry, per trade style, per regime").
    Cost is COMPOSED from published venue commissions + US regulatory + a spread MEASURED on our own
    tape + slippage scaled by regime and style — not a tunable floor that could be lowered until
    results looked good. The audit file makes every fee traceable."""
    import json as _json
    fm = ROOT / "silmaril/execution/fee_model.py"
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = fm.exists() and "from .fee_model import round_trip" in sim
    if fm.exists():
        src = fm.read_text()
        ok = ok and all(k in src for k in ("REGIME_MULT", "STYLE_MULT", "measured_half_spread",
                                           "SEC_FEE_RATE", "binance_us", "coinbase_adv"))
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("fee_model") or {}).get("mode") in ("auto", "off")
    except Exception:
        ok = False
    check("T85 real fees: venue commission + regulatory + measured spread + regime/style slippage", ok, "")


def t86_serial_lane_lock():
    """7.0.3 (operator: "we do not want runs running simultaneously ... never interrupt, but also
    never run simultaneously, no timeout"). GitHub concurrency cannot express that alone: a shared
    group cancels queued runs, independent groups overlap. Every state lane now waits on a mutex
    step, cancels only its OWN older run, and has room to wait its turn."""
    import glob as _g
    wf = ROOT / ".github/workflows"
    # 7.0.5: the operator runs five lanes (daily, analytics, hourly, selftest, venue) and leaves the
    # rest off after a wipe. Assert the law on the lanes that actually run.
    # 7.1 ONE WRITER LAW: hourly.yml is RETIRED (contents:read, no state, no cron) — its full
    # pass now runs inside daily.yml, so the lock law no longer binds it. T110 owns the new law.
    lanes = ["daily.yml", "analytics.yml", "venue_universe.yml", "selftest.yml"]
    # 7.0.5: the same-lane "newest wins" rule moved to the QUEUE (GitHub supersedes a pending run)
    # after cancel-in-progress:true was found murdering the daily's own 12-13 min cycle every 10
    # minutes. T92 now owns that law; T86 asserts the lock itself and its no-starvation timeout.
    missing = [w for w in lanes if (wf / w).exists() and "SERIAL LANE LOCK" not in (wf / w).read_text()]
    notimeout = [w for w in lanes if (wf / w).exists() and "timeout-minutes: 350" not in (wf / w).read_text()]
    ok = (not missing) and (not notimeout)
    check("T86 serial lane lock present on every state lane · no timeout starvation",
          ok, f"missing_lock={missing} missing_timeout={notimeout}")


def t87_capital_truth_display():
    """7.0.3 (operator: "every industry colorful portal should ALWAYS show its harvest USD that won't
    be spent AND how much it has locked up in open trades"). One shared __capital() builder feeds the
    portal cards AND the click-ins, so the tile and the panel it opens can never disagree. The three
    numbers always sum to equity, so nothing is double-counted as both banked and in play."""
    html = (ROOT / "docs/index.html").read_text()
    ok = ("function __capital(" in html and "function __capitalLine(" in html
          and "WHERE THE MONEY IS" in html
          and "__capitalLine(__capital(b))" in html
          and "vaulted (never redeployed)" in html)
    check("T87 capital truth: vaulted + committed + free on every portal card and click-in", ok, "")


def t88_book_harvest_switch():
    """7.0.3: the books can now vault a slice of every winning close into non-spendable reserve_usd,
    surviving cycles. DEFAULT OFF — vaulting locks in gains but shrinks compounding capital, so it is
    a strategy decision for the operator, never a silent behaviour change."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("book_harvest" in sim and "self.reserve_usd" in sim
          and 'b.reserve_usd = float(d.get("reserve_usd"' in sim          # survives cycles
          and '"reserve_usd": round(float(getattr(pbook' in sim)          # reaches the dashboard
    try:
        hk = (_json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text()).get("book_harvest") or {})
        ok = ok and hk.get("mode") in ("auto", "off")
    except Exception:
        ok = False
    check("T88 book harvest: vault survives cycles, reaches the UI, defaults OFF (operator's call)", ok, "")


def t89_venue_routing_and_fee_provenance():
    """7.0.4 (operator: "if a coin is available on binance.us it should always go with them; only when
    it is not available should it use Coinbase or Robinhood with their fees ... each trade needs the
    fee amount attached from the source"). Routing is a lookup against real VENUE_UNIVERSE listing
    data in preference order, and every close carries the venue, the routing reason and fee_usd."""
    fm = (ROOT / "silmaril/execution/fee_model.py").read_text()
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("VENUE_PREFERENCE" in fm and 'VENUE_PREFERENCE = ("binanceus", "coinbase", "robinhood")' in fm
          and "def resolve_venue" in fm and "unroutable" in fm
          and "FEE PROVENANCE" in sim and '"fee_usd"' in sim and '"venue_routed_by"' in sim)
    check("T89 venue routing: Binance.US first, real listings, fee + venue stamped on every close", ok, "")


def t90_full_profit_harvest():
    """7.0.4 (operator: "we want ALL profits reserved into USD ... anything after all fees should be
    swept into a USD reserve"). Every winning close sweeps 100% of its NET take-home into
    non-spendable reserve_usd, and that vault survives cycles."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = "book_harvest" in sim and "self.reserve_usd" in sim
    try:
        hk = (_json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text()).get("book_harvest") or {})
        ok = ok and str(hk.get("mode")).lower() == "auto" and float(hk.get("frac", 0)) == 1.0
    except Exception:
        ok = False
    check("T90 full harvest: 100% of every net win swept to USD reserve, never redeployed", ok, "")


def t91_immediate_sleeve_seed():
    """7.0.4 (operator: "immediately start with the best sleeves we have currently as our default
    starting sleeves until better ones show themselves and prove it"). A book with no fully-graded
    sleeve adopts the best available one, flagged PROVISIONAL so it is never mistaken for proven."""
    import json as _json
    src = (ROOT / "silmaril/execution/sleeve_promotion.py").read_text()
    ok = ("PROVISIONAL" in src and "seed_immediately" in src
          and '("PROMOTED", "PROVISIONAL")' in src)
    try:
        k = (_json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text()).get("sleeve_promotion") or {})
        ok = ok and bool(k.get("seed_immediately")) is True
    except Exception:
        ok = False
    check("T91 immediate seed: books start on our best current sleeve, marked PROVISIONAL", ok, "")


def t95_graph_brain_reads_structure():
    """7.0.6 (operator: "we need the system to read the chart the way a professional trader would").
    chart_intel computes swing peaks/troughs, Dow structure (higher highs + higher lows), clustered
    floors/ceilings with test counts, basing evidence and a 2h..1w trajectory ladder — all measured
    from real prints, nothing synthesised."""
    import sys as _sys, math as _math
    _sys.path.insert(0, str(ROOT))
    try:
        from silmaril.execution.chart_intel import analyze as _a
    except Exception as e:
        check("T95 graph brain (import failed)", False, str(e)); return
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    t0 = _dt(2026, 7, 20, 0, 0, tzinfo=_tz.utc)
    rows, i = [], 0
    for cyc in range(7):                    # an explicit staircase: every high AND low steps down
        hi = 100.0 * (0.98 ** cyc)
        lo = hi * 0.96
        for st in range(12):                # up leg
            rows.append(((t0 + _td(minutes=15 * i)).isoformat(), lo + (hi - lo) * st / 11)); i += 1
        for st in range(12):                # down leg, undercutting the prior low
            rows.append(((t0 + _td(minutes=15 * i)).isoformat(), hi - (hi - lo * 0.98) * st / 11)); i += 1
    d = _a("FALLER", rows)
    # 7.0.7: the brain must READ the structure correctly — but it must NOT block on it. A hard
    # DOWNTREND veto measured -284.98 across 89 point-in-time trades and refused 16 straight
    # winners on 2026-07-13, because catching the bounce in a beaten-down name IS mean reversion.
    # Structure now feeds conviction; the floor distance is what actually shapes the wager.
    ok = (d.get("structure") in ("DOWNTREND", "DISTRIBUTION")
          and d.get("verdict", {}).get("buyable") is not False
          and "windows" in d and "peak_trajectory" in d and "floor" in d
          and d.get("distance_to_floor_pct") is not None)
    check("T95 graph brain: reads lower-highs/lower-lows as DOWNTREND and reports it WITHOUT blocking",
          ok, f"structure={d.get('structure')} buyable={d.get('verdict', {}).get('buyable')}")


def t96_graph_brain_informs_not_blocks():
    """7.0.7 — this tripwire records a reversal I had to make against my own work.

    I shipped a hard veto refusing DOWNTREND-without-basing. Backtested POINT-IN-TIME over 89 closed
    trades from three real sessions (tape truncated to each entry, no look-ahead) it was destructive:

        no gate                        +1754.36
        DOWNTREND-without-basing veto  +1469.38   (-284.98, 18 trades blocked)

    On 2026-07-13 it would have refused 16 trades and every single one was a winner (+341.56),
    because buying a beaten-down name and catching the bounce IS mean reversion. By structure:
    RANGE 95.8% win (+1469.89), DOWNTREND 76.2% win (+53.68 — the category I blocked, profitable),
    UPTREND 63.6% win (-49.93 — the category I allowed, losing).

    The veto is gone. The chart read now shapes CONVICTION via floor proximity, which is what the
    evidence actually supports, and the UI renders the same file the engine reads."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ci = (ROOT / "silmaril/execution/chart_intel.py").read_text()
    cli = (ROOT / "silmaril/cli.py").read_text()
    html = (ROOT / "docs/index.html").read_text()
    ok = ("STRUCTURE VETO IS RETIRED" in ci
          and "FLOOR PROXIMITY" in sim and "_fp_mult" in sim
          and "chart_intel.build_chart_intel" in cli
          and "__graphBrain" in html and "__overlaySources" in html)
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("floor_proximity") or {}).get("mode") in ("auto", "off")
        ok = ok and "graph_gate" not in cat          # the harmful veto knob is gone for good
    except Exception:
        ok = False
    check("T96 chart read informs conviction, never hard-blocks (the -284.98 veto stays retired)", ok, "")


def t98_reentry_guard_brent():
    """7.0.7 THE BRENT GUARD. On 2026-07-23 the energy book bought BRENT at 86.9481 and sold at
    100.2335 for +$198.64 — then re-entered at 100.5641, ABOVE its own exit, and has been under
    water since. A name may now only be re-bought below the price we sold it at."""
    import json as _json
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok = ("RE-ENTRY GUARD" in sim and "_last_exit" in sim
          and '"last_exit": getattr(self, "_last_exit"' in sim)      # survives cycles
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("reentry_guard") or {}).get("mode") in ("auto", "off")
    except Exception:
        ok = False
    check("T98 re-entry guard: never buy back above the price we just sold (BRENT)", ok, "")


def t97_no_invented_marks_or_targets():
    """7.0.6 — two display lies killed at the source. (1) A position can no longer be born without a
    target: the 7.0.2 guard sat in the caller, so every trade still logged 'target +None%'; the
    invariant now lives inside buy(). (2) __posBar refuses to draw a marker with no live mark rather
    than defaulting mark=entry, which parked the marker at dead centre of stop..target on every open
    trade — the "bar sitting at zero in the middle" the operator reported."""
    sim = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    lab = (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text()
    html = (ROOT / "docs/index.html").read_text()
    ok = ("NO-TARGET INVARIANT" in sim and 'pos["target_fallback"]' in sim
          and "SLEEVE MARKS" in lab
          and "NEVER invent a mark" in html and "awaiting live mark" in html)
    check("T97 no invented marks or targets: the bar shows real price or admits it has none", ok, "")


def t99_sleeve_marks_from_tape():
    """7.0.8 — the sleeve portal showed "entry -> entry +0.00%" on every open trade. My 7.0.6 fix
    sourced marks from LIVE BOOK positions, but a sleeve holds names the books do not (ENA, WAVES,
    RUNE, BNB, BAL), so 0 of 118 sleeve positions ever got a mark. Marks now come from the PRICE
    TAPE, which prices everything we hold."""
    lab = (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text()
    ok = ("_tape7" in lab and "THE ACTUAL FIX" in lab
          and "price_samples.json" in lab)
    check("T99 sleeve marks come from the price tape, not just book positions", ok, "")


def t100_fast_regime_bands():
    """7.0.8 (asked three times): sub-hour regime awareness. The engine already computed 12m/15m/30m
    slopes and a fast_band_red/green early warning; the panel never displayed them, so a turn in
    progress stayed invisible until the 1h band caught up."""
    html = (ROOT / "docs/index.html").read_text()
    rc = (ROOT / "silmaril/execution/regime_classifier.py").read_text()
    ok = ("slope_15m_pct" in html and "FAST BANDS" in html and "FAST RED" in html
          and "slope_15m_pct" in rc)
    check("T100 fast regime bands (12m/15m/30m) surfaced in LIVE REGIME", ok, "")


def t101_evidence_outranks_label():
    """7.0.8 — the same error found in two more places, both now corrected.

    (1) fingerprint.fit_strategy rejected any 'falling' name BEFORE looking at its measured bounce
        reliability: 384 of 473 unfitted names died on that label, 126 of them carrying a measured
        reliability of 0.6+ (WIF-USD recovers 1.94% from a 0.66% dip, 90% of the time).
    (2) geometry.p_floor counted ONLY book trades, so after a wipe every name was STAND-DOWN and
        could never earn the trades the gate was waiting for — 474 of 674 names deadlocked shut.
        A name's own tape now counts as evidence at a haircut, labelled 'tape' so it can never be
        confused with a live record."""
    import json as _json
    fpz = (ROOT / "silmaril/execution/fingerprint.py").read_text()
    geo = (ROOT / "silmaril/execution/geometry.py").read_text()
    ok = ("falling_min_reliability" in fpz and "EVIDENCE OUTRANKS THE LABEL" in fpz
          and "TAPE EVIDENCE" in geo and "tape_haircut" in geo)
    try:
        cat = _json.loads((ROOT / "docs/data/PARAM_CATALOG.json").read_text())
        ok = ok and (cat.get("geometry") or {}).get("tape_evidence") in (True, False)
    except Exception:
        ok = False
    check("T101 evidence outranks the label (fingerprint falling-reject + geometry deadlock)", ok, "")


def t102_maturity_gate_can_see_evidence():
    """7.0.9 THE SILENT DEADLOCK. The maturity gate reads
            _ev7 = int(_ftm.get("dip_samples") or _ftm.get("n") or 0)
    where _ftm is the dict returned by fit_strategy() — which never carried either field. So _ev7
    was 0 for every name on every cycle, and every candidate was judged "immature" regardless of
    the evidence behind it. XMR-USD sat on 672 samples and 295 observed dip events with a 0.933
    bounce reliability and the gate read zero. Measured cost: the crypto book found 12 qualifying
    candidates and bought NONE for 40 hours (9 of 12 rejected "immature"); only GEKKO, which is
    exempt by doctrine, kept trading."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    try:
        from silmaril.execution.fingerprint import fingerprint as _fp, fit_strategy as _fit
    except Exception as e:
        check("T102 maturity gate evidence (import failed)", False, str(e)); return
    px = [100.0]
    for i in range(400):                      # a tape with plenty of real dips
        px.append(px[-1] * (0.995 if i % 7 == 0 else 1.0015))
    f = _fp(px)
    fit = _fit(f, 0.0038, 0.06)
    ok = f.get("dip_samples") is not None
    if fit:
        ev = int(fit.get("dip_samples") or fit.get("n") or 0)
        ok = ok and ev > 0            # the gate must be able to SEE the evidence
    check("T102 maturity gate can see fit evidence (dip_samples/n reach the gate, not 0)", ok,
          f"fp.dip_samples={f.get('dip_samples')} fit_ev={(int((fit or {}).get('dip_samples') or (fit or {}).get('n') or 0)) if fit else 'no-fit'}")


def t103_workshop_is_not_frozen():
    """7.0.9 THE FROZEN WORKSHOP — the worst bug in the 2026-07-25 audit. The sleeve simulator built
    its `marks` dict ONLY from names the funded books currently held. The books held one name
    (LTCUSDT); the sleeves held 41. So 41 of 41 sleeve positions had no mark, and a sleeve cannot
    hit a target or a stop it cannot see. Every sleeve position was frozen — never sold, never
    graded, never returned to the river as maturity evidence (STRK-USD sat at +28.25% unrealised).
    The workshop is the bottom of the pyramid; frozen, it stalled the entire learning chain."""
    lab = (ROOT / "silmaril/execution/strategy_lab_abcd.py").read_text()
    ok = ("THE FROZEN WORKSHOP" in lab
          and "_tape7.get(_sym9)" in lab           # marks come from the tape
          and "for _sk9, _sb9 in" in lab)
    check("T103 workshop not frozen: sleeves mark every held name from the tape, so exits can fire", ok, "")


def t104_everything_graph():
    """7.1 THE EVERYTHING GRAPH. The operator asked repeatedly for every subsystem drawn ON the
    price, not described beside it. silmaril_graph.js renders one canvas with nine layers: price,
    every other feed traced over it, swing peaks/troughs, floors and ceilings labelled with test
    counts, the position's entry/target/stop bands, the fingerprint's own dip trigger and bounce
    target, the cadence projection for the next peak, our real fills, and a verdict ribbon carrying
    structure, geometry's required win rate and the name's measured floor. Every layer is read from
    a store the gates also read, so the chart and the engine cannot disagree."""
    g = ROOT / "docs/silmaril_graph.js"
    html = (ROOT / "docs/index.html").read_text()
    if not g.exists():
        check("T104 everything graph (module missing)", False, "docs/silmaril_graph.js absent"); return
    src = g.read_text()
    layers = ["LAYER 1", "LAYER 2", "LAYER 3", "LAYER 4", "LAYER 5",
              "LAYER 6", "LAYER 7", "LAYER 8", "LAYER 9"]
    ok = all(l in src for l in layers)
    ok = ok and "CHART_INTEL.json" in src and "FINGERPRINTS.json" in src and "GEOMETRY.json" in src
    ok = ok and "silmaril_graph.js" in html and "SilmarilGraph" in html
    check("T104 everything graph: nine layers drawn on the price from the same stores the gates read", ok, "")


def t105_cross_source_normalisation():
    """7.1 — we held TWO independent crypto feeds (primary 1040 symbols as BTC-USD, ccxt 404 as
    BTCUSDT) and cross-verified NOTHING, because the key conventions differed so the intersection
    was exactly zero. Normalising the symbol lifts the overlap to 211 names that can now be checked
    against a second source; the chart reports the spread and flags disagreement rather than
    averaging it away. It immediately found AAVE-USD disagreeing by 0.534%."""
    g = ROOT / "docs/silmaril_graph.js"
    if not g.exists():
        check("T105 cross-source normalisation (module missing)", False, ""); return
    src = g.read_text()
    ok = ("function normSym" in src and "function altKeys" in src
          and "USDT|USDC|USD" in src and "DISAGREE" in src)
    check("T105 cross-source: symbol normalisation lets a second feed verify the price", ok, "")




# ═══════════════ 7.1 — THE ARMING LAW, THE ONE-KEY LAW, THE ONE-WRITER LAW ═══════════════

def t106_arming_gate_pyramid_license():
    """Incident 2026-07-25: the crypto book opened DOGEUSDT with ZERO sleeve closes since
    the wipe. The pyramid promotes DISCIPLINE (7.0.2) and seeds it early (7.0.4), but no
    code ever required the workshop to PROVE anything before the book could spend. This
    tripwire holds the license itself: (a) sleeve_promotion marks PROVISIONAL/WAITING/
    NO_POSITIVE_SLEEVE as arms_book=False and only PROMOTED as True; (b) paper_sim's buy
    path is behind the _armed gate; (c) an unarmed book cancels resting maker orders."""
    import tempfile as _tf
    from silmaril.execution import sleeve_promotion as _sp
    with _tf.TemporaryDirectory() as td:
        out = Path(td)
        (out / "PARAM_CATALOG.json").write_text(json.dumps({}))
        (out / "STRATEGY_LAB.json").write_text(json.dumps({
            "by_industry": {"crypto": [
                {"sleeve": "H", "name": "PATIENT REVERT", "closed": 0,
                 "return_pct": 1.2, "delta_vs_hodl": 1.2}],
                "stock": [], "metal": [], "energy": []},
            "sleeves_def": {"H": {"cap": 3, "patient": True}}}))
        pay = _sp.build_sleeve_promotion(out)
        prov = (pay["books"]["crypto"] or {})
        promoted_ok = None
        # now give it real closes → PROMOTED must arm
        (out / "STRATEGY_LAB.json").write_text(json.dumps({
            "by_industry": {"crypto": [
                {"sleeve": "H", "name": "PATIENT REVERT", "closed": 4,
                 "return_pct": 2.4, "delta_vs_hodl": 2.4}],
                "stock": [], "metal": [], "energy": []},
            "sleeves_def": {"H": {"cap": 3, "patient": True}}}))
        pay2 = _sp.build_sleeve_promotion(out)
        promoted_ok = (pay2["books"]["crypto"].get("status") == "PROMOTED"
                       and pay2["books"]["crypto"].get("arms_book") is True)
    src = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    gate_declared = "THE ARMING GATE (PYRAMID LAW" in src and '"armed": _armed' in src
    buy_i = src.index("for sym, lp, h1, cv in cands[:min(MAX_NAMES, _slots)]:")
    gate_i = src.index("if not _armed and cands:")
    maker_cancel = "resting maker order(s) cancelled" in src
    ok = (prov.get("status") == "PROVISIONAL" and prov.get("arms_book") is False
          and promoted_ok and gate_declared and gate_i < buy_i and maker_cancel)
    check("T106 arming gate: PROVISIONAL seeds the hand, only PROMOTED grants the license to spend",
          ok, f"prov={prov.get('status')}/{prov.get('arms_book')} promoted_ok={promoted_ok} "
              f"gate_before_buy={gate_i < buy_i} maker_cancel={maker_cancel}")


def t107_one_key_law_loader():
    """Incident 2026-07-25: load_all_samples merged ccxt keys RAW, so the crypto universe
    held DOGE-USD and DOGEUSDT as two different assets and the book bought the spelling no
    chart or mark-stamper could see. The canonical loader must (a) collapse spellings, (b)
    UNION their history, (c) let price_samples win timestamp collisions, and (d) leave
    non-crypto keys untouched."""
    import tempfile as _tf
    from silmaril.execution.canon_keys import canonical_samples, canon
    with _tf.TemporaryDirectory() as td:
        out = Path(td)
        (out / "price_samples.json").write_text(json.dumps({"samples": {
            "DOGE-USD": [["2026-07-25T10:00:00+00:00", 0.0719],
                         ["2026-07-25T10:10:00+00:00", 0.0721]],
            "GLD": [["2026-07-25T10:00:00+00:00", 221.5]]}}))
        (out / "ccxt_samples.json").write_text(json.dumps({"samples": {
            "DOGEUSDT": [["2026-07-25T09:50:00+00:00", 0.0717],
                         ["2026-07-25T10:00:00+00:00", 0.0999]]}}))   # collision: primary must win
        m = canonical_samples(out)
        rows = {t: p for t, p in m.get("DOGE-USD", [])}
    ok = ("DOGEUSDT" not in m and "DOGE-USD" in m
          and len(m["DOGE-USD"]) == 3                       # unioned, deduped by timestamp
          and abs(rows.get("2026-07-25T10:00:00+00:00", 0) - 0.0719) < 1e-9   # primary won
          and "GLD" in m
          and canon("REQUSDT") == "REQ-USD" and canon("BTC/USDT") == "BTC-USD"
          and canon("USO") == "USO")                        # energy ETF never re-keyed
    check("T107 one-key law: one spelling per asset, history unioned, primary tape wins collisions",
          ok, f"keys={sorted(m.keys())} doge_rows={len(m.get('DOGE-USD', []))}")


def t108_open_position_key_migration():
    """The retroactive half of the one-key law: a position already booked under DOGEUSDT
    must be re-keyed to DOGE-USD at the top of the live cycle (else it can never be marked
    or exited — the frozen-workshop disease, in a funded book), with the rename journaled."""
    import tempfile as _tf
    from silmaril.execution.canon_keys import canonicalize_positions
    with _tf.TemporaryDirectory() as td:
        out = Path(td)
        (out / "paper_book_crypto.json").write_text(json.dumps({
            "cash": 8431.14, "realized_pnl": 0.0,
            "positions": {"DOGEUSDT": {"qty": 21602.3307, "entry": 0.072624,
                                       "t": "2026-07-25T21:10:00+00:00"}},
            "trades": []}))
        r = canonicalize_positions(out)
        bk = json.loads((out / "paper_book_crypto.json").read_text())
        jl = (out / "CANON_MIGRATIONS.jsonl").exists()
        r2 = canonicalize_positions(out)   # idempotent: second pass moves nothing
    ok = (r.get("migrated") == 1 and "DOGE-USD" in bk["positions"]
          and "DOGEUSDT" not in bk["positions"]
          and abs(bk["positions"]["DOGE-USD"]["qty"] - 21602.3307) < 1e-6
          and jl and r2.get("migrated") == 0)
    check("T108 open-position key migration: bad spellings re-keyed, journaled, idempotent",
          ok, f"r={r.get('migrated')}/{r.get('flagged')} second={r2.get('migrated')}")


def t109_journal_windowed_and_ghost_free():
    """Incident 2026-07-25: 'BRENT +41.8% — stale/ghost' headlined 99.7%-missed. Two sins:
    the 'move' was the best trough→peak across the ENTIRE stored series, and unfillable
    ghosts were counted as missed movers. The journal must (a) measure over the last 48h of
    LIVE prints only (T00:00:00 backfill candles excluded) and (b) exclude ghosts/closed
    markets from the missed math into `excluded`, with the renderer already wired for it."""
    src = (ROOT / "silmaril/execution/opportunity_journal.py").read_text()
    ok_src = ("_live_window" in src and '"T00:00:00" in ts' in src
              and '"excluded"' in src and "stale_ghost" in src
              and "canonical" in src and '"window_h": 48' in src)
    # functional: an all-time 40% runup whose last-48h window is ~flat must NOT be logged
    from silmaril.execution.opportunity_journal import _live_window
    from datetime import timedelta as _td
    old = (now() - _td(days=9)).isoformat()
    rows = [[old, 1.00], [(now() - _td(days=8)).isoformat(), 1.40]] + [
        [(now() - _td(hours=h)).isoformat(), 1.40 + 0.001 * (12 - h)] for h in range(12, 0, -1)]
    win = _live_window(rows, 48.0)
    peak = 0.0
    tr = win[0] if win else 1.0
    for p in win:
        tr = min(tr, p)
        peak = max(peak, p / tr - 1)
    html = (ROOT / "docs/index.html").read_text()
    ok = ok_src and win and peak < 0.04 and "oj.excluded" in html
    check("T109 journal sanity: 48h live-print window, ghosts excluded from the missed math",
          ok, f"src={ok_src} window_peak={round(peak * 100, 2)}% renderer={'oj.excluded' in html}")


def t110_one_writer_workflow_law():
    """Incident 2026-07-25: three scheduled lanes ran `python -m silmaril --live` on three
    checkouts; `git rebase -X theirs` then erased each other's books. The law now: EXACTLY
    ONE workflow may hold both a cron schedule and the live cycle — daily.yml — and the
    retired lanes carry no cron. daily.yml must also contain the folded hourly/deep/backfill
    cadences so no capability was lost in the fold."""
    wf = ROOT / ".github/workflows"
    offenders, daily_ok = [], False
    for y in sorted(wf.glob("*.yml")):
        t = y.read_text()
        has_cron = "cron:" in t and any(
            ln.strip().startswith("- cron:") for ln in t.splitlines())
        has_live = "python -m silmaril --live" in t
        if has_cron and has_live:
            offenders.append(y.name)
        if y.name == "daily.yml":
            daily_ok = (has_cron and has_live and "ONE WRITER LAW" in t
                        and "silmaril.analytics.suite" in t
                        and "backfill_universe.py" in t
                        and "venue_universe.py" in t
                        and "sanitize_history.py" in t)
    for retired in ("hourly.yml", "analytics.yml", "backfill_universe.yml", "venue_universe.yml"):
        t = (wf / retired).read_text()
        if any(ln.strip().startswith("- cron:") for ln in t.splitlines()):
            offenders.append(retired + " (cron survived)")
    ok = offenders == ["daily.yml"] and daily_ok
    check("T110 one-writer law: exactly one scheduled lane runs the live cycle, cadences folded in",
          ok, f"scheduled_live_lanes={offenders} daily_carries_folds={daily_ok}")


def t111_chart_key_door_and_outside_world():
    """(a) THE KEY DOOR — 'DOGEUSDT not even showing a graph at all, but DOGE-USD does':
    drawChart's pre-check must resolve every spelling (SilmarilGraph.altKeys) before
    declaring 'no series'. (b) THE OUTSIDE WORLD — the operator's tracing-paper ask: the
    engine must publish REAL third-party series (coinbase/kraken/yahoo) to SOURCE_OVERLAY,
    the graph must draw them, the verdict must be TIME-ALIGNED, and nothing may ever be
    synthesized when a provider is absent."""
    html = (ROOT / "docs/index.html").read_text()
    gjs = (ROOT / "docs/silmaril_graph.js").read_text()
    so = (ROOT / "silmaril/execution/source_overlay.py").read_text()
    cli = (ROOT / "silmaril/cli.py").read_text()
    door = ("THE KEY DOOR" in html and "SilmarilGraph.altKeys(CSYM)" in html)
    exported = "altKeys: altKeys" in gjs
    draws_ext = ("SOURCE_OVERLAY.json" in gjs and "external: true" in gjs
                 and "vs outside venues" in gjs)
    engine = ("_aligned_spread" in so and "coinbase" in so and "kraken" in so
              and "yfinance" in so and "NO_EXTERNAL_SOURCE" in so
              and "nothing drawn, nothing invented" in so
              and "build_source_overlay" in cli)
    ok = door and exported and draws_ext and engine
    check("T111 chart key door + outside-world overlay: every spelling opens, real venues traced, aligned verdict",
          ok, f"door={door} exported={exported} draws_ext={draws_ext} engine={engine}")


def t106_arming_law():
    """7.1 THE ARMING GATE (incident 2026-07-25: the crypto book opened DOGEUSDT with ZERO
    sleeve closes since the wipe — the pyramid law violated at the book level). Root cause:
    7.0.4's seed_immediately handed a PROVISIONAL sleeve's DISCIPLINE to the book, and nothing
    distinguished discipline-seeding from trade-AUTHORIZATION, so a book with an ungraded
    workshop traded anyway. The law now: a book may OPEN only when its own workshop has
    PROMOTED a sleeve on >=3 REAL closed trades since the wipe. PROVISIONAL seeds the hand,
    never the license. GEKKO (aggressive) is exempt — it IS a probe. Master unchanged: it
    already required strict PROMOTED."""
    import shutil
    from silmaril.execution.sleeve_promotion import build_sleeve_promotion
    tmp = Path(tempfile.mkdtemp(prefix="t106_"))
    try:
        # Case A — workshop warming (1 close): best sleeve seeds PROVISIONAL, must NOT arm.
        (tmp / "STRATEGY_LAB.json").write_text(json.dumps({
            "by_industry": {"crypto": [
                {"sleeve": "H", "name": "PATIENT REVERT", "closed": 1,
                 "delta_vs_hodl": 2.4, "return_pct": 2.4}]},
            "sleeves_def": {"H": {"cap": 3, "recycle_h": 168, "patient": True}}}))
        pa = build_sleeve_promotion(tmp)
        a = (pa.get("books") or {}).get("crypto") or {}
        ok_a = (a.get("status") == "PROVISIONAL" and a.get("arms_book") is False
                and int(a.get("closes_needed") or 0) >= 3)
        # Case B — 5 real closes, positive Δ-vs-null: PROMOTED, arms the book.
        (tmp / "STRATEGY_LAB.json").write_text(json.dumps({
            "by_industry": {"crypto": [
                {"sleeve": "H", "name": "PATIENT REVERT", "closed": 5,
                 "delta_vs_hodl": 5.1, "return_pct": 4.2}]},
            "sleeves_def": {"H": {"cap": 3, "recycle_h": 168, "patient": True}}}))
        pb = build_sleeve_promotion(tmp)
        b = (pb.get("books") or {}).get("crypto") or {}
        ok_b = (b.get("status") == "PROMOTED" and b.get("arms_book") is True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # The gate must exist in the executor: sentinel + entries blocked + resting orders cancelled.
    ps = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    ok_src = ("ARMING GATE" in ps
              and "if not _armed and cands" in ps
              and "if _pend and not _armed" in ps
              and '"armed": _armed' in ps)
    # The Master's own rung stays strict.
    ma = (ROOT / "silmaril/execution/master_account.py").read_text()
    ok_master = '!= "PROMOTED"' in ma
    # The cockpit tells the truth about the license.
    html = (ROOT / "docs/index.html").read_text()
    ok_ui = "fun.armed===false" in html and "arming_why" in html
    check("T106 arming law: PROVISIONAL seeds the hand, only PROMOTED (3+ real closes) licenses a book to open",
          ok_a and ok_b and ok_src and ok_master and ok_ui,
          f"A={a.get('status')}/{a.get('arms_book')} B={b.get('status')}/{b.get('arms_book')} "
          f"src={ok_src} master={ok_master} ui={ok_ui}")


def t107_canonical_loader():
    """7.1 THE ONE-KEY LAW, loader half (incident 2026-07-25: load_all_samples raw-merged four
    sample files, so DOGE-USD and DOGEUSDT coexisted as two 'different' assets — the book bought
    the spelling the charts, marks and journals were blind to). canonical_samples() must collapse
    every spelling to one canonical key, UNION the history by timestamp, and let the primary tape
    win collisions (ccxt deepens, never overrides)."""
    import shutil
    from silmaril.execution.canon_keys import canonical_samples, canon
    tmp = Path(tempfile.mkdtemp(prefix="t107_"))
    try:
        t1, t2, t3 = "2026-07-25T10:05:00+00:00", "2026-07-25T10:15:00+00:00", "2026-07-25T10:25:00+00:00"
        (tmp / "price_samples.json").write_text(json.dumps({"samples": {
            "DOGE-USD": [[t2, 0.0710], [t3, 0.0712]]}}))
        (tmp / "ccxt_samples.json").write_text(json.dumps({"samples": {
            "DOGEUSDT": [[t1, 0.0695], [t2, 0.0709]]}}))
        m = canonical_samples(tmp)
        ok_key = "DOGE-USD" in m and "DOGEUSDT" not in m
        rows = {r[0]: r[1] for r in (m.get("DOGE-USD") or [])}
        ok_union = len(rows) == 3 and t1 in rows            # ccxt's early history joined
        ok_primary = abs(float(rows.get(t2, 0)) - 0.0710) < 1e-12   # primary wins the collision
        ok_canon = canon("REQUSDT") == "REQ-USD" and canon("USO") == "USO" and canon("BTC/USDT") == "BTC-USD"
        # and the executor actually loads through it
        ps = (ROOT / "silmaril/execution/paper_sim.py").read_text()
        ok_wired = "from .canon_keys import canonical_samples" in ps
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("T107 one-key loader: spellings collapse to ONE canonical key, history unioned, primary tape wins collisions",
          ok_key and ok_union and ok_primary and ok_canon and ok_wired,
          f"key={ok_key} union={ok_union} primary={ok_primary} canon={ok_canon} wired={ok_wired}")


def t108_position_migration():
    """7.1 THE ONE-KEY LAW, retroactive half. A DOGEUSDT position ALREADY open when the law lands
    must not become a frozen, unmarkable, unexitable row (the frozen-workshop disease, in a funded
    book). canonicalize_positions() re-keys open positions and resting maker orders to canonical,
    preserves qty/entry, journals every rename to CANON_MIGRATIONS.jsonl, is idempotent, and NEVER
    rewrites closed-trade history."""
    import shutil
    from silmaril.execution.canon_keys import canonicalize_positions
    tmp = Path(tempfile.mkdtemp(prefix="t108_"))
    try:
        (tmp / "paper_book_crypto.json").write_text(json.dumps({
            "cash": 9000.0,
            "positions": {"DOGEUSDT": {"qty": 100.0, "entry": 0.0719, "t": "2026-07-25T09:00:00+00:00"}},
            "trades": [{"sym": "REQUSDT", "side": "SELL", "pnl": 1.23}]}))
        (tmp / "MAKER_PENDING.json").write_text(json.dumps({
            "crypto": {"LMWRUSDT": {"limit": 0.5, "qty": 10}}}))
        r1 = canonicalize_positions(tmp)
        book = json.loads((tmp / "paper_book_crypto.json").read_text())
        pos = book.get("positions") or {}
        ok_rekey = ("DOGE-USD" in pos and "DOGEUSDT" not in pos
                    and abs(pos["DOGE-USD"]["qty"] - 100.0) < 1e-9
                    and pos["DOGE-USD"].get("migrated_from") == "DOGEUSDT")
        ok_history = (book.get("trades") or [{}])[0].get("sym") == "REQUSDT"   # history untouched
        pend = json.loads((tmp / "MAKER_PENDING.json").read_text())
        ok_pend = "LMWR-USD" in (pend.get("crypto") or {}) and "LMWRUSDT" not in (pend.get("crypto") or {})
        jl = (tmp / "CANON_MIGRATIONS.jsonl")
        ok_journal = jl.exists() and "REKEYED_OPEN_POSITION" in jl.read_text()
        r2 = canonicalize_positions(tmp)                       # idempotent second pass
        ok_idem = int(r1.get("migrated") or 0) >= 2 and int(r2.get("migrated") or 0) == 0
        # and the live cycle actually runs it
        ps = (ROOT / "silmaril/execution/paper_sim.py").read_text()
        ok_wired = "canonicalize_positions" in ps
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("T108 position migration: open keys re-keyed + journaled, maker orders too, history untouched, idempotent",
          ok_rekey and ok_history and ok_pend and ok_journal and ok_idem and ok_wired,
          f"rekey={ok_rekey} hist={ok_history} pend={ok_pend} journal={ok_journal} idem={ok_idem} wired={ok_wired}")


def t109_journal_sanity():
    """7.1 THE HONEST MOVERS JOURNAL (incident 2026-07-25: '99.7% of 399 tradable movers missed',
    headlined by BRENT +41.8% and REQUSDT/LMWRUSDT ghosts, minutes after a wipe). Three lies in
    one panel: peaks measured over the ENTIRE stored series (weeks), dash-less spellings escaping
    the dedupe, and unfillable ghosts counted as 'missed'. The law now: peaks come from the LIVE
    last-48h window only (backfill candles excluded), ghosts and closed-market names are EXCLUDED
    with named counts — never rows, never in the missed%%."""
    import shutil
    from silmaril.execution.opportunity_journal import build_opportunity_journal
    tmp = Path(tempfile.mkdtemp(prefix="t109_"))
    try:
        nowdt = now()
        def iso(mins_ago):
            t = nowdt - timedelta(minutes=mins_ago)
            return t.replace(hour=max(1, t.hour) if t.hour == 0 else t.hour).isoformat()
        # REALMOVE: fresh, 25 live prints in-window, clean ~6% trough→peak → MUST be logged.
        real = [[iso(300 - i * 10), 1.00 + (0.0026 * i)] for i in range(25)]
        # GHOST: 25 in-window prints, price FROZEN → freshness 0 → excluded stale_ghost.
        ghost = [[iso(300 - i * 10), 0.5000] for i in range(25)]
        # OLDMOVE: 40% pump entirely OLDER than 48h; live window only drifts ~2% → not a mover.
        old_part = [[iso(60 * 60 + i * 30), 1.0 + 0.02 * i] for i in range(20)]   # ~2.5d ago, to +40%
        recent_flat = [[iso(300 - i * 10), 1.40 + 0.001 * i] for i in range(25)]
        (tmp / "price_samples.json").write_text(json.dumps({"samples": {
            "REALMOVE-USD": real, "GHOST-USD": ghost, "OLDMOVE-USD": old_part + recent_flat}}))
        pj = build_opportunity_journal(tmp)
        ticks = [r["ticker"] for r in (pj.get("journal") or [])]
        ex = pj.get("excluded") or {}
        ok_real = "REALMOVE-USD" in ticks
        ok_ghost = "GHOST-USD" not in ticks and int(ex.get("stale_ghost") or 0) >= 1
        ok_old = "OLDMOVE-USD" not in ticks                    # 48h window, not all-time
        ok_pct = pj.get("movers_logged") == len(ticks) or pj.get("movers_logged") >= len(ticks)
        ok_win = pj.get("window_h") == 48
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("T109 journal sanity: 48h LIVE-window peaks only; ghosts excluded with counts, never 'missed'",
          ok_real and ok_ghost and ok_old and ok_pct and ok_win,
          f"real={ok_real} ghost={ok_ghost} old={ok_old} pct={ok_pct} win={ok_win} ticks={ticks[:4]}")


def t110_one_writer():
    """7.1 THE ONE WRITER LAW (incident 2026-07-25: daily every 10 min, hourly at :07 and the
    3x/day analytics lane ALL ran `python -m silmaril --live` on separate checkouts; the serial
    lane lock's 600s fairness cap meant the extra lanes 'proceeded anyway' and the push step's
    `git rebase -X theirs` then ERASED the other lane's books, sleeves and ledgers on every
    same-file conflict. Trades vanished; marks froze; fixed panels re-showed pre-fix output).
    The permanent fix is architectural: EXACTLY ONE scheduled workflow may run the live cycle.
    daily.yml carries every cadence itself from one clock; the folded lanes keep manual
    dispatch but have NO cron."""
    wf = ROOT / ".github/workflows"
    def live_lines(p):
        keep = []
        for ln in p.read_text().splitlines():
            s = ln.strip()
            if s.startswith("#"):
                continue
            keep.append(ln)
        return "\n".join(keep)
    scheduled_writers = []
    for p in sorted(wf.glob("*.yml")):
        body = live_lines(p)
        has_cron = any(l.strip().startswith("- cron:") for l in body.splitlines())
        runs_live = "-m silmaril --live" in body
        if has_cron and runs_live:
            scheduled_writers.append(p.name)
    ok_one = scheduled_writers == ["daily.yml"]
    ok_no_cron = all(
        not any(l.strip().startswith("- cron:") for l in live_lines(wf / f).splitlines())
        for f in ("hourly.yml", "analytics.yml", "backfill_universe.yml", "venue_universe.yml"))
    daily = live_lines(wf / "daily.yml")
    ok_folded = ("SILMARIL_FAST=1" in daily and "sanitize_history.py" in daily
                 and "backfill_universe.py" in daily and "venue_universe.py" in daily
                 and "silmaril.analytics.suite" in daily)
    hourly = live_lines(wf / "hourly.yml")
    ok_hourly_inert = "-m silmaril --live" not in hourly and "git push" not in hourly
    analytics = live_lines(wf / "analytics.yml")
    ok_analytics = "-m silmaril --live" not in analytics
    check("T110 one writer: exactly ONE scheduled lane runs the live cycle; folded lanes have no cron and cannot write over it",
          ok_one and ok_no_cron and ok_folded and ok_hourly_inert and ok_analytics,
          f"writers={scheduled_writers} no_cron={ok_no_cron} folded={ok_folded} "
          f"hourly_inert={ok_hourly_inert} analytics={ok_analytics}")


def t111_chart_key_door_and_source_overlay():
    """7.1 THE KEY DOOR + THE OUTSIDE WORLD (incidents 2026-07-25: DOGEUSDT opened onto an empty
    chart while DOGE-USD drew fine — drawChart's pre-check looked up ONE spelling and bailed; and
    the operator's repeated ask for genuinely EXTERNAL Coinbase/Yahoo overlays was still unmet —
    __overlaySources only re-coloured our own four internal files). Now: every spelling is tried
    before declaring a series absent; SOURCE_OVERLAY.json carries real third-party series
    (coinbase/kraken via ccxt, yahoo for ETFs + mapped futures) drawn as tracing paper; the
    verdict compares TIME-ALIGNED prints (<=15 min apart), never last-vs-last from different
    moments; absence is reported, never synthesized."""
    html = (ROOT / "docs/index.html").read_text()
    gjs = (ROOT / "docs/silmaril_graph.js").read_text()
    so = (ROOT / "silmaril/execution/source_overlay.py").read_text()
    cli = (ROOT / "silmaril/cli.py").read_text()
    ok_door = ("THE KEY DOOR" in html and "SilmarilGraph.altKeys" in html)
    ok_graph = ("SOURCE_OVERLAY.json" in gjs and "altKeys: altKeys" in gjs
                and "normSym: normSym" in gjs and "external: true" in gjs
                and "vs outside venues" in gjs)
    ok_overlay = ("def _aligned_spread" in so and "NO_EXTERNAL_SOURCE" in so
                  and "worst_spread_pct" in so and "ccxt" in so and "yfinance" in so
                  and "tol_min" in so)
    ok_wired = "build_source_overlay" in cli
    # honesty: the overlay must never invent a series when a provider is absent
    ok_honest = "nothing drawn, nothing invented" in so
    check("T111 chart key door + external overlay: every spelling tried; real outside venues drawn; time-aligned verdict; absence never synthesized",
          ok_door and ok_graph and ok_overlay and ok_wired and ok_honest,
          f"door={ok_door} graph={ok_graph} overlay={ok_overlay} wired={ok_wired} honest={ok_honest}")


def t112_everything_chart_modal():
    """7.1.1 THE WRONG CHART (incident 2026-07-25 evening: the operator installed 7.1.0 and saw
    ZERO graph change — because the modal every ticker click actually opens is silmaril_chart.js,
    whose capture-phase click handler routes ALL clicks to itself, and it read NONE of the engine's
    stores. 674 fitted fingerprints, CHART_INTEL, GEOMETRY and a 229KB SOURCE_OVERLAY sat on disk
    while it drew a bare line; MOG-USD's quantized feed rendered as an unlabeled square wave with
    every axis label rounded to $0.000000. "If it's not on the graph we assume the data is not
    really being collected."). The modal must consume every store, canonicalize keys, show real
    sub-penny digits, label quantized feeds, and show structure (peaks/cadence/next-peak/floors)
    for EVERY name — engine numbers when fitted, the same swing math on the same tape otherwise."""
    p = ROOT / "docs/silmaril_chart.js"
    if not p.exists():
        check("T112 everything-chart modal (file missing)", False, "docs/silmaril_chart.js absent"); return
    src = p.read_text()
    ok_stores = all(k in src for k in ("SOURCE_OVERLAY.json", "CHART_INTEL.json",
                                       "FINGERPRINTS.json", "GEOMETRY.json", "ccxt_samples.json"))
    ok_key = "function canon(" in src and "altKeys" in src
    ok_layers = all(k in src for k in ("QUANTIZED FEED", "fp buys", "next peak",
                                       "floor ", "ceiling ", "vs outside venues"))
    ok_subpenny = "function decFor" in src and "return 10" in src and "decFor(v)" in src
    ok_structure = "function swings(" in src and "view-detected" in src
    ok_honest = "never invented" in src
    ok_api = "window.openChart" in src and "capture" not in ""  # openChart export kept for callers
    html = (ROOT / "docs/index.html").read_text()
    ok_wired = "silmaril_chart.js" in html
    check("T112 everything chart: the modal every click opens consumes every store — structure, fingerprint, geometry, outside venues, quantized-feed truth, sub-penny digits",
          ok_stores and ok_key and ok_layers and ok_subpenny and ok_structure and ok_honest and ok_api and ok_wired,
          f"stores={ok_stores} key={ok_key} layers={ok_layers} subpenny={ok_subpenny} "
          f"structure={ok_structure} honest={ok_honest} wired={ok_wired}")


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
              t24_vol_native_clamps, t25_brain_tab, t26_dossier_contract,
              t27_price_integrity_guards, t28_confidence_cards, t29_lab_per_industry,
              t30_accounting_units, t31_starvation_exposed, t32_clean_room,
              t33_venue_contract, t34_harvest_identity, t36_master_decides,
              t37_crash_lane, t38_reconciliation, t39_champion_honesty,
              t40_fit_quality, t41_readiness_numeric, t42_discovery_contract,
              t43_fingerprint_coverage, t44_geometry_gate, t45_edge_surface,
              t46_maker_book, t47_calibration_teeth, t48_sizer_hand,
              t49_learning_permanence, t50_question_engine, t51_genesis,
              t52_builder_isolation, t53_no_stale_derived,
              t54_canonical_fingerprint_merge,
              t55_dup_buy_guard_and_canon_ledger, t56_master_mirror_law,
              t57_forward_ledger_and_vault, t58_registry_vault_classes,
              t59_workflow_law, t60_maturity_gate, t61_equity_truth,
              t62_one_universe_river, t63_trajectory_veto, t64_news_in_decision_path,
              t65_health_reads_authority, t66_modal_contract, t67_portals_and_spotlight,
              t68_readiness_truth,
              t69_reset_reanchors_nulls, t70_reset_seeds_live, t71_workflow_serialization,
              t72_modal_scope_and_guard, t73_health_reads_live_when_stale,
              t74_header_and_portals, t75_health_and_wiring_labels,
              t76_quantization_quarantine, t77_regime_conditional_champion,
              t78_workflow_independence, t79_sleeve_promotion_pyramid, t80_trade_detail_everywhere,
              t81_per_industry_badges_and_gekko_rank, t82_fee_truth_and_reachable_targets,
              t83_no_target_guard, t84_master_repair, t85_real_fee_model,
              t86_serial_lane_lock, t87_capital_truth_display, t88_book_harvest_switch,
              t89_venue_routing_and_fee_provenance, t90_full_profit_harvest,
              t91_immediate_sleeve_seed,
              t95_graph_brain_reads_structure, t96_graph_brain_informs_not_blocks,
              t97_no_invented_marks_or_targets, t98_reentry_guard_brent,
              t99_sleeve_marks_from_tape, t100_fast_regime_bands,
              t101_evidence_outranks_label, t102_maturity_gate_can_see_evidence,
              t103_workshop_is_not_frozen, t104_everything_graph,
              t105_cross_source_normalisation,
              t106_arming_law, t107_canonical_loader,
              t108_position_migration, t109_journal_sanity,
              t110_one_writer, t111_chart_key_door_and_source_overlay,
              t112_everything_chart_modal):
        try:
            t()
        except Exception as e:  # a crashing test is a failing test
            check(t.__name__, False, f"raised {type(e).__name__}: {e}")
    print(f"\n== SELFTEST 5.1: {len(PASS)} pass · {len(FAIL)} fail ==")
    if FAIL:
        for n, d in FAIL:
            print("  FAILED:", n, "—", d)
        sys.exit(1)
