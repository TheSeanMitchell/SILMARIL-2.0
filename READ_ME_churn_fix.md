# SILMARIL — strategy change: stop the churn (re-entry cooldown + hourly confirmation)

This is the first change to **what the engine buys and when** — not plumbing.
Two files, drop on the repo root. Both compile clean and are proven on your
12:40 PM data. They carry every prior fix, so this is a complete drop.

## What changed and why

The thing you kept watching — buy XTZ, sell XTZ at a loss, re-buy XTZ next run —
has two direct causes, and this fixes both:

### 1. Re-entry cooldown  (`alpaca_paper.py`)
After any position is CLOSED, that name is **stamped** and the buy path will not
re-open it for **45 minutes** (`REENTRY_COOLDOWN_MIN`). A freshly-dumped coin
keeps reading "green" on the next 10-min snapshot and was getting re-bought
immediately, round-tripping into losses. Now it has to settle first.
- Proven: with XTZ closed 12 min ago, the re-buy is blocked. The loop is broken.
- Keyed canonically (XTZ-USD == XTZUSD == XTZ/USD).

### 2. Hourly confirmation  (`fresh_gate.py`)
A name green on the 10-min read is now **still blocked** if the hour is in a clear
downtrend (`h1 < CONFIRM_H1_FLOOR`, default −0.5%). A fresh spike inside a falling
hour is the classic dead-cat bounce: you buy it, it reverts on the next read, you
sell the bottom.
- Proven on your chain: 7 names that *would* have passed are now blocked —
  AXS (+0.17% / hour −2.21%), MANA, WLD, ZEC, ETC, REZ, BK. Those are the
  spike-into-downtrend entries.
- Conservative: only blocks when the hour is meaningfully red, so flat/mixed
  hours still pass. It targets the revert pattern, not normal noise.

## The knobs (tune these on your real data)
- `REENTRY_COOLDOWN_MIN` (alpaca_paper.py) — raise to trade the same name less
  often; lower to allow faster re-entry.
- `CONFIRM_H1_FLOOR` (fresh_gate.py) — make more negative to block fewer names
  (looser), closer to 0 to demand a cleaner hour (stricter).
- `REQUIRE_HOUR_CONFIRM = False` turns confirmation off entirely.

## What this does and does not do — straight
These two changes will **visibly change behavior on the next run**: the same-coin
churn stops, and the worst spike-into-downtrend entries get rejected. That removes
a real chunk of the *self-inflicted* losses.

They do **not** manufacture edge. Your dashboard still shows the entry signal is
near-random (sentiment↔return r≈0.03; 85% of strong-positive names fell). These
changes stop the bleeding from buying tops and re-buying dumps; they do not by
themselves make the signal predictive. The next levers, in order, are: require
rising volume on entry, hold for the confirmed trend instead of round-tripping,
and de-weight news in favor of the catalysts that actually paid (IPOs +1.84%).
I'll do those next if the churn fix shows up clean in the fills.

## Verify after deploy
- Next crypto run: the log should show `blocked_reentry_cooldown` on names just
  closed, and `CONFIRM BLOCK` on fresh spikes inside hourly downtrends — instead
  of immediately re-buying them.
- Watch whether the round-trip count drops and the same 4–5 coins stop cycling.
