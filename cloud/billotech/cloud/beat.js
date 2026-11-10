/* Copyright (c) 2026 Billy Sorrells Entertainment LLC · BilloTech Source License 1.1 (free for personal and school use; paid client work needs BilloTech Pro) · billysorrells.com/billotech/license */
/* Billo Forge · Beat — hits, kicks, tempo and Cadence cut lists, in the browser.
   Same maths as billo_fx.py cadence: spectral flux onsets, low-band kicks, autocorrelation tempo with a parabolic refine. */
(function () {
  "use strict";
  function fft(re, im) { // in-place radix-2
    var n = re.length, i, j = 0, k, len, ang, wr, wi, ur, ui, vr, vi, t;
    for (i = 1; i < n; i++) { var bit = n >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit; if (i < j) { t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
    for (len = 2; len <= n; len <<= 1) {
      ang = -2 * Math.PI / len; wr = Math.cos(ang); wi = Math.sin(ang);
      for (i = 0; i < n; i += len) {
        var cr = 1, ci = 0;
        for (k = 0; k < len / 2; k++) {
          ur = re[i + k]; ui = im[i + k];
          vr = re[i + k + len / 2] * cr - im[i + k + len / 2] * ci; vi = re[i + k + len / 2] * ci + im[i + k + len / 2] * cr;
          re[i + k] = ur + vr; im[i + k] = ui + vi; re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi;
          t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
        }
      }
    }
  }
  function mono(buf, target) { // downmix + decimate to ~target Hz
    var sr = buf.sampleRate, step = Math.max(1, Math.round(sr / target)), n = Math.floor(buf.length / step);
    var out = new Float32Array(n), chs = [];
    for (var c = 0; c < buf.numberOfChannels; c++) chs.push(buf.getChannelData(c));
    for (var i = 0; i < n; i++) { var s = 0; for (c = 0; c < chs.length; c++) s += chs[c][i * step]; out[i] = s / chs.length; }
    return { y: out, sr: sr / step };
  }
  function flux(y, sr, hop) { // one STFT, two onset curves: full band and the kick band (20-150 Hz)
    var N = 2048, frames = Math.max(0, Math.floor((y.length - N) / hop)), win = new Float32Array(N), prev = null;
    var full = new Float32Array(frames), low = new Float32Array(frames);
    for (var i = 0; i < N; i++) win[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1));
    var klo = Math.max(1, Math.floor(20 * N / sr)), khi = Math.ceil(150 * N / sr);
    var re = new Float32Array(N), im = new Float32Array(N), cur = new Float32Array(N / 2), pv = new Float32Array(N / 2);
    for (var f = 0; f < frames; f++) {
      for (i = 0; i < N; i++) { re[i] = y[f * hop + i] * win[i]; im[i] = 0; }
      fft(re, im);
      var s = 0, k = 0;
      for (i = 1; i < N / 2; i++) {
        cur[i] = Math.log(1 + 10 * Math.hypot(re[i], im[i]));
        if (prev) { var d = Math.max(0, cur[i] - pv[i]); s += d; if (i >= klo && i < khi) k += d; }
      }
      full[f] = s; low[f] = k; var tmp = pv; pv = cur; cur = tmp; prev = true;
    }
    return { full: norm(full, hop / sr), low: norm(low, hop / sr) };
  }
  function norm(out, dt) {
    var n = out.length, m = 0, v = 0, i;
    for (i = 0; i < n; i++) m += out[i]; m /= n || 1;
    for (i = 0; i < n; i++) v += (out[i] - m) * (out[i] - m); v = Math.sqrt(v / (n || 1)) || 1;
    for (i = 0; i < n; i++) out[i] = (out[i] - m) / v;
    return { f: out, dt: dt };
  }
  function peaks(o, thresh, gap) {
    var r = [], last = -9, f = o.f;
    for (var i = 1; i < f.length - 1; i++) {
      var t = (i + 1) * o.dt;
      if (f[i] > thresh && f[i] >= f[i - 1] && f[i] >= f[i + 1] && t - last >= gap) { r.push(+t.toFixed(3)); last = t; }
    }
    return r;
  }
  function tempo(o) {
    var f = o.f, n = f.length, best = -1e9, bi = 0, ac = [];
    var lo = Math.floor(60 / 180 / o.dt), hi = Math.ceil(60 / 70 / o.dt);
    for (var lag = Math.max(1, lo - 1); lag <= hi + 1; lag++) { var s = 0; for (var i = 0; i + lag < n; i++) s += f[i] * f[i + lag]; ac[lag] = s; }
    for (lag = lo; lag <= hi; lag++) if (ac[lag] > best) { best = ac[lag]; bi = lag; }
    var a0 = ac[bi - 1] || 0, a1 = ac[bi], a2 = ac[bi + 1] || 0, off = 0.5 * (a0 - a2) / (a0 - 2 * a1 + a2 || 1e-9);
    return 60 / ((bi + off) * o.dt);
  }
  async function analyze(file) {
    var ab = await file.arrayBuffer();
    var AC = window.AudioContext || window.webkitAudioContext, ctx = new AC();
    var buf = await new Promise(function (res, rej) { var p = ctx.decodeAudioData(ab, res, rej); if (p && p.then) p.then(res, rej); });
    ctx.close && ctx.close();
    var m = mono(buf, 22050), o = flux(m.y, m.sr, 512);
    return { duration: buf.duration, bpm: tempo(o.full), hits: peaks(o.full, 1.5, 0.25), kicks: peaks(o.low, 1.2, 0.18) };
  }
  var RECIPES = {
    burst_hold: "Runs of 3-frame shots on the drop, then a long hold. Hype and sports.",
    pattern3: "The same 3-cut figure every bar. Montages and fashion.",
    kick_cut: "Cut on every kick drum hit. Party and event recaps.",
    slow_locked: "One cut per bar, long hero hold at the end. Docs and trailers.",
  };
  function cadence(a, recipe, fps, clips, seed, maxDur) {
    var beat = 60 / a.bpm, first = a.kicks.length ? a.kicks[0] : 0, dur = Math.min(a.duration, maxDur || 1e9), cuts = [first], t, i;
    var rnd = (function (s) { return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; })(seed || 7);
    if (recipe === "kick_cut") a.kicks.forEach(function (k) { if (k - cuts[cuts.length - 1] >= 6 / fps && k < dur) cuts.push(k); });
    else if (recipe === "pattern3") for (t = first; t < dur; t += 4 * beat) cuts.push(t + beat, t + 2 * beat, t + 4 * beat);
    else if (recipe === "slow_locked") { t = first; while (t + 4 * beat < dur - 207 / fps) { t += 4 * beat; cuts.push(t); } }
    else { t = first; while (t < dur) { var n = 12 + Math.floor(rnd() * 4); for (i = 0; i < n; i++) { t += 3 / fps; cuts.push(t); } t += 130 / fps; t = first + Math.ceil((t - first) / beat) * beat; cuts.push(t); } }
    var fr = Array.from(new Set(cuts.filter(function (c) { return c < dur; }).map(function (c) { return Math.round(c * fps); }))).sort(function (x, y) { return x - y; });
    fr.push(Math.round(dur * fps));
    var shots = [];
    for (i = 0; i < fr.length - 1; i++) {
      if (fr[i + 1] <= fr[i]) continue;
      var src = clips.length ? shots.length % clips.length : 0, need = (fr[i + 1] - fr[i]) / fps;
      var len = clips.length ? clips[src].duration : 0;
      shots.push({ n: shots.length + 1, rec_in: fr[i], rec_out: fr[i + 1], frames: fr[i + 1] - fr[i], clip: src, src_in: +(rnd() * Math.max(0, len - need)).toFixed(3) });
    }
    return { recipe: recipe, rule: RECIPES[recipe], bpm: +a.bpm.toFixed(2), fps: fps, kicks: a.kicks.length, shots: shots };
  }
  function edl(plan, names, title) {
    var fps = plan.fps;
    function tc(f) { f = Math.round(f); var h = Math.floor(f / (3600 * fps)), m = Math.floor(f / (60 * fps)) % 60, s = Math.floor(f / fps) % 60, ff = f % fps; return [h, m, s, ff].map(function (x) { return String(x).padStart(2, "0"); }).join(":"); }
    var out = "TITLE: " + (title || "BILLO CADENCE " + plan.recipe.toUpperCase()) + "\nFCM: NON-DROP FRAME\n\n";
    plan.shots.forEach(function (s) {
      var si = Math.round(s.src_in * fps);
      out += String(s.n).padStart(3, "0") + "  AX       V     C        " + tc(si) + " " + tc(si + s.frames) + " " + tc(s.rec_in) + " " + tc(s.rec_out) + "\n";
      if (names[s.clip]) out += "* FROM CLIP NAME: " + names[s.clip] + "\n";
    });
    return out;
  }
  window.ForgeBeat = { analyze: analyze, cadence: cadence, edl: edl, RECIPES: RECIPES };
})();
