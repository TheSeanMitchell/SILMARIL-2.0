# SILMARIL 9 — THE HEADLINE TEST — REGISTRATION

headline-rules-hash: ef1453ae2a6bc6ed

Frozen on 8 November 2026, before the first headline was scored. `ladder/headlines.py`
holds the same rules (`HEADLINE_RULES`); `scripts/test_ladder.py` fails if the two disagree.

**Watch-only.** This test never places, changes or blocks a trade. The trading rules and
their fingerprint (`d6ebfac647c082b8`, REGISTRATION_9.md) are untouched by it.

## The two questions

1. **DIRECTION.** Does a week of headline tone call the next week's direction?
2. **WARNING.** Does a surge in headline volume come before an unusually big move?

## How headlines are read

* Source: Google News RSS search (en-US, last 24 hours), once a day with the ladder run.
* One search per category:
  * crypto: `bitcoin OR ethereum OR crypto`
  * stocks: `"stock market" OR Nasdaq OR "S&P 500" OR "Wall Street"`
  * metals: `"gold price" OR "silver price" OR "gold prices"`
  * energy: `"oil price" OR "oil prices" OR crude OR OPEC OR "Middle East"`
* Each headline counts once, on the day it is first seen (the publisher name is stripped,
  so the same story from two outlets counts once).
* Score: +1 if a headline has an "up" word and no "down" word, −1 the reverse, else 0.
  Energy adds supply words: sanctions, conflict, war, attack, escalation, disruption,
  outage, blockade, tensions, cuts count as up for oil; ceasefire, truce, peace, glut,
  oversupply, surplus count as down. Full word lists are in `HEADLINE_RULES`.

## The weekly call

* Weeks run Monday to Sunday (UTC). On the first run of a new week, each category's tone is
  (up − down) ÷ all headlines over the previous 7 days.
* Tone ≥ +0.10 calls **UP**, ≤ −0.10 calls **DOWN**, otherwise no call. A week with fewer
  than 4 days of headlines makes no call.
* **Surge:** the week's headline count is at least twice the median of the previous 8 weeks
  (needs 4 earlier weeks).

## Grading (no lookahead)

* From the first market close **after** the headlines were read, over the next 5 closes.
* DIRECTION: the category basket (50/50 of its two assets) minus T-bills, signed by the call.
  A hit is a positive signed result.
* WARNING: the basket's absolute 5-close move divided by its median absolute 5-close move
  over the prior 252 closes.

## Pass and kill, stated before the data

| test | pass | kill |
|---|---|---|
| DIRECTION | 100+ graded calls, hit rate z ≥ 2.5 against a coin flip, **and** the average signed excess return ≥ +0.5% per call | 100+ calls and z ≤ 0.5 |
| WARNING | 30+ surges, next-week move averages ≥ 1.5× normal, t ≥ 2.5 | 30+ surges and the move is not bigger than normal on average |

Expect about a year before either test can pass or fail: four categories a week, and many
weeks will not be loud enough to make a call. A pass earns a conversation about a
re-registration. It never becomes an automatic trade.
