#!/usr/bin/env python3
# Copyright (c) 2026 Billy Sorrells Entertainment LLC. BilloTech Source License 1.0: free for personal and school use; paid work needs a BilloTech subscription. See LICENSE.md.
"""
BILLO FX FORGE — procedural effects, grades and cut rhythm for Billo OS.

Every pixel this makes comes from code (numpy + ffmpeg). No third-party
pack, preset or footage is copied or bundled, so everything it renders is
Billy's to ship. The effects wall (bay.fx_asset) was mined for technique
only: what a glitch, leak, burn, grain or flash *does*, rebuilt from scratch.

  gen     render a standalone overlay/loop       billo_fx.py gen leak -o leak.mp4 --dur 3
  fx      apply an effect to footage             billo_fx.py fx glitch -i in.mp4 -o out.mp4 --at 1.2,3.4
  lut     build a .cube grade                    billo_fx.py lut --look teal-warm -o teal.cube
                                                 billo_fx.py lut --ref still.jpg --src frame.jpg -o match.cube
  grade   apply a .cube to footage               billo_fx.py grade -i in.mp4 --cube teal.cube -o out.mp4
  cadence beat-locked cut list from a song       billo_fx.py cadence --audio song.wav --clips a.mp4 b.mp4 --recipe burst_hold -o cut
  sheet   contact sheet PNG of any video         billo_fx.py sheet -i out.mp4 -o out.png

House rules baked in:
  * previews render at 540x960; anything >= 1080 needs --final (lock references first)
  * --hits takes a Billo Sound FX cues.json so picture hits land on the same frames as the sound
  * deterministic: same --seed, same pixels
"""
import argparse, json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image

PREVIEW = (540, 960)
EFFECTS = ["glitch", "vhs", "leak", "burn", "grain", "flash", "strobe", "shake", "punch", "gradient", "bwsnap"]


# ───────────────────────── ffmpeg plumbing ─────────────────────────
def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    n, d = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(n) / float(d), float(j["format"].get("duration", 0))


def has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return bool(out.strip())


def check_size(w, h, final):
    if max(w, h) >= 1080 and not final:
        sys.exit(f"refusing {w}x{h}: previews stay under 1080. Lock the reference, then add --final.")


def reader(path, w, h):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size = w * h * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0
    p.wait()


def writer(out, w, h, fps, alpha=False, audio_from=None):
    pix = "rgba" if alpha else "rgb24"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", pix, "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-"]
    if audio_from and has_audio(audio_from):
        cmd += ["-i", audio_from, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    if alpha:
        cmd += ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    return subprocess.Popen(cmd + [out], stdin=subprocess.PIPE)


def emit(p, img, alpha=False):
    img = np.clip(img, 0, 1)
    if alpha:
        a = img.max(axis=2, keepdims=True)
        img = np.concatenate([img, a], axis=2)
    p.stdin.write((img * 255 + 0.5).astype(np.uint8).tobytes())


# ───────────────────────── noise helpers ─────────────────────────
def fbm(w, h, rng, octaves=4, base=4):
    """Fractal value noise in [0,1], built by upsampling random grids."""
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gw, gh = base * 2 ** o + 1, max(2, int(base * 2 ** o * h / w) + 1)
        g = rng.random((gh, gw)).astype(np.float32)
        acc += amp * np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC))
        tot += amp
        amp *= 0.5
    acc /= tot
    return (acc - acc.min()) / (np.ptp(acc) + 1e-6)


def blob(w, h, cx, cy, r):
    y, x = np.ogrid[:h, :w]
    return np.exp(-(((x - cx) ** 2 + (y - cy) ** 2) / (2 * r * r))).astype(np.float32)


def env(t, hits, length, shape="decay"):
    """0..1 strength at time t given hit times. Glitch-style effects ramp across the hit."""
    if not hits:
        return 1.0
    best = 0.0
    for h in hits:
        d = t - h
        if shape == "decay" and 0 <= d < length:
            best = max(best, math.exp(-5 * d / length))
        elif shape == "window" and abs(d) < length / 2:
            best = max(best, 1 - abs(d) / (length / 2))
    return best


LEAK_PALETTES = {
    "amber": [(1.0, 0.55, 0.15), (1.0, 0.25, 0.05), (1.0, 0.85, 0.5)],
    "magenta": [(1.0, 0.2, 0.55), (0.9, 0.35, 0.1), (1.0, 0.7, 0.8)],
    "teal": [(0.18, 0.84, 0.68), (0.6, 0.5, 1.0), (1.0, 0.8, 0.5)],
}


# ───────────────────────── the effects ─────────────────────────
class FX:
    def __init__(self, name, w, h, fps, seed, strength, palette, dur):
        self.name, self.w, self.h, self.fps, self.k = name, w, h, fps, strength
        self.rng = np.random.default_rng(seed)
        self.dur = dur
        self.pal = LEAK_PALETTES.get(palette, LEAK_PALETTES["amber"])
        if name == "leak":
            self.blobs = [(self.rng.random() * w, self.rng.random() * h, (0.12 + 0.16 * self.rng.random()) * max(w, h),
                           self.rng.random() * 6.28, 0.15 + 0.3 * self.rng.random(), c) for c in self.pal]
        if name == "burn":
            self.n1, self.n2 = fbm(w, h, self.rng, 5, 3), fbm(w, h, self.rng, 5, 3)
        if name in ("grain", "vhs"):
            self.scratches = []
        if name == "gradient":
            self.n1 = fbm(w, h, self.rng, 3, 2)

    def __call__(self, img, t, s):
        """img float32 HxWx3, t seconds, s envelope strength 0..1 (already scaled by --strength)."""
        w, h, r = self.w, self.h, self.rng
        if s <= 0.001 and self.name not in ("grain", "gradient", "bwsnap"):
            return img
        n = self.name
        if n == "glitch":
            out = img.copy()
            sh = int(2 + 18 * s)
            out[..., 0] = np.roll(img[..., 0], -sh, axis=1)
            out[..., 2] = np.roll(img[..., 2], sh, axis=1)
            for _ in range(int(3 + 14 * s)):                      # displaced bands
                y0 = r.integers(0, h - 4); bh = r.integers(2, max(3, int(h * 0.08 * s) + 3))
                out[y0:y0 + bh] = np.roll(out[y0:y0 + bh], int(r.normal(0, 60 * s)), axis=1)
            if r.random() < 0.5 * s:                              # crushed colour block
                y0, x0 = r.integers(0, h // 2), r.integers(0, w // 2)
                blk = out[y0:y0 + h // 6, x0:x0 + w // 3]
                out[y0:y0 + h // 6, x0:x0 + w // 3] = np.round(blk * 3) / 3
            out[::2] *= 1 - 0.25 * s                               # scanlines
            return out
        if n == "vhs":
            out = img.copy()
            ycc = out @ np.array([[0.299, -0.169, 0.5], [0.587, -0.331, -0.419], [0.114, 0.5, -0.081]], np.float32)
            k = int(4 + 10 * s)                                    # chroma bleed
            ker = np.ones(k, np.float32) / k
            for c in (1, 2):
                ycc[..., c] = np.apply_along_axis(lambda row: np.convolve(row, ker, "same"), 1, ycc[..., c]) * (1 - 0.3 * s)
            rows = (np.sin(np.arange(h) / 9.0 + t * 7) * 2 * s).astype(int)   # line wobble
            ycc[..., 0] = np.stack([np.roll(ycc[i, :, 0], rows[i]) for i in range(h)])
            band_y = int((t * 0.35 % 1.0) * (h + 80)) - 40                      # rolling tracking band
            y0, y1 = max(0, band_y), min(h, band_y + int(20 + 30 * s))
            if y1 > y0:
                ycc[y0:y1, :, 0] += r.random((y1 - y0, w)) * 0.5 * s
            ycc[-int(h * 0.02):, :, 0] += r.random((int(h * 0.02), w)) * 0.6       # head-switch noise
            ycc[..., 0] += r.normal(0, 0.03 * s, (h, w))
            m = np.array([[1, 1, 1], [0, -0.344, 1.772], [1.402, -0.714, 0]], np.float32)
            return ycc @ m
        if n == "leak":
            lay = np.zeros((h, w, 3), np.float32)
            for (cx, cy, rad, ph, sp, col) in self.blobs:
                x = cx + math.sin(t * sp * 2 + ph) * w * 0.35
                y = cy + math.cos(t * sp * 1.3 + ph) * h * 0.25
                b = blob(w, h, x, y, rad * (0.8 + 0.2 * math.sin(t + ph)))
                lay += (b ** 1.6)[..., None] * np.array(col, np.float32) * (0.55 + 0.45 * math.sin(t * sp * 3 + ph) ** 2)
            lay *= 0.85 * s * (0.85 + 0.15 * math.sin(t * 5.3))     # flicker
            return 1 - (1 - img) * (1 - np.clip(lay, 0, 1))      # screen
        if n == "burn":
            prog = s
            a = (self.n1 * (1 - (t % 1)) + self.n2 * (t % 1))
            thr = 1 - prog * 0.7
            edge = np.exp(-((a - thr) / 0.05) ** 2) * (prog > 0.02)
            core = np.clip((a - thr - 0.03) * 8, 0, 1)
            col = (edge[..., None] * np.array([1.0, 0.45, 0.08], np.float32)
                   + core[..., None] * np.array([1.0, 0.93, 0.78], np.float32)
                   + prog * 0.25 * np.array([0.9, 0.35, 0.05], np.float32))
            return 1 - (1 - img) * (1 - np.clip(col, 0, 1))
        if n == "grain":
            k = self.k
            lum = img.mean(axis=2, keepdims=True)
            g = r.normal(0, 0.06 * k, (h, w, 1)).astype(np.float32) * (0.5 + (1 - np.abs(lum - 0.5) * 2))
            out = img + g
            for _ in range(r.poisson(3 * k)):                     # dust specks
                cx, cy, rad = r.integers(0, w), r.integers(0, h), r.integers(1, 4)
                out[max(0, cy - rad):cy + rad, max(0, cx - rad):cx + rad] = 0.05 if r.random() < 0.7 else 0.95
            if r.random() < 0.08 * k:
                self.scratches.append([r.integers(0, w), r.integers(3, 12)])
            for sc in self.scratches:                              # vertical scratches that persist
                out[:, sc[0]:sc[0] + 1] *= 0.55
                sc[1] -= 1
            self.scratches = [sc for sc in self.scratches if sc[1] > 0]
            dx, dy = int(r.normal(0, 0.8 * k)), int(r.normal(0, 0.8 * k))   # gate weave
            out = np.roll(out, (dy, dx), axis=(0, 1))
            vig = 1 - 0.35 * k * (blob(w, h, w / 2, h / 2, max(w, h) * 0.55) < 0.5)
            return out * (vig[..., None] if np.ndim(vig) else vig) * (1 + r.normal(0, 0.015 * k))
        if n == "flash":
            return img + (1 - img) * s
        if n == "strobe":
            on = int(t * self.fps) % 2 == 0
            return img + (1 - img) * s if on else img * (1 - 0.6 * s)
        if n in ("shake", "punch"):
            z = 1 + (0.3 if n == "punch" else 0.06) * s
            dx = int(r.normal(0, 18 * s)) if n == "shake" else 0
            dy = int(r.normal(0, 18 * s)) if n == "shake" else 0
            cw, ch = int(w / z), int(h / z)
            x0 = np.clip((w - cw) // 2 + dx, 0, w - cw); y0 = np.clip((h - ch) // 2 + dy, 0, h - ch)
            crop = (img[y0:y0 + ch, x0:x0 + cw] * 255).astype(np.uint8)
            return np.asarray(Image.fromarray(crop).resize((w, h), Image.BICUBIC), np.float32) / 255
        if n == "gradient":                                        # seamless LED-wall loop
            ph = 2 * math.pi * (t / self.dur)
            y, x = np.mgrid[0:h, 0:w].astype(np.float32)
            u = (x / w) * math.cos(ph) + (y / h) * math.sin(ph) + self.n1 * 0.6
            cols = np.array(self.pal, np.float32)
            v = (np.sin(u * 2 * math.pi + ph) + 1) / 2
            lay = cols[0] * v[..., None] + cols[1] * (1 - v[..., None])
            return img * (1 - s) + lay * s
        if n == "bwsnap":                                          # B&W for the past, colour snaps back on the hit
            lum = (img @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
            bw = np.clip((lum - 0.5) * 1.25 + 0.5, 0, 1).repeat(3, 2)
            return img * (1 - s) + bw * s
        return img


def parse_hits(args, fps):
    hits = []
    if args.at:
        hits += [float(x) for x in args.at.split(",") if x.strip()]
    if args.hits:
        j = json.load(open(args.hits))
        cues = j.get("cues", j) if isinstance(j, dict) else j
        for c in cues:
            if "t" in c: hits.append(float(c["t"]))
            elif "frame" in c: hits.append(c["frame"] / fps)
    return sorted(hits)


def cmd_gen(a):
    w, h = map(int, a.size.split("x")) if a.size else PREVIEW
    check_size(w, h, a.final)
    fx = FX(a.effect, w, h, a.fps, a.seed, a.strength, a.palette, a.dur)
    p = writer(a.o, w, h, a.fps, alpha=a.alpha)
    hits = parse_hits(a, a.fps)
    nfr = int(a.dur * a.fps)
    for i in range(nfr):
        t = i / a.fps
        if a.effect == "burn" and not hits:
            s = min(1, math.sin(math.pi * t / a.dur) * 1.2) * a.strength
        else:
            s = env(t, hits, a.len, "window" if a.effect in ("glitch", "vhs") else "decay") * a.strength
        base = np.zeros((h, w, 3), np.float32)
        emit(p, fx(base, t, s), a.alpha)
    p.stdin.close(); p.wait()
    print(json.dumps({"out": a.o, "effect": a.effect, "size": f"{w}x{h}", "frames": nfr, "seed": a.seed}))


def cmd_fx(a):
    W, H, fps, dur = probe(a.i)
    w, h = map(int, a.size.split("x")) if a.size else PREVIEW
    check_size(w, h, a.final)
    fx = FX(a.effect, w, h, fps, a.seed, a.strength, a.palette, dur)
    hits = parse_hits(a, fps)
    if a.effect == "bwsnap" and hits:                          # B&W until the first hit, then colour
        snap = hits[0]
    p = writer(a.o, w, h, fps, audio_from=a.i)
    for i, img in enumerate(reader(a.i, w, h)):
        t = i / fps
        if a.effect == "bwsnap":
            s = (1.0 if not hits or t < snap else max(0, 1 - (t - snap) / 0.08)) * a.strength
        elif a.effect in ("grain", "gradient"):
            s = a.strength
        else:
            s = env(t, hits, a.len, "window" if a.effect in ("glitch", "vhs", "burn") else "decay") * a.strength
        emit(p, fx(img, t, s))
    p.stdin.close(); p.wait()
    print(json.dumps({"out": a.o, "effect": a.effect, "hits": hits, "size": f"{w}x{h}"}))


# ───────────────────────── grades (.cube) ─────────────────────────
LOOKS = {
    # name: (description, fn(rgb) -> rgb) — mined from the reference wall's grade notes, rebuilt as maths
    "teal-warm": "teal shadows, warm skin (sports broadcast recap)",
    "golden-amber": "golden-hour amber as the whole grade (narrated trailer)",
    "low-sat-bright": "bright, low-saturation outdoor (brand spot)",
    "warm-red": "warm red grade (track & field golden hour)",
    "neutral-teal-accent": "neutral grade, teal accent kept (event recap)",
    "bw-contrast": "black & white with lifted contrast (the past / the walk-out)",
    "practical-warm": "warm practical gym light kept warm (hoops mixtape)",
}


def _sat(rgb, k):
    l = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return l[..., None] + (rgb - l[..., None]) * k


def look_fn(name):
    def f(x):
        l = (x @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
        if name == "teal-warm":
            sh = (1 - l) ** 2; hi = l ** 2
            y = x + sh * np.array([-0.06, 0.02, 0.06]) + hi * np.array([0.05, 0.015, -0.04])
            return _sat(y, 1.08)
        if name == "golden-amber":
            y = x * np.array([1.06, 0.98, 0.82]) + np.array([0.03, 0.015, 0])
            return _sat(y, 0.92) ** 0.95
        if name == "low-sat-bright":
            return _sat(x, 0.7) * 0.92 + 0.08
        if name == "warm-red":
            return _sat(x * np.array([1.08, 0.95, 0.88]), 1.05)
        if name == "neutral-teal-accent":
            # pull everything toward neutral except hues near teal
            hue_teal = np.clip(1 - np.abs((x[..., 1:2] + x[..., 2:3]) / 2 - x[..., 0:1] - 0.25) * 3, 0, 1)
            return _sat(x, 0.75 + 0.45 * hue_teal)
        if name == "bw-contrast":
            y = np.clip((l - 0.5) * 1.25 + 0.5, 0, 1)
            return np.repeat(y, 3, axis=-1)
        if name == "practical-warm":
            return _sat(x * np.array([1.05, 1.0, 0.9]), 0.98)
        return x
    return f


def ycc_stats(img):
    m = np.array([[0.299, 0.587, 0.114], [-0.169, -0.331, 0.5], [0.5, -0.419, -0.081]], np.float32)
    y = img.reshape(-1, 3) @ m.T
    return y.mean(0), y.std(0) + 1e-6, m


def transfer_fn(src, ref):
    ms, ss, m = ycc_stats(src); mr, sr, _ = ycc_stats(ref)
    mi = np.linalg.inv(m)
    def f(x):
        y = x @ m.T
        y = (y - ms) / ss * sr + mr
        return y @ mi.T
    return f


def write_cube(fn, path, n=33, title="Billo"):
    g = np.linspace(0, 1, n, dtype=np.float32)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")      # .cube order: R fastest
    rgb = np.stack([r, gg, b], -1).reshape(-1, 3)
    out = np.clip(fn(rgb), 0, 1)
    with open(path, "w") as fh:
        fh.write(f'TITLE "{title}"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        for v in out:
            fh.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")


def load_img(p):
    im = Image.open(p).convert("RGB"); im.thumbnail((512, 512))
    return np.asarray(im, np.float32) / 255


def cmd_lut(a):
    if a.ref:
        if not a.src:
            sys.exit("--ref needs --src (a frame from the footage you are grading)")
        fn, title = transfer_fn(load_img(a.src), load_img(a.ref)), f"Billo match {os.path.basename(a.ref)}"
    else:
        if a.look not in LOOKS:
            sys.exit("looks: " + ", ".join(LOOKS))
        fn, title = look_fn(a.look), f"Billo {a.look}"
    write_cube(fn, a.o, a.n, title)
    print(json.dumps({"out": a.o, "title": title, "size": a.n}))


def cmd_grade(a):
    w, h = map(int, a.size.split("x")) if a.size else PREVIEW
    check_size(w, h, a.final)
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},lut3d='{a.cube}'"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.i, "-vf", vf, "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", a.o], check=True)
    print(json.dumps({"out": a.o, "cube": a.cube}))


# ───────────────────────── cadence (cut rhythm) ─────────────────────────
def load_audio(path, sr=22050):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768, sr


def onsets(y, sr, hop=512, band=None):
    n = 2048
    frames = 1 + (len(y) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    S = np.abs(np.fft.rfft(y[idx] * np.hanning(n), axis=1))
    f = np.fft.rfftfreq(n, 1 / sr)
    if band:
        S = S[:, (f >= band[0]) & (f < band[1])]
    S = np.log1p(S * 10)
    flux = np.maximum(0, np.diff(S, axis=0)).sum(1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-6)
    times = (np.arange(len(flux)) + 1) * hop / sr
    return flux, times


def peaks(flux, times, thresh=1.0, min_gap=0.12):
    out, last = [], -9
    for i in range(1, len(flux) - 1):
        if flux[i] > thresh and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and times[i] - last >= min_gap:
            out.append(float(times[i])); last = times[i]
    return out


def tempo(flux, sr, hop=512):
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    lags = np.arange(len(ac)) * hop / sr
    ok = (lags > 60 / 180) & (lags < 60 / 70)
    i = int(np.flatnonzero(ok)[np.argmax(ac[ok])])
    a0, a1, a2 = ac[i - 1], ac[i], ac[i + 1]              # parabolic peak refine
    off = 0.5 * (a0 - a2) / (a0 - 2 * a1 + a2 + 1e-9)
    return 60 / ((i + off) * hop / sr)


RECIPES = {
    "burst_hold": "runs of 3-frame shots (12-15) on the drop, then a long hold (130 f); repeat",
    "pattern3": "the same 3-cut figure every bar: texture / effort / wide, third shot holds to the bar line",
    "kick_cut": "cut on the kick / sub-hit (20-150 Hz onsets), not just the beat; min 6 frames per shot",
    "slow_locked": "slow cut that is still beat-locked: one cut per bar, final hero hold 207 f",
}


def cmd_cadence(a):
    y, sr = load_audio(a.audio)
    full, times = onsets(y, sr, hop=256)
    bpm = a.bpm or tempo(full, sr, hop=256)
    beat = 60 / bpm
    kicks = peaks(*onsets(y, sr, band=(20, 150)), thresh=1.2, min_gap=0.18)
    first = kicks[0] if kicks else 0.0
    dur = min(len(y) / sr, a.max or 1e9)
    fps = a.fps
    cuts = [first]
    if a.recipe == "kick_cut":
        for k in kicks:
            if k - cuts[-1] >= 6 / fps and k < dur:
                cuts.append(k)
    elif a.recipe == "pattern3":
        t = first
        while t < dur:
            cuts += [t + beat, t + 2 * beat, t + 4 * beat]
            t += 4 * beat
    elif a.recipe == "slow_locked":
        t = first
        while t + 4 * beat < dur - 207 / fps:
            t += 4 * beat; cuts.append(t)
    else:  # burst_hold
        t = first
        rng = np.random.default_rng(a.seed)
        while t < dur:
            for _ in range(int(rng.integers(12, 16))):
                t += 3 / fps; cuts.append(t)
            t += 130 / fps
            t = first + math.ceil((t - first) / beat) * beat     # land the next burst on a beat
            cuts.append(t)
    cuts = sorted(set(round(c * fps) for c in cuts if c < dur))
    cuts.append(round(dur * fps))
    shots, rng = [], np.random.default_rng(a.seed)
    lens = [probe(c)[3] for c in a.clips] if a.clips else []
    for i in range(len(cuts) - 1):
        f0, f1 = cuts[i], cuts[i + 1]
        if f1 <= f0:
            continue
        src = i % max(1, len(a.clips or [1]))
        need = (f1 - f0) / fps
        cin = float(rng.uniform(0, max(0.0, lens[src] - need))) if lens else 0.0
        shots.append({"n": len(shots) + 1, "rec_in": f0, "rec_out": f1, "frames": f1 - f0,
                      "clip": a.clips[src] if a.clips else None, "src_in": round(cin, 3)})
    os.makedirs(os.path.dirname(a.o) or ".", exist_ok=True)
    plan = {"recipe": a.recipe, "rule": RECIPES[a.recipe], "bpm": round(bpm, 2), "fps": fps,
            "kicks": len(kicks), "shots": shots, "audio": a.audio}
    json.dump(plan, open(a.o + ".json", "w"), indent=1)
    tc = lambda f: f"{int(f // (3600 * fps)):02d}:{int(f // (60 * fps)) % 60:02d}:{int(f // fps) % 60:02d}:{int(f % fps):02d}"
    with open(a.o + ".edl", "w") as e:
        e.write(f"TITLE: BILLO CADENCE {a.recipe.upper()}\nFCM: NON-DROP FRAME\n\n")
        for s in shots:
            si = round(s["src_in"] * fps)
            e.write(f"{s['n']:03d}  AX       V     C        {tc(si)} {tc(si + s['frames'])} {tc(s['rec_in'])} {tc(s['rec_out'])}\n")
            if s["clip"]:
                e.write(f"* FROM CLIP NAME: {os.path.basename(s['clip'])}\n")
    if a.preview and a.clips:
        w, h = PREVIEW
        lst = a.o + ".parts"
        os.makedirs(lst, exist_ok=True)
        names = []
        for s in shots:
            pn = os.path.join(lst, f"{s['n']:04d}.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-ss", str(s["src_in"]), "-i", s["clip"], "-frames:v", str(s["frames"]),
                            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}", "-an",
                            "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", pn], check=True)
            names.append(pn)
        with open(lst + ".txt", "w") as fh:
            fh.writelines(f"file '{os.path.abspath(n)}'\n" for n in names)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst + ".txt", "-i", a.audio,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", a.o + ".preview.mp4"], check=True)
    print(json.dumps({k: plan[k] for k in ("recipe", "bpm", "kicks")} | {"shots": len(shots), "edl": a.o + ".edl"}))


def cmd_sheet(a):
    W, H, fps, dur = probe(a.i)
    n = a.n
    tiles = []
    for k in range(n):
        t = dur * (k + 0.5) / n
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", a.i, "-frames:v", "1", "-vf", "scale=180:-2",
                              "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        import io
        tiles.append(Image.open(io.BytesIO(raw)).convert("RGB"))
    tw, th = tiles[0].size
    sheet = Image.new("RGB", (tw * n, th), (0, 0, 0))
    for k, im in enumerate(tiles):
        sheet.paste(im, (k * tw, 0))
    sheet.save(a.o)
    print(json.dumps({"out": a.o, "tiles": n}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--size"); p.add_argument("--final", action="store_true")
        p.add_argument("--seed", type=int, default=7); p.add_argument("--strength", type=float, default=1.0)
        p.add_argument("--palette", default="amber", choices=list(LEAK_PALETTES))
        p.add_argument("--at", help="hit times in seconds, comma separated"); p.add_argument("--hits", help="Billo Sound FX cues.json")
        p.add_argument("--len", type=float, default=0.5, help="seconds each hit lasts")

    g = sp.add_parser("gen"); g.add_argument("effect", choices=EFFECTS); g.add_argument("-o", required=True)
    g.add_argument("--dur", type=float, default=3); g.add_argument("--fps", type=float, default=24)
    g.add_argument("--alpha", action="store_true", help="ProRes 4444 with alpha"); common(g)
    f = sp.add_parser("fx"); f.add_argument("effect", choices=EFFECTS); f.add_argument("-i", required=True); f.add_argument("-o", required=True); common(f)
    l = sp.add_parser("lut"); l.add_argument("--look"); l.add_argument("--ref"); l.add_argument("--src"); l.add_argument("-o", required=True); l.add_argument("-n", type=int, default=33)
    gr = sp.add_parser("grade"); gr.add_argument("-i", required=True); gr.add_argument("--cube", required=True); gr.add_argument("-o", required=True)
    gr.add_argument("--size"); gr.add_argument("--final", action="store_true")
    c = sp.add_parser("cadence"); c.add_argument("--audio", required=True); c.add_argument("--clips", nargs="*")
    c.add_argument("--recipe", default="burst_hold", choices=list(RECIPES)); c.add_argument("-o", required=True)
    c.add_argument("--fps", type=int, default=24); c.add_argument("--bpm", type=float); c.add_argument("--max", type=float)
    c.add_argument("--seed", type=int, default=7); c.add_argument("--preview", action="store_true")
    s = sp.add_parser("sheet"); s.add_argument("-i", required=True); s.add_argument("-o", required=True); s.add_argument("-n", type=int, default=6)
    a = ap.parse_args()
    {"gen": cmd_gen, "fx": cmd_fx, "lut": cmd_lut, "grade": cmd_grade, "cadence": cmd_cadence, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    main()
