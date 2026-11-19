#!/usr/bin/env python3
"""
BILLO VOICE · natural narration fixer · BilloTech (free, local, no API)

Fixes the "tingy / hingy" sound of AI voices and phone reads by matching them
to a reference recording of the real speaker (Billy's own voice).

What it does, in order:
  1. Clean      high-pass rumble, optional gentle denoise (ffmpeg afftdn)
  2. Body       spectral match: measures the reference's long-term tone curve and
                EQs the narration to it (puts the chest 150-500 Hz back in)
  3. Tame       dynamic de-esser on 4.5-9 kHz, softens the metallic vocoder fizz
  4. Warmth     light tube-style saturation (adds harmonics real mics have)
  5. Air        fills dead digital silence with the reference's own room tone
                and adds a short early-reflection room so it isn't "in your skull"
  6. Level      gentle compression, loudness to target LUFS, -1 dBTP ceiling

Usage:
  python3 billo_voice.py narration.wav --ref billy_real.wav -o narration_billo.wav
  python3 billo_voice.py vo.m4a --ref ref.wav --lufs -14 --room 0.10 --report report.json

Any format ffmpeg reads works (wav, mp3, m4a, mov, mp4). Output is 48 kHz 24-bit WAV.
Best results: --ref = 30-120 s of Billy talking on a good mic (podcast, special),
no music under it.
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
import soundfile as sf
from scipy import signal

SR = 48000


def load(path, denoise=False):
    """Decode anything with ffmpeg to 48 kHz mono float32."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "x.wav")
        af = "highpass=f=70"
        if denoise:
            af += ",afftdn=nr=10:nf=-45"
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", path,
               "-vn", "-ac", "1", "-ar", str(SR), "-af", af, "-c:a", "pcm_f32le", out]
        subprocess.run(cmd, check=True)
        x, _ = sf.read(out, dtype="float32")
    return x.astype(np.float64)


def frames_db(x, win=2048, hop=1024):
    n = max(1, 1 + (len(x) - win) // hop)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    idx = np.clip(idx, 0, len(x) - 1)
    rms = np.sqrt(np.mean(x[idx] ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms), hop


def voiced_mask(x):
    db, hop = frames_db(x)
    thr = np.percentile(db, 90) - 25
    m = np.repeat(db > thr, hop)
    return np.pad(m, (0, max(0, len(x) - len(m))))[: len(x)].astype(bool)


def ltas(x, nper=4096):
    """Long-term average spectrum of voiced audio, 1/3-octave smoothed (dB)."""
    v = x[voiced_mask(x)]
    if len(v) < nper:
        v = x
    f, p = signal.welch(v, SR, nperseg=nper)
    db = 10 * np.log10(p + 1e-20)
    sm = np.empty_like(db)
    for i, fc in enumerate(f):
        lo, hi = fc / 2 ** (1 / 6), fc * 2 ** (1 / 6)
        sel = (f >= lo) & (f <= hi) if fc > 0 else (f <= 20)
        sm[i] = db[sel].mean() if sel.any() else db[i]
    return f, sm


def band_db(f, db, lo, hi):
    s = (f >= lo) & (f < hi)
    return float(10 * np.log10(np.mean(10 ** (db[s] / 10)) + 1e-20))


def tone_profile(f, db):
    """Numbers that describe 'tinny' vs 'full'. Higher body_minus_bite = fuller."""
    body = band_db(f, db, 150, 500)
    bite = band_db(f, db, 2000, 5000)
    fizz = band_db(f, db, 6000, 12000)
    return {"body_150_500_db": round(body, 1), "bite_2k_5k_db": round(bite, 1),
            "fizz_6k_12k_db": round(fizz, 1), "body_minus_bite_db": round(body - bite, 1)}


def match_eq(x, ref, max_db=12.0, ntaps=4097):
    f, d_in = ltas(x)
    _, d_ref = ltas(ref)
    # align overall level in the speech band before taking the difference
    sb = (f > 200) & (f < 4000)
    diff = (d_ref - d_ref[sb].mean()) - (d_in - d_in[sb].mean())
    diff[f < 60] = min(diff[(f >= 60) & (f < 90)].mean(), 0)  # never boost rumble
    diff = np.clip(diff, -max_db, max_db)
    gain = 10 ** (diff / 20)
    fir = signal.firwin2(ntaps, f / (SR / 2), gain)
    y = signal.fftconvolve(x, fir, mode="same")
    return y, f, diff


def deess(x, lo=4500, hi=9000, thresh_db=-6.0, ratio=4.0):
    sos = signal.butter(4, [lo, hi], btype="band", fs=SR, output="sos")
    s = signal.sosfiltfilt(sos, x)
    env_s = np.abs(signal.hilbert(s))
    env_x = np.abs(signal.hilbert(x)) + 1e-9
    k = int(0.005 * SR)
    win = np.ones(k) / k
    env_s = np.convolve(env_s, win, "same")
    env_x = np.convolve(env_x, win, "same")
    rel = 20 * np.log10(env_s / env_x + 1e-9)
    over = np.maximum(rel - thresh_db, 0)
    red_db = over * (1 - 1 / ratio)
    g = 10 ** (-red_db / 20)
    return x - s + s * g


def warmth(x, drive=1.6, mix=0.18):
    sat = np.tanh(drive * x) / np.tanh(drive)
    return (1 - mix) * x + mix * sat


def room_ir(rt=0.28, pre=0.012):
    """Short, small-room early reflections + quick tail. Synthetic, deterministic."""
    rng = np.random.default_rng(713)
    n = int(rt * SR)
    t = np.arange(n) / SR
    tail = rng.standard_normal(n) * np.exp(-6.9 * t / rt)
    tail = signal.sosfilt(signal.butter(2, 6000, fs=SR, output="sos"), tail)
    ir = np.zeros(n + int(pre * SR))
    for d, a in [(0.0, 1.0)] + [(pre + rng.uniform(0, 0.03), rng.uniform(.2, .45)) for _ in range(6)]:
        ir[int(d * SR)] += a
    ir[int(pre * SR):] += 0.12 * tail
    return ir / np.max(np.abs(ir))


def add_room(x, amount):
    if amount <= 0:
        return x
    wet = signal.fftconvolve(x, room_ir(), mode="full")[: len(x)]
    wet *= np.sqrt(np.mean(x ** 2) / (np.mean(wet ** 2) + 1e-12))
    return (1 - amount) * x + amount * wet


def room_tone(ref, x, level_db=-58.0):
    """Lay the reference's own background under the narration so silences breathe."""
    m = voiced_mask(ref)
    quiet = ref[~m]
    if len(quiet) < SR // 2:
        rng = np.random.default_rng(1)
        quiet = signal.sosfilt(signal.butter(2, [100, 3000], "band", fs=SR, output="sos"),
                               rng.standard_normal(SR * 2))
    reps = int(np.ceil(len(x) / len(quiet)))
    bed = np.tile(quiet, reps)[: len(x)]
    bed *= 10 ** (level_db / 20) / (np.sqrt(np.mean(bed ** 2)) + 1e-12)
    return x + bed


def compress(x, thresh_db=-20.0, ratio=2.5, att=0.008, rel=0.12):
    env = np.abs(x)
    a_a, a_r = np.exp(-1 / (att * SR)), np.exp(-1 / (rel * SR))
    # vectorised-ish one-pole follower in blocks for speed
    out = np.empty_like(env)
    e = 0.0
    for i, v in enumerate(env):
        e = a_a * e + (1 - a_a) * v if v > e else a_r * e + (1 - a_r) * v
        out[i] = e
    db = 20 * np.log10(out + 1e-9)
    red = np.maximum(db - thresh_db, 0) * (1 - 1 / ratio)
    return x * 10 ** (-red / 20)


def loudness(x, lufs):
    import pyloudnorm as pyln
    meter = pyln.Meter(SR)
    cur = meter.integrated_loudness(x)
    y = pyln.normalize.loudness(x, cur, lufs)
    peak = np.max(np.abs(y))
    ceiling = 10 ** (-1.0 / 20)
    if peak > ceiling:  # simple soft limiter to -1 dBFS
        y = np.tanh(y / ceiling) * ceiling
    return y, cur, meter.integrated_loudness(y)


def run(inp, ref_path, out, lufs=-16.0, room=0.08, denoise=False, report=None):
    x = load(inp, denoise)
    ref = load(ref_path, denoise=False)
    f0, d0 = ltas(x)
    _, dref = ltas(ref)
    before, target = tone_profile(f0, d0), tone_profile(f0, dref)

    y, f, curve = match_eq(x, ref)
    y = deess(y)
    y = warmth(y)
    y = add_room(y, room)
    y = compress(y)
    y = room_tone(ref, y)
    y, l_in, l_out = loudness(y, lufs)

    sf.write(out, y.astype(np.float32), SR, subtype="PCM_24")
    f1, d1 = ltas(y)
    after = tone_profile(f1, d1)
    rep = {
        "input": inp, "reference": ref_path, "output": out,
        "lufs_in": round(l_in, 1), "lufs_out": round(l_out, 1),
        "tone_before": before, "tone_after": after, "tone_reference": target,
        "gap_closed_db": round(abs(target["body_minus_bite_db"] - before["body_minus_bite_db"])
                               - abs(target["body_minus_bite_db"] - after["body_minus_bite_db"]), 1),
        "eq_curve_db": {str(int(fc)): round(float(v), 1)
                        for fc, v in zip(f, curve) if fc in (0,) or any(abs(fc - c) < 6 for c in
                        (100, 200, 300, 500, 1000, 2000, 3000, 5000, 8000, 12000))},
    }
    if report:
        with open(report, "w") as fh:
            json.dump(rep, fh, indent=2)
    return rep


def main():
    ap = argparse.ArgumentParser(description="Billo Voice: make narration sound like the real room")
    ap.add_argument("input")
    ap.add_argument("--ref", required=True, help="clean recording of the real speaker")
    ap.add_argument("-o", "--out", help="output .wav (default: <input>_billo.wav)")
    ap.add_argument("--lufs", type=float, default=-16.0, help="-16 narration/podcast, -14 social")
    ap.add_argument("--room", type=float, default=0.08, help="0 = bone dry, 0.15 = roomy")
    ap.add_argument("--denoise", action="store_true", help="for phone reads with hiss")
    ap.add_argument("--report", help="write a JSON report")
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.input)[0] + "_billo.wav"
    rep = run(a.input, a.ref, out, a.lufs, a.room, a.denoise, a.report)
    print(json.dumps({k: rep[k] for k in ("output", "lufs_out", "tone_before", "tone_after",
                                          "tone_reference", "gap_closed_db")}, indent=2))


if __name__ == "__main__":
    sys.exit(main())
