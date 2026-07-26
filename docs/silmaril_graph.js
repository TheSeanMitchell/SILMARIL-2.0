// ═══════════════════════════════════════════════════════════════════════════════════════════════
// SILMARIL — THE EVERYTHING GRAPH  (docs/silmaril_graph.js)
//
// The operator's brief, verbatim from the July 24 notes:
//   "imports other graphs from other sites ... puts them side by side, to confirm that our graph
//    matches the real world graph, and then overlays them ... and then on that overlay cast ALL of
//    our metrics, prediction data, peak estimates, heartbeat estimates cadence, fingerprints
//    system, everything. Throw the entire system into these graph, on graph ... make sure the
//    system is aware if there is a price difference between sources."
//
// Previous attempts gave a TEXT panel beside the chart and dashed source lines. That was not the
// ask. This draws ONE canvas where every subsystem is a visible layer on the price itself:
//
//   LAYER 1  price, from our primary tape
//   LAYER 2  every other feed we hold, traced over it (the "tracing paper"), with a live spread
//            readout that turns red the moment sources disagree
//   LAYER 3  swing structure — peaks (▲) and troughs (▼) as detected by chart_intel
//   LAYER 4  floors and ceilings as horizontal bands, labelled with how many times each was tested
//   LAYER 5  the position: entry, target, stop, and the live mark
//   LAYER 6  the fingerprint's own plan for this name (its dip trigger and bounce target)
//   LAYER 7  the cadence projection — where the next peak is due, from the measured rhythm
//   LAYER 8  our actual fills on this name, buys and sells, placed at their real timestamps
//   LAYER 9  the verdict ribbon — structure, what the gates decided, and why
//
// Nothing here is synthetic. Every layer is read from a store the engine already publishes, so if
// a layer is missing the answer is "that subsystem has not produced data yet", never a drawn guess.
// ═══════════════════════════════════════════════════════════════════════════════════════════════

(function () {
  const NS = 'http://www.w3.org/2000/svg';

  const FEEDS = [
    ['data/price_samples.json', 'primary', '#4da3ff', 1.6, ''],
    ['data/ccxt_samples.json', 'ccxt', '#c98bff', 1.0, '5 3'],
    ['data/metals_samples.json', 'metals', '#ffd166', 1.0, '5 3'],
    ['data/energy_samples.json', 'energy', '#ff8fab', 1.0, '5 3'],
  ];

  // ── SYMBOL NORMALISATION — the reason cross-source verification never once ran. ─────────────
  // We hold two independent crypto feeds: the primary tape (1040 symbols, "BTC-USD") and the ccxt
  // tape (404 symbols, "BTCUSDT"). Same assets, different conventions, so the intersection was
  // literally ZERO and no price was ever checked against a second source. Normalising the key is
  // all that stood between us and real cross-feed verification on hundreds of names.
  function normSym(s) {
    s = String(s || '').toUpperCase().trim();
    if (s.indexOf('-') >= 0) return s;                    // already BASE-QUOTE
    const m = s.match(/^(.*?)(USDT|USDC|USD)$/);
    return m && m[1] ? m[1] + '-USD' : s;
  }
  function altKeys(sym) {
    const n = normSym(sym), base = n.replace(/-USD$/, '');
    return [sym, n, base + 'USDT', base + 'USD', base + 'USDC'];
  }

  const _cache = {};
  async function grab(path) {
    if (_cache[path] === undefined) {
      try {
        const r = await fetch(path, { cache: 'no-store' });
        _cache[path] = r.ok ? await r.json() : null;
      } catch (e) { _cache[path] = null; }
    }
    return _cache[path];
  }

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function fmtPx(v) {
    if (v == null || !isFinite(v)) return '—';
    const a = Math.abs(v);
    return '$' + v.toFixed(a >= 100 ? 2 : a >= 1 ? 4 : 6);
  }

  function fmtAge(ms) {
    const m = Math.round(ms / 60000);
    if (m < 60) return m + 'm';
    const h = m / 60;
    return (h < 48 ? h.toFixed(1) + 'h' : (h / 24).toFixed(1) + 'd');
  }

  /**
   * Draw the everything-graph for one symbol.
   * @param {string} sym    the ticker
   * @param {Element} host  container element
   * @param {object} opts   {hours: window, entry, mark, target, stop}
   */
  async function draw(sym, host, opts) {
    opts = opts || {};
    if (!host) return;
    host.innerHTML = '<div style="padding:10px;opacity:.7;font-size:11px">reading every layer for ' + esc(sym) + '…</div>';

    // ── gather every layer the engine publishes ────────────────────────────────────────────────
    const [ci, fp, geo, cards, live, lab, srcov] = await Promise.all([
      grab('data/CHART_INTEL.json'), grab('data/FINGERPRINTS.json'), grab('data/GEOMETRY.json'),
      grab('data/CONFIDENCE_CARDS.json'), grab('data/paper_sim_live.json'),
      grab('data/STRATEGY_LAB.json'), grab('data/SOURCE_OVERLAY.json'),
    ]);

    const series = [];
    for (const [path, label, colour, width, dash] of FEEDS) {
      const d = await grab(path);
      let rows = null;
      if (d && d.samples) {
        for (const k of altKeys(sym)) { if (d.samples[k] && d.samples[k].length > 3) { rows = d.samples[k]; break; } }
      }
      if (!rows || rows.length < 2) continue;
      const pts = rows
        .map(r => [new Date(r[0]).getTime(), +r[1]])
        .filter(r => isFinite(r[0]) && r[1] > 0)
        .sort((a, b) => a[0] - b[0]);
      if (pts.length >= 2) series.push({ label, colour, width, dash, pts, internal: true });
    }
    // ── 7.1 THE OUTSIDE WORLD (operator: "imports other graphs from other sites like Coinbase
    // or Yahoo Finance … overlay it with three sources"). SOURCE_OVERLAY.json carries genuinely
    // EXTERNAL series — Coinbase and Kraken via ccxt for crypto, Yahoo for equities/ETFs and the
    // mapped futures for spot metals/energy — fetched by the engine on the full pass. Each is
    // drawn as its own tracing-paper line; the verdict below compares TIME-ALIGNED prints. An
    // absent provider is an absent line (the store says so) — nothing here is ever synthesized.
    let extAgree = null, extAge = null;
    try {
      const so = await grab('data/SOURCE_OVERLAY.json');
      if (so && so.symbols) {
        let rec = null;
        for (const k of altKeys(sym)) { if (so.symbols[k]) { rec = so.symbols[k]; break; } }
        if (rec) {
          const EXT_COL = { coinbase: '#f7931a', kraken: '#5741d9' };
          let ci2 = 0;
          for (const [plabel, prow] of Object.entries(rec.providers || {})) {
            const pts = (prow || [])
              .map(r => [new Date(r[0]).getTime(), +r[1]])
              .filter(r => isFinite(r[0]) && r[1] > 0)
              .sort((a, b) => a[0] - b[0]);
            if (pts.length >= 2) {
              const col = EXT_COL[plabel] || ['#e6b800', '#00bcd4', '#e91e63'][ci2++ % 3];
              series.push({ label: plabel + ' ⇡', colour: col, width: 1.2, dash: '7 3', pts, external: true });
            }
          }
          extAgree = rec.agreement || null;
          if (so.generated_at) extAge = Date.now() - new Date(so.generated_at).getTime();
        }
      }
    } catch (e) { /* external layer is optional; the internal graph never breaks for it */ }
    if (!series.length) {
      host.innerHTML = '<div style="padding:14px;font-size:11px;line-height:1.7"><b>' + esc(sym) +
        '</b> — no price series on file yet.<br><span style="opacity:.65">Every trade stays fully accounted in the books; the tape joins on the next recorder cycle.</span></div>';
      return;
    }

    const hours = +opts.hours || 0;
    const now = Date.now();
    if (hours > 0) {
      const cut = now - hours * 3600000;
      series.forEach(s => { const f = s.pts.filter(p => p[0] >= cut); if (f.length >= 2) s.pts = f; });
    }

    const A = (ci && ci.by_symbol) ? (ci.by_symbol[sym] || {}) : {};
    const card = (cards && cards.by_symbol) ? (cards.by_symbol[sym] || {}) : {};
    const gRow = (geo && geo.by_symbol) ? (geo.by_symbol[sym] || {}) : {};
    let fpCard = null;
    if (fp && Array.isArray(fp.cards)) fpCard = fp.cards.find(c => c.sym === sym) || null;

    // our real fills on this name, from every book and sleeve
    const fills = [];
    ['crypto', 'stock', 'metal', 'energy', 'aggressive'].forEach(bk => {
      const b = (live || {})[bk] || {};
      (b.recent_trades || []).forEach(t => {
        if (t.sym === sym && t.t) fills.push({ t: new Date(t.t).getTime(), side: t.side, px: t.price, pnl: t.pnl, book: bk });
      });
    });
    if (lab && lab.sleeves) {
      Object.entries(lab.sleeves).forEach(([sk, sb]) => {
        (sb.trades || []).slice(-40).forEach(t => {
          if (t.sym === sym && t.t) fills.push({ t: new Date(t.t).getTime(), side: t.side, px: t.price, pnl: t.pnl, book: sk });
        });
      });
    }

    // ── geometry of the canvas ─────────────────────────────────────────────────────────────────
    const W = 900, H = 420, padL = 62, padR = 96, padT = 30, padB = 42;
    const all = series.flatMap(s => s.pts);
    let xmin = Math.min(...all.map(p => p[0])), xmax = Math.max(...all.map(p => p[0]));
    let ymin = Math.min(...all.map(p => p[1])), ymax = Math.max(...all.map(p => p[1]));

    // the frame must contain every level we intend to draw, or lines silently vanish
    const extra = [opts.entry, opts.mark,
      A.floor && A.floor.level, A.ceiling && A.ceiling.level]
      .concat((A.floors || []).map(f => f.level))
      .concat((A.ceilings || []).map(c => c.level))
      .filter(v => v != null && isFinite(v) && v > 0);
    if (opts.entry && opts.target != null) extra.push(opts.target < 1 ? opts.entry * (1 + opts.target) : opts.target);
    if (opts.entry && opts.stop != null) extra.push(opts.stop < 1 ? opts.entry * (1 - opts.stop) : opts.stop);
    extra.forEach(v => { ymin = Math.min(ymin, v); ymax = Math.max(ymax, v); });

    const yPad = (ymax - ymin) * 0.08 || (ymax * 0.01) || 1;
    ymin -= yPad; ymax += yPad;
    const xr = (xmax - xmin) || 1, yr = (ymax - ymin) || 1;
    const X = t => padL + (t - xmin) / xr * (W - padL - padR);
    const Y = v => H - padB - (v - ymin) / yr * (H - padT - padB);

    const out = [];
    out.push('<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="' + NS + '" style="width:100%;height:auto;display:block">');
    out.push('<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="transparent"/>');

    // ── LAYER 4: floors and ceilings, drawn as bands with their test counts ────────────────────
    (A.ceilings || []).slice(0, 3).forEach((c, i) => {
      if (c.level < ymin || c.level > ymax) return;
      const y = Y(c.level);
      out.push('<line x1="' + padL + '" y1="' + y.toFixed(1) + '" x2="' + (W - padR) + '" y2="' + y.toFixed(1) +
        '" stroke="#ff6b6b" stroke-width="' + (i === 0 ? 1.4 : 0.7) + '" stroke-dasharray="2 4" opacity="' + (i === 0 ? 0.85 : 0.4) + '"/>');
      out.push('<text x="' + (W - padR + 4) + '" y="' + (y - 2).toFixed(1) + '" font-size="8" fill="#ff6b6b">ceiling ' +
        fmtPx(c.level) + ' ·' + c.tested + '×</text>');
    });
    (A.floors || []).slice(0, 3).forEach((f, i) => {
      if (f.level < ymin || f.level > ymax) return;
      const y = Y(f.level);
      out.push('<line x1="' + padL + '" y1="' + y.toFixed(1) + '" x2="' + (W - padR) + '" y2="' + y.toFixed(1) +
        '" stroke="#39d353" stroke-width="' + (i === 0 ? 1.4 : 0.7) + '" stroke-dasharray="2 4" opacity="' + (i === 0 ? 0.85 : 0.4) + '"/>');
      out.push('<text x="' + (W - padR + 4) + '" y="' + (y + 8).toFixed(1) + '" font-size="8" fill="#39d353">floor ' +
        fmtPx(f.level) + ' ·' + f.tested + '×</text>');
    });

    // ── LAYER 5: the live position — target band, stop band, entry ─────────────────────────────
    if (opts.entry && isFinite(opts.entry) && opts.entry > 0) {
      const tgt = opts.target != null ? (opts.target < 1 ? opts.entry * (1 + opts.target) : opts.target) : null;
      const stp = opts.stop != null ? (opts.stop < 1 ? opts.entry * (1 - opts.stop) : opts.stop) : null;
      if (tgt) {
        out.push('<rect x="' + padL + '" y="' + Y(tgt).toFixed(1) + '" width="' + (W - padL - padR) +
          '" height="' + Math.max(0, Y(opts.entry) - Y(tgt)).toFixed(1) + '" fill="#39d353" opacity="0.07"/>');
        out.push('<line x1="' + padL + '" y1="' + Y(tgt).toFixed(1) + '" x2="' + (W - padR) + '" y2="' + Y(tgt).toFixed(1) +
          '" stroke="#39d353" stroke-width="1"/>');
        out.push('<text x="' + (W - padR + 4) + '" y="' + (Y(tgt) + 3).toFixed(1) + '" font-size="8" fill="#39d353">TARGET ' + fmtPx(tgt) + '</text>');
      }
      if (stp) {
        out.push('<rect x="' + padL + '" y="' + Y(opts.entry).toFixed(1) + '" width="' + (W - padL - padR) +
          '" height="' + Math.max(0, Y(stp) - Y(opts.entry)).toFixed(1) + '" fill="#ff6b6b" opacity="0.07"/>');
        out.push('<line x1="' + padL + '" y1="' + Y(stp).toFixed(1) + '" x2="' + (W - padR) + '" y2="' + Y(stp).toFixed(1) +
          '" stroke="#ff6b6b" stroke-width="1"/>');
        out.push('<text x="' + (W - padR + 4) + '" y="' + (Y(stp) + 3).toFixed(1) + '" font-size="8" fill="#ff6b6b">STOP ' + fmtPx(stp) + '</text>');
      }
      out.push('<line x1="' + padL + '" y1="' + Y(opts.entry).toFixed(1) + '" x2="' + (W - padR) + '" y2="' + Y(opts.entry).toFixed(1) +
        '" stroke="#e6e6e6" stroke-width="1" stroke-dasharray="6 3" opacity="0.8"/>');
      out.push('<text x="' + (W - padR + 4) + '" y="' + (Y(opts.entry) + 3).toFixed(1) + '" font-size="8" fill="#e6e6e6">ENTRY ' + fmtPx(opts.entry) + '</text>');
    }

    // ── LAYER 6: the fingerprint's own plan (what THIS name is expected to do) ─────────────────
    if (fpCard && fpCard.fit && series[0]) {
      const last = series[0].pts[series[0].pts.length - 1][1];
      const dipTrig = last * (1 - (fpCard.fit.entry || 0));
      const bounceTgt = last * (1 + (fpCard.fit.target || 0));
      if (dipTrig > ymin && dipTrig < ymax) {
        out.push('<line x1="' + padL + '" y1="' + Y(dipTrig).toFixed(1) + '" x2="' + (W - padR) + '" y2="' + Y(dipTrig).toFixed(1) +
          '" stroke="#4da3ff" stroke-width="0.8" stroke-dasharray="1 5" opacity="0.7"/>');
        out.push('<text x="' + (padL + 4) + '" y="' + (Y(dipTrig) - 3).toFixed(1) + '" font-size="7.5" fill="#4da3ff">fingerprint buys a ' +
          ((fpCard.fit.entry || 0) * 100).toFixed(2) + '% dip → ' + fmtPx(dipTrig) + '</text>');
      }
      if (bounceTgt > ymin && bounceTgt < ymax) {
        out.push('<line x1="' + padL + '" y1="' + Y(bounceTgt).toFixed(1) + '" x2="' + (W - padR) + '" y2="' + Y(bounceTgt).toFixed(1) +
          '" stroke="#7ee787" stroke-width="0.8" stroke-dasharray="1 5" opacity="0.6"/>');
        out.push('<text x="' + (padL + 4) + '" y="' + (Y(bounceTgt) - 3).toFixed(1) + '" font-size="7.5" fill="#7ee787">its measured bounce → ' +
          ((fpCard.fit.target || 0) * 100).toFixed(2) + '%</text>');
      }
    }

    // ── LAYERS 1 + 2: the price, and every other feed traced over it ───────────────────────────
    series.forEach(s => {
      const d = s.pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(' ');
      out.push('<path d="' + d + '" fill="none" stroke="' + s.colour + '" stroke-width="' + s.width +
        '"' + (s.dash ? ' stroke-dasharray="' + s.dash + '"' : '') + ' opacity="' + (s.label === 'primary' ? 1 : 0.75) + '"/>');
    });

    // ── LAYER 3: swing structure, from chart_intel ─────────────────────────────────────────────
    (A.peaks || []).forEach(p => {
      const t = new Date(p.t).getTime();
      if (t < xmin || t > xmax) return;
      out.push('<polygon points="' + X(t).toFixed(1) + ',' + (Y(p.px) - 7).toFixed(1) + ' ' +
        (X(t) - 4).toFixed(1) + ',' + (Y(p.px) - 1).toFixed(1) + ' ' + (X(t) + 4).toFixed(1) + ',' + (Y(p.px) - 1).toFixed(1) +
        '" fill="#ff6b6b" opacity="0.9"><title>peak ' + fmtPx(p.px) + '</title></polygon>');
    });
    (A.troughs || []).forEach(p => {
      const t = new Date(p.t).getTime();
      if (t < xmin || t > xmax) return;
      out.push('<polygon points="' + X(t).toFixed(1) + ',' + (Y(p.px) + 7).toFixed(1) + ' ' +
        (X(t) - 4).toFixed(1) + ',' + (Y(p.px) + 1).toFixed(1) + ' ' + (X(t) + 4).toFixed(1) + ',' + (Y(p.px) + 1).toFixed(1) +
        '" fill="#39d353" opacity="0.9"><title>trough ' + fmtPx(p.px) + '</title></polygon>');
    });

    // ── LAYER 7: the cadence projection — when the rhythm says the next peak is due ────────────
    if (A.cadence_min && A.peaks && A.peaks.length) {
      const lastPeak = new Date(A.peaks[A.peaks.length - 1].t).getTime();
      const due = lastPeak + A.cadence_min * 60000;
      if (due > xmin) {
        const x = Math.min(X(due), W - padR);
        out.push('<line x1="' + x.toFixed(1) + '" y1="' + padT + '" x2="' + x.toFixed(1) + '" y2="' + (H - padB) +
          '" stroke="#d4af37" stroke-width="0.9" stroke-dasharray="3 4" opacity="0.75"/>');
        out.push('<text x="' + (x + 3).toFixed(1) + '" y="' + (padT + 9) + '" font-size="7.5" fill="#d4af37">next peak due (rhythm ' +
          Math.round(A.cadence_min) + 'm)</text>');
      }
    }

    // ── LAYER 8: our actual fills ──────────────────────────────────────────────────────────────
    fills.forEach(fl => {
      if (!fl.px || fl.t < xmin || fl.t > xmax) return;
      const x = X(fl.t), y = Y(fl.px), buy = fl.side === 'BUY';
      out.push('<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="3.6" fill="' +
        (buy ? '#4da3ff' : (fl.pnl >= 0 ? '#39d353' : '#ff6b6b')) + '" stroke="#0b0e14" stroke-width="1"><title>' +
        esc(fl.side) + ' ' + esc(fl.book) + ' @ ' + fmtPx(fl.px) + (fl.pnl != null ? ' · P&L ' + fl.pnl : '') + '</title></circle>');
    });

    // ── the live mark ──────────────────────────────────────────────────────────────────────────
    if (opts.mark && isFinite(opts.mark) && opts.mark > 0) {
      const y = Y(opts.mark);
      out.push('<circle cx="' + (W - padR - 2) + '" cy="' + y.toFixed(1) + '" r="4" fill="#fff"/>');
      out.push('<text x="' + (W - padR + 4) + '" y="' + (y - 6).toFixed(1) + '" font-size="8.5" fill="#fff">now ' + fmtPx(opts.mark) + '</text>');
    }

    // ── axes ───────────────────────────────────────────────────────────────────────────────────
    out.push('<line x1="' + padL + '" y1="' + (H - padB) + '" x2="' + (W - padR) + '" y2="' + (H - padB) + '" stroke="#ffffff22"/>');
    [0, 0.5, 1].forEach(f => {
      const v = ymin + yr * f, y = Y(v);
      out.push('<text x="' + (padL - 6) + '" y="' + (y + 3).toFixed(1) + '" font-size="8" fill="#8b949e" text-anchor="end">' + fmtPx(v) + '</text>');
    });
    out.push('<text x="' + padL + '" y="' + (H - 6) + '" font-size="8" fill="#8b949e">' + new Date(xmin).toISOString().slice(5, 16).replace('T', ' ') + '</text>');
    out.push('<text x="' + (W - padR) + '" y="' + (H - 6) + '" font-size="8" fill="#8b949e" text-anchor="end">' + new Date(xmax).toISOString().slice(5, 16).replace('T', ' ') + '</text>');

    // ── LAYER 2b: the cross-source verdict, top-right ──────────────────────────────────────────
    let lx = padL;
    series.forEach(s => {
      out.push('<rect x="' + lx + '" y="10" width="9" height="3" fill="' + s.colour + '"/>');
      out.push('<text x="' + (lx + 12) + '" y="14" font-size="8" fill="' + s.colour + '">' + esc(s.label) + '</text>');
      lx += 20 + s.label.length * 5.4;
    });
    if (series.length > 1) {
      // 7.1: prefer the ENGINE's time-aligned verdict (our last live print vs each external
      // venue's print nearest in time, ≤15 min apart) over a naive last-vs-last, which compared
      // prints from different moments. Internal feeds still get the quick spread as a fallback.
      if (extAgree && extAgree.worst_spread_pct != null) {
        const sp = extAgree.worst_spread_pct, ok = extAgree.verdict === 'AGREE';
        out.push('<text x="' + (W - padR) + '" y="14" text-anchor="end" font-size="8.5" fill="' + (ok ? '#39d353' : '#ff6b6b') + '">' +
          'vs outside venues ' + (sp >= 0 ? '+' : '') + sp.toFixed(3) + '% ' + (ok ? '(agree' : '— DISAGREE, price suspect (') +
          (extAge != null ? ', checked ' + fmtAge(extAge) + ' ago)' : ')') + '</text>');
      } else {
        const lasts = series.filter(s => !s.external).map(s => s.pts[s.pts.length - 1][1]);
        if (lasts.length > 1) {
          const spread = (Math.max(...lasts) / Math.min(...lasts) - 1) * 100;
          const agree = spread <= 0.5;
          out.push('<text x="' + (W - padR) + '" y="14" text-anchor="end" font-size="8.5" fill="' + (agree ? '#39d353' : '#ff6b6b') + '">' +
            'internal feed spread ' + spread.toFixed(3) + '% ' + (agree ? '(agree)' : '— DISAGREE, price suspect') + '</text>');
        }
      }
    }
    out.push('</svg>');

    // ── LAYER 9: the verdict ribbon ────────────────────────────────────────────────────────────
    const structCol = A.structure === 'UPTREND' ? '#39d353' : A.structure === 'DOWNTREND' ? '#ff6b6b' : '#d4af37';
    const chip = (label, value, colour) =>
      '<span style="display:inline-block;margin:2px 6px 2px 0;padding:2px 6px;border:1px solid ' + (colour || '#ffffff33') +
      ';border-radius:3px;font-size:9.5px"><span style="opacity:.6">' + label + '</span> <b style="color:' + (colour || '#e6e6e6') + '">' + value + '</b></span>';

    const wins = A.windows || {};
    const ladder = ['2h', '4h', '8h', '12h', '1d', '2d', '3d', '1w']
      .filter(k => wins[k] != null)
      .map(k => chip(k, (wins[k] >= 0 ? '+' : '') + wins[k] + '%', wins[k] >= 0 ? '#39d353' : '#ff6b6b')).join('');

    const gv = gRow.verdict || '—';
    const gCol = gv === 'TRADEABLE' ? '#39d353' : gv.indexOf('UNTRADEABLE') === 0 ? '#ff6b6b' : '#8b949e';

    let ribbon = '<div style="margin-top:8px;font-size:10.5px;line-height:1.6">';
    ribbon += '<div style="font-weight:800;color:' + structCol + '">' + esc(sym) + ' · ' + esc(A.structure || 'structure unread') +
      (A.structure_why ? ' <span style="font-weight:400;opacity:.75">(' + esc(A.structure_why) + ')</span>' : '') + '</div>';
    if (ladder) ribbon += '<div style="margin:4px 0">' + ladder + '</div>';
    ribbon += '<div>' +
      chip('peaks', (A.peak_trajectory || {}).direction || '—',
        (A.peak_trajectory || {}).direction === 'RISING' ? '#39d353' : (A.peak_trajectory || {}).direction === 'FALLING' ? '#ff6b6b' : null) +
      chip('lows', (A.trough_trajectory || {}).direction || '—',
        (A.trough_trajectory || {}).direction === 'RISING' ? '#39d353' : (A.trough_trajectory || {}).direction === 'FALLING' ? '#ff6b6b' : null) +
      chip('based', A.based ? 'YES' : 'NO', A.based ? '#39d353' : '#ff6b6b') +
      chip('in range', A.position_in_range != null ? Math.round(A.position_in_range * 100) + '%' : '—', null) +
      chip('above floor', A.distance_to_floor_pct != null ? A.distance_to_floor_pct + '%' : '—',
        (A.distance_to_floor_pct != null && A.distance_to_floor_pct <= 3) ? '#39d353' : '#d4af37') +
      chip('σ tick', A.sigma_pct != null ? A.sigma_pct + '%' : '—', null) +
      chip('rhythm', A.cadence_min != null ? Math.round(A.cadence_min) + 'm' : 'learning', null) +
      '</div>';
    ribbon += '<div>' +
      chip('geometry', gv, gCol) +
      (gRow.p_star_pct != null ? chip('needs to win', gRow.p_star_pct + '%', '#d4af37') : '') +
      (gRow.p_floor_pct != null ? chip('its measured floor', gRow.p_floor_pct + '%',
        (gRow.p_floor_pct >= (gRow.p_star_pct || 999)) ? '#39d353' : '#ff6b6b') : '') +
      (card.confidence != null ? chip('confidence', Math.round(card.confidence * 100) + '%', null) : '') +
      (fpCard && fpCard.fp && fpCard.fp.bounce_reliability != null
        ? chip('bounce reliability', (fpCard.fp.bounce_reliability * 100).toFixed(0) + '%',
          fpCard.fp.bounce_reliability >= 0.6 ? '#39d353' : '#d4af37') : '') +
      '</div>';
    if (fpCard && fpCard.summary) {
      ribbon += '<div style="opacity:.7;margin-top:3px">🧬 ' + esc(fpCard.summary) + '</div>';
    }
    ribbon += '<div style="opacity:.55;margin-top:4px;font-size:9px">Every layer above is read from a store the engine publishes — ' +
      'CHART_INTEL (structure, peaks, floors, rhythm), FINGERPRINTS (this name\'s own plan), GEOMETRY (the win rate it needs), ' +
      'CONFIDENCE_CARDS, and the live books for our real fills. The entry gate reads the same files, so the chart and the engine cannot disagree.</div>';
    ribbon += '</div>';

    host.innerHTML = out.join('') + ribbon;
  }

  window.SilmarilGraph = { draw: draw, altKeys: altKeys, normSym: normSym,
                           clearCache: () => { for (const k in _cache) delete _cache[k]; } };
})();
