# SILMARIL 7.0.1 — THE CASCADE REPAIR
*Diagnosed against your July-17 5 AM tree. Battery 52/52.*

## The verdict: your engine was never broken. It was ASLEEP — plus one real bug that was mine.

### 1 · The short daily run + everything "STARVED" = the wipe timer, working
`QUIET_AFTER_WIPE_MIN = 120.0`. You wiped at **10:38**; your 12:05 run was **87 minutes in — 33 minutes still to go.** `marks_health.state` said it plainly: *"QUIET after wipe — 32 min left (by design)."* During the quiet window the engine marks the tape but takes no action: that is `seen=0`, `dep 0/7 STARVED`, and a 3-minute run instead of 12. **It self-healed at 12:38.** Not a bug — the clean-room guard you asked for, doing its job.

### 2 · THE REAL BUG — a cascade I introduced in 5.3 (my fault, root-caused, repaired)
`parameter_registry.build_parameter_registry` raised **`TypeError: _entry() missing 1 required positional argument: 'source'`** on every single cycle since 5.3.

**Root cause with receipts:** my 5.3 Hold-timer patch appended a `#` comment onto a line that was *mid-argument-list*:
```python
"Hold-timer",  # 5.3: the hold IS the rhythm now ("rhythm-hold: ..." if (opt is None and cryp) else ...),
```
The comment **swallowed the champion argument.** `_entry()` lost its last positional and raised.

**Why that cost you eight builders:** those calls were semicolon-chained inside ONE try-block:
```python
_tor = _to(out); _cor = _co(out); _tcr = _tc(out); _pregr = _preg(out); _cmp(out); _djent = _djr(out)
```
When `_preg` raised, `_cmp` and `_djr` died on the same line — and the outer `except` swallowed it, so the **entire next block never ran**: session_reconstruction · session_anatomy · **crypto_concentration** · reality_check · champion_timeline.

**That is your +$71.60 ghost** (concentration frozen at July-16), your empty Forensics session/anatomy, and a chunk of the missing run time.

**Fixed:** argument restored, comment on its own line, and **all 12 hourly builders now run isolated** — a failure names itself in the log and costs nothing else. **T52** asserts both forever.

### 3 · The stale-DERIVED sweep — and it caught 14 ghosts
Any DERIVED store older than `WIPE_MARKER` is now deleted before the builders run, so a crashed builder shows *pending* instead of yesterday's number wearing today's clothes. First run swept **14**, including `CHAMPION_STATUS` (June 22!), `capital_allocation` (July 1), `verified_harvest_ledger`, and all four `strategy_leaderboard_holds`. Live stores dropped **191.6 MB → 166.8 MB**. **T53** fails the battery if one ever survives again.

### 4 · "crypto 91 listed" was a panel lie, not an engine failure
The engine marks from **four** sample stores (price + ccxt + metals + energy) — `marks_health.marked = **886**`. The census counted `price_samples.json` alone, so after genesis it read 91 while the engine saw 886. **Census now counts exactly what the engine sees.**

### 5 · Heatshield "has stats with no trades" — correct, now labeled
It is a **what-if simulation over the recorded tape**, not your book. It needs price history, not fills, so it populates from cycle one. The panel now says so in bold.

### 6 · Cosmetics: SPINE header 5.1 → **7.0** · readiness bar legible (absolute label, text-shadow halo, 34px)

## After the fix, on your tree
```
52/52 battery · reconciliation ALL GREEN (7 checks) · brain 25/25 wired+fresh
concentration $0 (ghost gone) · questions TOWARD-EDGE · 9✓ 4~ 0✗
sizer GREEN ×1.0 · retention 274 stores 166.8MB · archive 3 files 3.25MB
```

## Expect this (and don't panic)
`geometry: 0 tradeable · 2 geo-locked · 4 evidence-short` — GENESIS wiped the tape, so only metals/energy have fingerprints yet, and those are exactly the unwinnable ones (XAU needs 98.4% wins). **As crypto/stock fingerprints rebuild over the next days, TRADEABLE climbs off zero.** The gate is working: it refuses to trade what it cannot yet prove.
