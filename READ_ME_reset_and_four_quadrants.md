# SILMARIL 2.5.1 — Pristine reset fix + four equal quadrants (+ clock, health, audit)

Drop on repo root. This fixes the two things you actually couldn't see.

## 1. The pristine reset now resets the four internal books (it didn't before)
You were right. `scripts/pristine_reset.py` only reset the Alpaca-style account
ledgers — it never touched `paper_book_crypto/stock/metal/energy.json` or
`paper_sim_live.json`. So your four internal books never went back to $10k.

Fixed: the reset now zeroes all four books (and the arena books) to a clean $10k,
and rewrites `paper_sim_live.json` so the UI immediately shows four clean $10,000
books. Verified: after reset, crypto/stock/metal/energy all read $10,000, combined
$40,000, zero open. Run "Pristine Reset" again and you'll see the clean slate.

## 2. Four equal, color-coded quadrants (were muted/buried)
The quadrant code was installed but metal/energy rendered at 45% opacity in a 2-column
grid — easy to miss, and not what you asked for. Now: a 4-up grid (2×2 on phone),
all four EQUAL, none muted, color-coded — CRYPTO amber, STOCKS blue, METALS silver,
ENERGY green. Each shows equity (starting $10k), return, open positions, champion, and
status ("TRADING" / "READY · awaiting data feed"). All four start at $10k and run
side by side, exactly as you described.

## 3. Bonus (you'd asked): Vegas market clock + health footer
- Top banner: live Las Vegas time + NYSE status with open/close countdown.
- Footer: project-health line (last run + age, books live, feeds, data-source note).

## Honest self-audit — what's real vs what I'd overclaimed
Engines built AND surfaced on the dashboard: Scorecard, Opportunity Audit, Exit
Forensics (+expansion), Stock Recovery, Regime Observer, four-book separation. Those
are genuinely there and visible.

Where I fell short and you were right to call it:
- The four-quadrant view was technically present but muted/buried — fixed here.
- The pristine reset didn't reset the internal books — fixed here.
- Performance Audit writes JSON but has no UI panel yet (data exists, not shown).
- Health footer + market clock were requested earlier and only now added.
- Metals/energy: architecture + feed are in, but no trades yet because the free
  metal/energy feeds are daily-cadence and need samples to accumulate — that's data
  latency, not missing code. The books are real and will fill.

## Your endgame vision (regime playoff / capital rotation) — acknowledged, scoped
What you described — every daily run: score each regime's health, vote on which
regime+champion is most likely to profit given volatility, then concentrate the single
$10k into that one regime/champion, rotating daily; each regime running ~1000
strategy simulations to pick the best recent performer — makes complete sense, and the
foundation for it now exists: four independent arenas, four champions, a regime
observer, survivability scoring, and a scorecard.

It is also a large, multi-build system, and the directives are explicit about not
building ahead of evidence. The honest path: it needs (a) the regime observer to
accumulate enough tagged trades to show regime prediction actually works, and (b) a
"regime+champion selector" that allocates the book to the best-scoring regime each
run. That selector is the natural NEXT major build once metals/energy have data and
the regime tags have a track record. I did not stub it with fake logic. When you're
ready, that's the one to commission as its own phase — and I'd want a clean week of
four-book data first so it's choosing on evidence, not noise.

## News/authority underutilization
Your instinct is fair — the authority/news engine collects events but is research-only
by mandate (it never trades). "Underutilized for prediction" is true by design: it
hasn't earned trading rights via measured forward signal. The way to use it is the
same gate as everything else — let authority_validation accumulate forward returns
until an authority/theme shows a real edge, then it graduates. Worth a dedicated
"does news predict?" measurement pass in a future round.

## Runtime note
You're back on 10-min runs. With four books + stocks, cycles may lengthen again; the
`silmaril-state` concurrency group means an overrun just queues the next run (no
corruption), but if runs routinely exceed 10 min, 15 gives breathing room.
