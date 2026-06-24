/* ============================================================================
   SILMARIL CHART v2 — a real replacement for Yahoo / Coinbase / Robinhood / Binance.
   Now with: X-AXIS DATES & TIMES, a Yahoo-style DETAIL PANEL (every stat derivable
   from real price data — no synthetic volume), full crosshair (date+time+price),
   timeframe tabs, and the SILMARIL prediction overlays (entry / target=cash-out /
   stop / live mark / bounce-timing + predicted next peak).
   HOVER any ticker (desktop) -> mini chart w/ axis. CLICK -> fullscreen chart+stats.
   ============================================================================ */
(function () {
  if (window.__silmarilChartBooted) return;
  window.__silmarilChartBooted = true;

  var DATA = {}, POS = {}, RHY = {}, OV = {}, READY = false;
  var MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function j(p) { return fetch(p + "?t=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function tsParse(s) { var d = new Date(s); return isNaN(d) ? null : d.getTime(); }
  function fmtP(v) { if (v == null) return "—"; var a = Math.abs(v); return "$" + (a >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : a >= 1 ? v.toFixed(2) : v.toFixed(a >= 0.01 ? 4 : 6)); }
  function pad(n) { return String(n).padStart(2, "0"); }
  function fmtDateTime(ms) { var d = new Date(ms); return MO[d.getMonth()] + " " + d.getDate() + ", " + pad(d.getHours()) + ":" + pad(d.getMinutes()); }
  function fmtAxis(ms, span) { var d = new Date(ms); if (span <= 864e5) return pad(d.getHours()) + ":" + pad(d.getMinutes()); if (span <= 7 * 864e5) return MO[d.getMonth()] + " " + d.getDate() + " " + pad(d.getHours()) + "h"; return MO[d.getMonth()] + " " + d.getDate(); }
  function spanMs(tf) { return { "1D": 864e5, "3D": 3 * 864e5, "1W": 7 * 864e5, "ALL": 1e15 }[tf] || 1e15; }

  function boot() {
    return Promise.all([j("data/price_samples.json"), j("data/paper_sim_live.json"), j("data/PEAK_RHYTHM.json"), j("data/champion_crypto.json"), j("data/champion_stock.json"), j("data/CHART_OVERLAYS.json")])
      .then(function (r) {
        var ps = r[0], live = r[1], rhy = r[2], cc = r[3], cs = r[4], ovf = r[5];
        if (ps && ps.samples) DATA = ps.samples;
        if (ovf && ovf.symbols) OV = ovf.symbols;
        function ts(nm) { var t = /_t(\d+)/.exec(nm || ""), s = /_s(\d+)/.exec(nm || ""); return [t ? +t[1] : null, s ? +s[1] : null]; }
        var champ = { crypto: cc && cc.name, stock: cs && cs.name };
        if (live) ["crypto", "stock", "metal", "energy"].forEach(function (bk) {
          var b = live[bk] || {}, arr = b.open_positions || [], p = ts(champ[bk] || live["champion_" + bk]);
          (Array.isArray(arr) ? arr : []).forEach(function (o) {
            if (!o || !o.sym) return;
            POS[o.sym] = { entry: o.entry, mark: o.mark, book: bk, tpct: p[0], spct: p[1], upl: o.upl_pct,
              target: (p[0] != null && o.entry) ? o.entry * (1 + p[0] / 100) : null,
              stop: (p[1] != null && o.entry) ? o.entry * (1 - p[1] / 100) : null };
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

  function chartSVG(sym, tf, w, h, withCross) {
    var rows = slice(DATA[sym] || [], tf);
    if (rows.length < 2) return { svg: "<div style='padding:30px;color:#8b93a7;text-align:center'>No price history for " + sym + "</div>" };
    var xs = rows.map(function (r) { return tsParse(r[0]); }), ys = rows.map(function (r) { return r[1]; });
    var p = POS[sym] || {}, extra = [p.entry, p.target, p.stop, p.mark].filter(function (v) { return v != null; });
    var mn = Math.min.apply(null, ys.concat(extra)), mx = Math.max.apply(null, ys.concat(extra));
    var rr = (mx - mn) || mx * 0.01 || 1; mn -= rr * 0.08; mx += rr * 0.08; rr = mx - mn;
    var padL = 4, padR = 62, padT = 8, padB = 26, iw = w - padL - padR, ih = h - padT - padB;
    var X = function (t) { return padL + (t - xs[0]) / ((xs[xs.length - 1] - xs[0]) || 1) * iw; };
    var Y = function (v) { return padT + (mx - v) / rr * ih; };
    var up = ys[ys.length - 1] >= ys[0], col = up ? "#16c784" : "#ea3943";
    var line = rows.map(function (rw, i) { return (i ? "L" : "M") + X(xs[i]).toFixed(1) + "," + Y(rw[1]).toFixed(1); }).join(" ");
    var area = line + " L" + X(xs[xs.length - 1]).toFixed(1) + "," + (padT + ih) + " L" + X(xs[0]).toFixed(1) + "," + (padT + ih) + " Z";
    var gid = "g" + Math.random().toString(36).slice(2, 7), sp = spanMs(tf) === 1e15 ? (xs[xs.length - 1] - xs[0]) : spanMs(tf);
    var s = "<svg viewBox='0 0 " + w + " " + h + "' width='100%' height='100%' preserveAspectRatio='none' class='slmchart' style='display:block;font-family:inherit'>";
    s += "<defs><linearGradient id='" + gid + "' x1='0' x2='0' y1='0' y2='1'><stop offset='0' stop-color='" + col + "' stop-opacity='.28'/><stop offset='1' stop-color='" + col + "' stop-opacity='0'/></linearGradient></defs>";
    [0, .25, .5, .75, 1].forEach(function (f) { var yv = mx - f * rr, yy = Y(yv); s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='#ffffff12'/><text x='" + (w - padR + 5) + "' y='" + (yy + 3).toFixed(1) + "' font-size='9.5' fill='#8b93a7'>" + fmtP(yv) + "</text>"; });
    var nT = w < 420 ? 4 : 6;
    for (var k = 0; k <= nT; k++) {
      var tt = xs[0] + (xs[xs.length - 1] - xs[0]) * k / nT, xx = X(tt);
      s += "<line x1='" + xx.toFixed(1) + "' x2='" + xx.toFixed(1) + "' y1='" + padT + "' y2='" + (padT + ih) + "' stroke='#ffffff0a'/>";
      var anchor = k === 0 ? "start" : k === nT ? "end" : "middle";
      s += "<text x='" + xx.toFixed(1) + "' y='" + (h - 8) + "' font-size='9.5' fill='#8b93a7' text-anchor='" + anchor + "'>" + fmtAxis(tt, sp) + "</text>";
    }
    s += "<path d='" + area + "' fill='url(#" + gid + ")'/><path d='" + line + "' fill='none' stroke='" + col + "' stroke-width='1.7'/>";
    function hline(v, c, lbl, dash) { if (v == null) return; var yy = Y(v); s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='" + c + "' stroke-width='1' stroke-dasharray='" + (dash || "4 3") + "' opacity='.9'/><rect x='" + padL + "' y='" + (yy - 8).toFixed(1) + "' width='" + (lbl.length * 5.3 + 6) + "' height='12' rx='2' fill='" + c + "' opacity='.92'/><text x='" + (padL + 3) + "' y='" + (yy + 1.5).toFixed(1) + "' font-size='8' fill='#06121f' font-weight='700'>" + lbl + "</text>"; }
    if (p.entry != null) hline(p.entry, "#9aa4b8", "ENTRY " + fmtP(p.entry));
    if (p.stop != null) hline(p.stop, "#ea3943", "STOP -" + p.spct + "%");
    if (p.target != null) hline(p.target, "#16c784", "TARGET +" + p.tpct + "% cash-out");
    if (p.mark != null) { var my = Y(p.mark); s += "<circle cx='" + (w - padR - 2) + "' cy='" + my.toFixed(1) + "' r='3.2' fill='#f7c948'><animate attributeName='r' values='3.2;5;3.2' dur='1.6s' repeatCount='indefinite'/></circle>"; }
    var ry = RHY[sym];
    if (ry && ry.predicted_next_peak_at) { var pt = tsParse(ry.predicted_next_peak_at); if (pt && pt >= xs[0] && pt <= xs[xs.length - 1] + 36e5) { var px = Math.min(X(pt), w - padR); s += "<line x1='" + px.toFixed(1) + "' x2='" + px.toFixed(1) + "' y1='" + padT + "' y2='" + (padT + ih) + "' stroke='#b388ff' stroke-width='1' stroke-dasharray='2 3'/><text x='" + (px - 2).toFixed(1) + "' y='" + (padT + 9) + "' font-size='8' fill='#b388ff' text-anchor='end'>next peak~</text>"; } }
    // ---- SILMARIL overlays: closed-trade markers + GOLD target + Dr Strange ----
    var ov = OV[sym] || {};
    var goldTgt = (p.target != null) ? null : null;   // open-position target already drawn green
    if (p.target == null && ov.trades && ov.trades.length) {
      var lt = ov.trades[ov.trades.length - 1];
      if (lt.target != null) hline(lt.target, "#f7c948", "TARGET (cash-out) " + fmtP(lt.target));
    }
    (ov.trades || []).forEach(function (t) {
      var et = tsParse(t.entry_t), xt = tsParse(t.exit_t);
      if (et && et >= xs[0] && et <= xs[xs.length - 1] && t.entry != null) {
        var ex = X(et), ey = Y(t.entry);
        s += "<path d='M" + ex.toFixed(1) + "," + (ey + 6).toFixed(1) + " l-4,7 l8,0 z' fill='#9aa4b8' opacity='.95'/>";
      }
      if (xt && xt >= xs[0] && xt <= xs[xs.length - 1] && t.exit != null) {
        var xx2 = X(xt), xy = Y(t.exit), c2 = t.pnl_pct >= 0 ? "#16c784" : "#ea3943";
        s += "<path d='M" + xx2.toFixed(1) + "," + (xy - 6).toFixed(1) + " l-4,-7 l8,0 z' fill='" + c2 + "'/>";
      }
    });
    if (ov.dr_strange && ov.dr_strange.expected_move_pct != null) {
      var dsm = ov.dr_strange.expected_move_pct, cur = ys[ys.length - 1], projP = cur * (1 + dsm / 100);
      if (projP >= mn && projP <= mx) {
        var py2 = Y(projP);
        s += "<line x1='" + (w - padR - 64).toFixed(1) + "' x2='" + (w - padR).toFixed(1) + "' y1='" + Y(cur).toFixed(1) + "' y2='" + py2.toFixed(1) + "' stroke='#b388ff' stroke-width='1.3' stroke-dasharray='3 2'/><circle cx='" + (w - padR).toFixed(1) + "' cy='" + py2.toFixed(1) + "' r='2.6' fill='#b388ff'/><text x='" + (w - padR - 2).toFixed(1) + "' y='" + (py2 - 4).toFixed(1) + "' font-size='8' fill='#b388ff' text-anchor='end'>DrStrange " + ov.dr_strange.direction + " " + (dsm >= 0 ? "+" : "") + dsm + "%</text>";
      }
    }
    if (withCross) s += "<g class='cross' style='display:none'><line stroke='#ffffff66' stroke-width='1'/><circle r='3.6' fill='#fff'/><g class='ctip'></g></g>";
    s += "</svg>";
    return { svg: s, rows: rows, X: X, Y: Y, w: w, h: h, up: up, st: stats(rows) };
  }

  function head(sym, c) {
    var st = c.st, col = c.up ? "#16c784" : "#ea3943";
    return "<div style='display:flex;align-items:baseline;gap:10px;flex-wrap:wrap'><span style='font-size:18px;font-weight:800'>" + sym + "</span><span style='font-size:18px;font-weight:800'>" + fmtP(st.close) + "</span><span style='color:" + col + ";font-weight:700'>" + (st.chgP >= 0 ? "▲ +" : "▼ ") + st.chgP.toFixed(2) + "% (" + (st.chg >= 0 ? "+" : "") + fmtP(st.chg) + ")</span></div>";
  }

  function statsPanel(sym, c) {
    var st = c.st, p = POS[sym] || {}, ry = RHY[sym] || {};
    function row(k, v, cls) { return "<div style='display:flex;justify-content:space-between;gap:12px;padding:3px 0;border-bottom:1px solid #ffffff0d'><span style='color:#8b93a7'>" + k + "</span><span style='font-weight:600" + (cls ? ";color:" + cls : "") + "'>" + v + "</span></div>"; }
    var H = "<div style='font-size:12px'>";
    H += "<div style='font-weight:700;color:#cfd6e4;margin:2px 0 6px'>PERFORMANCE (this view)</div>";
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
      H += "<div style='font-weight:700;color:#b388ff;margin:10px 0 6px'>🔮 BOUNCE TIMING (fingerprint)</div>";
      H += row("Peaks detected", ry.peaks_found + " · troughs " + (ry.troughs_found || "—"));
      H += row("Typical gap (peaks)", m >= 60 ? (m / 60).toFixed(1) + "h" : m + "m");
      H += row("Typical amplitude", (ry.typical_peak_amplitude_pct != null ? ry.typical_peak_amplitude_pct + "%" : "—"));
      H += row("Current trend", (ry.current_trend || "—"), ry.current_trend === "up" ? "#16c784" : "#ea3943");
      H += row("Predicted next peak", ry.predicted_next_peak_at ? fmtDateTime(tsParse(ry.predicted_next_peak_at)) : "—", "#b388ff");
    }
    var ov = OV[sym] || {};
    if (ov.dr_strange || ov.conviction || (ov.trades && ov.trades.length)) {
      H += "<div style='font-weight:700;color:#b388ff;margin:10px 0 6px'>🔮 PREDICTIONS & SIGNALS</div>";
      if (ov.dr_strange) H += row("Dr Strange (" + (ov.dr_strange.horizon_days || 3) + "d)", ov.dr_strange.direction + " " + (ov.dr_strange.expected_move_pct >= 0 ? "+" : "") + ov.dr_strange.expected_move_pct + "% · " + Math.round((ov.dr_strange.agreement || 0) * 100) + "% agree", ov.dr_strange.expected_move_pct >= 0 ? "#16c784" : "#ea3943");
      if (ov.conviction) H += row("Conviction", (ov.conviction.signal || "—") + " · " + (ov.conviction.backers || 0) + " agents · " + (ov.conviction.trend || ""), ov.conviction.signal === "BUY" ? "#16c784" : "#9aa4b8");
      if (ov.trades && ov.trades.length) {
        var wins = ov.trades.filter(function (t) { return t.pnl_pct > 0; }).length;
        H += row("Past trades here", ov.trades.length + " · " + wins + "W/" + (ov.trades.length - wins) + "L");
        var lastT = ov.trades[ov.trades.length - 1];
        H += row("Last exit", (lastT.pnl_pct >= 0 ? "+" : "") + lastT.pnl_pct + "% · " + fmtDateTime(tsParse(lastT.exit_t)), lastT.pnl_pct >= 0 ? "#16c784" : "#ea3943");
      }
    }
    H += "</div>";
    return H;
  }

  var pop;
  function showPop(sym, x, y) {
    if (!READY || !DATA[sym]) return;
    var c = chartSVG(sym, "1W", 360, 150, false);
    if (!pop) { pop = document.createElement("div"); pop.id = "slm-pop"; pop.style.cssText = "position:fixed;z-index:99998;width:392px;background:#0c1622;border:1px solid #ffffff22;border-radius:10px;box-shadow:0 12px 40px #000a;padding:10px 12px;display:none;pointer-events:none;color:#e8edf5"; document.body.appendChild(pop); }
    var st = c.st || {}, ry = RHY[sym] || {};
    var quick = st.close != null ? "<div style='display:flex;gap:14px;font-size:10.5px;color:#9aa4b8;margin-top:5px'><span>H " + fmtP(st.hi) + "</span><span>L " + fmtP(st.lo) + "</span><span>σ " + (st.vol || 0).toFixed(2) + "%</span>" + (ry.median_minutes_between_peaks ? "<span style='color:#b388ff'>peak~" + Math.round(ry.median_minutes_between_peaks) + "m</span>" : "") + "</div>" : "";
    pop.innerHTML = head(sym, c) + "<div style='height:150px;margin-top:5px'>" + c.svg + "</div>" + quick + "<div style='font-size:10px;color:#6b7488;margin-top:3px'>click for fullscreen + full detail</div>";
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
    var ry = RHY[curSym] || {};
    modal.querySelector("#slm-foot").innerHTML = "Custom SILMARIL chart · " + (c.rows ? c.rows.length : 0) + " pts · " + curTF + " · time axis + real OHLC/range/volatility" + (ry.peaks_found ? " · " + ry.peaks_found + " peaks" : "") + " · entry/target(cash-out)/stop + bounce-timing overlaid";
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
    curSym = sym; ensureModal(); modal.style.display = "flex"; modal.__resp();
    var tabs = modal.querySelector("#slm-tabs"); tabs.innerHTML = "";
    ["1D", "3D", "1W", "ALL"].forEach(function (tf) {
      var b = document.createElement("button"); b.textContent = tf;
      b.style.cssText = "background:" + (tf === curTF ? "#2f74ff" : "#ffffff12") + ";border:0;color:#fff;padding:5px 13px;border-radius:7px;cursor:pointer;font-size:12px";
      b.onclick = function () { curTF = tf; tabs.querySelectorAll("button").forEach(function (x) { x.style.background = "#ffffff12"; }); b.style.background = "#2f74ff"; draw(); };
      tabs.appendChild(b);
    });
    setTimeout(draw, 30);
  }

  var TICK_RE = /^\$?([A-Z]{2,6}(?:-USD)?|[A-Z]{1,5}\/USD)$/;
  function symFromEl(el) {
    if (!el) return null;
    if (el.dataset && el.dataset.sym) return el.dataset.sym;
    var t = (el.textContent || "").trim().replace(/^[^A-Za-z$]*/, "").split(/\s+/)[0];
    if (t && DATA[t]) return t; if (t && DATA[t + "-USD"]) return t + "-USD";
    var up = t.toUpperCase(); if (DATA[up]) return up; if (DATA[up + "-USD"]) return up + "-USD"; return null;
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
    // (a) whole-element tickers (e.g. a cell that is exactly "BTC-USD")
    (root || document).querySelectorAll("td,th,span,div,b,strong,a,li").forEach(function (c) {
      if (c.__slm || c.children.length || c.classList.contains("tick") || (c.dataset && c.dataset.sym)) return;
      var m = TICK_RE.exec((c.textContent || "").trim()); if (!m) return;
      var s = symFromEl(c); if (!s) return;
      c.__slm = 1; c.dataset.sym = s; c.style.cursor = "pointer"; c.style.borderBottom = "1px dotted #ffffff40";
      c.title = "Click for fullscreen chart + full detail" + (hasHover ? " · hover to preview" : "");
    });
    // (b) ticker TEXT NODES inside cells that also hold a badge — e.g. "[SELL] DYDX-USD".
    //     This is why hovering past-trade rows did nothing: the symbol was a bare text node.
    (root || document).querySelectorAll("td,li,div,span,p").forEach(function (c) {
      if (c.__slmTx) return;
      var nodes = [];
      for (var n = c.firstChild; n; n = n.nextSibling) if (n.nodeType === 3 && n.nodeValue.trim()) nodes.push(n);
      nodes.forEach(function (n) {
        var txt = n.nodeValue.trim(); var m = TICK_RE.exec(txt); if (!m) return;
        var sym = DATA[txt] ? txt : (DATA[txt + "-USD"] ? txt + "-USD" : (DATA[txt.toUpperCase()] ? txt.toUpperCase() : (DATA[txt.toUpperCase() + "-USD"] ? txt.toUpperCase() + "-USD" : null)));
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
  window.SilmarilChart = { boot: boot, openFull: openFull, autotag: autotag, refresh: function () { READY = false; return boot().then(function () { autotag(document); }); } };
  function start() { boot().then(function () { delegate(); autotag(document); setInterval(function () { autotag(document); }, 4000); }); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
