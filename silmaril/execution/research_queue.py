"""
RESEARCH QUEUE (Movement V, Phase 27) — long-term hypothesis memory. Under-evidenced ideas LIVE and
WAIT with explicit wake conditions; auto-wake when their evidence bar is met. SURVIVES WIPES.
Seeded from the live feature gates; recheck runs every hourly pass.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def build_research_queue(out_dir):
    out = Path(out_dir)
    f = out / "RESEARCH_QUEUE.json"
    try:
        q = json.loads(f.read_text())
    except Exception:
        q = []
    try:
        gates = json.loads((out / "FEATURE_GATES_STATUS.json").read_text()).get("gates", {})
    except Exception:
        gates = {}
    byid = {h["id"]: h for h in q}
    for name, g in gates.items():
        h = byid.get(name)
        if not h:
            h = {"id": name, "created": datetime.now(timezone.utc).isoformat(),
                 "hypothesis": g.get("promote_rule"), "state": "SLEEPING"}
            q.append(h); byid[name] = h
        h["evidence_n"] = g.get("evidence_n", 0)
        h["wake_at_n"] = g.get("evidence_needed")
        if h["state"] == "SLEEPING" and h["evidence_n"] >= (h["wake_at_n"] or 10 ** 9):
            h["state"] = "AWAKE — enter shadow lifecycle"
            h["woke"] = datetime.now(timezone.utc).isoformat()
    f.write_text(json.dumps(q, indent=1))
    return q
