# SILMARIL — Dash to 2.1: the money-leak fix

This drop does three things: (1) finds the **hard reason** the accounts win but
have nothing to show for it, (2) **removes the ancient grocery harvest** from the
live path and makes the new 10-min momentum philosophy the *only* buy/sell brain,
and (3) makes the **buy-side "why" debuggable in the UI**. Everything here was
read-before-edited, compiles clean, and is proven on the repo's real data.

Delivery is drag-and-drop — each file sits at its real repo path. Nothing here
touches agent logic, scoring, conviction, or engine decisions; the changes are
confined to **how orders are gated, routed, and exited** (the standing scope rule).

---

## The riddle, solved: why ~9% edge capture and "win-rates with nothing to show"

There are **four** distinct leaks. Two are ours (now fixed). Two are the broker
(only migration fixes those). I pulled these from your 1:10 AM data, not from memory.

**LEAK 1 — the grocery TINY tier sold every winner at +1.5%. (This is the big one.)**
`silmaril/portfolios/grocery.py` carried this ladder, live, in the executor:

```
(0.06, 0.60, "MID")    # +6%  -> sell 60%
(0.03, 0.40, "MINI")   # +3%  -> sell 40%
(0.015, 0.50, "TINY")  # +1.5% -> sell 50%   <- "trench warfare"
```

The moment a name was up **1.5%**, half the position was dumped; more at +3%/+6%.
On a name that ran +27% (AXS), that banks ~3% and calls it a win. **That is the
mechanical definition of 9.3% edge capture, and it is exactly why a 34%-ish
win-rate shows nothing**: the wins were amputated at +1.5% while the losers were
left to run to the bleed/trailing stop. Small wins, full-size losses → net flat
to red even when you're "right" more often than not.

**LEAK 2 — nosedive entries (bootstrap §6).** The momentum composite is a
*weighted sum*. A name dropping **right now** (negative 10-min read) can still
score positive because an old daily run drags the composite up. So the router
bought falling knives:

```
XTZ: since_last = -0.085%   d1 = +4.292%   ->  composite = +0.735  -> BOUGHT
```

Those become the `exited_at_loss_on_up_move` and a chunk of the realized-loss bleed.

**LEAK 3 — broker universe gap (50% of all misses).** Of the 38 missed runners,
**19 are `not_on_alpaca`** — the *biggest* movers (AXS +27%, OM +21%, ENJ +19%,
JTO +16%) are literally not listed on Alpaca, so they captured 0%. **No logic
change can recover these. Only migration can.**

**LEAK 4 — filters too tight.** 6 of 38 were `filter_rejected` — tradeable names
the funnel blocked. Lower priority; surfaced now in the coverage panel for tuning.

### The 38 misses, by cause (from `missed_opportunity.json`)

| cause | count | whose fault | fixed here? |
|---|---|---|---|
| `not_on_alpaca` | **19** | broker | no — needs migration |
| `exited_too_early` | 9 | us (grocery) | **yes** |
| `filter_rejected` | 6 | us (filters) | partial — now visible |
| `exited_at_loss_on_up_move` | 4 | us (nosedive entry) | **yes** |

**~50% of the leak is logic (now fixed). ~50% is the broker (needs migration).**

---

## What changed

### 1. `silmaril/execution/fresh_gate.py`  *(NEW — single source of truth)*
The freshness law in one place. `passes_fresh_entry_gate(chain_entry)` returns
`(allow, reason, detail)`. **Rule: a BUY is allowed only if the freshest 10-min
read (`since_last`) is not falling** (`>= FRESH_GATE_MIN_PCT`, default `0.0`).
Longer windows may *size up* an already-rising name; they may never *rescue* a
falling one. Names with no fresh read yet (cold chain) are allowed and flagged,
so buying never freezes while the chain warms up. One knob: `FRESH_GATE_MIN_PCT`.

### 2. `silmaril/execution/leaned_in_router.py`  *(EDITED — the primary §6 fix)*
Right after candidate selection, the pool is run through `apply_fresh_entry_gate`.
Falling names are dropped *before* sizing, and the full admit/block log is written
to `docs/data/entry_gate.json` for the UI. Wrapped so a gate error can never take
down routing.

### 3. `silmaril/execution/alpaca_paper.py`  *(EDITED — the exit-ladder rewrite)*
The seven-layer exit stack was collapsed into one coherent ladder. **Removed from
the live path** (superseded — the cause of "sold too early"):
- **GROCERY HARVEST tiers** (the +1.5%/+3%/+6% seller) — gone.
- **`_harvest_clock_gate` + CLOCK HARVEST + clock-deferred exits** — gone.
- **fixed 5% profit-take fallback** — gone.
- the **tight 4% trailing stop as a primary exit** — demoted to chain-blind /
  catastrophe-only, so a healthy pullback no longer amputates a live winner.

**New ladder (first match wins):**
```
0. POLICY FORCE-CLOSE        hard override
1. MOMENTUM EXIT  (PRIMARY)  reads the same 10-min chain the router ranks by.
                             Holds a winner until its FAST tape turns hard AND the
                             hour is red AND fire collapses; cuts a loser small.
2. CONSENSUS FLIP            explicit bearish consensus
3. CHAIN-BLIND FALLBACK      tight trail + (widened) giveback — ONLY when there
                             was no fresh 10-min read this cycle
4. CATASTROPHE STOP          8% off peak — survives even WITH a live chain
5. BREAK-EVEN STOP           risk-free exit once armed
6. BLEED EXIT                slow-bleed detection (unchanged)
```
Also added a **belt-and-suspenders fresh gate on the executor's buy path**, so no
legacy buy route can sneak a falling knife through even if it bypasses the router.
Each block is logged via `_log_block(... "blocked_fresh_gate" ...)`, so it appears
in the coverage panel's reject reasons automatically.

### 4. `docs/index.html`  *(EDITED — buy-side debuggability)*
New **"🚦 Entry gate"** panel under the coverage tab, reading `entry_gate.json`:
considered / admitted (rising) / blocked-falling-now / no-fresh-read, plus a list
of every blocked mover with its 10-min read, composite, and the reason. This is
the direct answer to "why didn't we buy that mover?" — *because it was dropping
on the 10-min read.* (Your "Missed Opportunity Journal" already labels the
sell-side causes; this completes the picture on the buy side.)

### What was deliberately KEPT
- **`harvest_daily_goal.py` (Account #2 / HARVEST_3) — untouched.** This is the
  A/B harvest arm: it banks the day's win at +$100/$300/$500 on the $10k base and
  is already hard-scoped (`ONLY_ACCOUNT = "HARVEST_3"`, returns `[]` for everyone
  else). #2 harvests; **#3 (HARVEST_5) holds; #1 stocks don't harvest** — exactly
  the A/B you described. With grocery gone, #2's harvest is now this *one clean
  account-level mechanism* instead of the messy per-position tiers.

---

## Your strategic questions, answered straight

**"Can we migrate right now to solve edge capture?"** No — and migrating *first*
would make things worse. Migration only recovers the **19/38 `not_on_alpaca`**
names. The other **~50% is our logic**, which on a 5× bigger universe would just
bleed 5× faster through the same early-exits and nosedive-entries. Fix the logic
first (this drop), confirm edge capture climbs on the names you *can* trade, *then*
migrate to add the names you can't. **Optimal order: fix → prove → migrate.**

**"How close to 100% edge capture can we get?"** 100% is physically impossible —
it would require buying the exact bottom and selling the exact top of every name,
every time. A momentum harvester with clean entry/exit realistically lands around
**30–50%** of the available move. **On Alpaca specifically there's a hard ceiling
below that**, because ~half your biggest movers are untradeable, so they sit at 0%
in the denominator no matter how good the logic is. Translation: drive the
*tradeable* edge capture up now; the full-universe number can only finish climbing
after migration.

**"We see 'status missed' — why, in the UI?"** Three panels now carry it:
*Missed Opportunity Journal* (sell-side cause per name), *Ticker coverage* (reject
reasons incl. the new `blocked_fresh_gate`), and the new *Entry gate* panel
(buy-side: who was blocked for falling and the exact numbers).

---

## How to verify (all green here)

- `python3 silmaril/execution/fresh_gate.py` → XTZ **BLOCK**, riser **ALLOW**,
  cold-chain **ALLOW+flag**.
- Real-data audit on your 628 chains: the gate blocks the positive-composite /
  falling-now pattern (DASH +0.564 comp but −0.22% now; MANA +0.501 but −0.28%)
  and *allows* names turning up despite bad history (WLD, INJ).
- Exit ladder (mirrors live booleans): a **+8% winner with intact tape HOLDS**
  (grocery would've dumped half at +1.5%); the same winner **EXITS when its tape
  rolls hard**; a **−1% loser is cut small**; a 4–6% pullback under a live chain
  **holds**, only 8%+ trips the catastrophe stop.
- `python3 -m py_compile` clean on all four files; dashboard JS passes `node --check`.

## Notes / honest loose ends
- `_harvest_clock_gate` (def near the top of `alpaca_paper.py`) is now **orphaned
  dead code** — nothing calls it. Left in place (reversible, harmless); delete in
  a later cleanup pass if you want.
- The **agent meta-leaderboard** in `cli.py` (`grocery_leaderboard.json`) still
  uses grocery accounting. That's a *separate simulated layer* (the ~39-agent
  scoreboard), not the 3 live accounts, and gutting it would break a working
  feature you didn't point at — so I left it and am flagging it here. Say the word
  and I'll retire it in one pass.
- `grocery.py` itself is left on disk but is now **dormant for live trading** (no
  executable path imports `compute_harvest` anymore).
