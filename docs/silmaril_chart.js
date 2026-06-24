/* ============================================================================
   SILMARIL CHART — one custom charting engine for the whole site.
   Coinbase / Robinhood / Yahoo / Binance feel, combined, self-built.
   - HOVER over any ticker (desktop) -> floating mini-chart popup
   - CLICK any ticker (desktop+mobile) -> fullscreen chart
   - Overlays: entry / target (cash-out hope) / stop / live mark + peak-rhythm
     prediction (typical time between bounces) + predicted next peak.
   Data: docs/data/price_samples.json (+ paper_sim_live, PEAK_RHYTHM, champions).
   No external libs. Works on index, paper_sim, and legacy dashboards.
   ============================================================================ */
(function () {
  if (window.__silmarilChartBooted) return;
  window.__silmarilChartBooted = true;

  var DATA = {};          // sym -> [[t,price],...]
  var POS = {};           // sym -> {entry,target,stop,mark,book}
  var RHY = {};           // sym -> peak rhythm
  var READY = false;
  var BASE = (location.pathname.indexOf("/docs/") >= 0) ? "" : "";

  function j(path) {
    return fetch(path + "?t=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function tsParse(s) { var d = new Date(s); return isNaN(d) ? null : d.getTime(); }
  function fmtP(v) {
    if (v == null) return "—";
    var a = Math.abs(v);
    return "$" + (a >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : a >= 1 ? v.toFixed(2) : v.toFixed(a >= 0.01 ? 4 : 6));
  }
  function fmtT(ms) { var d = new Date(ms); return (d.getMonth() + 1) + "/" + d.getDate() + " " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); }

  // ---- load data once -------------------------------------------------------
  function boot() {
    return Promise.all([
      j("data/price_samples.json"), j("data/paper_sim_live.json"),
      j("data/PEAK_RHYTHM.json"), j("data/champion_crypto.json"), j("data/champion_stock.json")
    ]).then(function (r) {
      var ps = r[0], live = r[1], rhy = r[2], cc = r[3], cs = r[4];
      if (ps && ps.samples) DATA = ps.samples;
      // parse target/stop % from champion strategy names like MR_d3_t3_s2
      function ts(nm) { var t = /_t(\d+)/.exec(nm || ""), s = /_s(\d+)/.exec(nm || ""); return [t ? +t[1] : null, s ? +s[1] : null]; }
      var champ = { crypto: cc && cc.name, stock: cs && cs.name };
      if (live) ["crypto", "stock", "metal", "energy"].forEach(function (bk) {
        var b = live[bk] || {}; var arr = b.open_positions || [];
        var p = ts(champ[bk] || (live["champion_" + bk]));
        (Array.isArray(arr) ? arr : []).forEach(function (o) {
          if (!o || !o.sym) return;
          var tgt = p[0] != null && o.entry ? o.entry * (1 + p[0] / 100) : null;
          var stp = p[1] != null && o.entry ? o.entry * (1 - p[1] / 100) : null;
          POS[o.sym] = { entry: o.entry, mark: o.mark, target: tgt, stop: stp, book: bk, tpct: p[0], spct: p[1], upl: o.upl_pct };
        });
      });
      if (rhy && rhy.by_symbol) RHY = rhy.by_symbol;
      READY = true;
    });
  }

  // ---- SVG chart renderer ---------------------------------------------------
  function slice(rows, tf) {
    if (!rows || !rows.length) return [];
    var last = tsParse(rows[rows.length - 1][0]) || Date.now();
    var span = { "1D": 864e5, "3D": 3 * 864e5, "1W": 7 * 864e5, "ALL": 1e15 }[tf] || 1e15;
    return rows.filter(function (r) { var t = tsParse(r[0]); return t && (last - t) <= span && r[1] > 0; });
  }

  function chartSVG(sym, tf, w, h, withCross) {
    var rows = slice(DATA[sym] || [], tf);
    if (rows.length < 2) return { svg: "<div style='padding:24px;color:#888;text-align:center'>No price history for " + sym + "</div>", first: null, last: null };
    var xs = rows.map(function (r) { return tsParse(r[0]); });
    var ys = rows.map(function (r) { return r[1]; });
    var p = POS[sym] || {};
    // include overlay levels in y-range so they're visible
    var extra = [p.entry, p.target, p.stop, p.mark].filter(function (v) { return v != null; });
    var mn = Math.min.apply(null, ys.concat(extra)), mx = Math.max.apply(null, ys.concat(extra));
    var r = (mx - mn) || (mx * 0.01) || 1; mn -= r * 0.08; mx += r * 0.08; r = mx - mn;
    var padL = 4, padR = 58, padT = 8, padB = 18;
    var iw = w - padL - padR, ih = h - padT - padB;
    var X = function (t) { return padL + (t - xs[0]) / ((xs[xs.length - 1] - xs[0]) || 1) * iw; };
    var Y = function (v) { return padT + (mx - v) / r * ih; };
    var up = ys[ys.length - 1] >= ys[0];
    var col = up ? "#16c784" : "#ea3943";
    var pathD = rows.map(function (rw, i) { return (i ? "L" : "M") + X(xs[i]).toFixed(1) + "," + Y(rw[1]).toFixed(1); }).join(" ");
    var areaD = pathD + " L" + X(xs[xs.length - 1]).toFixed(1) + "," + (padT + ih) + " L" + X(xs[0]).toFixed(1) + "," + (padT + ih) + " Z";
    var gid = "g_" + Math.random().toString(36).slice(2, 7);
    var s = "";
    s += "<svg viewBox='0 0 " + w + " " + h + "' width='100%' preserveAspectRatio='none' style='display:block;font-family:inherit' class='slmchart' data-sym='" + sym + "' data-tf='" + tf + "'>";
    s += "<defs><linearGradient id='" + gid + "' x1='0' x2='0' y1='0' y2='1'><stop offset='0' stop-color='" + col + "' stop-opacity='0.28'/><stop offset='1' stop-color='" + col + "' stop-opacity='0'/></linearGradient></defs>";
    // horizontal gridlines + price axis (right)
    [0, .25, .5, .75, 1].forEach(function (f) {
      var yv = mx - f * r, yy = Y(yv);
      s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='#ffffff14'/>";
      s += "<text x='" + (w - padR + 4) + "' y='" + (yy + 3).toFixed(1) + "' font-size='9' fill='#8b93a7'>" + fmtP(yv) + "</text>";
    });
    s += "<path d='" + areaD + "' fill='url(#" + gid + ")'/>";
    s += "<path d='" + pathD + "' fill='none' stroke='" + col + "' stroke-width='1.7'/>";
    // overlays
    function hline(v, color, label, dash) {
      if (v == null) return;
      var yy = Y(v); s += "<line x1='" + padL + "' x2='" + (w - padR) + "' y1='" + yy.toFixed(1) + "' y2='" + yy.toFixed(1) + "' stroke='" + color + "' stroke-width='1' stroke-dasharray='" + (dash || "4 3") + "' opacity='0.9'/>";
      s += "<rect x='" + padL + "' y='" + (yy - 8).toFixed(1) + "' width='" + (label.length * 5.4 + 6) + "' height='12' fill='" + color + "' opacity='0.92' rx='2'/>";
      s += "<text x='" + (padL + 3) + "' y='" + (yy + 1.5).toFixed(1) + "' font-size='8' fill='#06121f' font-weight='700'>" + label + "</text>";
    }
    if (p.entry != null) hline(p.entry, "#9aa4b8", "ENTRY " + fmtP(p.entry));
    if (p.stop != null) hline(p.stop, "#ea3943", "STOP -" + p.spct + "%");
    if (p.target != null) hline(p.target, "#16c784", "TARGET +" + p.tpct + "% (cash-out hope)");
    // live mark dot
    if (p.mark != null) { var my = Y(p.mark); s += "<circle cx='" + (w - padR - 2) + "' cy='" + my.toFixed(1) + "' r='3.2' fill='#f7c948'><animate attributeName='r' values='3.2;5;3.2' dur='1.6s' repeatCount='indefinite'/></circle>"; }
    // peak-rhythm prediction: mark predicted next peak time if within view, else annotate
    var ry = RHY[sym];
    if (ry && ry.predicted_next_peak_at) {
      var pt = tsParse(ry.predicted_next_peak_at);
      if (pt && pt >= xs[0] && pt <= xs[xs.length - 1] + 36e5) {
        var px = Math.min(X(pt), w - padR);
        s += "<line x1='" + px.toFixed(1) + "' x2='" + px.toFixed(1) + "' y1='" + padT + "' y2='" + (padT + ih) + "' stroke='#b388ff' stroke-width='1' stroke-dasharray='2 3'/>";
        s += "<text x='" + (px - 2).toFixed(1) + "' y='" + (padT + 9) + "' font-size='8' fill='#b388ff' text-anchor='end'>next peak~</text>";
      }
    }
    if (withCross) s += "<g class='cross' style='display:none'><line stroke='#ffffff55' stroke-width='1'/><circle r='3.5' fill='#fff'/><g class='ctip'></g></g>";
    s += "</svg>";
    return { svg: s, first: ys[0], last: ys[ys.length - 1], up: up, rows: rows, X: X, Y: Y, w: w, h: h, padR: padR };
  }

  function header(sym, c) {
    var p = POS[sym] || {}, ry = RHY[sym] || {};
    var chg = c.first ? (c.last / c.first - 1) * 100 : 0;
    var col = c.up ? "#16c784" : "#ea3943";
    var h = "<div style='display:flex;align-items:baseline;gap:10px;flex-wrap:wrap'>";
    h += "<span style='font-size:17px;font-weight:800'>" + sym + "</span>";
    h += "<span style='font-size:17px;font-weight:800'>" + fmtP(c.last) + "</span>";
    h += "<span style='color:" + col + ";font-weight:700'>" + (chg >= 0 ? "▲ +" : "▼ ") + chg.toFixed(2) + "%</span>";
    if (p.upl != null) h += "<span style='color:" + (p.upl >= 0 ? "#16c784" : "#ea3943") + ";font-size:12px'>· open " + (p.upl >= 0 ? "+" : "") + p.upl + "%</span>";
    h += "</div>";
    var bits = [];
    if (p.book) bits.push("📌 OPEN in " + p.book.toUpperCase() + " — entry " + fmtP(p.entry) + ", cash-out hope " + fmtP(p.target));
    if (ry.median_minutes_between_peaks) {
      var m = Math.round(ry.median_minutes_between_peaks);
      bits.push("🔮 peaks ~every " + (m >= 60 ? (m / 60).toFixed(1) + "h" : m + "m") + " · trend " + (ry.current_trend || "?") +
        (ry.predicted_next_peak_at ? " · next peak ~" + fmtT(tsParse(ry.predicted_next_peak_at)).split(" ")[1] : ""));
    }
    if (bits.length) h += "<div style='font-size:11px;color:#9aa4b8;margin-top:3px;line-height:1.6'>" + bits.join("<br>") + "</div>";
    return h;
  }

  // ---- popup (hover, desktop) ----------------------------------------------
  var pop;
  function ensurePop() {
    if (pop) return pop;
    pop = document.createElement("div");
    pop.id = "slm-pop";
    pop.style.cssText = "position:fixed;z-index:99998;width:360px;background:#0c1622;border:1px solid #ffffff22;border-radius:10px;box-shadow:0 12px 40px #000a;padding:10px 12px;display:none;pointer-events:none;color:#e8edf5";
    document.body.appendChild(pop);
    return pop;
  }
  function showPop(sym, x, y) {
    if (!READY || !DATA[sym]) return;
    var c = chartSVG(sym, "1W", 336, 130, false);
    var el = ensurePop();
    el.innerHTML = header(sym, c) + "<div style='margin-top:6px'>" + c.svg + "</div><div style='font-size:10px;color:#6b7488;margin-top:4px'>click for fullscreen · 1W view</div>";
    el.style.display = "block";
    var vw = innerWidth, vh = innerHeight, bw = 360, bh = el.offsetHeight || 200;
    el.style.left = Math.min(x + 16, vw - bw - 8) + "px";
    el.style.top = Math.min(Math.max(8, y - bh / 2), vh - bh - 8) + "px";
  }
  function hidePop() { if (pop) pop.style.display = "none"; }

  // ---- fullscreen modal (click) --------------------------------------------
  var modal, curSym, curTF = "1W";
  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "slm-modal";
    modal.style.cssText = "position:fixed;inset:0;z-index:99999;background:#060d16f2;display:none;align-items:center;justify-content:center";
    modal.innerHTML = "<div style='width:min(1000px,96vw);height:min(640px,92vh);background:#0a1320;border:1px solid #ffffff1f;border-radius:14px;padding:16px 18px;display:flex;flex-direction:column;color:#e8edf5'>" +
      "<div style='display:flex;justify-content:space-between;align-items:start;gap:10px'><div id='slm-hd'></div><button id='slm-x' style='background:#ffffff15;border:0;color:#fff;font-size:18px;width:34px;height:34px;border-radius:8px;cursor:pointer'>✕</button></div>" +
      "<div id='slm-tabs' style='display:flex;gap:6px;margin:10px 0'></div>" +
      "<div id='slm-body' style='flex:1;position:relative;min-height:0'></div>" +
      "<div id='slm-foot' style='font-size:11px;color:#7b8499;margin-top:8px'></div></div>";
    document.body.appendChild(modal);
    modal.addEventListener("click", function (e) { if (e.target === modal || e.target.id === "slm-x") modal.style.display = "none"; });
    return modal;
  }
  function drawModal() {
    var host = modal.querySelector("#slm-body");
    var W = host.clientWidth || 920, H = host.clientHeight || 420;
    var c = chartSVG(curSym, curTF, W, H, true);
    host.innerHTML = c.svg;
    modal.querySelector("#slm-hd").innerHTML = header(curSym, c);
    var ry = RHY[curSym] || {};
    modal.querySelector("#slm-foot").innerHTML = "Custom SILMARIL chart · " + (c.rows ? c.rows.length : 0) + " points · " + curTF +
      (ry.peaks_found ? " · " + ry.peaks_found + " peaks detected, typical amplitude " + (ry.typical_peak_amplitude_pct || "?") + "%" : "") +
      " · entry/target(cash-out)/stop + bounce-timing overlaid";
    // crosshair
    var svg = host.querySelector("svg.slmchart");
    if (svg && c.rows) bindCross(svg, c);
  }
  function bindCross(svg, c) {
    var cross = svg.querySelector(".cross"); if (!cross) return;
    var line = cross.querySelector("line"), dot = cross.querySelector("circle"), tip = cross.querySelector(".ctip");
    svg.addEventListener("mousemove", function (e) {
      var pt = svg.getBoundingClientRect(); var rx = (e.clientX - pt.left) / pt.width * c.w;
      // nearest point
      var best = 0, bd = 1e15;
      for (var i = 0; i < c.rows.length; i++) { var d = Math.abs(c.X(tsParse(c.rows[i][0])) - rx); if (d < bd) { bd = d; best = i; } }
      var rw = c.rows[best], px = c.X(tsParse(rw[0])), py = c.Y(rw[1]);
      cross.style.display = ""; line.setAttribute("x1", px); line.setAttribute("x2", px); line.setAttribute("y1", 8); line.setAttribute("y2", c.h - 18);
      dot.setAttribute("cx", px); dot.setAttribute("cy", py);
      var tx = px > c.w - 130 ? px - 120 : px + 6;
      tip.innerHTML = "<rect x='" + tx + "' y='10' width='118' height='30' rx='4' fill='#06121f' stroke='#ffffff2a'/>" +
        "<text x='" + (tx + 6) + "' y='24' font-size='10' fill='#fff' font-weight='700'>" + fmtP(rw[1]) + "</text>" +
        "<text x='" + (tx + 6) + "' y='35' font-size='9' fill='#9aa4b8'>" + fmtT(tsParse(rw[0])) + "</text>";
    });
    svg.addEventListener("mouseleave", function () { cross.style.display = "none"; });
  }
  function openFull(sym) {
    if (!READY) { boot().then(function () { openFull(sym); }); return; }
    curSym = sym;
    ensureModal(); modal.style.display = "flex";
    var tabs = modal.querySelector("#slm-tabs"); tabs.innerHTML = "";
    ["1D", "3D", "1W", "ALL"].forEach(function (tf) {
      var b = document.createElement("button");
      b.textContent = tf;
      b.style.cssText = "background:" + (tf === curTF ? "#2f74ff" : "#ffffff12") + ";border:0;color:#fff;padding:5px 12px;border-radius:7px;cursor:pointer;font-size:12px";
      b.onclick = function () { curTF = tf; drawModal(); tabs.querySelectorAll("button").forEach(function (x) { x.style.background = "#ffffff12"; }); b.style.background = "#2f74ff"; };
      tabs.appendChild(b);
    });
    setTimeout(drawModal, 30);
  }

  // ---- ticker detection + delegation ---------------------------------------
  var TICK_RE = /^\$?([A-Z]{2,6}(?:-USD)?|[A-Z]{1,5}\/USD)$/;
  function symFromEl(el) {
    if (!el) return null;
    if (el.dataset && el.dataset.sym) return el.dataset.sym;
    var t = (el.textContent || "").trim().replace(/^[^A-Za-z$]*/, "").split(/\s+/)[0];
    if (t && DATA[t]) return t;
    if (t && DATA[t + "-USD"]) return t + "-USD";
    var up = t.toUpperCase();
    if (DATA[up]) return up; if (DATA[up + "-USD"]) return up + "-USD";
    return null;
  }
  function isTicker(el) {
    if (!el || !el.classList) return false;
    if (el.classList.contains("tick") || (el.dataset && el.dataset.sym)) return true;
    return false;
  }
  var hasHover = matchMedia("(hover:hover) and (pointer:fine)").matches;
  function delegate() {
    document.addEventListener("mouseover", function (e) {
      if (!hasHover) return;
      var el = e.target.closest ? e.target.closest(".tick,[data-sym]") : null;
      if (!el) return; var sym = symFromEl(el); if (!sym) return;
      showPop(sym, e.clientX, e.clientY);
    });
    document.addEventListener("mousemove", function (e) {
      if (!hasHover || !pop || pop.style.display === "none") return;
      var el = e.target.closest ? e.target.closest(".tick,[data-sym]") : null;
      if (!el) { hidePop(); return; }
      var sym = symFromEl(el); if (sym) showPop(sym, e.clientX, e.clientY);
    });
    document.addEventListener("mouseout", function (e) {
      var el = e.target.closest ? e.target.closest(".tick,[data-sym]") : null;
      if (el) hidePop();
    });
    document.addEventListener("click", function (e) {
      var el = e.target.closest ? e.target.closest(".tick,[data-sym]") : null;
      if (!el) return; var sym = symFromEl(el); if (!sym) return;
      e.preventDefault(); e.stopPropagation(); hidePop(); openFull(sym);
    }, true);
  }
  // auto-tag: scan text nodes in tables/cards for ticker-looking tokens, wrap them
  function autotag(root) {
    if (!READY) return;
    var cells = (root || document).querySelectorAll("td,th,span,div,b,strong,a,li");
    cells.forEach(function (c) {
      if (c.__slm || c.children.length || c.classList.contains("tick") || (c.dataset && c.dataset.sym)) return;
      var txt = (c.textContent || "").trim();
      var m = TICK_RE.exec(txt);
      if (!m) return;
      var sym = symFromEl(c);
      if (!sym) return;
      c.__slm = 1; c.dataset.sym = sym;
      c.style.cursor = "pointer"; c.style.borderBottom = "1px dotted #ffffff40";
      c.title = "Click for fullscreen chart" + (hasHover ? " · hover to preview" : "");
    });
  }

  // ---- public API + boot ----------------------------------------------------
  window.openChart = function (sym) { openFull(sym); };          // replaces legacy openChart (entry/mark args ignored; pulled from POS)
  window.SilmarilChart = {
    boot: boot, openFull: openFull, autotag: autotag,
    refresh: function () { READY = false; return boot().then(function () { autotag(document); }); }
  };
  function start() {
    boot().then(function () {
      delegate(); autotag(document);
      // re-tag periodically as dashboards re-render their tables
      setInterval(function () { autotag(document); }, 4000);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
