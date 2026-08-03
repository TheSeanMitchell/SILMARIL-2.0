# SILMARIL 7.2.3 — "MAKING A WIN STAY A WIN"
### STOCK:E audited trade-by-trade. The $438 is not $438. The harvest system you asked for. And the arm bug that was bleeding 84 trades.

**Battery: 126/126** on the full tree, a reset tree, and a simulated install over your 10 AM backup. Click path 9/9.

---

## 1 · IS STOCK:E's +$438 REAL? — audited every trade against the tape

I checked all nine closed trades and all four open positions. **The sleeve itself is clean.** Every closed net% agrees with its own entry→exit, the sum of closed P&L equals the stored realized figure exactly, and the capital identity balances to the cent:

```
cash 176.42 + positions 9,926.40 + vault 0.00 - realized 102.83  =  10,000.00 ✓
```

**But the $438 is not $438:**

| | |
|---|---|
| realized (banked, fee-paid) | **+$102.83** ← this is money |
| unrealized (4 open marks) | **+$335.57** ← this is not money yet |
| headline | +$438.40 |

Its four positions verified against the tape: BSX +8.01% (peak 8.08%), DXCM +5.00% (peak 5.22%), WDAY −1.21%, XLF −0.23%.

**And to your direct question — trail milking, or bugged and holding out?** BSX peaked 8.08% and sits at 8.01%; the give-back cap would exit it at 6.06%. DXCM peaked 5.22%, sits at 5.00%, cap at 3.92%. **They are riding correctly, and the peaks are recorded.** Not bugged, not wishful — trailing exactly as designed.

## 2 · EVERY EXIT TAG, GRADED — they are working

378 closed trades graded against the tape:

| tag | n | mean got | mean peak | gave back | win% |
|---|---|---|---|---|---|
| RIDE_TRAIL | 27 | **+3.59%** | +5.52% | 1.93% | **100%** |
| TARGET | 23 | **+3.58%** | +4.41% | 0.83% | **100%** |
| **CEILING_READ** | 6 | **+3.37%** | +3.82% | **0.45%** | **100%** |
| GIVEBACK_CAP | 71 | **+2.39%** | +4.14% | 1.76% | **100%** |
| RECYCLE_FLAT | 84 | −0.11% | +1.96% | **2.07%** | 48% |
| BREAKEVEN_LOCK | 4 | −1.11% | +3.54% | 4.65% | 25% |
| STOP | 163 | −3.87% | +0.52% | 4.39% | 0% |

**All four profit-taking tags are 100% win rate.** CEILING_READ — the graph-reading exit — gives back the least of anything in the system. Your floor/ceiling recognition is genuinely working; it is not a broken graph and you are not misreading it.

## 3 · THE BUG THIS AUDIT FOUND — the arm never scaled

**RECYCLE_FLAT: 84 trades, mean peak +1.96%, exit −0.11%.** Look at that peak figure against the give-back governor's arm of **2.0% flat**. Those positions peaked *just under the arm* and were then recycled flat. A position with a 1% target could **never** be protected — it cannot reach a 2% arm before hitting its own goal.

Re-swept across all 378 real closed trades, arming at **40% of the position's own target** (capped at 2.0%):

```
flat 2.0% arm (7.1.9)     -275.4%   168 winners
arm = target x 0.40       -138.1%   211 winners     +137.3 points, +43 winners
```

Same trades, same give-back fraction. Only the arm changed. This is the single largest measured improvement in the project so far, and it came from asking why one tag underperformed rather than from adding anything.

## 4 · THE HARVEST SYSTEM — `harvest.py`

Your ask: *"when accounts get to a checkpoint they know we hit a monthly goal, pocket the profit, balance back to 10k, harvest into something un-spendable."*

**Why previous attempts slid back to $10k:** the gain was never banked in the first place. There was nothing to protect. So the rule is absolute — **harvest banks REALIZED profit only.** Sweeping stock:E's $438 would put $335 in the vault that was never earned, and this project has watched marks evaporate 24 times.

**The vault is non-spendable by construction:** `_avail()` returns `cash`, and harvest moves money `cash → vault_usd`. No path in the engine spends the vault. A harvested dollar cannot be re-risked.

Two modes:
- **`bank_realized`** (default) — checkpoint met on banked profit → sweep, working capital returns toward $10k, open positions keep running.
- **`realize_and_bank`** (opt-in) — total profit crosses the checkpoint but realized alone doesn't → close the winners comfortably above cost, converting marks into money, then sweep. **This is what you mean by "take it off the table,"** and its honest price is the remaining upside on those names. It never closes a loser to manufacture a number.

Checkpoint defaults to 3% of starting equity ($300), cooldown-guarded so a book can't churn its own vault, knob-gated, killable. Running it on your tree right now:

```
total already vaulted: $894.02
stock:E   realized +102.83  unrealized +335.58  -> "only 102.83 is REAL — below the 300 checkpoint"
crypto:R  realized +260.92  unrealized  +68.52  -> below checkpoint on banked money
metal:B   realized +145.91                      -> below checkpoint
```

**So: no, you cannot call stock:E a $438 month yet.** You can call it **+$102.83 banked and $335 still at risk** — and if you want it certain today, set `harvest.mode: "realize_and_bank"` and it will close BSX and DXCM into the vault.

## 5 · THE M FLOOR ARTIST CONFUSION — solved

The Strategy tab and the portal disagree because **they sort by different columns**:

```
CRYPTO  by headline (equity):  I +0.88%, M +0.23%, L -0.43%
        by REALIZED (Law 1):   T +2.80%, R +2.61%, S +0.49%
STOCK   by headline (equity):  E +4.38%, M +3.04%, K +0.98%
        by REALIZED (Law 1):   E +1.03%, K +0.98%, A +0.07%
```

M looks best by headline because it carries large unrealized marks. **On banked money the crypto leaders are T, R and S — the three graph readers.** Every row now publishes `realized_pct`, `unrealized_pct` and `realized_usd` so the split is visible everywhere.

## 6 · THE $26,130 STILL SITTING IN YOUR BOOKS

The 7.2.2 repair was never run. Crypto R/S/T still carry the frozen leak damage — **exactly $26,130.39, identical to yesterday's figure.** That is the good news: my 7.2.2 fix held and nothing is still leaking. But those books show headlines of −64% and −96% against positive realized until you repair them.

**Run this once after installing:**
```
python scripts/repair_capital_leak.py docs/data --apply
```
Verified on your tree: $26,130.38 restored, then **0 broken identities across all 80 books** after a further live cycle.

## 7 · A PATH FORWARD ON BUGS — what I actually recommend

You asked how to avoid more of these. Here is the honest pattern from the last ten releases: **every one of my bugs has been a wiring or arithmetic-scope error, never a logic error.** The graph never reaching decisions; readers never reaching candidates; cash never reaching a position; an arm that could never be reached. Unit tests are structurally poor at all four, which is why 125 of them stayed green through every one.

Three things that would change the rate, in order of value:

1. **The INSPECTOR is the mechanism** — it reads the *record*, not the laws, and it caught the capital leak from the outside on its first run. Read `INSPECTOR.json` daily; its verdict line is `CLEAN` or `ATTENTION — N`.
2. **Two invariants now exist that would have caught most of it**: capital conservation (T129) and realized-vs-headline (published on every row). Add one every time we find a class of failure, not one per bug.
3. **Fit parameters on the record, don't guess them.** The arm change was worth +137 points and cost one sweep over data we already had. My guesses have been wrong twice now in ways that measurement caught immediately.

**On going live next week: I would not.** Not because the engine is unsafe — the fill laws, calendar, capital conservation and quarantine are all in place — but because the books are still net negative on realized money and the graph readers have 20 closed trades between them. The bar you set was 100 out-of-sample trades over 90 unbroken days, and you are at day ~7. Going live now would be trading the one thing you have left to spend, which is time, for the one thing you already know, which is that the edge is unproven.

---

## INSTALL (5 files + report)

```
silmaril/execution/harvest.py         (NEW)   silmaril/execution/strategy_lab_abcd.py
silmaril/cli.py                               scripts/selftest_5_1.py
scripts/repair_capital_leak.py                SILMARIL_7_2_3_RELEASE_REPORT.md (root)
```

**Then run once:** `python scripts/repair_capital_leak.py docs/data --apply`

To take stock:E off the table today, set `PARAM_CATALOG.harvest.mode = "realize_and_bank"`.

## THE HONESTY CAVEAT

The good news is real: your exit tags all work, CEILING_READ is the most disciplined thing in the system, the trail is genuinely milking winners rather than hoping, and the arm fix is worth +137 points on data you already have.

The rest is unchanged. Realized P&L across the workshop is still negative, 163 of 378 closes are stops, and the four positions carrying stock:E's headline can still give it all back before Monday's close. **$102.83 is the number. Everything above it is weather.**
