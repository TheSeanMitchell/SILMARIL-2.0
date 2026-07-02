"""
FEATURE GATES — the judgment system the operator specified: every experimental signal starts in OBSERVE
(zero influence on decisions), accrues shadow evidence against reality, and is promoted to LIVE only when
FEATURE_GATES.json's rule is met by REAL forward data. Nothing unproven ever touches a trade.

Modes:
  observe — signal is computed + logged; influences NOTHING (default for everything unproven)
  shadow  — signal writes what it WOULD have done next to what actually happened (evidence accrual)
  live    — signal may influence decisions (only reachable by promotion rule, or manual edit of the json)

This module never flips a gate to live on its own guess: promotion requires min_samples of shadow evidence
AND the win condition in the config. Today every experimental gate correctly reports observe with n=0 —
news and Dr. Strange FAILED their earlier informal trials, so they restart from zero here, honestly.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

def _now(): return datetime.now(timezone.utc).isoformat()

DEFAULT_GATES = {
    "news_signals":   {"mode": "observe", "min_samples": 60,
                       "promote_rule": "shadow hit-rate beats coin-flip at p<0.05 over min_samples",
                       "evidence_file": "NEWS_TRIAL.json"},
    "dr_strange":     {"mode": "observe", "min_samples": 50,
                       "promote_rule": "projection direction beats baseline drift over min_samples",
                       "evidence_file": "DR_STRANGE_TRIAL.json"},
    "lifecycle":      {"mode": "observe", "min_samples": 50,
                       "promote_rule": "state-conditioned MR beats unconditioned MR net-of-fees",
                       "evidence_file": None},
    "fingerprint_weighting": {"mode": "observe", "min_samples": 50,
                       "promote_rule": "fingerprint-ranked entries out-earn conviction-ranked entries",
                       "evidence_file": None},
}

def build_feature_gates(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cfgp = out / "FEATURE_GATES.json"
    try:
        cfg = json.loads(cfgp.read_text())
    except Exception:
        cfg = dict(DEFAULT_GATES)
        cfgp.write_text(json.dumps(cfg, indent=1))
    status = {}
    for name, g in cfg.items():
        if not isinstance(g, dict):
            continue
        n = 0
        ev = g.get("evidence_file")
        if ev:
            try:
                led = json.loads((out / ev).read_text())
                n = len(led) if isinstance(led, list) else len(led.get("entries", []))
            except Exception:
                n = 0
        need = int(g.get("min_samples", 50))
        status[name] = {
            "mode": g.get("mode", "observe"),
            "evidence_n": n, "evidence_needed": need,
            "eligible_for_promotion": bool(n >= need and g.get("mode") == "shadow"),
            "promote_rule": g.get("promote_rule"),
            "influences_trading_today": g.get("mode") == "live",
        }
    payload = {"generated_at": _now(),
               "what": ("Every experimental signal and its gate. mode=observe means it influences NOTHING "
                        "until real shadow evidence clears the promotion rule — the operator's own spec: "
                        "no feature affects judgment before it proves it is edge, not noise."),
               "gates": status}
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "FEATURE_GATES_STATUS.json", payload)
    except Exception:
        (out / "FEATURE_GATES_STATUS.json").write_text(json.dumps(payload, indent=1))
    return payload
