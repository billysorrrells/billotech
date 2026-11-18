"""BILLO REBIRTH - 'STAY THROWED' (third iteration) - original instrumental, built from scratch.
No samples from any record. 83 BPM, E minor, i-iv vamp with a bVI-bVII turn on the hook.
Renders stems + mixed/mastered stereo WAV.  python3 make_track.py outdir
"""
import sys, os, numpy as np, soundfile as sf
from scipy import signal
import pyloudnorm as pyln

SR = 44100
BPM = 83.0
BEAT = 60.0 / BPM
STEP = BEAT / 4
BAR = BEAT * 4
rng = np.random.default_rng(713)
out = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(out, exist_ok=True)

# ---------- arrangement ----------
SECTIONS = [("intro", 4), ("hook", 8), ("verse1", 16), ("hook", 8), ("verse2", 16), ("hook", 8)]
bars = []
for name, n in SECTIONS:
    for i in range(n):
        bars.append((name, i, n))
NB = len(bars)
N = int((NB * BAR + 4.0) * SR)
t_bar = lambda b, step=0.0: int((b * BAR + step * STEP) * SR)

def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)
E, A, C, D = 40, 45, 48, 50  # E2 A2 C3 D3
CH = {"Em": (E, [64, 67, 71, 74]), "Am": (A, [64, 67, 69, 72]), "C": (C, [64, 67, 72, 76]), "D": (D, [66, 69, 74, 78])}

def chords_for(b):
    name, i, n = bars[b]
    k = i % 4
    if k in (0, 1): return [("Em", 0, 16)]
    if k == 2: return [("Am", 0, 16)]
    if name == "hook" or (name.startswith("verse") and i % 8 == 7):
        return [("C", 0, 8), ("D", 8, 8)]
    return [("Am", 0, 16)]

def butter(x, kind, fc, order=2):
    sos = signal.butter(order, fc, kind, fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)

def place(buf, s, start, gain=1.0):
    if start >= len(buf): return
    e = min(len(buf), start + len(s))
    buf[start:e] += s[: e - start] * gain

def env_ar(n, a=0.005, r=0.03):
    e = np.ones(n, np.float32)
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr)
    return e

# ---------- drum one-shots ----------
def kick():
    n = int(0.32 * SR); t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t * 38)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)
    x[:120] += rng.normal(0, 0.25, 120) * np.linspace(1, 0, 120)
    return np.tanh(x * 1.8).astype(np.float32)

def snare():
    n = int(0.3 * SR); t = np.arange(n) / SR
    nz = butter(rng.normal(0, 1, n), "bandpass", [1400, 7500]) * np.exp(-t * 17)
    body = np.sin(2 * np.pi * (185 + 60 * np.exp(-t * 60)) * t) * np.exp(-t * 26)
    return (nz * 0.9 + body * 0.7).astype(np.float32)

def clap():
    n = int(0.35 * SR); x = np.zeros(n, np.float32)
    for d in (0, 0.011, 0.023, 0.034):
        m = n - int(d * SR); tt = np.arange(m) / SR
        x[int(d * SR):] += butter(rng.normal(0, 1, m), "bandpass", [900, 4200]) * np.exp(-tt * (30 if d < 0.03 else 12))
    return x * 0.5

def hat(dec):
    n = int(dec * 6 * SR); t = np.arange(n) / SR
    return (butter(rng.normal(0, 1, n), "highpass", 7200, 4) * np.exp(-t / dec)).astype(np.float32)

def rim():
    n = int(0.06 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1700 * t) * np.exp(-t * 90) + np.sin(2 * np.pi * 820 * t) * np.exp(-t * 70)).astype(np.float32) * 0.6

KICK, SNARE, CLAP, HATC, HATO, RIM = kick(), snare(), clap(), hat(0.018), hat(0.11), rim()

def sub808(midi, dur, glide_to=None):
    n = int(dur * SR); t = np.arange(n) / SR
    f0 = mtof(midi - 12)
    f = np.full(n, f0)
    if glide_to is not None:
        g0 = int(n * 0.45)
        f[g0:] = f0 * (mtof(glide_to - 12) / f0) ** np.clip((np.arange(n - g0)) / (0.18 * SR), 0, 1)
    f = f * (1 + 1.2 * np.exp(-t * 55))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x = np.tanh(x * 3.2) * 0.7 + 0.25 * np.sin(2 * np.pi * np.cumsum(f * 2) / SR) + x * 0.2
    return (x * np.exp(-t * 1.6) * env_ar(n, 0.003, 0.05)).astype(np.float32)

# ---------- guitar engine ----------
def gtr(midi, dur, bend=0.0, vib=0.0, drive=6.0, bright=4200, slide_from=None):
    n = int(dur * SR); t = np.arange(n) / SR
    semi = np.zeros(n)
    if bend:
        semi += bend * np.clip(t / min(0.22, dur * 0.4), 0, 1) ** 1.5
    if slide_from is not None:
        semi += (slide_from - midi) * np.clip(1 - t / 0.09, 0, 1)
    if vib:
        semi += vib * np.sin(2 * np.pi * 5.6 * t) * np.clip((t - 0.18) / 0.25, 0, 1)
    f = mtof(midi) * 2 ** (semi / 12)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros(n)
    for k in range(1, 13):
        x += np.sin(k * ph + 0.3 * k) / k ** 0.9 * np.exp(-t * (0.9 + 0.55 * k))
    x[: int(0.004 * SR)] += rng.normal(0, 0.4, int(0.004 * SR))
    x = np.tanh(x * drive) / np.tanh(drive * 0.6)
    x = butter(butter(x, "lowpass", bright, 2), "highpass", 110)
    pk = signal.sosfilt(signal.butter(2, [1500, 2600], "bandpass", fs=SR, output="sos"), x)
    return ((x + 0.6 * pk) * env_ar(n, 0.002, 0.04) * 0.5).astype(np.float32)

def stab(notes, dur=0.11):
    n = int(dur * SR); x = np.zeros(n, np.float32)
    for i, m in enumerate(notes):
        s = gtr(m, dur, drive=1.6, bright=5200)
        d = int(i * 0.004 * SR); x[d:] += s[: n - d]
    return x * 0.5

# licks: (step, midi, steps_long, bend, vib, slide_from)
LICKS = {
    "call":   [(0, 64, 3, 0, 0, 62), (3, 67, 1, 0, 0, None), (4, 69, 4, 1, .25, None), (9, 67, 1, 0, 0, None), (10, 64, 2, 0, 0, None), (12, 62, 1, 0, 0, None), (13, 64, 3, 0, .3, None)],
    "answer": [(2, 71, 2, 0, 0, None), (4, 74, 4, 2, .3, None), (8, 74, 1, 0, 0, None), (9, 71, 1, 0, 0, None), (10, 69, 2, 1, 0, None), (12, 67, 1, 0, 0, None), (13, 64, 3, 0, .35, 62)],
    "cry":    [(0, 76, 6, 0, .35, 74), (6, 74, 2, 0, 0, None), (8, 71, 2, 0, 0, None), (10, 70, 1, 0, 0, None), (11, 69, 1, 0, 0, None), (12, 67, 4, 0, .3, None)],
    "turn":   [(0, 67, 2, 0, 0, None), (2, 72, 2, 0, 0, None), (4, 76, 4, 0, .3, None), (8, 69, 2, 0, 0, None), (10, 74, 2, 0, 0, None), (12, 78, 4, 0, .35, 76)],
    "fill":   [(8, 64, 1, 0, 0, None), (9, 67, 1, 0, 0, None), (10, 69, 1, 0, 0, None), (11, 70, 1, 0, 0, None), (12, 71, 4, 1, .3, None)],
    "low":    [(0, 52, 2, 0, 0, 50), (2, 55, 1, 0, 0, None), (3, 57, 3, 0, .2, None), (8, 55, 1, 0, 0, None), (9, 52, 2, 0, 0, None), (12, 50, 1, 0, 0, None), (13, 52, 3, 0, .25, None)],
}

def organ(notes, dur, level=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    L = np.zeros(n); R = np.zeros(n)
    draw = [(0.5, .7), (1, 1.0), (1.5, .55), (2, .6), (3, .25), (4, .3), (6, .12)]
    for m in notes:
        f = mtof(m - 12)
        for mult, w in draw:
            vibL = 0.0025 * np.sin(2 * np.pi * 6.1 * t); vibR = 0.0025 * np.sin(2 * np.pi * 6.1 * t + 1.9)
            L += w * np.sin(2 * np.pi * f * mult * (t + vibL)); R += w * np.sin(2 * np.pi * f * mult * (t + vibR))
    trL = 1 + 0.18 * np.sin(2 * np.pi * 6.1 * t); trR = 1 + 0.18 * np.sin(2 * np.pi * 6.1 * t + 2.4)
    e = env_ar(n, 0.04, 0.12) * level / (len(notes) * 3.2)
    x = np.stack([L * trL * e, R * trR * e], 1)
    x = np.tanh(x * 1.6)
    return signal.sosfilt(signal.butter(2, 4200, "lowpass", fs=SR, output="sos"), x, axis=0).astype(np.float32)

def rhodes(midi, dur):
    n = int(dur * SR); t = np.arange(n) / SR; f = mtof(midi)
    x = np.sin(2 * np.pi * f * t + 1.3 * np.exp(-t * 5) * np.sin(2 * np.pi * f * t)) * np.exp(-t * 2.6)
    x += 0.25 * np.sin(2 * np.pi * f * 14 * t) * np.exp(-t * 30)
    return (x * env_ar(n, 0.002, 0.05) * 0.35).astype(np.float32)

VOW = {"a": (730, 1090), "o": (500, 900), "e": (530, 1840), "u": (325, 870), "i": (300, 2250)}
def talk(midi, dur, v1, v2, bend=0.0):
    n = int(dur * SR); t = np.arange(n) / SR
    semi = bend * np.clip(1 - t / 0.08, 0, 1) * -1 + 0.18 * np.sin(2 * np.pi * 5.2 * t) * np.clip((t - 0.2) / 0.3, 0, 1)
    f = mtof(midi) * 2 ** (semi / 12)
    saw = signal.sawtooth(2 * np.pi * np.cumsum(f) / SR) + 0.5 * signal.sawtooth(2 * np.pi * np.cumsum(f * 1.006) / SR)
    def form(v):
        y = np.zeros(n)
        for fc, q, g in ((VOW[v][0], 7, 1.0), (VOW[v][1], 9, 0.7), (2700, 10, 0.25)):
            y += g * signal.sosfilt(signal.butter(2, [fc * (1 - .5 / q), fc * (1 + .5 / q)], "bandpass", fs=SR, output="sos"), saw)
        return y
    mix = np.clip(t / dur * 1.6 - 0.2, 0, 1)
    x = form(v1) * (1 - mix) + form(v2) * mix
    return (np.tanh(x * 2.5) * env_ar(n, 0.02, 0.06) * 0.5).astype(np.float32)

# hook melody for talkbox, 4 bars: (bar, step, midi, steps, v1, v2)
HOOK = [(0, 0, 64, 3, "e", "i"), (0, 4, 67, 3, "o", "u"), (0, 8, 69, 6, "a", "o"),
        (1, 0, 67, 2, "e", "i"), (1, 3, 64, 2, "o", "u"), (1, 6, 62, 2, "a", "e"), (1, 8, 64, 7, "o", "a"),
        (2, 0, 69, 3, "e", "i"), (2, 4, 72, 3, "o", "u"), (2, 8, 71, 3, "a", "o"), (2, 12, 69, 3, "e", "a"),
        (3, 0, 67, 6, "o", "u"), (3, 8, 69, 3, "a", "e"), (3, 12, 71, 4, "o", "a")]

# ---------- stems ----------
M = lambda: np.zeros(N, np.float32)
S2 = lambda: np.zeros((N, 2), np.float32)
kickb, snb, hatb, percb, subb = M(), M(), M(), M(), M()
orgb = S2(); rhob = M(); leadb = M(); rgb = M(); lowgb = M(); talkb = M()

for b in range(NB):
    name, i, n = bars[b]
    intro = name == "intro"; hook = name == "hook"; v1 = name == "verse1"; v2 = name == "verse2"
    last = i == n - 1; k4 = i % 4
    chs = chords_for(b)
    # --- organ / keys
    for cn, s0, ln in chs:
        root, notes = CH[cn]
        lvl = 0.55 if intro else (1.0 if hook else 0.6)
        place(orgb, organ(notes, ln * STEP + 0.05, lvl), t_bar(b, s0))
        if v2 or hook:
            arp = notes + [notes[1] + 12]
            for j in range(0, ln, 2):
                place(rhob, rhodes(arp[(j // 2 + b) % len(arp)] + 12, STEP * 3), t_bar(b, s0 + j), 0.8 if hook else 0.6)
    if intro and i < 2:
        pass
    else:
        # --- 808 + kick
        pat = [0, 6, 10] if k4 != 3 else [0, 6, 11]
        if i % 2 == 1 and not intro: pat = pat + [14]
        for cn, s0, ln in chs:
            root = CH[cn][0]
            for s in pat:
                if s0 <= s < s0 + ln:
                    longn = s in (0, 10, 11, 8)
                    glide = root + 12 if (k4 == 3 and s >= 10 and not (hook)) else None
                    d = (4.6 if longn else 2.4) * STEP
                    if not intro:
                        place(subb, sub808(root, d, glide), t_bar(b, s), 1.0 if longn else 0.8)
                    place(kickb, KICK, t_bar(b, s), 1.0 if s == 0 else 0.85)
            if s0 == 8 and not intro:
                place(subb, sub808(root, 4.5 * STEP), t_bar(b, 8)); place(kickb, KICK, t_bar(b, 8), 0.9)
        # --- backbeat
        if not intro:
            for s in (4, 12):
                place(snb, SNARE, t_bar(b, s), 0.9); place(snb, CLAP, t_bar(b, s), 0.8 if hook else 0.55)
            if last or k4 == 3:
                place(snb, SNARE, t_bar(b, 15), 0.45)
                if last:
                    for s, g in ((13, .35), (14, .5), (14.5, .55), (15, .7), (15.5, .8)): place(snb, SNARE, t_bar(b, s), g)
            for s in (7, 10) if v2 else ((10,) if v1 else ()): place(percb, RIM, t_bar(b, s), 0.5)
        # --- hats
        sw = 0.14
        for s in range(16):
            if intro and i < 3: break
            off = sw if s % 2 == 1 else 0
            vel = (0.75 if s % 4 == 0 else 0.45 if s % 2 == 0 else 0.3) * (1 + rng.normal(0, .06))
            if s % 2 == 0 or hook or v2 or (k4 == 3):
                place(hatb, HATC, t_bar(b, s + off), vel)
        if not intro:
            if i % 2 == 1:
                for r in range(6): place(hatb, HATC, t_bar(b, 12 + r * (2 / 3)), 0.25 + r * .07)   # triplet roll
            if k4 == 1:
                for r in range(8): place(hatb, HATC, t_bar(b, 14 + r * .25), 0.2 + r * .05)        # 32nd roll
            if k4 in (0, 2): place(hatb, HATO, t_bar(b, 14), 0.4)
    # --- rhythm guitar (chicken scratch on the upbeats)
    if not intro:
        for cn, s0, ln in chs:
            notes = [m for m in CH[cn][1][:3]]
            for s in (2, 7, 10, 15) if hook else (2, 10):
                if s0 <= s < s0 + ln: place(rgb, stab(notes), t_bar(b, s + (0.14 if s % 2 else 0)), 0.9 if hook else 0.6)
    # --- lead guitar
    lick = None
    if intro: lick = ["call", "answer", "cry", "turn"][i]
    elif hook: lick = ["answer", None, "cry", "turn", "call", None, "cry", "turn"][i]
    elif k4 == 3: lick = "fill" if i % 8 == 3 else "turn"
    elif v2 and k4 == 1: lick = "answer" if i % 8 == 5 else None
    if lick:
        for s, m, ln, bd, vb, sl in LICKS[lick]:
            place(leadb, gtr(m, ln * STEP * 1.15, bend=bd, vib=vb, slide_from=sl, drive=7.5), t_bar(b, s), 0.9)
    if (intro and i >= 2) or (hook and i % 4 in (0, 2)):
        for s, m, ln, bd, vb, sl in LICKS["low"]:
            if k4 == 2: m += 5
            place(lowgb, gtr(m, ln * STEP * 1.1, vib=vb, slide_from=(sl + 5 if (sl and k4 == 2) else sl), drive=3.5, bright=3000), t_bar(b, s), 0.8)
    # --- talkbox hook
    if hook:
        for hb, s, m, ln, a, o in HOOK:
            if hb == k4: place(talkb, talk(m, ln * STEP, a, o, bend=1.0), t_bar(b, s), 0.9 if i >= 4 else 0.75)

# ---------- mix ----------
def pan(x, p):  # -1..1
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1).astype(np.float32)

def reverb(x, secs=1.8, wet=0.25, pre=0.02, lp=5000):
    n = int(secs * SR); t = np.arange(n) / SR
    outp = np.zeros_like(x)
    for c in range(2):
        ir = rng.normal(0, 1, n) * np.exp(-t * 6.9 / secs); ir = butter(ir, "lowpass", lp); ir = butter(ir, "highpass", 300)
        ir = np.concatenate([np.zeros(int(pre * SR), np.float32), ir]); ir /= np.sqrt((ir ** 2).sum())
        outp[:, c] = signal.fftconvolve(x[:, c], ir)[: len(x)]
    return x + wet * outp

def delay(x, steps=3, fb=0.38, wet=0.3, cross=True):
    d = int(steps * STEP * SR); y = np.zeros_like(x); cur = x.copy()
    for k in range(5):
        cur = np.roll(cur, d, axis=0) * fb; cur[:d] = 0
        cur = signal.sosfilt(signal.butter(1, 2800, "lowpass", fs=SR, output="sos"), cur, axis=0).astype(np.float32)
        if cross: cur = cur[:, ::-1]
        y += cur
    return x + wet * y / fb

# sidechain from kick
kenv = np.abs(kickb); kenv = signal.sosfilt(signal.butter(1, 12, "lowpass", fs=SR, output="sos"), kenv); kenv /= kenv.max()
duck = (1 - 0.45 * np.clip(kenv * 3, 0, 1)).astype(np.float32)[:, None]

sub_m = butter(subb, "lowpass", 900) ; sub_m = np.tanh(sub_m * 1.3)
stems = {}
stems["drums"] = pan(kickb, 0) * 1.2 + reverb(pan(snb, 0.04), 0.9, 0.16) * 0.95 + pan(butter(hatb, "highpass", 6000), 0.22) * 0.85 + reverb(pan(percb, -0.4), 0.7, 0.3) * 0.5
stems["808"] = pan(sub_m, 0) * 0.70 * (1 - 0.25 * (1 - duck))
keys = orgb * 0.62 + reverb(pan(rhob, -0.25), 1.6, 0.35) * 0.9
stems["keys"] = reverb(keys, 2.0, 0.18) * duck
gt = delay(pan(leadb, 0.18), 3, 0.36, 0.26) * 0.8 + pan(rgb, -0.45) * 0.7 + pan(lowgb, 0.4) * 0.6
stems["guitars"] = reverb(gt, 1.7, 0.22)
stems["talkbox"] = reverb(delay(pan(talkb, -0.05), 4, 0.3, 0.2), 1.5, 0.2) * 1.8 * (0.6 + 0.4 * duck)

# ---------- screwed outro: slow the last hook phrase down (pitch + time), tape style ----------
body_end = t_bar(NB)
seg0, seg1 = t_bar(NB - 4), body_end
def screw(x):
    seg = x[seg0:seg1]
    rate = np.concatenate([np.full(len(seg) // 8, 0.84), np.linspace(0.84, 0.62, len(seg) - len(seg) // 8)])
    pos = np.cumsum(rate); pos = pos[pos < len(seg) - 2]
    i0 = pos.astype(int); fr = (pos - i0)[:, None]
    y = seg[i0] * (1 - fr) + seg[i0 + 1] * fr
    y *= np.linspace(1, 0, len(y))[:, None] ** 0.7
    full = np.concatenate([x[:body_end], y.astype(np.float32)])
    return full
stems = {k: screw(v) for k, v in stems.items()}
mix = sum(stems.values())

# ---------- master ----------
def master(x, target=-9.0):
    x = signal.sosfilt(signal.butter(2, 28, "highpass", fs=SR, output="sos"), x, axis=0)
    # mono the low end below 120 Hz
    lo = signal.sosfiltfilt(signal.butter(2, 120, "lowpass", fs=SR, output="sos"), x, axis=0); hi = x - lo
    lo[:] = lo.mean(axis=1, keepdims=True); x = lo + hi
    # gentle tilt: +1.5 dB air shelf, -1.5 dB at 300 Hz mud
    air = signal.sosfilt(signal.butter(1, 8000, "highpass", fs=SR, output="sos"), x, axis=0); x = x + 0.3 * air
    mud = signal.sosfilt(signal.butter(1, [220, 420], "bandpass", fs=SR, output="sos"), x, axis=0); x = x - 0.16 * mud
    # glue compressor 2:1, 30 ms attack, 200 ms release
    lvl = np.abs(x).max(axis=1); at, rl = np.exp(-1 / (0.03 * SR)), np.exp(-1 / (0.2 * SR))
    env = signal.lfilter([1 - rl], [1, -rl], lvl); thr = np.percentile(env, 70)
    g = np.where(env > thr, (thr / np.maximum(env, 1e-9)) ** 0.5, 1.0); g = signal.lfilter([1 - at], [1, -at], g)
    x = x * g[:, None]
    x = np.tanh(x / np.abs(x).max() * 1.5) / np.tanh(1.5)        # soft clip / tape
    meter = pyln.Meter(SR)
    for _ in range(4):                                             # loudness to target through a lookahead limiter
        l = meter.integrated_loudness(x.astype(np.float64)); x = x * 10 ** ((target - l) / 20)
        pk = np.abs(x).max(axis=1); win = int(0.004 * SR)
        from scipy.ndimage import maximum_filter1d, uniform_filter1d
        need = np.minimum(1.0, 0.891 / np.maximum(maximum_filter1d(pk, win * 2), 1e-9))
        x = x * uniform_filter1d(need, win)[:, None]
    x = np.clip(x, -0.891, 0.891)
    return x.astype(np.float32), meter.integrated_loudness(x.astype(np.float64))

final, lufs = master(mix)
gain = float(np.abs(final).max() / (np.abs(mix).max() + 1e-9))
sf.write(f"{out}/stay_throwed_master.wav", final, SR, subtype="PCM_24")
scale = 0.891 / max(np.abs(v).max() for v in stems.values())
for k, v in stems.items():
    sf.write(f"{out}/stem_{k}.wav", v * scale, SR, subtype="PCM_16")
import json
side = (final[:, 0] - final[:, 1]) / 2; mid = final.mean(axis=1)
info = {"bpm": BPM, "key": "E minor", "bars": NB, "seconds": round(len(final) / SR, 1), "lufs": round(float(lufs), 1),
        "peak_db": round(float(20 * np.log10(np.abs(final).max())), 2), "crest_db": round(float(20 * np.log10(np.abs(mid).max() / np.sqrt((mid ** 2).mean()))), 1),
        "stereo_width": round(float(np.sqrt((side ** 2).mean()) / np.sqrt((mid ** 2).mean())), 3),
        "sections": [{"name": n, "bars": c} for n, c in SECTIONS] + [{"name": "screwed outro", "bars": 4}]}
json.dump(info, open(f"{out}/track.json", "w"), indent=1); print(info)
