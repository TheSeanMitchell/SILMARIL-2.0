# STEWARD — THE REGISTRATION

registration-hash: cd5feead39c46f3b

This document and `steward/config.py` describe the same frozen experiment. The hash
above is the SHA-256 (first 16 hex) of the canonical parameters; `scripts/test_steward.py`
fails CI if the two ever disagree. **Editing a parameter is a re-registration event**:
new hash, new epoch, every clock restarts. There is no such thing as a quiet tweak.

Registered before forward data, 19 August 2026.

---

## 1. What is being tested, and why this family

**Long-only time-series momentum rotation, monthly.** Eight liquid proxies in four
classes — BTC-USD/ETH-USD, SPY/QQQ, GLD/SLV, XLE/USO. Each class book holds its
stronger asset or cash; the ROTATOR book holds the top 2 of all 8 or cash. Signal:
mean of 21/63/126-bar returns. Absolute gate at +1.11% blended (cash yield): below
it, cash IS the position. Hysteresis 1%: an incumbent is evicted only by a
decisively better challenger.

**Why this family and no other.** Three independent lines point the same way:

1. *Arithmetic.* The round trip costs 0.4–0.6% and is non-negotiable at retail. At
   the registered cadence (≤ ~24 fills per book-year, hysteresis usually fewer) the
   cost drag is ≤ ~1.5%/yr. The retired system's fastest sleeve paid the toll 23.6
   times a DAY — a ~4,700%/yr drag hunted with a signal measured at 0.0%.
2. *External evidence.* Time-series momentum is the most robustly documented
   anomaly retail can implement at monthly cadence (Moskowitz–Ooi–Pedersen 2012;
   AQR "A Century of Evidence on Trend-Following", 1880–present; Antonacci's dual
   momentum), chosen from that literature — not mined from our own tape.
3. *Our own tape.* In the audited 16-day window, buy-and-hold beat all 80 sleeves
   in every book, and the only sleeves in profit after honest fees were the ones
   that traded least and held longest. Every honest signal pointed slow.

## 2. Execution law

Signal at completed bar D → fill at the close of the FIRST bar strictly after D.
Partial same-day bars are dropped. Entry pays half the round trip, exit the other
half, from the first line ever run. Prices are raw closes in an append-only store;
dividends are ignored (a small drag AGAINST the equity books — the safe direction).

**Asymmetric cadence — fast out, slow in.** ENTRIES happen only at the monthly
seam (first run whose newest bar lands in a new calendar month). EXITS are checked
every run: the day a held asset's blended score falls through the absolute gate,
its sell is queued. This was sized on the warmup tape — where silver crashed 52%
and a monthly-only exit sat through half of it waiting for the calendar — and is
disclosed here as a design decision made before the forward epoch.

## 3. The primary hypothesis (the only funded one)

> Monthly blended-momentum rotation with an absolute gate beats buy-and-hold of
> each book's benchmark, net of registered costs.

* **Horizon:** 104 weeks from epoch.
* **Pass:** delta-vs-hold > $0 AND one-sided paired weekly t ≥ 1.7.
* **Why t ≥ 1.7 suffices here:** this is ONE hypothesis, selected from external
  published evidence BEFORE any forward data. Pre-registration closes the garden of
  forking paths, so the 80-sleeve multiplicity debt does not attach to it. Anything
  mined from our own data (see shadows) pays a t ≥ 3 replication bar instead.
* **Quarterly checkpoints (days 91/182/273):** execution audits ONLY — fills match
  spec, turnover within bounds, zero unscheduled trades. A quarter cannot validate
  a monthly strategy, and no verdict will be read from one. This is written down
  now so nobody is tempted later.

## 4. Kill criteria (checked by code, no discretion)

Drawdown kills are PER CLASS, sized on the warmup tape and disclosed as a design
decision made before the forward epoch. A flat −20% would be fired by asset
volatility rather than strategy failure — on the design tape SPY alone drew −19%,
BTC −53%, silver −52%. Each level sits well inside its own benchmark's design-tape
drawdown, so reaching it means the trend filter failed at its one job.

| Trigger | Action |
|---|---|
| Drawdown from book peak: crypto −40% · stock −30% · metal −30% · energy −30% · rotator −30% | liquidate, status KILLED, stays cash until re-registration |
| Week ≥ 52 and delta-vs-hold ≤ −$1,500 | KILLED |
| Newest bar older than 7 days | HALTED — no new buys until the tape resumes |

A KILLED book is a completed experiment with a negative result, recorded in the
ledger. It is not restarted by enthusiasm.

## 5. Shadow hypotheses (graded daily, funded never)

| | Claim | Pass | Kill |
|---|---|---|---|
| **NEWSFADE** | ≥+2 net-bullish headline day → negative 3-bar return. Found IN-SAMPLE (t=−2.51, overlapping) — owes the mining debt | n ≥ 400 non-overlapping AND t ≤ −3.0 | n ≥ 400 AND t ≥ −1.0 |
| **FORM4** | Clustered insider filing activity → positive 21-bar excess vs SPY. Scorer is a FILING-COUNT PROXY, stated plainly | n ≥ 200 AND t ≥ +2.5 | n ≥ 200 AND t ≤ +0.5 |
| **CONGRESS** | Congressional disclosures → positive excess despite ≤45-day lag | REGISTERED-INACTIVE: hypothesis predates the data by design; activation is a future re-registration |

A shadow that passes earns a re-registration conversation — never an automatic
promotion. A shadow that hits its kill is closed in writing.

## 6. The honest expectation, stated before the data

* Central estimate: **6–10% per year net** ($50–85/month on $10k). Full range −5%
  to +15%; a whipsaw year of small losses is a normal outcome, not a malfunction.
* **P(beat buy-and-hold over 104 weeks): 40–55%.** Trend-following earns its keep
  mainly by sidestepping deep bear markets; in a sustained bull, hold usually wins.
  If these two years are a straight bull run, expect the hold twins to win and this
  experiment to record that honestly.
* **P($1,000/month on $10k): ~0.** That target is 214%/yr — roughly three times the
  best sustained record in industry history. No registered parameter pursues it,
  and any future system that claims to should be presumed broken until audited.
* Worst case: a drawdown kill fires (crypto −40%, others −30%) — on $10k paper,
  $3,000–4,000 locked in as a recorded negative result. On the design tape three of
  five books ended KILLED inside 18 months; kills are expected outcomes, and a kill
  with positive delta (metal locked in +$11,050 there) is a completed run whose
  result stands. Do not run this experiment with money whose loss would change
  your housing.

## 7. What was deleted, and why

The 348-module engine this replaces was retired after an independent audit measured
its pooled gross edge at −0.02% (t=−0.46) across 2,403 closed trades and traced all
apparent edge to three measurement faults. Its data stores are frozen read-only in
`docs/data/` as the archive; `scripts/recompute_fees.py` and `scripts/test_fee_law.py`
remain as the audit trail. One module earned a seat here: `form4.py`.

The RESET workflow was deliberately not carried forward. Nine wipes in sixteen days
destroyed more evidence than both accounting faults combined. **Wipes are not a
feature of this system.** The epoch is set once, and the clock only runs forward.
