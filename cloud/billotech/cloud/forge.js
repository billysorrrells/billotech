/* Copyright (c) 2026 Billy Sorrells Entertainment LLC · BilloTech Source License 1.0 (free for personal and school use; paid work needs a BilloTech subscription) · billysorrells.com/billotech/license */
/* Billo Forge — BilloTech Cloud editor. Drop a clip, pick a recipe, export. All processing happens in this browser. */
(function () {
  "use strict";
  var $ = function (s) { return document.querySelector(s); }, $$ = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };
  var B = window.BilloCloud;
  var cv = $("#cv"), G;
  try { G = new window.ForgeGL(cv); } catch (e) { $("#status").textContent = e.message; }
  var src2d = document.createElement("canvas"), sctx = src2d.getContext("2d");
  var out = document.createElement("canvas"), octx = out.getContext("2d");

  var EFFECTS = [
    ["glitch", "Glitch", "RGB split, torn bands, crushed color blocks.", "window"],
    ["vhs", "VHS tape", "Color bleed, wobble, rolling tracking line.", "window"],
    ["leak", "Light leak", "Warm light spilling across the frame.", "decay"],
    ["burn", "Film burn", "The frame burns orange to white and back.", "window"],
    ["grain", "Film grain", "Grain, dust, scratches and a soft vignette.", "decay"],
    ["flash", "Flash", "A white flash that falls off fast.", "decay"],
    ["strobe", "Strobe", "Frame-by-frame white flicker.", "decay"],
    ["shake", "Impact shake", "A hard knock on the camera.", "decay"],
    ["punch", "Punch-in", "Snap in 1.3x on the hit, then ease out.", "decay"],
    ["grad", "Color wash", "Looping gradient wash, like an LED wall.", "decay"],
    ["bw", "B&W to color", "Black and white until the first hit, then color.", "snap"],
  ];
  var LOOKS = ["Natural", "Teal & warm", "Golden hour", "Bright & soft", "Warm red", "Neutral, teal kept", "Black & white", "Gym practical"];
  var LOOK_SW = [["#777", "#aaa"], ["#1d6f7a", "#e3a36a"], ["#e0a040", "#f7d58a"], ["#c9c9c4", "#eeeeea"], ["#a33b2b", "#f1a07a"], ["#6b6f70", "#2DD6AE"], ["#111", "#eee"], ["#d79a52", "#f4d2a2"]];
  var PALETTES = { amber: [[1, .55, .15], [1, .25, .05], [1, .85, .5]], magenta: [[1, .2, .55], [.9, .35, .1], [1, .7, .8]], teal: [[.18, .84, .68], [.6, .5, 1], [1, .8, .5]] };
  var RECIPES = [
    { id: "hype", n: "Hype spine", d: "Teal and warm, punch-in and flash on every hit.", look: 1, len: .35, fx: { punch: ["hits", 1], flash: ["hits", .6], grain: ["all", .35] } },
    { id: "recap", n: "Event recap", d: "Clean color, light leaks on the hits.", look: 5, len: .8, pal: "amber", fx: { leak: ["hits", .9], grain: ["all", .25], flash: ["hits", .3] } },
    { id: "trailer", n: "Narrated trailer", d: "Black and white until the hit, then golden color and a burn.", look: 2, len: 1.2, fx: { bw: ["hits", 1], burn: ["hits", .8], grain: ["all", .3] } },
    { id: "tape", n: "Retro tape", d: "VHS the whole way, glitch on the hits.", look: 4, lookAmt: .6, len: .4, fx: { vhs: ["all", .7], glitch: ["hits", 1] } },
    { id: "club", n: "Club night", d: "Strobe and glitch on the kick, magenta leaks.", look: 1, len: .3, pal: "magenta", fx: { strobe: ["hits", .7], glitch: ["hits", .6], leak: ["hits", .7] } },
    { id: "film", n: "Film stock", d: "Heavy grain and warm leaks, like 16mm.", look: 2, lookAmt: .5, len: 1, pal: "amber", fx: { grain: ["all", .8], leak: ["hits", .5] } },
    { id: "deadpan", n: "Deadpan", d: "Warm practical light. Punch in on the punchline.", look: 7, len: 1, fx: { punch: ["hits", 1] } },
    { id: "clean", n: "Clean pro", d: "Bright, soft color. No effects.", look: 3, lookAmt: .8, len: .5, fx: { grain: ["all", .15] } },
  ];

  var S = { title: "Untitled project", mode: "single", src: null, clip: null, hits: [], kicks: [], hitLen: .5, fx: {}, pal: "amber", look: 0, lookAmt: 1, match: null,
    recipe: null, seed: 7, cut: { song: null, clips: [], recipe: "burst_hold", plan: null, a: null }, docId: null, driveId: null, dirty: false };
  EFFECTS.forEach(function (e) { S.fx[e[0]] = { on: false, mode: "hits", amt: 1 }; });

  var video = document.createElement("video"); video.playsInline = true; video.preload = "auto"; video.crossOrigin = "anonymous";
  var song = document.createElement("audio"); song.preload = "auto";
  var demo = null, demoT0 = 0, playing = false, frame = 0;

  // ---------- helpers ----------
  function toast(msg, ms) { var t = document.createElement("div"); t.className = "toast"; t.innerHTML = msg; document.body.appendChild(t); setTimeout(function () { t.remove(); }, ms || 3800); }
  function status(msg) { $("#status").innerHTML = msg; }
  function fmt(t) { t = Math.max(0, t || 0); return Math.floor(t / 60) + ":" + (t % 60).toFixed(1).padStart(4, "0"); }
  function dirty(on) { S.dirty = on !== false; $("#state").textContent = S.dirty ? "Unsaved changes" : "Saved"; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function dur() {
    if (S.mode === "cut") return S.cut.plan ? S.cut.plan.shots[S.cut.plan.shots.length - 1].rec_out / S.cut.plan.fps : (song.duration || 0);
    if (S.src === "demo") return 8;
    return video.duration || 0;
  }
  function now() {
    if (S.mode === "cut") return song.currentTime || 0;
    if (S.src === "demo") return playing ? ((performance.now() - demoT0) / 1000) % 8 : (demo ? demo.t : 0);
    return video.currentTime || 0;
  }
  function env(t, hits, len, shape) {
    var best = 0;
    for (var i = 0; i < hits.length; i++) {
      var d = t - hits[i];
      if (shape === "window" && Math.abs(d) < len / 2) best = Math.max(best, 1 - Math.abs(d) / (len / 2));
      else if (shape !== "window" && d >= 0 && d < len) best = Math.max(best, Math.exp(-5 * d / len));
    }
    return best;
  }
  function activeHits() {
    if (S.mode === "cut" && S.cut.plan) return S.cut.plan.shots.map(function (s) { return s.rec_in / S.cut.plan.fps; });
    return S.hits;
  }

  // ---------- sizing ----------
  function aspectOf(shape, w, h) {
    if (shape === "v") return [9, 16]; if (shape === "w") return [16, 9]; if (shape === "s") return [1, 1];
    return w && h ? [w, h] : [9, 16];
  }
  function sizeFor(longSide, shape, w, h) {
    var a = aspectOf(shape, w, h), r = a[0] / a[1], W, H;
    if (r < 1) { H = longSide; W = Math.round(H * r / 2) * 2; } else { W = longSide; H = Math.round(W / r / 2) * 2; }
    return [W, H];
  }
  function srcDims() {
    if (S.mode === "cut" && S.cut.clips[0]) return [S.cut.clips[0].w, S.cut.clips[0].h];
    if (S.src === "demo") return [1080, 1920];
    return [video.videoWidth, video.videoHeight];
  }
  function setPreviewSize() {
    var d = srcDims(), sz = sizeFor(960, $("#exShape").value, d[0], d[1]);
    cv.width = src2d.width = sz[0]; cv.height = src2d.height = sz[1];
  }

  // ---------- demo source (drawn, no download, works on locked-down networks) ----------
  function makeDemo() {
    var c = document.createElement("canvas"); c.width = 540; c.height = 960; var x = c.getContext("2d");
    demo = { c: c, t: 0, draw: function (t) {
      this.t = t; var g = x.createLinearGradient(0, 0, 540, 960);
      g.addColorStop(0, "hsl(" + (180 + 40 * Math.sin(t * .7)) + ",55%,22%)"); g.addColorStop(1, "hsl(" + (20 + 30 * Math.cos(t * .5)) + ",70%,45%)");
      x.fillStyle = g; x.fillRect(0, 0, 540, 960);
      for (var i = 0; i < 7; i++) { x.fillStyle = "rgba(255,255,255," + (.06 + .05 * i) + ")"; var r = 40 + 30 * i; x.beginPath(); x.arc(270 + 180 * Math.sin(t * .6 + i), 480 + 260 * Math.cos(t * .4 + i * 1.3), r, 0, 6.283); x.fill(); }
      x.fillStyle = "#fff"; x.font = "400 92px Anton, Impact, sans-serif"; x.textAlign = "center";
      x.fillText("BILLO", 270, 430 + 6 * Math.sin(t * 4)); x.fillText("FORGE", 270, 530 + 6 * Math.sin(t * 4 + 1));
      x.font = "500 22px 'JetBrains Mono', monospace"; x.fillStyle = "#2DD6AE"; x.fillText("DEMO · 120 BPM", 270, 600);
      var beat = (t * 2) % 1; x.fillStyle = "rgba(45,214,174," + (1 - beat) + ")"; x.fillRect(0, 930, 540 * (1 - beat), 30);
    } };
  }
  function useDemo() {
    leaveCut(true); makeDemo(); S.src = "demo"; S.clip = { name: "BilloTech demo", duration: 8 };
    S.hits = []; for (var b = 0; b < 16; b++) S.hits.push(b * .5); S.kicks = S.hits.slice();
    $("#drop").hidden = true; setPreviewSize(); demoT0 = performance.now(); playing = true; $("#playBtn").textContent = "❚❚";
    if (!S.recipe) applyRecipe(RECIPES[0]);
    status("Demo loaded. Pick a recipe, or <b>choose your own clip</b>.");
    drawLane();
  }

  // ---------- loading ----------
  function loadClip(file) {
    if (!file) return;
    leaveCut(true);
    if (S.clip && S.clip.url) URL.revokeObjectURL(S.clip.url);
    var url = URL.createObjectURL(file);
    S.src = "video"; S.clip = { name: file.name, url: url, file: file, size: file.size };
    video.src = url; video.muted = false;
    video.onloadedmetadata = function () {
      S.clip.duration = video.duration; S.clip.w = video.videoWidth; S.clip.h = video.videoHeight;
      $("#drop").hidden = true; setPreviewSize(); video.currentTime = 0; drawLane(); dirty();
      status("Loaded <b>" + esc(file.name) + "</b> · " + video.videoWidth + "×" + video.videoHeight + " · " + fmt(video.duration) + ". Finding hits in the audio…");
      findHits(file, true);
    };
    video.onerror = function () { status("This browser can't play that file. Try an MP4 (H.264) or WebM."); };
  }
  function findHits(file, quiet) {
    if (!file) { toast("Load a clip first."); return; }
    return window.ForgeBeat.analyze(file).then(function (a) {
      S.hits = a.hits; S.kicks = a.kicks; drawLane(); dirty();
      status("Found <b>" + a.hits.length + "</b> hits and " + a.kicks.length + " kick drums (about " + Math.round(a.bpm) + " BPM). Pick a recipe or press play.");
    }).catch(function () { if (!quiet) toast("Couldn't read audio from that file. Tap + Hit while it plays instead."); status("No audio hits found. Tap <b>+ Hit</b> while it plays to mark them."); });
  }

  // ---------- recipes / effects / looks UI ----------
  function renderRecipes() {
    $("#recipes").innerHTML = RECIPES.map(function (r) {
      var sw = LOOK_SW[r.look];
      return '<button class="rc" data-r="' + r.id + '" aria-pressed="' + (S.recipe === r.id) + '"><span class="sw"><i style="background:' + sw[0] + '"></i><i style="background:' + sw[1] + '"></i></span><b>' + r.n + "</b><small>" + r.d + "</small></button>";
    }).join("");
  }
  function applyRecipe(r) {
    S.recipe = r.id; S.look = r.look; S.lookAmt = r.lookAmt == null ? 1 : r.lookAmt; S.hitLen = r.len; S.pal = r.pal || "amber";
    EFFECTS.forEach(function (e) { var f = r.fx[e[0]]; S.fx[e[0]] = f ? { on: true, mode: f[0], amt: f[1] } : { on: false, mode: "hits", amt: 1 }; });
    renderRecipes(); renderFx(); renderLooks(); $("#hitLen").value = S.hitLen; $("#lookAmt").value = S.lookAmt; dirty();
    if (!activeHits().length && S.src === "video") status("Recipe set. No hits yet: tap <b>+ Hit</b> while it plays, or use Effects → Find hits.");
  }
  function renderFx() {
    $("#fxList").innerHTML = EFFECTS.map(function (e) {
      var f = S.fx[e[0]];
      return '<div class="fx"><input type="checkbox" class="tg" id="fx_' + e[0] + '" data-fx="' + e[0] + '" ' + (f.on ? "checked" : "") + '><label for="fx_' + e[0] + '">' + e[1] + "</label>" +
        '<select data-mode="' + e[0] + '" aria-label="' + e[1] + ' timing"><option value="hits"' + (f.mode === "hits" ? " selected" : "") + '>On hits</option><option value="all"' + (f.mode === "all" ? " selected" : "") + ">Whole clip</option></select>" +
        '<span class="d">' + e[2] + '</span><input type="range" min="0" max="1" step="0.01" value="' + f.amt + '" data-amt="' + e[0] + '" aria-label="' + e[1] + ' strength" style="grid-column:2/4"></div>';
    }).join("") + '<div class="field"><span>Leak and wash colors</span><select id="palSel"><option value="amber">Amber</option><option value="magenta">Magenta</option><option value="teal">Teal</option></select></div>';
    $("#palSel").value = S.pal;
  }
  function renderLooks() {
    $("#looks").innerHTML = LOOKS.map(function (n, i) {
      return '<button class="rc" data-look="' + i + '" aria-pressed="' + (S.look === i) + '"><span class="sw"><i style="background:' + LOOK_SW[i][0] + '"></i><i style="background:' + LOOK_SW[i][1] + '"></i></span><b style="font-size:15px">' + n + "</b></button>";
    }).join("");
  }
  function drawLane() {
    var d = dur() || 1, lane = $("#lane");
    $$("#lane i").forEach(function (x) { x.remove(); });
    var h = activeHits(), frag = "";
    h.forEach(function (t) { frag += '<i style="left:' + (t / d * 100) + '%"></i>'; });
    if (S.mode !== "cut") S.kicks.forEach(function (t) { if (S.hits.indexOf(t) < 0) frag += '<i class="k" style="left:' + (t / d * 100) + '%;opacity:.45"></i>'; });
    lane.insertAdjacentHTML("beforeend", frag);
  }

  // ---------- render loop ----------
  var shotIdx = -1;
  function currentSource(t) {
    if (S.mode === "cut" && S.cut.plan) {
      var p = S.cut.plan, f = t * p.fps, i = 0;
      while (i < p.shots.length - 1 && p.shots[i].rec_out <= f) i++;
      var s = p.shots[i], c = S.cut.clips[s.clip];
      if (!c) return null;
      var want = s.src_in + (t - s.rec_in / p.fps);
      if (i !== shotIdx || Math.abs(c.el.currentTime - want) > .3) { c.el.currentTime = Math.min(want, (c.duration || want) - .05); shotIdx = i; }
      if (playing && c.el.paused) c.el.play().catch(function () {});
      S.cut.clips.forEach(function (o) { if (o !== c && !o.el.paused) o.el.pause(); });
      return c.el;
    }
    if (S.src === "demo") { demo.draw(t); return demo.c; }
    if (S.src === "video") return video.readyState >= 2 ? video : null;
    return null;
  }
  function params(t) {
    var h = activeHits(), s = {};
    EFFECTS.forEach(function (e) {
      var f = S.fx[e[0]]; if (!f.on) { s[e[0]] = 0; return; }
      if (e[3] === "snap") s[e[0]] = f.mode === "all" || !h.length ? f.amt : (t < h[0] ? f.amt : Math.max(0, 1 - (t - h[0]) / .08) * f.amt);
      else s[e[0]] = (f.mode === "all" ? 1 : env(t, h, S.hitLen, e[3])) * f.amt;
    });
    return { t: t, seed: S.seed, frame: frame, s: s, look: S.look, lookAmt: S.lookAmt, pal: PALETTES[S.pal], match: S.match, shk: [Math.random() * 2 - 1, Math.random() * 2 - 1] };
  }
  function drawCover(el) {
    var sw = el.videoWidth || el.width, sh = el.videoHeight || el.height, W = src2d.width, H = src2d.height;
    if (!sw || !sh) return false;
    var k = Math.max(W / sw, H / sh), dw = sw * k, dh = sh * k;
    sctx.drawImage(el, (W - dw) / 2, (H - dh) / 2, dw, dh); return true;
  }
  function tick() {
    var t = now(), el = currentSource(t);
    if (G && el && drawCover(el)) { G.draw(src2d, params(t)); frame++; }
    if (rec && rec.state === "recording") recordFrame(t);
    var d = dur();
    $("#tc").textContent = fmt(t) + " / " + fmt(d);
    if (!scrubbing && d) $("#scrub").value = Math.round(t / d * 1000);
    $("#ph").style.left = (d ? t / d * 100 : 0) + "%";
    if (S.mode === "cut" && playing && t >= d - .02) { pause(); song.currentTime = 0; }
    requestAnimationFrame(tick);
  }

  // ---------- transport ----------
  function play() {
    if (!S.src && S.mode !== "cut") { toast("Load a clip or try the demo first."); return; }
    playing = true; $("#playBtn").textContent = "❚❚"; $("#playBtn").setAttribute("aria-label", "Pause");
    if (S.mode === "cut") song.play().catch(function () {});
    else if (S.src === "demo") demoT0 = performance.now() - (demo.t || 0) * 1000;
    else video.play().catch(function () { video.muted = true; video.play().catch(function () {}); toast("Playing muted. Tap the clip's sound on in your browser to hear it."); });
  }
  function pause() {
    playing = false; $("#playBtn").textContent = "▶"; $("#playBtn").setAttribute("aria-label", "Play");
    video.pause(); song.pause(); S.cut.clips.forEach(function (c) { c.el.pause(); });
  }
  function seek(t) {
    if (S.mode === "cut") { song.currentTime = t; shotIdx = -1; }
    else if (S.src === "demo") { demo.t = t; demoT0 = performance.now() - t * 1000; }
    else video.currentTime = t;
  }
  video.onended = function () { if (!rec || rec.state !== "recording") pause(); };
  var scrubbing = false;
  $("#scrub").addEventListener("input", function () { scrubbing = true; seek(this.value / 1000 * dur()); });
  $("#scrub").addEventListener("change", function () { scrubbing = false; });
  $("#playBtn").onclick = function () { playing ? pause() : play(); };
  function markHit() { var t = +now().toFixed(3); S.hits.push(t); S.hits.sort(function (a, b) { return a - b; }); drawLane(); dirty(); }
  $("#hitBtn").onclick = markHit;
  $("#lane").addEventListener("click", function (e) {
    if (S.mode === "cut") return;
    var r = this.getBoundingClientRect(), t = (e.clientX - r.left) / r.width * dur();
    if (e.shiftKey) { var best = -1, bd = 1e9; S.hits.forEach(function (h, i) { if (Math.abs(h - t) < bd) { bd = Math.abs(h - t); best = i; } }); if (best >= 0 && bd < dur() * .02) S.hits.splice(best, 1); }
    else { S.hits.push(+t.toFixed(3)); S.hits.sort(function (a, b) { return a - b; }); }
    drawLane(); dirty();
  });
  document.addEventListener("keydown", function (e) {
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
    if (e.code === "Space") { e.preventDefault(); playing ? pause() : play(); }
    else if (e.key === "h" || e.key === "H") markHit();
    else if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); saveDevice(); }
  });

  // ---------- inputs ----------
  $("#fileIn").onchange = function () { loadClip(this.files[0]); this.value = ""; };
  $("#demoBtn").onclick = useDemo;
  var stage = $("#stage");
  ["dragenter", "dragover"].forEach(function (ev) { stage.addEventListener(ev, function (e) { e.preventDefault(); $("#drop").hidden = false; $("#drop").classList.add("on"); }); });
  ["dragleave", "drop"].forEach(function (ev) { stage.addEventListener(ev, function (e) { e.preventDefault(); $("#drop").classList.remove("on"); if (ev === "dragleave" && S.src) $("#drop").hidden = true; }); });
  stage.addEventListener("drop", function (e) { var f = e.dataTransfer.files[0]; if (f && /^video\//.test(f.type)) loadClip(f); else if (f && /json|billo/.test(f.name)) openFile(f); else if (S.src) $("#drop").hidden = true; });
  $("#recipes").addEventListener("click", function (e) { var b = e.target.closest("[data-r]"); if (b) applyRecipe(RECIPES.filter(function (r) { return r.id === b.dataset.r; })[0]); });
  $("#fxList").addEventListener("change", function (e) {
    var d = e.target.dataset;
    if (d.fx) S.fx[d.fx].on = e.target.checked; else if (d.mode) S.fx[d.mode].mode = e.target.value; else if (e.target.id === "palSel") S.pal = e.target.value;
    S.recipe = null; renderRecipes(); dirty();
  });
  $("#fxList").addEventListener("input", function (e) { var d = e.target.dataset; if (d.amt) { S.fx[d.amt].amt = +e.target.value; S.fx[d.amt].on = true; $("#fx_" + d.amt).checked = true; dirty(); } });
  $("#looks").addEventListener("click", function (e) { var b = e.target.closest("[data-look]"); if (b) { S.look = +b.dataset.look; renderLooks(); dirty(); } });
  $("#lookAmt").oninput = function () { S.lookAmt = +this.value; dirty(); };
  $("#hitLen").oninput = function () { S.hitLen = +this.value; dirty(); };
  $("#autoHits").onclick = function () { if (S.src === "video") { status("Listening for hits…"); findHits(S.clip.file); } else toast("Load your own clip to find its hits."); };
  $("#clearHits").onclick = function () { S.hits = []; drawLane(); dirty(); };
  $("#exShape").onchange = function () { setPreviewSize(); };
  $("#title").oninput = function () { S.title = this.value || "Untitled project"; dirty(); };

  // match a still
  function stats(el) {
    var c = document.createElement("canvas"), w = 192, h = 192; c.width = w; c.height = h;
    var x = c.getContext("2d"); x.drawImage(el, 0, 0, w, h);
    var d = x.getImageData(0, 0, w, h).data, n = w * h, m = [0, 0, 0], q = [0, 0, 0];
    for (var i = 0; i < d.length; i += 4) {
      var r = d[i] / 255, g = d[i + 1] / 255, b = d[i + 2] / 255, Y = [.299 * r + .587 * g + .114 * b, -.169 * r - .331 * g + .5 * b, .5 * r - .419 * g - .081 * b];
      for (var k = 0; k < 3; k++) { m[k] += Y[k]; q[k] += Y[k] * Y[k]; }
    }
    m = m.map(function (v) { return v / n; });
    return { m: m, s: q.map(function (v, k) { return Math.sqrt(Math.max(1e-6, v / n - m[k] * m[k])); }) };
  }
  $("#refIn").onchange = function () {
    var f = this.files[0]; this.value = ""; if (!f) return;
    if (!S.src) { toast("Load a clip first, then match it to a still."); return; }
    var img = new Image(); img.onload = function () {
      var a = stats(src2d), r = stats(img);
      S.match = { ms: a.m, ss: a.s, mr: r.m, sr: r.s, name: f.name }; dirty();
      status("Matched to <b>" + esc(f.name) + "</b>. Pick “Natural” in Look to see the match on its own.");
    }; img.src = URL.createObjectURL(f);
  };
  $("#clearMatch").onclick = function () { S.match = null; dirty(); };

  // ---------- beat cut ----------
  $("#cutRecipe").innerHTML = Object.keys(window.ForgeBeat.RECIPES).map(function (k) { return '<option value="' + k + '">' + k.replace("_", " ") + "</option>"; }).join("");
  function ruleNote() { $("#cutRule").textContent = window.ForgeBeat.RECIPES[$("#cutRecipe").value]; }
  $("#cutRecipe").onchange = function () { S.cut.recipe = this.value; ruleNote(); if (S.cut.plan) buildCut(); };
  ruleNote();
  function renderClips() {
    var rows = [];
    if (S.cut.song) rows.push("<div><span>♪ " + esc(S.cut.song.name) + "</span><span>" + (S.cut.a ? Math.round(S.cut.a.bpm) + " BPM" : "reading…") + "</span></div>");
    S.cut.clips.forEach(function (c) { rows.push("<div><span>▣ " + esc(c.name) + "</span><span>" + fmt(c.duration) + "</span></div>"); });
    $("#clipList").innerHTML = rows.join("") || '<p class="note">No song or clips yet.</p>';
    $("#buildCut").disabled = !(S.cut.song && S.cut.a && S.cut.clips.length);
  }
  $("#songIn").onchange = function () {
    var f = this.files[0]; this.value = ""; if (!f) return;
    S.cut.song = { name: f.name, file: f, url: URL.createObjectURL(f) }; S.cut.a = null; renderClips();
    song.src = S.cut.song.url;
    window.ForgeBeat.analyze(f).then(function (a) { S.cut.a = a; renderClips(); status("Song: <b>" + Math.round(a.bpm) + " BPM</b>, " + a.kicks.length + " kick drums. Add clips, then build the cut."); })
      .catch(function () { toast("Couldn't read that song. Try an MP3, M4A or WAV."); });
  };
  $("#clipsIn").onchange = function () {
    var fs = Array.prototype.slice.call(this.files); this.value = "";
    fs.forEach(function (f) {
      var el = document.createElement("video"); el.muted = true; el.playsInline = true; el.preload = "auto";
      var c = { name: f.name, file: f, url: URL.createObjectURL(f), el: el, duration: 0 };
      el.onloadedmetadata = function () { c.duration = el.duration; c.w = el.videoWidth; c.h = el.videoHeight; renderClips(); };
      el.src = c.url; S.cut.clips.push(c);
    });
    renderClips();
  };
  function buildCut() {
    var a = S.cut.a; if (!a) return;
    S.cut.plan = window.ForgeBeat.cadence(a, S.cut.recipe, 30, S.cut.clips, S.seed);
    S.mode = "cut"; S.src = "cut"; pause(); video.pause(); $("#drop").hidden = true; setPreviewSize(); song.currentTime = 0; shotIdx = -1;
    $("#leaveCut").hidden = false; $("#edlBtn").disabled = false; $("#cutJson").disabled = false; drawLane(); dirty();
    status("Cut built: <b>" + S.cut.plan.shots.length + " shots</b> at " + S.cut.plan.bpm + " BPM. Press play. Effects fire on every cut.");
  }
  $("#buildCut").onclick = buildCut;
  function leaveCut(silent) { if (S.mode !== "cut") return; pause(); S.mode = "single"; S.src = S.clip ? (S.clip.url ? "video" : "demo") : null; $("#leaveCut").hidden = true; if (!silent) { setPreviewSize(); drawLane(); } }
  $("#leaveCut").onclick = function () { leaveCut(); };
  $("#edlBtn").onclick = function () {
    if (!B.isPaid()) { toast('EDL export is part of Basic. <a href="/billotech/pro/">$8 a month</a>.'); return; }
    B.saveDevice(S.title.replace(/[^\w\- ]+/g, "") + ".edl", window.ForgeBeat.edl(S.cut.plan, S.cut.clips.map(function (c) { return c.name; }), S.title.toUpperCase()), "text/plain");
  };
  $("#cutJson").onclick = function () { B.saveDevice(S.title.replace(/[^\w\- ]+/g, "") + ".cut.json", JSON.stringify(S.cut.plan, null, 1)); };

  // ---------- project files ----------
  function project() {
    return { format: "billo-forge", v: 1, title: S.title, saved_at: new Date().toISOString(), mode: S.mode,
      media: S.mode === "cut" ? { song: S.cut.song && S.cut.song.name, clips: S.cut.clips.map(function (c) { return c.name; }) } : { clip: S.clip && S.clip.name, duration: S.clip && S.clip.duration },
      hits: S.hits, kicks: S.kicks, hitLen: S.hitLen, fx: S.fx, pal: S.pal, look: S.look, lookAmt: S.lookAmt, match: S.match, recipe: S.recipe, seed: S.seed,
      cut: { recipe: S.cut.recipe, plan: S.cut.plan } };
  }
  function applyProject(p) {
    if (!p || p.format !== "billo-forge") throw new Error("That isn't a Billo Forge project.");
    S.title = p.title || "Untitled project"; $("#title").value = S.title;
    S.hits = p.hits || []; S.kicks = p.kicks || []; S.hitLen = p.hitLen || .5; S.pal = p.pal || "amber"; S.look = p.look || 0; S.lookAmt = p.lookAmt == null ? 1 : p.lookAmt;
    S.match = p.match || null; S.recipe = p.recipe || null; S.seed = p.seed || 7;
    EFFECTS.forEach(function (e) { if (p.fx && p.fx[e[0]]) S.fx[e[0]] = p.fx[e[0]]; });
    S.cut.recipe = (p.cut && p.cut.recipe) || "burst_hold"; $("#cutRecipe").value = S.cut.recipe; ruleNote();
    renderRecipes(); renderFx(); renderLooks(); $("#hitLen").value = S.hitLen; $("#lookAmt").value = S.lookAmt; drawLane(); dirty(false);
    var need = p.mode === "cut" ? [p.media.song].concat(p.media.clips || []).filter(Boolean).join(", ") : p.media && p.media.clip;
    status("Opened <b>" + esc(S.title) + "</b>." + (need ? " Your footage stays on your machine, so add it again: <b>" + esc(need) + "</b>." : ""));
  }
  function stem() { return (S.title || "project").replace(/[^\w\- ]+/g, "").trim() || "project"; }
  function saveDevice() { B.saveDevice(stem() + ".billo", JSON.stringify(project(), null, 1)).then(function () { dirty(false); toast("Saved <b>" + esc(stem()) + ".billo</b> to this device."); }); }
  function needAccount(then) { openAccount(then); }
  $("#saveDevice").onclick = saveDevice;
  $("#saveDrive").onclick = function () {
    B.saveDrive(stem() + ".billo", JSON.stringify(project(), null, 1), "application/json", S.driveId).then(function (r) {
      S.driveId = r.id; dirty(false); toast('Snapped to your Google Drive, folder <b>BilloTech</b>.' + (r.link ? ' <a href="' + r.link + '" target="_blank" rel="noopener">Open</a>' : ""));
    }).catch(function (e) { toast(esc(e.message)); });
  };
  $("#saveCloud").onclick = function () {
    if (!B.key()) return needAccount(function () { $("#saveCloud").click(); });
    B.saveCloud("forge", S.title, project(), S.docId).then(function (d) { S.docId = d.doc.id; dirty(false); toast("Synced to your BilloTech account."); }).catch(function (e) { toast(esc(e.message)); });
  };
  function openFile(f) { f.text().then(function (t) { applyProject(JSON.parse(t)); }).catch(function (e) { toast(esc(e.message)); }); }
  $("#openDevice").onclick = function () { $("#projIn").click(); };
  $("#projIn").onchange = function () { if (this.files[0]) openFile(this.files[0]); this.value = ""; };
  function pick(kind, heading, rows, onPick) {
    $("#pkK").textContent = kind; $("#pkH").textContent = heading;
    $("#pkList").innerHTML = rows.length ? rows.map(function (r, i) { return '<div><span>' + esc(r.name) + '</span><button class="b" data-i="' + i + '">Open</button></div>'; }).join("") : '<p class="note">Nothing saved there yet.</p>';
    $("#pkList").onclick = function (e) { var b = e.target.closest("[data-i]"); if (b) { $("#picker").close(); onPick(rows[+b.dataset.i]); } };
    $("#picker").showModal();
  }
  $("#pkClose").onclick = function () { $("#picker").close(); };
  $("#openDrive").onclick = function () {
    B.listDrive(".billo").then(function (d) {
      pick("Google Drive", "Your Billo projects", (d.files || []).map(function (f) { return { name: f.name, id: f.id }; }), function (r) {
        B.loadDrive(r.id).then(function (t) { applyProject(JSON.parse(t)); S.driveId = r.id; }).catch(function (e) { toast(esc(e.message)); });
      });
    }).catch(function (e) { toast(esc(e.message)); });
  };
  $("#openCloud").onclick = function () {
    if (!B.key()) return needAccount(function () { $("#openCloud").click(); });
    B.listCloud("forge").then(function (d) {
      pick("BilloTech account", "Your Billo projects", (d.docs || []).map(function (x) { return { name: x.title, id: x.id }; }), function (r) {
        B.loadCloud(r.id).then(function (d) { applyProject(d.doc.body); S.docId = r.id; }).catch(function (e) { toast(esc(e.message)); });
      });
    }).catch(function (e) { toast(esc(e.message)); });
  };

  // ---------- menus + tabs ----------
  $$(".menu > .b").forEach(function (b) { b.addEventListener("click", function (e) { e.stopPropagation(); var m = b.parentNode, on = !m.classList.contains("on"); $$(".menu").forEach(function (x) { x.classList.remove("on"); }); if (on) m.classList.add("on"); }); });
  document.addEventListener("click", function () { $$(".menu").forEach(function (x) { x.classList.remove("on"); }); });
  $$(".tabs button").forEach(function (b) {
    b.onclick = function () {
      $$(".tabs button").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); });
      $$("[data-panel]").forEach(function (p) { p.hidden = p.dataset.panel !== b.dataset.tab; });
    };
  });
  $("#exportBtn").onclick = function () { $('[data-tab="export"]').click(); };

  // ---------- account dialog ----------
  var afterAccount = null;
  function openAccount(then) {
    afterAccount = then || null; $("#acctNew").hidden = false; $("#acctKey").hidden = true; $("#acGo").hidden = false; $("#acctHave").hidden = false; $("#acUse").hidden = false;
    $("#acct").showModal();
  }
  $("#acClose").onclick = function () { $("#acct").close(); if (B.key() && afterAccount) { var f = afterAccount; afterAccount = null; f(); } };
  $("#acGo").onclick = function () {
    var h = $("#acHandle").value.trim(); if (h.length < 2) { toast("Add a name (2 letters or more)."); return; }
    B.createAccount(h, $("#acEmail").value.trim()).then(function (d) {
      $("#acctNew").hidden = true; $("#acctHave").hidden = true; $("#acGo").hidden = true; $("#acUse").hidden = true;
      $("#acctKey").hidden = false; $("#acKey").textContent = d.api_key; $("#acctH").textContent = "You're in";
    }).catch(function (e) { toast(esc(e.message)); });
  };
  $("#acUse").onclick = function () { B.useKey($("#acPaste").value).then(function () { $("#acct").close(); toast("Signed in."); if (afterAccount) { var f = afterAccount; afterAccount = null; f(); } }).catch(function (e) { toast(esc(e.message)); }); };

  // ---------- export ----------
  var rec = null, chunks = [], exBlob = null, exEndAt = 0, exCard = false, exSize = [0, 0], audioCtx = null, audioNodes = new Map();
  function audioTrackFor(el) {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      var n = audioNodes.get(el);
      if (!n) { var srcN = audioCtx.createMediaElementSource(el), dest = audioCtx.createMediaStreamDestination(); srcN.connect(audioCtx.destination); srcN.connect(dest); n = dest; audioNodes.set(el, n); }
      if (audioCtx.state === "suspended") audioCtx.resume();
      return n.stream.getAudioTracks()[0] || null;
    } catch (e) { return null; }
  }
  function pickMime() {
    var c = ["video/mp4;codecs=avc1.42E01E,mp4a.40.2", "video/mp4", "video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"];
    for (var i = 0; i < c.length; i++) if (window.MediaRecorder && MediaRecorder.isTypeSupported(c[i])) return c[i];
    return "";
  }
  function recordFrame(t) {
    if (exCard) return; // the end card owns the frame
    octx.drawImage(cv, 0, 0, out.width, out.height);
    var d = dur();
    $("#exBar").style.width = Math.min(100, t / (d || 1) * 100) + "%";
    var ended = S.mode === "cut" ? t >= d - .03 : (S.src === "video" ? video.ended || t >= d - .03 : t >= d - .05);
    if (ended && !exCard) {
      if (!B.isPaid()) { exCard = true; exEndAt = performance.now() + 2000; pause(); }
      else stopExport();
    }
  }
  function endCard() {
    if (!exCard || !rec || rec.state !== "recording") return;
    var W = out.width, H = out.height, k = Math.min(W, H) / 540;
    octx.fillStyle = "#000"; octx.fillRect(0, 0, W, H);
    octx.fillStyle = "#2DD6AE"; octx.font = 500 + " " + Math.round(18 * k) + "px 'JetBrains Mono', monospace"; octx.textAlign = "center";
    octx.fillText("MADE WITH", W / 2, H / 2 - 50 * k);
    octx.fillStyle = "#fff"; octx.font = "400 " + Math.round(72 * k) + "px Anton, Impact, sans-serif"; octx.fillText("BILLOTECH", W / 2, H / 2 + 20 * k);
    octx.fillStyle = "#A1A1A1"; octx.font = "500 " + Math.round(16 * k) + "px Outfit, sans-serif"; octx.fillText("billysorrells.com/billotech", W / 2, H / 2 + 60 * k);
    if (performance.now() >= exEndAt) { exCard = false; stopExport(); } else requestAnimationFrame(endCard);
  }
  function stopExport() { if (rec && rec.state === "recording") rec.stop(); pause(); }
  $("#exGo").onclick = function () {
    if (!S.src && S.mode !== "cut") { toast("Load a clip, the demo, or build a beat cut first."); return; }
    var size = $("#exSize").value;
    if (size !== "720" && !B.isPaid()) { $("#exLock").hidden = false; toast('1080p and source size are part of Basic. <a href="/billotech/pro/">$8 a month</a>.'); return; }
    var mime = pickMime(); if (!mime) { toast("This browser can't record video. Use Chrome, Edge or Firefox."); return; }
    var d = srcDims(), long = size === "720" ? 1280 : size === "1080" ? 1920 : Math.max(d[0] || 1920, d[1] || 1080);
    exSize = sizeFor(long, $("#exShape").value, d[0], d[1]);
    cv.width = src2d.width = out.width = exSize[0]; cv.height = src2d.height = out.height = exSize[1];
    var stream = out.captureStream(30), at = null;
    if (S.mode === "cut") at = audioTrackFor(song); else if (S.src === "video") at = audioTrackFor(video);
    if (at) stream.addTrack(at);
    chunks = []; exBlob = null; exCard = false;
    rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: long >= 1920 ? 10e6 : 5e6 });
    rec.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
    rec.onstop = function () {
      exBlob = new Blob(chunks, { type: mime.split(";")[0] }); setPreviewSize(); $("#exStop").hidden = true; $("#exGo").disabled = false; $("#exDone").hidden = false; $("#exBar").style.width = "100%";
      status("Export ready: <b>" + exSize[0] + "×" + exSize[1] + "</b>, " + (exBlob.size / 1e6).toFixed(1) + " MB. Save it to this device or snap it to Google Drive.");
      B.usage("export.seconds", Math.round(dur()), "forge");
    };
    seek(0); shotIdx = -1; rec.start(500); $("#exGo").disabled = true; $("#exStop").hidden = false; $("#exDone").hidden = true;
    status("Exporting in real time… keep this tab open.");
    setTimeout(function () { play(); var watch = setInterval(function () { if (exCard) { clearInterval(watch); requestAnimationFrame(endCard); } else if (!rec || rec.state !== "recording") clearInterval(watch); }, 50); }, 150);
  };
  $("#exStop").onclick = stopExport;
  function exName() { return stem() + (exBlob && /mp4/.test(exBlob.type) ? ".mp4" : ".webm"); }
  $("#exSave").onclick = function () { if (exBlob) B.saveDevice(exName(), exBlob); };
  $("#exDrive").onclick = function () { if (exBlob) B.saveDrive(exName(), exBlob, exBlob.type).then(function (r) { toast("Snapped to your Google Drive." + (r.link ? ' <a href="' + r.link + '" target="_blank" rel="noopener">Open</a>' : "")); }).catch(function (e) { toast(esc(e.message)); }); };

  // ---------- plan ----------
  B.on(function (c) {
    var p = c.plan.plan, pill = $("#planPill");
    pill.textContent = { free: "Free", basic: "Basic", premium: "Premium", schools: "Schools" }[p] || p;
    pill.className = "plan" + (p === "free" ? " free" : "");
    $("#exLock").hidden = B.isPaid();
    $("#saveDrive").title = B.driveReady() ? "" : "Google Drive saving is switching on soon";
    status(c.account ? "Signed in as <b>" + esc(c.account.handle) + "</b> · " + pill.textContent + " plan." : (S.src ? $("#status").innerHTML : "Ready. <b>Free</b> for personal use. <a href=\"/billotech/pro/\">Plans</a>"));
  });
  B.boot();

  renderRecipes(); renderFx(); renderLooks(); renderClips(); setPreviewSize();
  if (/[?&]demo\b/.test(location.search)) useDemo();
  window.addEventListener("beforeunload", function (e) { if (S.dirty && S.src) { e.preventDefault(); e.returnValue = ""; } });
  requestAnimationFrame(tick);
})();
