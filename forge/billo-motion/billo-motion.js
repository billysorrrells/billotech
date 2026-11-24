/* Billo Motion engine v1 · Billy Sorrells Entertainment
   One deterministic canvas renderer for show banners and motion cards.
   draw(ctx, W, H, t, card) paints frame at time t (seconds). Same code runs
   in the BilloTech browser app and the headless renderer (render.mjs).
   Brand: ink #0A0A0B · bone #F4F2EC · gold #D4AF37 · Anton / Outfit / JetBrains Mono. */
(function (root) {
  const DUR = 7.0;
  const BRAND = { ink: '#0A0A0B', ink2: '#141416', bone: '#F4F2EC', gold: '#D4AF37', goldDeep: '#B8922A', punch: '#FFD23F', dim: 'rgba(244,242,236,.62)' };

  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);            // easeOutCubic
  const back = (x) => { x = clamp(x); const c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
  const prog = (t, start, len) => clamp((t - start) / len);

  function fit(ctx, text, family, weight, maxW, maxSize, minSize = 8) {
    let s = maxSize;
    ctx.font = `${weight} ${s}px ${family}`;
    const w = ctx.measureText(text).width;
    if (w > maxW) s = Math.max(minSize, Math.floor(s * maxW / w));
    return s;
  }
  function tracked(ctx, text, x, y, track, align) {
    // letter-spaced text (JetBrains Mono kickers)
    const chars = [...text];
    const widths = chars.map((c) => ctx.measureText(c).width);
    const total = widths.reduce((a, b) => a + b, 0) + track * (chars.length - 1);
    let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
    const prev = ctx.textAlign; ctx.textAlign = 'left';
    chars.forEach((c, i) => { ctx.fillText(c, cx, y); cx += widths[i] + track; });
    ctx.textAlign = prev;
    return total;
  }
  function cover(ctx, img, x, y, w, h, fx = 0.5, fy = 0.5, zoom = 1) {
    const iw = img.naturalWidth || img.videoWidth || img.width, ih = img.naturalHeight || img.videoHeight || img.height;
    const s = Math.max(w / iw, h / ih) * zoom;
    const dw = iw * s, dh = ih * s;
    const dx = x + (w - dw) * fx, dy = y + (h - dh) * fy;
    ctx.drawImage(img, dx, dy, dw, dh);
  }
  function fmtCount(n) { return Math.round(n).toLocaleString('en-US'); }

  function layoutOf(W, H) {
    const r = W / H;
    if (r >= 2.4) return 'strip';      // site / web banners 1600x500, 1500x500
    if (r >= 1.3) return 'wide';       // 1920x1080, 2160x1080
    if (r >= 0.9) return 'square';     // 1080x1080
    if (r >= 0.7) return 'feed';       // 1080x1350
    return 'story';                    // 1080x1920
  }

  function drawOnce(ctx, W, H, t, card, assets, k) {
    const B = Object.assign({}, BRAND, card.theme || {});
    const L = layoutOf(W, H);
    const u = Math.min(W, H) / 100;            // 1 unit = 1% of short side
    const still = t >= DUR;
    if (still) t = DUR;

    // ---- background ----
    ctx.save();
    ctx.fillStyle = B.ink; ctx.fillRect(0, 0, W, H);
    const bg = assets && assets.bg;
    if (bg) {
      const z = 1.0 + 0.07 * ease(t / DUR);
      const f = (card.focus && card.focus[L]) || card.focus?.all || [0.5, 0.35];
      ctx.globalAlpha = 0.25 + 0.75 * ease(prog(t, 0, 0.9));
      ctx.filter = card.bgFilter || 'saturate(1.05) contrast(1.05)';
      if (L === 'strip' || L === 'wide') cover(ctx, bg, W * 0.38, 0, W * 0.62, H, f[0], f[1], z);
      else cover(ctx, bg, 0, 0, W, L === 'story' ? H * 0.56 : H * 0.6, f[0], f[1], z);
      ctx.filter = 'none'; ctx.globalAlpha = 1;
    }
    // darkening gradients so type always reads (brand: photo luma under ~35%)
    let g;
    if (L === 'strip' || L === 'wide') {
      g = ctx.createLinearGradient(W * 0.36, 0, W * 0.66, 0);
      g.addColorStop(0, B.ink); g.addColorStop(1, 'rgba(10,10,11,0)');
      ctx.fillStyle = g; ctx.fillRect(W * 0.36, 0, W * 0.3, H);
      ctx.fillStyle = B.ink; ctx.fillRect(0, 0, W * 0.365, H);
      g = ctx.createLinearGradient(0, H * 0.7, 0, H);
      g.addColorStop(0, 'rgba(10,10,11,0)'); g.addColorStop(1, 'rgba(10,10,11,.75)');
      ctx.fillStyle = g; ctx.fillRect(0, H * 0.7, W, H * 0.3);
    } else {
      const top = L === 'story' ? 0.28 : 0.26, bot = L === 'story' ? 0.56 : 0.6;
      g = ctx.createLinearGradient(0, H * top, 0, H * bot);
      g.addColorStop(0, 'rgba(10,10,11,0)'); g.addColorStop(1, B.ink);
      ctx.fillStyle = g; ctx.fillRect(0, H * top, W, H * (bot - top) + 2);
      ctx.fillStyle = B.ink; ctx.fillRect(0, H * bot, W, H * (1 - bot));
      g = ctx.createLinearGradient(0, 0, 0, H * 0.14);
      g.addColorStop(0, 'rgba(10,10,11,.7)'); g.addColorStop(1, 'rgba(10,10,11,0)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H * 0.14);
    }
    let insetBottom = 0;
    // inset real photo (e.g. headshot) in a gold-ruled window
    if (assets && assets.inset && card.inset !== false) {
      const a = ease(prog(t, 0.6, 0.8));
      let iw, ih, ix, iy;
      if (L === 'strip' || L === 'wide') { ih = H * 0.62; iw = ih * 0.75; ix = W - iw - W * 0.04; iy = H * 0.12; }
      else { iw = W * (L === 'story' ? 0.34 : 0.27); ih = iw * 1.25; ix = W - iw - W * 0.06; iy = H * (L === 'story' ? 0.14 : 0.07); }
      insetBottom = iy + ih + 0.6 * u;
      ctx.globalAlpha = a;
      ctx.save(); ctx.translate(0, (1 - a) * 2 * u);
      ctx.fillStyle = B.gold; ctx.fillRect(ix - 0.6 * u, iy - 0.6 * u, iw + 1.2 * u, ih + 1.2 * u);
      ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
      cover(ctx, assets.inset, ix, iy, iw, ih, 0.5, 0.25, 1 + 0.04 * ease(t / DUR)); ctx.restore();
      if (card.insetLabel) {
        ctx.fillStyle = B.ink; ctx.fillRect(ix, iy + ih - 4.2 * u, iw, 4.2 * u);
        ctx.fillStyle = B.bone; ctx.font = `500 ${1.7 * u}px "JetBrains Mono"`; ctx.textBaseline = 'middle';
        tracked(ctx, card.insetLabel.toUpperCase(), ix + iw / 2, iy + ih - 2.1 * u, 0.25 * u, 'center');
      }
      ctx.restore(); ctx.globalAlpha = 1;
    }
    ctx.restore();

    // ---- type block ----
    const wideL = L === 'strip' || L === 'wide';
    const pad = wideL ? W * 0.045 : W * 0.07;
    const colW = wideL ? W * 0.44 : W - pad * 2;
    const y0 = wideL ? H * (L === 'strip' ? 0.14 : 0.12) : Math.max(H * (L === 'story' ? 0.42 : L === 'feed' ? 0.42 : 0.36), insetBottom + 2 * u);
    let y = y0;
    const x = pad;
    ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
    const S = (L === 'strip' ? H / 100 * 0.9 : wideL ? H / 100 * 0.95 : u) * k;   // type scale

    // corner mark (show/brand) top-right on vertical, top-left above kicker on wide
    if (card.corner) {
      ctx.globalAlpha = 0.85 * ease(prog(t, 0.2, 0.6));
      ctx.font = `500 ${1.6 * S}px "JetBrains Mono"`;
      { const cw = ctx.measureText(card.corner).width + 0.3 * S * card.corner.length, cx2 = wideL ? W - W * 0.03 : W - pad, cy2 = wideL ? H * 0.07 : H * 0.05;
        ctx.fillStyle = 'rgba(10,10,11,.72)'; ctx.fillRect(cx2 - cw - 1.2 * S, cy2 - 2.0 * S, cw + 2.4 * S, 3.0 * S); }
      ctx.fillStyle = B.bone;
      if (wideL) tracked(ctx, card.corner.toUpperCase(), W - W * 0.03, H * 0.07, 0.3 * S, 'right');
      else tracked(ctx, card.corner.toUpperCase(), W - pad, H * 0.05, 0.3 * S, 'right');
      ctx.globalAlpha = 1;
    }

    // kicker
    if (card.kicker) {
      const a = ease(prog(t, 0.25, 0.6));
      ctx.globalAlpha = a; ctx.fillStyle = B.gold;
      ctx.font = `700 ${2.1 * S}px "JetBrains Mono"`;
      tracked(ctx, card.kicker.toUpperCase(), x + (1 - a) * -3 * S, y, 0.38 * S, 'left');
      ctx.globalAlpha = 1; y += 2.0 * S;
    }
    // title lines (Anton, masked rise)
    const lines = L === 'strip' ? [(card.title || []).join(' ')] : (card.title || []);
    const maxTitle = L === 'strip' ? 13 : wideL ? 12.5 : L === 'story' ? 15 : 13.5;
    lines.forEach((ln, i) => {
      const s = fit(ctx, ln.toUpperCase(), 'Anton', 400, colW, maxTitle * S);
      const a = ease(prog(t, 0.45 + i * 0.16, 0.55));
      const lh = s * 1.02;
      y += lh;
      ctx.save(); ctx.beginPath(); ctx.rect(x - 2, y - lh - 2, colW + 4, lh + s * 0.12); ctx.clip();
      ctx.fillStyle = (card.titleGold && card.titleGold.includes(i)) ? B.gold : B.bone;
      ctx.font = `400 ${s}px Anton`;
      ctx.fillText(ln.toUpperCase(), x, y + (1 - a) * lh);
      ctx.restore();
    });
    // gold rule
    y += 2.0 * S;
    const ra = ease(prog(t, 1.3, 0.7));
    ctx.fillStyle = B.gold; ctx.fillRect(x, y, colW * 0.42 * ra, Math.max(2, 0.45 * S));
    y += 1.2 * S;

    // flag (e.g. 3RD SHOW ADDED · 5 PM)
    if (card.flag) {
      const a = prog(t, 1.65, 0.45);
      const sc = 1.25 - 0.25 * back(a);
      const fs = fit(ctx, card.flag.toUpperCase(), 'Anton', 400, colW - 3 * S, (L === 'strip' ? 5.2 : 5.6) * S);
      ctx.font = `400 ${fs}px Anton`;
      const fw = ctx.measureText(card.flag.toUpperCase()).width + 2.6 * S, fh = fs * 1.3;
      y += 1.4 * S;
      ctx.save(); ctx.globalAlpha = clamp(a * 3);
      ctx.translate(x + fw / 2, y + fh / 2); ctx.scale(sc, sc); ctx.rotate(-0.012);
      ctx.fillStyle = B.gold; ctx.fillRect(-fw / 2, -fh / 2, fw, fh);
      ctx.fillStyle = B.ink; ctx.textBaseline = 'middle';
      ctx.fillText(card.flag.toUpperCase(), -fw / 2 + 1.3 * S, fs * 0.04);
      ctx.restore(); ctx.textBaseline = 'alphabetic';
      y += fh + 0.6 * S;
    }

    // date / venue
    const info = (L === 'strip' ? [card.date] : [card.date, card.venue]).filter(Boolean);
    info.forEach((ln, i) => {
      const a = ease(prog(t, 2.1 + i * 0.12, 0.5));
      ctx.globalAlpha = a;
      const big = i === 0;
      const s = fit(ctx, ln.toUpperCase(), big ? 'Anton' : 'Outfit', big ? 400 : 600, colW, (big ? (L === 'strip' ? 5.0 : 5.4) : 2.7) * S);
      ctx.font = big ? `400 ${s}px Anton` : `600 ${s}px Outfit`;
      ctx.fillStyle = big ? B.bone : B.dim;
      y += s * (big ? 1.25 : 1.35);
      ctx.fillText(big ? ln.toUpperCase() : ln, x, y);
      ctx.globalAlpha = 1;
    });

    // times chips
    if (card.times && card.times.length) {
      y += 1.6 * S;
      let cx = x;
      const ch = 4.6 * S;
      card.times.forEach((tm, i) => {
        const a = ease(prog(t, 2.6 + i * 0.14, 0.4));
        const open = tm.state === 'open';
        ctx.font = `400 ${2.9 * S}px Anton`;
        const tw = ctx.measureText(tm.t).width;
        ctx.font = `700 ${1.35 * S}px "JetBrains Mono"`;
        const sw = ctx.measureText(tm.s.toUpperCase()).width + 0.18 * S * tm.s.length;
        const cw = Math.max(tw, sw) + 2.6 * S;
        if (cx + cw > x + colW && cx > x) { cx = x; y += ch + 1.0 * S; }
        ctx.globalAlpha = a;
        ctx.save(); ctx.translate(0, (1 - a) * 1.5 * S);
        ctx.fillStyle = open ? B.gold : 'rgba(244,242,236,.08)';
        ctx.fillRect(cx, y, cw, ch + 2.2 * S);
        if (!open) { ctx.strokeStyle = 'rgba(244,242,236,.28)'; ctx.lineWidth = Math.max(1, 0.18 * S); ctx.strokeRect(cx, y, cw, ch + 2.2 * S); }
        ctx.fillStyle = open ? B.ink : B.bone;
        ctx.font = `400 ${2.9 * S}px Anton`; ctx.fillText(tm.t, cx + 1.3 * S, y + 3.4 * S);
        ctx.fillStyle = open ? B.ink : B.dim; ctx.font = `700 ${1.35 * S}px "JetBrains Mono"`;
        tracked(ctx, tm.s.toUpperCase(), cx + 1.3 * S, y + 5.7 * S, 0.18 * S, 'left');
        ctx.restore(); ctx.globalAlpha = 1;
        cx += cw + 1.0 * S;
      });
      y += ch + 2.2 * S;
    }

    // lineup
    if (card.lineup && L !== 'strip') {
      const a = ease(prog(t, 3.0, 0.5));
      ctx.globalAlpha = a; y += 2.6 * S;
      ctx.fillStyle = B.gold; ctx.font = `700 ${1.45 * S}px "JetBrains Mono"`;
      tracked(ctx, (card.lineupLabel || 'Lineup').toUpperCase(), x, y, 0.3 * S, 'left');
      const s = fit(ctx, card.lineup, 'Outfit', 600, colW, 2.6 * S);
      ctx.font = `600 ${s}px Outfit`; ctx.fillStyle = B.bone;
      y += s * 1.35; ctx.fillText(card.lineup, x, y);
      if (card.lineup2) { const s2 = fit(ctx, card.lineup2, 'Outfit', 600, colW, 2.6 * S); ctx.font = `600 ${s2}px Outfit`; y += s2 * 1.3; ctx.fillText(card.lineup2, x, y); }
      ctx.globalAlpha = 1;
    }

    // proof counter (e.g. YouTube views)
    if (card.proof && L !== 'strip') {
      const a = prog(t, 3.5, 1.4);
      const n = card.proof.n * ease(a);
      ctx.globalAlpha = clamp(a * 4); y += 3.2 * S;
      const s = (L === 'strip' ? 3.6 : 4.2) * S;
      ctx.font = `400 ${s}px Anton`; ctx.fillStyle = B.punch;
      const label = (a >= 1 ? card.proof.final : fmtCount(n)) ;
      ctx.fillText(label, x, y + s * 0.85);
      const lw = ctx.measureText(label).width;
      ctx.font = `600 ${1.9 * S}px Outfit`; ctx.fillStyle = B.bone;
      ctx.fillText(card.proof.label, x + lw + 1.2 * S, y + s * 0.8);
      y += s; ctx.globalAlpha = 1;
    }

    // CTA bar at bottom
    if (card.cta) {
      const a = ease(prog(t, 4.2, 0.6));
      ctx.globalAlpha = a;
      const s = fit(ctx, card.cta.toUpperCase(), 'Anton', 400, colW, (L === 'strip' ? 3.4 : 3.6) * S);
      ctx.font = `400 ${s}px Anton`;
      const by = L === 'strip' ? Math.min(H - H * 0.12, y + 7.5 * S) : wideL ? H - H * 0.09 : H - (L === 'story' ? H * 0.1 : H * 0.055);
      ctx.fillStyle = B.bone; ctx.fillText(card.cta.toUpperCase(), x, by);
      ctx.fillStyle = B.gold; ctx.fillRect(x, by + 0.8 * S, Math.min(colW, ctx.measureText(card.cta.toUpperCase()).width) * a, Math.max(2, 0.35 * S));
      if (card.fine) {
        ctx.fillStyle = B.dim; ctx.font = `500 ${1.35 * S}px "JetBrains Mono"`;
        tracked(ctx, card.fine.toUpperCase(), x, by + 3.0 * S, 0.2 * S, 'left');
      }
      ctx.globalAlpha = 1;
    }
    // end fade on motion only
    if (!still && card.fadeOut && t > DUR - 0.35) { ctx.fillStyle = `rgba(0,0,0,${(t - (DUR - 0.35)) / 0.35})`; ctx.fillRect(0, 0, W, H); }
    return { y, y0, ctaTop: card.cta ? (wideL ? H - H * 0.09 : H - (L === 'story' ? H * 0.1 : H * 0.055)) - 5 * S : H * 0.95 };
  }
  // fit pass: measure at the final frame, shrink type until the block clears the CTA line
  function draw(ctx, W, H, t, card, assets) {
    let k = 1, r;
    for (let i = 0; i < 4; i++) {
      r = drawOnce(ctx, W, H, DUR, card, assets, k);
      if (r.y <= r.ctaTop) break;
      k *= Math.max(0.6, (r.ctaTop - r.y0) / (r.y - r.y0)) * 0.98;
    }
    r = drawOnce(ctx, W, H, t, card, assets, k);
    return r.y;
  }

  const api = { draw, DUR, BRAND, layoutOf };
  if (typeof module !== 'undefined') module.exports = api; else root.BilloMotion = api;
})(typeof window !== 'undefined' ? window : globalThis);
