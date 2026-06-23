"""
silmaril.execution.atomic_io — atomic JSON writes + a run lock (2.5 hardening).

write_json_atomic(): writes to a temp file in the same dir, fsyncs, then os.replace
(atomic on POSIX). A run killed mid-write can never leave a half-written/corrupt
JSON — readers either see the old file or the new one, never a torn one. This is
the protection behind "if the leaderboard is corrupt, do not deploy."

run_lock(): a context manager around a lock file so two cycles can't mutate state
at once (belt-and-suspenders with the GitHub `concurrency` group). Stale locks
(older than ttl) are reclaimed so a crashed run can't wedge the system forever.
"""
from __future__ import annotations
import json, os, time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

def write_json_atomic(path, obj: Any, indent: int = 2) -> bool:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w") as f:
            json.dump(obj, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)            # atomic swap
        return True
    except Exception:
        try:
            if tmp.exists(): tmp.unlink()
        except Exception:
            pass
        # last-resort non-atomic fallback so we never silently lose data
        try:
            p.write_text(json.dumps(obj, indent=indent)); return True
        except Exception:
            return False

@contextmanager
def run_lock(lock_path, ttl_sec: int = 1800):
    """Acquire an advisory lock; reclaim if older than ttl. Yields True if acquired,
    False if a fresh lock is already held (caller should skip the run)."""
    lp = Path(lock_path)
    held = False
    try:
        if lp.exists():
            try:
                age = time.time() - lp.stat().st_mtime
            except Exception:
                age = ttl_sec + 1
            if age < ttl_sec:
                yield False
                return
        try:
            lp.parent.mkdir(parents=True, exist_ok=True)
            lp.write_text(f"{os.getpid()} {time.time()}")
            held = True
        except Exception:
            pass
        yield True
    finally:
        if held:
            try: lp.unlink()
            except Exception: pass
