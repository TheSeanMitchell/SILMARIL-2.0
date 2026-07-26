/* ============================================================================
   SILMARIL CHART v3 — THE EVERYTHING CHART (the modal every ticker click opens).

   7.1.1 INCIDENT RECEIPT: v2 was the chart the operator actually uses — the
   capture-phase click handler routes EVERY ticker on the dashboard here — yet it
   read NONE of the engine's stores. 674 fitted fingerprints, CHART_INTEL
   structure, GEOMETRY verdicts and a 229KB SOURCE_OVERLAY of real Coinbase/
   Kraken/Yahoo series sat on disk while this modal drew a bare price line.
   "If it's not on the graph we assume the data is not really being collected."
   Correct. Now it is on the graph.

   LAYERS (all real, nothing synthetic — every line names its source):
     price · EXTERNAL venues traced over it (SOURCE_OVERLAY: coinbase/kraken/
     yahoo, time-aligned agreement verdict) · peaks ▲ / troughs ▼ · floors &
     ceilings with test counts · cadence → next-peak ETA · fingerprint's own
     dip-trigger and bounce-target lines (its custom fit, not a blanket rule) ·
     entry/target/stop/live-mark · our real fills · Dr Strange projection ·
     geometry verdict · trajectory ladder (2h→1W) · QUANTIZED-FEED banner when
     a venue only reports a coin at 2-3 representable sub-penny levels (the
     MOG-USD "glitch": the feed's tick size, not our system inventing prices) ·
     sub-penny prices shown with real digits, never rounded to $0.000000.

   Structure source of truth: CHART_INTEL when the engine has fitted the name;
   otherwise the SAME swing math runs here on the SAME tape, labeled
   "view-detected". Same data, same math — displayed for every valuable, so no
   name ever opens onto an unread chart again.
   ============================================================================ */
(function () {
  if (window.__silmarilChartBooted) return;
  window.__silmarilChartBooted = true;

  var DATA = {}, POS = {}, RHY = {}, OV = {}, CI = {}, FP = {}, GEO = {}, SRC = {}, SRCMETA = {}, READY = false;
  var MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function j(p) { return fetch(p + "?t=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function tsParse(s) { var d = new Date(s); return isNaN(d) ? null : d.getTime(); }

  /* ── sub-penny honest formatting (the $0.000000 fix): enough digits to SHOW the price ── */
  function decFor(v) {
    var a = Math.abs(v);
    if (a >= 1000) return 2; if (a >= 1) return 2; if (a >= 0.01) return 4; if (a >= 0.0001) return 6;
    if (a >= 0.000001) return 8; return 10;
  }
  function fmtP(v) {
    if (v == null || !isFinite(v)) return "—";
    var a = Math.abs(v);
    if (a >= 1000) return "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return "$" + v.toFixed(decFor(v));
  }
  /* axis precision from the RANGE, so gridlines are distinguishable on quantized coins */
  function axisDec(rr, ref) { var need = rr > 0 ? Math.ceil(-Math.log10(rr / 4)) + 1 : decFor(ref); return Math.max(2, Math.min(10, Math.max(need, 2))); }
  function fmtAxisP(v, dec) { return "$" + v.toFixed(dec); }
  function pad(n) { return String(n).padStart(2, "0"); }
  function fmtDateTime(ms) { var d = new Date(ms); return MO[d.getMonth()] + " " + d.getDate() + ", " + pad(d.getHours()) + ":" + pad(d.getMinutes()); }
  function fmtAxis(ms, span) { var d = new Date(ms); if (span <= 864e5) return pad(d.getHours()) + ":" + pad(d.getMinutes()); if (span <= 7 * 864e5) return MO[d.getMonth()] + " " + d.getDate() + " " + pad(d.getHours()) + "h"; return MO[d.getMonth()] + " " + d.getDate(); }
  function fmtEta(ms) { if (ms == null) return "—"; var m = Math.round(ms / 60000); if (m <= 0) return "due now"; if (m < 60) return "~in " + m + "m"; var h = m / 60; return h < 48 ? "~in " + h.toFixed(1) + "h" : "~in " + (h / 24).toFixed(1) + "d"; }
  function fmtAge(ms) { var m = Math.round(ms / 60000); return m < 60 ? m + "m ago" : (m / 60).toFixed(1) + "h ago"; }
  function spanMs(tf) { var m=60000,H=36e5,D=864e5; return { "5m":5*m,"15m":15*m,"30m":30*m,"1h":H,"2h":2*H,"4h":4*H,"8h":8*H,"12h":12*H,"1D":D,"2D":2*D,"3D":3*D,"1W":7*D,"2W":14*D,"1M":30*D,"2M":60*D,"YTD":(Date.now()-new Date(new Date().getFullYear(),0,1).getTime()),"1Y":365*D,"MAX":1e15 }[tf] || 1e15; }

  /* ── ONE-KEY LAW, client half: same canon as silmaril/execution/canon_keys.py ── */
  var NEVER = { USD:1, USDT:1, USDC:1, USO:1, USL:1, USOI:1 };
  function canon(sym) {
    var s = String(sym || "").toUpperCase().trim().replace("/", "");
    if (NEVER[s]) return s;
    if (s.indexOf("-") >= 0) return s;
    var m = s.match(/^(.*?)(USDT|USDC|USD)$/);
    return (m && m[1] && !NEVER[m[1]]) ? m[1] + "-USD" : s;
  }
  function altKeys(sym) {
    var c = canon(sym), base = c.replace(/-USD$/, "");
    var out = [sym, c], seen = {}, uq = [];
    if (c.slice(-4) === "-USD") out = out.concat([base + "USDT", base + "USD", base + "USDC", base + "/USD", base + "/USDT"]);
    out.forEach(function (k) { if (k && !seen[k]) { seen[k] = 1; uq.push(k); } });
    return uq;
  }
  function series(sym) { var ks = altKeys(sym); for (var i = 0; i < ks.length; i++) if (DATA[ks[i]] && DATA[ks[i]].length) return DATA[ks[i]]; return null; }
  function rec(store, sym) { if (!store) return null; var ks = altKeys(sym); for (var i = 0; i < ks.length; i++) if (store[ks[i]]) return store[ks[i]]; return null; }

  function boot() {
    return Promise.all([
      j("data/price_samples.json"), j("data/metals_samples.json"), j("data/energy_samples.json"), j("data/ccxt_samples.json"),
      j("data/paper_sim_live.json"), j("data/PEAK_RHYTHM.json"), j("data/champion_crypto.json"), j("data/champion_stock.json"),
      j("data/CHART_OVERLAYS.json"), j("data/CHART_INTEL.json"), j("data/FINGERPRINTS.json"), j("data/GEOMETRY.json"), j("data/SOURCE_OVERLAY.json")
    ]).then(function (r) {
      var ps = r[0], mt = r[1], en = r[2], cx = r[3], live = r[4], rhy = r[5], cc = r[6], cs = r[7], ovf = r[8], ci = r[9], fp = r[10], geo = r[11], so = r[12];
      DATA = (ps && ps.samples) || {};
      [mt, en].forEach(function (S) { if (S && S.samples) Object.keys(S.samples).forEach(function (k) { if (!DATA[k]) DATA[k] = S.samples[k]; }); });
      /* ccxt joins UNDER THE CANON KEY — union by timestamp, primary tape wins collisions.
         This is why DOGEUSDT now opens onto DOGE-USD's full graph instead of an empty room. */
      if (cx && cx.samples) Object.keys(cx.samples).forEach(function (k) {
        var ck = canon(k), rows = cx.samples[k] || [];
        if (!rows.length) return;
        if (!DATA[ck]) { DATA[ck] = rows; return; }
        var m = {}; rows.forEach(function (r2) { m[String(r2[0])] = r2[1]; });
        (DATA[ck] || []).forEach(function (r2) { m[String(r2[0])] = r2[1]; });
        DATA[ck] = Object.keys(m).sort().map(function (t) { return [t, m[t]]; });
      });
      if (ovf && ovf.symbols) OV = ovf.symbols;
      if (ci && ci.by_symbol) CI = ci.by_symbol;
      if (geo && geo.by_symbol) GEO = geo.by_symbol;
      if (fp && fp.cards) fp.cards.forEach(function (c2) { if (c2 && c2.sym) FP[canon(c2.sym)] = c2; });
      if (so && so.symbols) { SRC = so.symbols; SRCMETA = { at: so.generated_at ? tsParse(so.generated_at) : null }; }
      function ts(nm) { var t = /_t(\d+)/.exec(nm || ""), s = /_s(\d+)/.exec(nm || ""); return [t ? +t[1] : null, s ? +s[1] : null]; }
      var champ = { crypto: cc && cc.name, stock: cs && cs.name };
      if (live) ["crypto", "stock", "metal", "energy"].forEach(function (bk) {
        var b = live[bk] || {}, arr = b.open_positions || b.positions || [], p = ts(champ[bk] || live["champion_" + bk]);
        (Array.isArray(arr) ? arr : []).forEach(function (o) {
          if (!o || !o.sym) return;
          POS[canon(o.sym)] = { entry: o.entry, mark: o.mark, book: bk, tpct: (o.target != null ? o.target * 100 : p[0]), spct: (o.stop != null ? o.stop * 100 : p[1]), upl: o.upl_pct,
            target: (o.target != null && o.entry) ? o.entry * (1 + o.target) : ((p[0] != null && o.entry) ? o.entry * (1 + p[0] / 100) : null),
            stop: (o.stop != null && o.entry) ? o.entry * (1 - o.stop) : ((p[1] != null && o.entry) ? o.entry * (1 - p[1] / 100) : null) };
        });
      });
      if (rhy && rhy.by_symbol) RHY = rhy.by_symbol;
      READY = true;
    });
  }

  function slice(rows, tf) {
    if (!rows || !rows.length) return [];
    var last = tsParse(rows[rows.length - 1][0]) || Date.now(), sp = spanMs(tf);
    return rows.filter(function (r) { var t = tsParse(r[0]); return t && (last - t) <= sp && r[1] > 0; });
  }

  /* ── VIEW-DETECTED STRUCTURE: the professional trader's read, computed from the SAME tape.
       Engine numbers (CHART_INTEL / PEAK_RHYTHM / FINGERPRINTS) draw on top when they exist;
       this guarantees EVERY chart shows peaks, cadence, trajectory, floors — no blank rooms. ── */
  function swings(rows) {
    var out = { peaks: [], troughs: [], floors: [], ceilings: [], cadMin: null, lastPeak: null, nextPeakAt: null, peakTraj: "—", trghTraj: "—" };
    if (!rows || rows.length < 8) return out;
    var xs = rows.map(function (r) { return tsParse(r[0]); }), ys = rows.map(function (r) { return r[1]; });
    var n = ys.length, mean = 0, i; for (i = 0; i < n; i++) mean += ys[i]; mean /= n;
    var rets = []; for (i = 1; i < n; i++) if (ys[i - 1] > 0) rets.push(Math.abs(ys[i] / ys[i - 1] - 1));
    rets.sort(function (a, b) { return a - b; });
    var sig = rets.length ? rets[Math.floor(rets.length / 2)] : 0.001;
    var prom = Math.max(sig * 3, 0.002);                       // swing must beat 3x median tick noise
    var w = Math.max(2, Math.floor(n / 40));                   // local-extreme window scales with view
    for (i = w; i < n - w; i++) {
      var hi = true, lo = true, k;
      for (k = i - w; k <= i + w; k++) { if (ys[k] > ys[i]) hi = false; if (ys[k] < ys[i]) lo = false; }
      if (hi && (!out.peaks.length || (xs[i] - out.peaks[out.peaks.length - 1].t) > (xs[n-1]-xs[0]) / 60)) {
        var base = Math.min.apply(null, ys.slice(Math.max(0, i - w * 3), i + 1));
        if (base > 0 && ys[i] / base - 1 >= prom) out.peaks.push({ t: xs[i], px: ys[i] });
      }
      if (lo && (!out.troughs.length || (xs[i] - out.troughs[out.troughs.length - 1].t) > (xs[n-1]-xs[0]) / 60)) {
        var cap = Math.max.apply(null, ys.slice(Math.max(0, i - w * 3), i + 1));
        if (ys[i] > 0 && cap / ys[i] - 1 >= prom) out.troughs.push({ t: xs[i], px: ys[i] });
      }
    }
    function cluster(pts) {                                     // levels tested 2+ times = floor/ceiling
      var lv = [], tol = Math.max(sig * 2, 0.004);
      pts.forEach(function (p) {
        for (var q = 0; q < lv.length; q++) if (Math.abs(p.px / lv[q].level - 1) <= tol) { lv[q].level = (lv[q].level * lv[q].tested + p.px) / (lv[q].tested + 1); lv[q].tested++; return; }
        lv.push({ level: p.px, tested: 1 });
      });
      return lv.filter(function (l) { return l.tested >= 2; }).sort(function (a, b) { return b.tested - a.tested; }).slice(0, 3);
    }
    out.floors = cluster(out.troughs); out.ceilings = cluster(out.peaks);
    if (out.peaks.length >= 2) {
      var gaps = []; for (i = 1; i < out.peaks.length; i++) gaps.push(out.peaks[i].t - out.peaks[i - 1].t);
      gaps.sort(function (a, b) { return a - b; });
      out.cadMin = Math.round(gaps[Math.floor(gaps.length / 2)] / 60000);
      out.lastPeak = out.peaks[out.peaks.length - 1];
      out.nextPeakAt = out.lastPeak.t + out.cadMin * 60000;
      var lp = out.peaks.slice(-3);
      if (lp.length >= 2) out.peakTraj = lp[lp.length - 1].px > lp[0].px * 1.002 ? "RISING" : lp[lp.length - 1].px < lp[0].px * 0.998 ? "FALLING" : "FLAT";
    } else if (out.peaks.length === 1) out.lastPeak = out.peaks[0];
    var lt = out.troughs.slice(-3);
    if (lt.length >= 2) out.trghTraj = lt[lt.length - 1].px > lt[0].px * 1.002 ? "RISING" : lt[lt.length - 1].px < lt[0].px * 0.998 ? "FALLING" : "FLAT";
    return out;
  }

  /* trajectory ladder — every window the operator listed, straight from the tape */
  function ladder(all) {
    if (!all || all.length < 3) return [];
    var last = tsParse(all[all.length - 1][0]), lp = all[all.length - 1][1], out = [];
    [["2h",2*36e5],["4h",4*36e5],["8h",8*36e5],["12h",12*36e5],["1D",864e5],["2D",2*864e5],["3D",3*864e5],["1W",7*864e5]].forEach(function (W) {
      var cut = last - W[1], ref = null;
      for (var i = 0; i < all.length; i++) { var t = tsParse(all[i][0]); if (t >= cut && all[i][1] > 0) { ref = all[i][1]; break; } }
      if (ref) out.push({ w: W[0], pct: (lp / ref - 1) * 100 });
    });
    return out;
  }

  /* quantized-feed detector — the MOG class, labeled instead of mystifying */
  function quantized(ys) {
    if (!ys || ys.length < 40) return null;
    var seen = {}, uq = 0;
    for (var i = 0; i < ys.length; i++) { var k = ys[i].toPrecision(6); if (!seen[k]) { seen[k] = 1; uq++; if (uq > 6) return null; } }
    var mx = Math.max.apply(null, ys), mn = Math.min.apply(null, ys);
    return { levels: uq, spreadPct: mn > 0 ? (mx / mn - 1) * 100 : 0 };
  }

  function stats(rows) {
    var ys = rows.map(function (r) { return r[1]; }), xs = rows.map(function (r) { return tsParse(r[0]); });
    var open = ys[0], close = ys[ys.length - 1], hi = -Infinity, lo = Infinity, hiI = 0, loI = 0, i;
    for (i = 0; i < ys.length; i++) { if (ys[i] > hi) { hi = ys[i]; hiI = i; } if (ys[i] < lo) { lo = ys[i]; loI = i; } }
    var rets = []; for (i = 1; i < ys.length; i++) rets.push(ys[i] / ys[i - 1] - 1);
    var mret = rets.reduce(function (a, b) { return a + b; }, 0) / (rets.length || 1);
    var vol = Math.sqrt(rets.reduce(function (a, b) { return a + (b - mret) * (b - mret); }, 0) / (rets.length || 1)) * 100;
    var avg = ys.reduce(function (a, b) { return a + b; }, 0) / ys.length;
    var last = xs[xs.length - 1];
    var d1 = rows.filter(function (r) { return last - tsParse(r[0]) <= 864e5; }).map(function (r) { return r[1]; });
    return { open: open, close: close, hi: hi, lo: lo, hiAt: xs[hiI], loAt: xs[loI], chg: close - open, chgP: (close / open - 1) * 100, range: hi - lo, rangeP: (hi - lo) / lo * 100, avg: avg, vol: vol, hi24: d1.length ? Math.max.apply(null, d1) : null, lo24: d1.length ? Math.min.apply(null, d1) : null, n: ys.length, fromT: xs[0], toT: last };
  }

  var EXTCOL = { coinbase: "#f7931a", kraken: "#5741d9" };
  var EXTPAL = ["#e6b800", "#00bcd4", "#e91e63"];

  function chartSVG(sym, tf, w, h, withCross) {
    sym = canon(sym);
    var all = series(sym) || [];
    var rows = slice(all, tf);
    if (rows.length < 2) return { svg: "<div style='padding:30px;color:#8b93a7;text-align:center'>No price history for " + sym + "</div>" };
    var xs = rows.map(function (r) { return tsParse(r[0]); }), ys = rows.map(function (r) { return r[1]; });
    var p = POS[sym] || {}, extra = [p.entry, p.target, p.stop, p.mark].filter(function (v) { return v != null; });

    /* external venue series sliced to the same window (SOURCE_OVERLAY — real third parties) */
    var srec = rec(SRC, sym), ext = [], epi = 0;
    if (srec && srec.providers) Object.keys(srec.providers).forEach(function (lab) {
      var rws = (srec.providers[lab] || []).map(function (r2) { return [tsParse(r2[0]), +r2[1]]; })
        .filter(function (r2) { return r2[0] && r2[1] > 0 && (xs[xs.length - 1] - r2[0]) <= (spanMs(tf) === 1e15 ? (xs[xs.length-1]-xs[0]) : spanMs(tf)) && r2[0] >= xs[0] - 36e5; })
        .sort(function (a, b) { return a[0] - b[0]; });
      if (rws.length >= 2) { ext.push({ lab: lab, col: EXTCOL[lab] || EXTPAL[epi++ % 3], pts: rws }); rws.forEach(function (r2) { extra.push(r2[1]); }); }
    });

    var ciR = rec(CI, sym) || {};
    var sw = swings(rows);
    var enginePeaks = (ciR.peaks || []).map(function (q) { return { t: tsParse(q.t), px: q.px }; }).filter(function (q) { return q.t >= xs[0] && q.t <= xs[xs.length - 1]; });
    var engineTr   = (ciR.troughs || []).map(function (q) { return { t: tsParse(q.t), px: q.px }; }).filter(function (q) { return q.t >= xs[0] && q.t <= xs[xs.length - 1]; });
    var peaks = enginePeaks.length ? enginePeaks : sw.peaks, troughs = engineTr.length ? engineTr : sw.troughs;
    var floors = (ciR.floors && ciR.floors.length ? ciR.floors : sw.floors) || [];
    var ceils  = (ciR.ceilings && ciR.ceilings.length ? ciR.ceilings : sw.ceilings) || [];
    var fpc = rec(FP, sym);
    var lastPx = ys[ys.length - 1];
    if (fpc && fpc.fit) { if (fpc.fit.entry) extra.push(lastPx * (1 - fpc.fit.entry)); if (fpc.fit.target) extra.push(lastPx * (1 + fpc.fit.target)); }
    floors.forEach(function (f) { extra.push(f.level); }); ceils.forEach(function (c) { extra.push(c.level); });

    var mn = Math.min.apply(null, ys.concat(extra)), mx = Math.max.apply(null, ys.concat(extra));
    var rr = (mx - mn) || mx * 0.01 || 1; mn -= rr * 0.08; mx += rr * 0.08; rr = mx - mn;
    var padL = 4, padR = 74, padT = 8, padB = 26, iw = w - padL - padR, ih = h - padT - padB;
    var X = function (t) { return padL + (t - xs[0]) / ((xs[xs.length - 1] - xs[0]) || 1) * iw; };
    var Y = function (v) { return padT + (mx - v) / rr * ih; };
    var up = ys[ys.length - 1] >= ys[0], col = up ? "#16c784" : "#ea3943";
    var line = rows.map(function (rw, i) { return (i ? "L" : "M") + X(xs[i]).toFixed(1) + "," + Y(rw[1]).toFixed(1); }).join(" ");
    var area = line + " L" + X(xs[xs.length - 1]).toFixed(1) + "," + (padT + ih) + " L" + X(xs[0]).toFixed(1) + "," + (padT + ih) + " Z";
    var gid = "g" + Math.random().toString(36).slice(2, 7), sp = spanMs(tf) === 1e15 ? (xs[xs.length - 1] - xs[0]) : spanMs(tf);
    var aDec = axisDec(rr, lastPx);
    var s = "<svg viewBox='0 0 " + w + " " + h + "' width='100%' height='100%' preserveAspectRatio='none' class='slmchart' style='display:block;font-family:inherit'>";
    s += "<defs><linearGradient id='" + gid + "' x1='0' x2='0' y1='0' y2='1'><stop offset='0' stop-color='" + col + "' stop-opacity='.28'/><stop offset='1' stop-color='" + col + "' stop-opacity='0'/></linearGradient></defs>";
    [0, .25, .5, .75, 1].forEach(function (f) { var yv = mx - f * rr, yy = Y(yv); s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='#ffffff12'/><text x='" + (w - padR + 5) + "' y='" + (yy + 3).toFixed(1) + "' font-size='9' fill='#8b93a7'>" + fmtAxisP(yv, aDec) + "</text>"; });
    var nT = w < 420 ? 4 : 6;
    for (var k = 0; k <= nT; k++) {
      var tt = xs[0] + (xs[xs.length - 1] - xs[0]) * k / nT, xx = X(tt);
      s += "<line x1='" + xx.toFixed(1) + "' x2='" + xx.toFixed(1) + "' y1='" + padT + "' y2='" + (padT + ih) + "' stroke='#ffffff0a'/>";
      var anchor = k === 0 ? "start" : k === nT ? "end" : "middle";
      s += "<text x='" + xx.toFixed(1) + "' y='" + (h - 8) + "' font-size='9.5' fill='#8b93a7' text-anchor='" + anchor + "'>" + fmtAxis(tt, sp) + "</text>";
    }
    /* floors / ceilings — labelled bands with their test counts */
    ceils.forEach(function (c2, i2) { if (c2.level < mn || c2.level > mx) return; var yy = Y(c2.level); s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='#ea3943' stroke-width='" + (i2 ? 0.7 : 1.2) + "' stroke-dasharray='2 4' opacity='" + (i2 ? 0.35 : 0.7) + "'/><text x='" + (w - padR - 3) + "' y='" + (yy - 2).toFixed(1) + "' font-size='7.5' fill='#ea3943' text-anchor='end'>ceiling " + fmtP(c2.level) + " ·" + c2.tested + "×</text>"; });
    floors.forEach(function (f2, i2) { if (f2.level < mn || f2.level > mx) return; var yy = Y(f2.level); s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='#39d353' stroke-width='" + (i2 ? 0.7 : 1.2) + "' stroke-dasharray='2 4' opacity='" + (i2 ? 0.35 : 0.7) + "'/><text x='" + (w - padR - 3) + "' y='" + (yy + 8).toFixed(1) + "' font-size='7.5' fill='#39d353' text-anchor='end'>floor " + fmtP(f2.level) + " ·" + f2.tested + "×</text>"; });
    s += "<path d='" + area + "' fill='url(#" + gid + ")'/><path d='" + line + "' fill='none' stroke='" + col + "' stroke-width='1.7'/>";
    /* EXTERNAL VENUES — the tracing paper (dashed, own colors), from SOURCE_OVERLAY */
    ext.forEach(function (e2) {
      var d2 = e2.pts.map(function (q, i2) { return (i2 ? "L" : "M") + X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1); }).join(" ");
      s += "<path d='" + d2 + "' fill='none' stroke='" + e2.col + "' stroke-width='1.1' stroke-dasharray='6 3' opacity='.85'/>";
    });
    function hline(v, c, lbl, dash) { if (v == null) return; var yy = Y(v); s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='" + c + "' stroke-width='1' stroke-dasharray='" + (dash || "4 3") + "' opacity='.9'/><rect x='" + padL + "' y='" + (yy - 8).toFixed(1) + "' width='" + (lbl.length * 5.3 + 6) + "' height='12' rx='2' fill='" + c + "' opacity='.92'/><text x='" + (padL + 3) + "' y='" + (yy + 1.5).toFixed(1) + "' font-size='8' fill='#06121f' font-weight='700'>" + lbl + "</text>"; }
    /* the fingerprint's OWN plan — its custom fit, not a blanket threshold */
    if (fpc && fpc.fit && fpc.fit.entry) hline(lastPx * (1 - fpc.fit.entry), "#4da3ff", "fp buys " + (fpc.fit.entry * 100).toFixed(2) + "% dip", "1 5");
    if (fpc && fpc.fit && fpc.fit.target) hline(lastPx * (1 + fpc.fit.target), "#7ee787", "fp bounce +" + (fpc.fit.target * 100).toFixed(2) + "%", "1 5");
    if (p.entry != null) hline(p.entry, "#9aa4b8", "ENTRY " + fmtP(p.entry));
    if (p.stop != null) hline(p.stop, "#ea3943", "STOP " + (p.spct != null ? "-" + (+p.spct).toFixed(1) + "%" : fmtP(p.stop)));
    if (p.target != null) hline(p.target, "#16c784", "TARGET " + (p.tpct != null ? "+" + (+p.tpct).toFixed(1) + "%" : fmtP(p.target)) + " cash-out");
    if (p.mark != null) { var my = Y(p.mark); s += "<circle cx='" + (w - padR - 2) + "' cy='" + my.toFixed(1) + "' r='3.2' fill='#f7c948'><animate attributeName='r' values='3.2;5;3.2' dur='1.6s' repeatCount='indefinite'/></circle>"; }
    /* peaks ▲ / troughs ▼ (engine when fitted, else view-detected — same tape, same math) */
    peaks.forEach(function (q) { var qx = X(q.t), qy = Y(q.px); s += "<path d='M" + qx.toFixed(1) + "," + (qy - 8).toFixed(1) + " l-4,6 l8,0 z' fill='#ea3943' opacity='.9'><title>peak " + fmtP(q.px) + " · " + fmtDateTime(q.t) + "</title></path>"; });
    troughs.forEach(function (q) { var qx = X(q.t), qy = Y(q.px); s += "<path d='M" + qx.toFixed(1) + "," + (qy + 8).toFixed(1) + " l-4,-6 l8,0 z' fill='#39d353' opacity='.9'><title>trough " + fmtP(q.px) + " · " + fmtDateTime(q.t) + "</title></path>"; });
    /* cadence → next-peak ETA (engine rhythm first, else view cadence) */
    var ry = rec(RHY, sym) || {};
    var nextPk = ry.predicted_next_peak_at ? tsParse(ry.predicted_next_peak_at) : sw.nextPeakAt;
    var cadM = ry.median_minutes_between_peaks != null ? Math.round(ry.median_minutes_between_peaks) : sw.cadMin;
    if (nextPk && nextPk >= xs[0]) {
      var px2 = Math.min(X(nextPk), w - padR);
      s += "<line x1='" + px2.toFixed(1) + "' x2='" + px2.toFixed(1) + "' y1='" + padT + "' y2='" + (padT + ih) + "' stroke='#b388ff' stroke-width='1' stroke-dasharray='2 3'/><text x='" + (px2 - 2).toFixed(1) + "' y='" + (padT + 9) + "' font-size='8' fill='#b388ff' text-anchor='end'>next peak " + fmtEta(nextPk - Date.now()) + (cadM ? " (rhythm " + (cadM >= 60 ? (cadM / 60).toFixed(1) + "h" : cadM + "m") + ")" : "") + "</text>";
    }
    /* our real fills + latest planned exits (CHART_OVERLAYS, unchanged) */
    var ov = rec(OV, sym) || {};
    if (p.target == null && ov.trades && ov.trades.length) {
      var lt = ov.trades[ov.trades.length - 1];
      if (lt.target != null) hline(lt.target, "#f7c948", "TARGET (cash-out) " + fmtP(lt.target));
      if (lt.stop != null) hline(lt.stop, "#ea3943", "STOP " + fmtP(lt.stop));
    }
    (ov.trades || []).forEach(function (t) {
      var et = tsParse(t.entry_t), xt = tsParse(t.exit_t);
      if (et && et >= xs[0] && et <= xs[xs.length - 1] && t.entry != null) { var ex = X(et), ey = Y(t.entry); s += "<path d='M" + ex.toFixed(1) + "," + (ey + 6).toFixed(1) + " l-4,7 l8,0 z' fill='#9aa4b8' opacity='.95'/>"; }
      if (xt && xt >= xs[0] && xt <= xs[xs.length - 1] && t.exit != null) { var xx2 = X(xt), xy = Y(t.exit), c2 = t.pnl_pct >= 0 ? "#16c784" : "#ea3943"; s += "<path d='M" + xx2.toFixed(1) + "," + (xy - 6).toFixed(1) + " l-4,-7 l8,0 z' fill='" + c2 + "'/>"; }
    });
    if (ov.dr_strange && ov.dr_strange.expected_move_pct != null) {
      var dsm = ov.dr_strange.expected_move_pct, cur = ys[ys.length - 1], projP = cur * (1 + dsm / 100);
      if (projP >= mn && projP <= mx) {
        var py2 = Y(projP);
        s += "<line x1='" + (w - padR - 64).toFixed(1) + "' x2='" + (w - padR).toFixed(1) + "' y1='" + Y(cur).toFixed(1) + "' y2='" + py2.toFixed(1) + "' stroke='#b388ff' stroke-width='1.3' stroke-dasharray='3 2'/><circle cx='" + (w - padR).toFixed(1) + "' cy='" + py2.toFixed(1) + "' r='2.6' fill='#b388ff'/><text x='" + (w - padR - 2).toFixed(1) + "' y='" + (py2 - 4).toFixed(1) + "' font-size='8' fill='#b388ff' text-anchor='end'>DrStrange " + ov.dr_strange.direction + " " + (dsm >= 0 ? "+" : "") + dsm + "%</text>";
      }
    }
    /* QUANTIZED-FEED banner — the MOG class, named instead of mystifying */
    var qz = quantized(ys);
    if (qz) {
      s += "<rect x='" + padL + "' y='" + padT + "' width='" + iw + "' height='16' fill='#d4af37' opacity='.13'/>";
      s += "<text x='" + (padL + iw / 2).toFixed(1) + "' y='" + (padT + 11) + "' font-size='8.5' fill='#d4af37' text-anchor='middle' font-weight='700'>⚠ QUANTIZED FEED — venue reports only " + qz.levels + " price levels at this precision (" + qz.spreadPct.toFixed(1) + "% apart). The square wave is the feed's tick size, not real trading; integrity rails exclude it from entries.</text>";
    }
    if (withCross) s += "<g class='cross' style='display:none'><line stroke='#ffffff66' stroke-width='1'/><circle r='3.6' fill='#fff'/><g class='ctip'></g></g>";
    s += "</svg>";
    return { svg: s, rows: rows, all: all, X: X, Y: Y, w: w, h: h, up: up, st: stats(rows), sw: sw, ext: ext, srec: srec, ciR: ciR, fpc: fpc, cadM: cadM, nextPk: nextPk, qz: qz };
  }

  function trend(rows) {
    if (!rows || rows.length < 6) return { dir: "flat", label: "—", slopePct: 0 };
    var n = rows.length, third = Math.max(2, Math.floor(n / 3));
    var early = rows.slice(0, third).map(function (r) { return r[1]; });
    var late = rows.slice(n - third).map(function (r) { return r[1]; });
    var ea = early.reduce(function (a, b) { return a + b; }, 0) / early.length;
    var la = late.reduce(function (a, b) { return a + b; }, 0) / late.length;
    var slope = (la / ea - 1) * 100;
    var dir = slope > 1.2 ? "up" : slope < -1.2 ? "down" : "flat";
    var label = dir === "up" ? "UPTREND ▲" : dir === "down" ? "DOWNTREND ▼" : "SIDEWAYS →";
    return { dir: dir, label: label, slopePct: Math.round(slope * 10) / 10 };
  }
  function bounceExpect(tr) {
    if (tr.dir === "down") return "downtrend → expect a WEAKER bounce; favor the safe/accuracy target";
    if (tr.dir === "up") return "uptrend → bounces tend to run; the aggressive target can pay";
    return "sideways → mean-reversion plays cleanest here";
  }

  function agreeChip(c) {
    var srec = c.srec; if (!srec || !srec.agreement) return "";
    var a = srec.agreement, v = a.verdict || "—", sp2 = a.worst_spread_pct;
    var colr = v === "AGREE" ? "#16c784" : v === "DISAGREE" ? "#ea3943" : "#9aa4b8";
    var age = SRCMETA.at ? " · checked " + fmtAge(Date.now() - SRCMETA.at) : "";
    return "<span style='background:" + colr + "18;color:" + colr + ";border:1px solid " + colr + "55;padding:1px 7px;border-radius:10px;font-size:10.5px;font-weight:700'>vs outside venues " + (sp2 != null ? ((sp2 >= 0 ? "+" : "") + (+sp2).toFixed(3) + "% ") : "") + v + age + "</span>";
  }

  function head(sym, c) {
    var st = c.st, col = c.up ? "#16c784" : "#ea3943", tr = trend(c.rows);
    var tcol = tr.dir === "up" ? "#16c784" : tr.dir === "down" ? "#ea3943" : "#9aa4b8";
    var gr = rec(GEO, canon(sym)) || {}, gv = gr.verdict, gcol = gv === "TRADEABLE" ? "#16c784" : (gv && gv.indexOf("UNTRADEABLE") === 0) ? "#ea3943" : "#9aa4b8";
    var H = "<div style='display:flex;align-items:baseline;gap:10px;flex-wrap:wrap'><span style='font-size:18px;font-weight:800'>" + sym + "</span><span style='font-size:18px;font-weight:800'>" + fmtP(st.close) + "</span><span style='color:" + col + ";font-weight:700'>" + (st.chgP >= 0 ? "▲ +" : "▼ ") + st.chgP.toFixed(2) + "% (" + (st.chg >= 0 ? "+" : "") + fmtP(st.chg) + ")</span><span style='background:" + tcol + "22;color:" + tcol + ";border:1px solid " + tcol + "55;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:700'>" + tr.label + " " + (tr.slopePct >= 0 ? "+" : "") + tr.slopePct + "%</span>";
    if (gv) H += "<span style='background:" + gcol + "18;color:" + gcol + ";border:1px solid " + gcol + "55;padding:1px 7px;border-radius:10px;font-size:10.5px;font-weight:700'>geometry " + gv + "</span>";
    H += agreeChip(c);
    H += "</div>";
    return H;
  }

  function statsPanel(sym, c) {
    sym = canon(sym);
    var st = c.st, p = POS[sym] || {}, ry = rec(RHY, sym) || {}, sw = c.sw || {}, ciR = c.ciR || {}, fpc = c.fpc, gr = rec(GEO, sym) || {};
    function row(k, v, cls) { return "<div style='display:flex;justify-content:space-between;gap:12px;padding:3px 0;border-bottom:1px solid #ffffff0d'><span style='color:#8b93a7'>" + k + "</span><span style='font-weight:600;text-align:right" + (cls ? ";color:" + cls : "") + "'>" + v + "</span></div>"; }
    var H = "<div style='font-size:12px'>";
    var tr = trend(c.rows), tcol = tr.dir === "up" ? "#16c784" : tr.dir === "down" ? "#ea3943" : "#9aa4b8";
    H += "<div style='padding:6px 8px;margin-bottom:8px;border:1px solid " + tcol + "44;border-radius:6px;background:" + tcol + "11'>";
    H += "<div style='font-weight:700;color:" + tcol + "'>" + tr.label + " (" + (tr.slopePct >= 0 ? "+" : "") + tr.slopePct + "% over view)</div>";
    H += "<div style='font-size:11px;color:#9aa4b8;margin-top:2px'>" + bounceExpect(tr) + "</div></div>";

    /* TRAJECTORY LADDER — every window, from the tape, always available */
    var lad = ladder(c.all);
    if (lad.length) {
      H += "<div style='font-weight:700;color:#cfd6e4;margin:2px 0 4px'>TRAJECTORY (multi-window)</div><div style='display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px'>";
      lad.forEach(function (L) { var lc = L.pct >= 0 ? "#16c784" : "#ea3943"; H += "<span style='border:1px solid " + lc + "44;color:" + lc + ";padding:1px 6px;border-radius:4px;font-size:10px'>" + L.w + " <b>" + (L.pct >= 0 ? "+" : "") + L.pct.toFixed(2) + "%</b></span>"; });
      H += "</div>";
    }

    /* STRUCTURE — peaks, cadence, next peak ETA, floors/ceilings, source-labelled */
    var srcLbl = (ciR.peaks && ciR.peaks.length) ? "engine (CHART_INTEL)" : "view-detected · same tape, same math";
    var lastPk = sw.lastPeak, cadM = c.cadM, nextPk = c.nextPk;
    H += "<div style='font-weight:700;color:#cfd6e4;margin:6px 0 4px'>STRUCTURE <span style='font-weight:400;font-size:9.5px;color:#6b7488'>(" + srcLbl + ")</span></div>";
    H += row("Peaks / troughs (view)", ((sw.peaks || []).length) + " ▲ · " + ((sw.troughs || []).length) + " ▼");
    if (lastPk) H += row("Last peak", fmtP(lastPk.px) + " · " + fmtDateTime(lastPk.t));
    H += row("Peak trajectory", sw.peakTraj || "—", sw.peakTraj === "RISING" ? "#16c784" : sw.peakTraj === "FALLING" ? "#ea3943" : null);
    H += row("Trough trajectory", sw.trghTraj || "—", sw.trghTraj === "RISING" ? "#16c784" : sw.trghTraj === "FALLING" ? "#ea3943" : null);
    H += row("Heartbeat (peak rhythm)", cadM ? (cadM >= 60 ? (cadM / 60).toFixed(1) + "h" : cadM + "m") + " between peaks" : "learning");
    H += row("Next peak ETA", nextPk ? fmtDateTime(nextPk) + " · " + fmtEta(nextPk - Date.now()) : "—", "#b388ff");
    if ((sw.floors || []).length) H += row("Nearest floor", fmtP(sw.floors[0].level) + " · tested " + sw.floors[0].tested + "×", "#39d353");
    if ((sw.ceilings || []).length) H += row("Nearest ceiling", fmtP(sw.ceilings[0].level) + " · tested " + sw.ceilings[0].tested + "×", "#ea3943");

    /* FINGERPRINT — its own custom fit (674/674 fitted; this is that fit, drawn) */
    if (fpc && (fpc.fit || fpc.fp)) {
      var ft = fpc.fit || {}, fpp = fpc.fp || {};
      H += "<div style='font-weight:700;color:#4da3ff;margin:8px 0 4px'>🧬 FINGERPRINT (its own bar)</div>";
      if (ft.entry != null) H += row("Buys its dip", (ft.entry * 100).toFixed(2) + "% → aims +" + ((ft.target || 0) * 100).toFixed(2) + "%", "#4da3ff");
      if (ft.stop != null) H += row("Its stop", (ft.stop * 100).toFixed(2) + "%");
      if (fpp.bounce_reliability != null) H += row("Bounce reliability", Math.round(fpp.bounce_reliability * 100) + "%", fpp.bounce_reliability >= 0.6 ? "#16c784" : "#d4af37");
      if (fpc.summary) H += "<div style='font-size:10px;color:#9aa4b8;margin:3px 0'>" + fpc.summary + "</div>";
    }

    /* GEOMETRY — the win rate this shape demands vs the name's measured floor */
    if (gr.verdict) {
      H += "<div style='font-weight:700;color:#d4af37;margin:8px 0 4px'>📐 GEOMETRY GATE</div>";
      H += row("Verdict", gr.verdict, gr.verdict === "TRADEABLE" ? "#16c784" : "#ea3943");
      if (gr.p_star_pct != null) H += row("Needs to win", gr.p_star_pct + "%", "#d4af37");
      if (gr.p_floor_pct != null) H += row("Measured floor", gr.p_floor_pct + "%", (gr.p_floor_pct >= (gr.p_star_pct || 999)) ? "#16c784" : "#ea3943");
    }

    /* EXTERNAL SOURCES — real venues, time-aligned agreement */
    if (c.srec && c.srec.providers && Object.keys(c.srec.providers).length) {
      H += "<div style='font-weight:700;color:#f7931a;margin:8px 0 4px'>🌐 OUTSIDE VENUES (drawn on chart)</div>";
      var per = (c.srec.agreement || {}).per_provider || {};
      Object.keys(c.srec.providers).forEach(function (lab) {
        var a2 = per[lab] || {}, v2 = a2.verdict || "—", spd = a2.spread_pct;
        H += row(lab, (spd != null ? ((spd >= 0 ? "+" : "") + (+spd).toFixed(3) + "% · ") : "") + v2, v2 === "AGREE" ? "#16c784" : v2 === "DISAGREE" ? "#ea3943" : null);
      });
      H += "<div style='font-size:9.5px;color:#6b7488;margin-top:2px'>aligned prints ≤15m apart" + (SRCMETA.at ? " · fetched " + fmtAge(Date.now() - SRCMETA.at) : "") + " · absent venue = absent line, never invented</div>";
    } else if (c.srec && c.srec.agreement) {
      H += "<div style='font-size:10px;color:#6b7488;margin:6px 0'>outside venues: " + (c.srec.agreement.why || c.srec.agreement.verdict || "—") + "</div>";
    }

    if (c.qz) {
      H += "<div style='margin:8px 0;padding:6px 8px;border:1px solid #d4af3755;border-radius:6px;background:#d4af3711;font-size:10.5px;color:#d4af37'><b>⚠ QUANTIZED FEED.</b> Only " + c.qz.levels + " representable price levels in view (" + c.qz.spreadPct.toFixed(1) + "% apart) — a precision limit of the venue feed, not trading. The square-wave shape is the feed's tick size; freshness/integrity rails keep it out of entries and learning.</div>";
    }

    try {
      // data source: CONFIDENCE_CARDS.json — loaded once by index.html into window.__SIL_CARDS
      var CC = (window.__SIL_CARDS || {})[sym];
      if (CC) {
        var _f = function(x,d){ return (x==null?'\u2014':(typeof x==='number'?x.toFixed(d==null?2:d):x)); };
        H += "<div style='font-weight:700;color:#d4af37;margin:10px 0 4px'>CONFIDENCE CARD</div>";
        H += "<div style='font-size:10px;line-height:1.55'>"
          + "confidence <b>" + Math.round((CC.confidence||0)*100) + "%</b> \u00b7 rhythm-tradeable <b>" + Math.round((CC.rhythm_tradeability||0)*100) + "%</b> \u00b7 compounder <b>" + _f(CC.compounder_score,3) + "</b><br>"
          + "cycle <b>" + _f(CC.cycle_min,0) + "m</b> \u00b7 expected hold <b>" + _f(CC.expected_hold_min,0) + "m</b> \u00b7 swing <b>" + _f(CC.amplitude_pct) + "%</b><br>"
          + "its own bar: dip \u2265 <b>" + _f(CC.vol_native_bar_pct) + "%</b> (\u03c31h " + _f(CC.sigma1h_pct) + "%) \u00b7 fp dip " + _f(CC.typical_dip_pct) + "% \u2192 bounce " + _f(CC.typical_bounce_pct) + "%<br>"
          + "bounce likelihood <b>" + (CC.bounce_reliability==null?'\u2014':Math.round(CC.bounce_reliability*100)+'%') + "</b> \u00b7 MTF " + _f(CC.mtf_confluence,2) + " \u00b7 mom h1 " + _f(CC.momentum&&CC.momentum.h1) + "% / d1 " + _f(CC.momentum&&CC.momentum.d1) + "%<br>"
          + "timing: buy " + (CC.timing_best_buy||'\u2014') + " \u00b7 sell " + (CC.timing_best_sell||'\u2014') + " \u00b7 our record: <b>" + (CC.book_win_pct==null?'no trades yet':(CC.book_wins+'/'+CC.book_trades+' ('+CC.book_win_pct+'%) $'+_f(CC.book_pnl_usd))) + "</b>"
          + "</div>";
      }
    } catch(e) {}
    H += "<div style='font-weight:700;color:#cfd6e4;margin:8px 0 6px'>PERFORMANCE (this view)</div>";
    H += row("Open", fmtP(st.open));
    H += row("Last", fmtP(st.close));
    H += row("Change", (st.chg >= 0 ? "+" : "") + fmtP(st.chg) + " (" + st.chgP.toFixed(2) + "%)", st.chg >= 0 ? "#16c784" : "#ea3943");
    H += row("Period High", fmtP(st.hi) + " · " + fmtDateTime(st.hiAt));
    H += row("Period Low", fmtP(st.lo) + " · " + fmtDateTime(st.loAt));
    H += row("Range", fmtP(st.range) + " (" + st.rangeP.toFixed(2) + "%)");
    H += row("24h High / Low", (st.hi24 != null ? fmtP(st.hi24) : "—") + " / " + (st.lo24 != null ? fmtP(st.lo24) : "—"));
    H += row("Average", fmtP(st.avg));
    H += row("Volatility (σ/step)", st.vol.toFixed(3) + "%");
    H += row("Data points", st.n + " · " + fmtDateTime(st.fromT).split(",")[0] + "→" + fmtDateTime(st.toT).split(",")[0]);
    if (p.book) {
      var dT = p.target ? (p.target / st.close - 1) * 100 : null, dS = p.stop ? (p.stop / st.close - 1) * 100 : null;
      H += "<div style='font-weight:700;color:#f7c948;margin:10px 0 6px'>📌 OPEN POSITION · " + p.book.toUpperCase() + "</div>";
      H += row("Entry", fmtP(p.entry));
      H += row("Mark (live)", fmtP(p.mark), "#f7c948");
      H += row("Unrealized", (p.upl >= 0 ? "+" : "") + p.upl + "%", p.upl >= 0 ? "#16c784" : "#ea3943");
      H += row("Target (cash-out)", fmtP(p.target) + (dT != null ? " · " + (dT >= 0 ? "+" : "") + dT.toFixed(2) + "% away" : ""), "#16c784");
      H += row("Stop", fmtP(p.stop) + (dS != null ? " · " + dS.toFixed(2) + "% away" : ""), "#ea3943");
    }
    if (ry.peaks_found) {
      var m = Math.round(ry.median_minutes_between_peaks || 0);
      H += "<div style='font-weight:700;color:#b388ff;margin:10px 0 6px'>🔮 BOUNCE TIMING (engine rhythm)</div>";
      H += row("Peaks detected", ry.peaks_found + " · troughs " + (ry.troughs_found || "—"));
      H += row("Typical gap (peaks)", m >= 60 ? (m / 60).toFixed(1) + "h" : m + "m");
      H += row("Typical amplitude", (ry.typical_peak_amplitude_pct != null ? ry.typical_peak_amplitude_pct + "%" : "—"));
      H += row("Current trend", (ry.current_trend || "—"), ry.current_trend === "up" ? "#16c784" : "#ea3943");
      H += row("Predicted next peak", ry.predicted_next_peak_at ? fmtDateTime(tsParse(ry.predicted_next_peak_at)) : "—", "#b388ff");
    }
    var ov = rec(OV, sym) || {};
    if (ov.dr_strange || ov.conviction || (ov.trades && ov.trades.length)) {
      H += "<div style='font-weight:700;color:#b388ff;margin:10px 0 6px'>🔮 PREDICTIONS & SIGNALS</div>";
      if (ov.dr_strange) H += row("Dr Strange (" + (ov.dr_strange.horizon_days || 3) + "d)", ov.dr_strange.direction + " " + (ov.dr_strange.expected_move_pct >= 0 ? "+" : "") + ov.dr_strange.expected_move_pct + "% · " + Math.round((ov.dr_strange.agreement || 0) * 100) + "% agree", ov.dr_strange.expected_move_pct >= 0 ? "#16c784" : "#ea3943");
      if (ov.conviction) H += row("Conviction", (ov.conviction.signal || "—") + " · " + (ov.conviction.backers || 0) + " agents · " + (ov.conviction.trend || ""), ov.conviction.signal === "BUY" ? "#16c784" : "#9aa4b8");
      if (ov.trades && ov.trades.length) {
        var wins = ov.trades.filter(function (t) { return t.pnl_pct > 0; }).length;
        H += row("Past trades here", ov.trades.length + " · " + wins + "W/" + (ov.trades.length - wins) + "L");
        ov.trades.slice(-3).reverse().forEach(function (t) {
          H += row((t.book || "?") + (t.strategy ? " · " + t.strategy : ""),
                   (t.pnl_pct >= 0 ? "+" : "") + t.pnl_pct + "% · " + fmtDateTime(tsParse(t.exit_t)),
                   t.pnl_pct >= 0 ? "#16c784" : "#ea3943");
        });
      }
    }
    H += "</div>";
    return H;
  }

  var pop;
  function showPop(sym, x, y) {
    if (!READY || !series(sym)) return;
    var c = chartSVG(sym, "1W", 360, 150, false);
    if (!pop) { pop = document.createElement("div"); pop.id = "slm-pop"; pop.style.cssText = "position:fixed;z-index:99998;width:392px;background:#0c1622;border:1px solid #ffffff22;border-radius:10px;box-shadow:0 12px 40px #000a;padding:10px 12px;display:none;pointer-events:none;color:#e8edf5"; document.body.appendChild(pop); }
    var st = c.st || {}, ry = rec(RHY, sym) || {}, cad = c.cadM;
    var quick = st.close != null ? "<div style='display:flex;gap:14px;font-size:10.5px;color:#9aa4b8;margin-top:5px'><span>H " + fmtP(st.hi) + "</span><span>L " + fmtP(st.lo) + "</span><span>σ " + (st.vol || 0).toFixed(2) + "%</span>" + (cad ? "<span style='color:#b388ff'>peak~" + (cad >= 60 ? (cad / 60).toFixed(1) + "h" : cad + "m") + "</span>" : "") + (c.ext.length ? "<span style='color:#f7931a'>" + c.ext.length + " outside venue(s)</span>" : "") + "</div>" : "";
    pop.innerHTML = head(canon(sym), c) + "<div style='height:150px;margin-top:5px'>" + c.svg + "</div>" + quick + "<div style='font-size:10px;color:#6b7488;margin-top:3px'>click for fullscreen + full detail</div>";
    pop.style.display = "block";
    var bw = 392, bh = pop.offsetHeight || 230;
    pop.style.left = Math.min(x + 16, innerWidth - bw - 8) + "px";
    pop.style.top = Math.min(Math.max(8, y - bh / 2), innerHeight - bh - 8) + "px";
  }
  function hidePop() { if (pop) pop.style.display = "none"; }

  var modal, curSym, curTF = "1W";
  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "slm-modal";
    modal.style.cssText = "position:fixed;inset:0;z-index:99999;background:#060d16f5;display:none;align-items:center;justify-content:center;padding:12px";
    modal.innerHTML = "<div style='width:min(1180px,97vw);height:min(720px,94vh);background:#0a1320;border:1px solid #ffffff1f;border-radius:14px;padding:16px 18px;display:flex;flex-direction:column;color:#e8edf5'>" +
      "<div style='display:flex;justify-content:space-between;align-items:start;gap:10px'><div id='slm-hd'></div><button id='slm-x' style='background:#ffffff15;border:0;color:#fff;font-size:18px;width:34px;height:34px;border-radius:8px;cursor:pointer;flex:none'>✕</button></div>" +
      "<div id='slm-tabs' style='display:flex;gap:6px;margin:10px 0'></div>" +
      "<div id='slm-main' style='flex:1;display:flex;gap:16px;min-height:0'><div id='slm-body' style='flex:1;position:relative;min-height:0'></div><div id='slm-stats' style='width:330px;max-width:42%;overflow:auto;flex:none'></div></div>" +
      "<div id='slm-foot' style='font-size:11px;color:#7b8499;margin-top:8px'></div></div>";
    document.body.appendChild(modal);
    modal.addEventListener("click", function (e) { if (e.target === modal || e.target.id === "slm-x") modal.style.display = "none"; });
    function resp() { var m = modal.querySelector("#slm-main"), sp = modal.querySelector("#slm-stats"); if (!m) return; if (innerWidth < 760) { m.style.flexDirection = "column"; sp.style.width = "100%"; sp.style.maxWidth = "100%"; sp.style.maxHeight = "40%"; } else { m.style.flexDirection = "row"; sp.style.width = "330px"; sp.style.maxWidth = "42%"; sp.style.maxHeight = "none"; } }
    window.addEventListener("resize", function () { resp(); if (modal.style.display === "flex") draw(); });
    modal.__resp = resp;
    return modal;
  }
  function draw() {
    var host = modal.querySelector("#slm-body"), W = host.clientWidth || 760, H = host.clientHeight || 420;
    var c = chartSVG(curSym, curTF, W, H, true);
    host.innerHTML = c.svg;
    modal.querySelector("#slm-hd").innerHTML = head(curSym, c);
    modal.querySelector("#slm-stats").innerHTML = c.st ? statsPanel(curSym, c) : "";
    var legend = "<div style='display:flex;gap:12px;flex-wrap:wrap;font-size:10.5px;margin-bottom:3px'>"
      + "<span><span style='color:#9aa4b8'>▲</span> buy</span>"
      + "<span><span style='color:#16c784'>▼</span>/<span style='color:#ea3943'>▼</span> sell (win/loss)</span>"
      + "<span style='color:#ea3943'>▲ peak</span><span style='color:#39d353'>▼ trough</span>"
      + "<span style='color:#39d353'>┄ floor ·N×</span><span style='color:#ea3943'>┄ ceiling ·N×</span>"
      + "<span style='color:#4da3ff'>┈ fp dip / <span style='color:#7ee787'>fp bounce</span></span>"
      + "<span style='color:#f7c948'>━ target / cash-out</span>"
      + "<span style='color:#ea3943'>┈ stop</span>"
      + "<span style='color:#b388ff'>┈ Dr Strange / next-peak ETA</span>"
      + (c.ext || []).map(function (e2) { return "<span style='color:" + e2.col + "'>╌ " + e2.lab + " (outside venue)</span>"; }).join("")
      + "</div>";
    var srcBits = (c.ext && c.ext.length ? " · " + c.ext.length + " outside venue(s) overlaid" : (c.srec ? " · outside venues: " + ((c.srec.agreement || {}).verdict || "—") : ""));
    modal.querySelector("#slm-foot").innerHTML = legend + "SILMARIL Everything Chart · " + (c.rows ? c.rows.length : 0) + " pts · " + curTF + " · price + structure (peaks/floors/cadence) + fingerprint fit + geometry + our fills" + srcBits + ((c.sw && c.sw.peaks) ? " · " + c.sw.peaks.length + " peaks in view" : "");
    var svg = host.querySelector("svg.slmchart");
    if (svg && c.rows) cross(svg, c);
  }
  function cross(svg, c) {
    var g = svg.querySelector(".cross"); if (!g) return;
    var ln = g.querySelector("line"), dot = g.querySelector("circle"), tip = g.querySelector(".ctip");
    svg.addEventListener("mousemove", function (e) {
      var b = svg.getBoundingClientRect(), rx = (e.clientX - b.left) / b.width * c.w, best = 0, bd = 1e15;
      for (var i = 0; i < c.rows.length; i++) { var d = Math.abs(c.X(tsParse(c.rows[i][0])) - rx); if (d < bd) { bd = d; best = i; } }
      var rw = c.rows[best], px = c.X(tsParse(rw[0])), py = c.Y(rw[1]);
      g.style.display = ""; ln.setAttribute("x1", px); ln.setAttribute("x2", px); ln.setAttribute("y1", 8); ln.setAttribute("y2", c.h - 26);
      dot.setAttribute("cx", px); dot.setAttribute("cy", py);
      var tx = px > c.w - 150 ? px - 138 : px + 6;
      tip.innerHTML = "<rect x='" + tx + "' y='10' width='134' height='32' rx='4' fill='#06121f' stroke='#ffffff2e'/><text x='" + (tx + 7) + "' y='24' font-size='11' fill='#fff' font-weight='700'>" + fmtP(rw[1]) + "</text><text x='" + (tx + 7) + "' y='36' font-size='9.5' fill='#9aa4b8'>" + fmtDateTime(tsParse(rw[0])) + "</text>";
    });
    svg.addEventListener("mouseleave", function () { g.style.display = "none"; });
  }
  function openFull(sym) {
    if (!READY) { boot().then(function () { openFull(sym); }); return; }
    curSym = canon(sym); ensureModal(); modal.style.display = "flex"; modal.__resp();
    var tabs = modal.querySelector("#slm-tabs"); tabs.innerHTML = ""; tabs.style.flexWrap="wrap"; tabs.style.gap="4px";
    ["5m","15m","30m","1h","2h","4h","8h","12h","1D","2D","3D","1W","2W","1M","2M","YTD","1Y","MAX"].forEach(function (tf) {
      var b = document.createElement("button"); b.textContent = tf;
      b.style.cssText = "background:" + (tf === curTF ? "#2f74ff" : "#ffffff12") + ";border:0;color:#fff;padding:4px 9px;border-radius:6px;cursor:pointer;font-size:11px";
      b.onclick = function () { curTF = tf; tabs.querySelectorAll("button").forEach(function (x) { x.style.background = "#ffffff12"; }); b.style.background = "#2f74ff"; draw(); };
      tabs.appendChild(b);
    });
    setTimeout(draw, 30);
  }

  var TICK_RE = /^\$?([A-Z]{2,6}(?:-USD)?|[A-Z]{1,5}\/USD|[A-Z]{2,8}(?:USDT|USDC))$/;
  function symFromEl(el) {
    if (!el) return null;
    if (el.dataset && el.dataset.sym) return el.dataset.sym;
    var t = (el.textContent || "").trim().replace(/^[^A-Za-z$]*/, "").split(/\s+/)[0];
    if (!t) return null;
    var cands = [t, t.toUpperCase(), t + "-USD", t.toUpperCase() + "-USD"];
    for (var i = 0; i < cands.length; i++) if (series(cands[i])) return canon(cands[i]);
    return null;
  }
  var hasHover = matchMedia("(hover:hover) and (pointer:fine)").matches;
  function delegate() {
    document.addEventListener("mouseover", function (e) { if (!hasHover) return; var el = e.target.closest && e.target.closest(".tick,[data-sym]"); if (!el) return; var s = symFromEl(el); if (s) showPop(s, e.clientX, e.clientY); });
    document.addEventListener("mousemove", function (e) { if (!hasHover || !pop || pop.style.display === "none") return; var el = e.target.closest && e.target.closest(".tick,[data-sym]"); if (!el) { hidePop(); return; } var s = symFromEl(el); if (s) showPop(s, e.clientX, e.clientY); });
    document.addEventListener("mouseout", function (e) { var el = e.target.closest && e.target.closest(".tick,[data-sym]"); if (el) hidePop(); });
    document.addEventListener("click", function (e) { var el = e.target.closest && e.target.closest(".tick,[data-sym]"); if (!el) return; var s = symFromEl(el); if (!s) return; e.preventDefault(); e.stopPropagation(); hidePop(); openFull(s); }, true);
  }
  function autotag(root) {
    if (!READY) return;
    (root || document).querySelectorAll("td,th,span,div,b,strong,a,li").forEach(function (c) {
      if (c.__slm || c.children.length || c.classList.contains("tick") || (c.dataset && c.dataset.sym)) return;
      var m = TICK_RE.exec((c.textContent || "").trim()); if (!m) return;
      var s = symFromEl(c); if (!s) return;
      c.__slm = 1; c.dataset.sym = s; c.style.cursor = "pointer"; c.style.borderBottom = "1px dotted #ffffff40";
      c.title = "Click for fullscreen chart + full detail" + (hasHover ? " · hover to preview" : "");
    });
    (root || document).querySelectorAll("td,li,div,span,p").forEach(function (c) {
      if (c.__slmTx) return;
      var nodes = [];
      for (var n = c.firstChild; n; n = n.nextSibling) if (n.nodeType === 3 && n.nodeValue.trim()) nodes.push(n);
      nodes.forEach(function (n) {
        var txt = n.nodeValue.trim(); var m = TICK_RE.exec(txt); if (!m) return;
        var sym = null, cands = [txt, txt.toUpperCase(), txt + "-USD", txt.toUpperCase() + "-USD"];
        for (var i = 0; i < cands.length; i++) if (series(cands[i])) { sym = canon(cands[i]); break; }
        if (!sym) return;
        var span = document.createElement("span");
        span.className = "tick"; span.dataset.sym = sym; span.textContent = txt;
        span.style.cssText = "cursor:pointer;border-bottom:1px dotted #ffffff40";
        span.title = "Click for chart + detail" + (hasHover ? " · hover to preview" : "");
        n.parentNode.replaceChild(span, n); c.__slmTx = 1;
      });
    });
  }

  window.openChart = function (sym) { openFull(sym); };
  window.SilmarilChart = { boot: boot, openFull: openFull, autotag: autotag, canon: canon, refresh: function () { READY = false; return boot().then(function () { autotag(document); }); } };
  function start() { boot().then(function () { delegate(); autotag(document); setInterval(function () { autotag(document); }, 4000); }); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
