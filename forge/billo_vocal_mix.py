#!/usr/bin/env python3
"""
BILLO VOCAL MIX · stems in, finished vocal bus out · BilloTech (free, ffmpeg + numpy)

Role-based vocal chains the way a rap/R&B mixer sets up a session:
  lead   : HPF 80, cut mud 250/520, de-ess, fast comp -> slow comp, presence 3.5k,
           air 12k, harmonic exciter, parallel crush underneath
  dbl    : doubles/stacks tighter and darker, HPF 180, LPF 12.5k, heavier de-ess, Haas widen
  ad     : ad-libs band-limited, forward mids, more delay and room
Bus     : plate send, tempo-locked delay throws (1/4, 1/2, 3/4), glue comp, -1 dB ceiling.
QC      : tone bands, sibilance, mono fold-down, L/R correlation, loudness, peak.

Usage:
  python3 billo_vocal_mix.py stage --stems DIR --plan plan.json --out OUT
  python3 billo_vocal_mix.py bus   --plan plan.json --out OUT [--bpm 148.5]
  python3 billo_vocal_mix.py qc    --out OUT
Stages write to disk, so each one can run on its own (short sandboxes, Grok runner).
"""
import argparse, json, os, re, subprocess, sys
import numpy as np

FF = os.environ.get("FFMPEG", "ffmpeg")
SR = 48000
CHAINS = {
 "lead": ("highpass=f=80:poles=2,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=520:t=q:w=1.4:g=-1.5,"
          "deesser=i=0.5:m=0.5:f=0.55,acompressor=threshold=-26dB:ratio=4:attack=2:release=60:makeup=2,"
          "acompressor=threshold=-20dB:ratio=2.5:attack=15:release=250,equalizer=f=3500:t=q:w=1:g=2.5,"
          "highshelf=f=12000:g=3,aexciter=amount=1:drive=5:freq=7500:blend=0,"
          "asplit[d][p];[p]acompressor=threshold=-36dB:ratio=10:attack=1:release=80:makeup=6,volume=-7dB[pc];"
          "[d][pc]amix=inputs=2:normalize=0"),
 "dbl":  ("highpass=f=180:poles=2,lowpass=f=12500,equalizer=f=300:t=q:w=1:g=-3,deesser=i=0.65:m=0.6:f=0.5,"
          "acompressor=threshold=-24dB:ratio=4:attack=5:release=80:makeup=2,equalizer=f=4000:t=q:w=1:g=1"),
 "ad":   ("highpass=f=250:poles=2,lowpass=f=9500,deesser=i=0.5:m=0.5:f=0.5,"
          "acompressor=threshold=-24dB:ratio=3:attack=4:release=90:makeup=2,equalizer=f=2000:t=q:w=1:g=2"),
}


def sh(*a, **k):
    return subprocess.run([FF, "-nostdin", "-loglevel", "error", "-y", *a], check=True, **k)


def lufs(p):
    e = subprocess.run([FF, "-nostdin", "-i", p, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return (float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]),
            float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1]),
            float(re.findall(r"LRA:\s+([\d.]+) LU", e)[-1]))


def mono(p, sr=22050):
    r = subprocess.run([FF, "-nostdin", "-loglevel", "error", "-i", p, "-ac", "1", "-ar", str(sr),
                        "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32)


def tempo(paths):
    arrs = [mono(p) for p in paths]
    n = min(len(a) for a in arrs)
    x = sum(a[:n] for a in arrs)
    hop = 256
    fr = len(x) // hop - 2
    e = np.add.reduceat(x[: fr * hop] ** 2, np.arange(0, fr * hop, hop))
    on = np.maximum(np.diff(np.log(e + 1e-9)), 0)
    on -= on.mean()
    ac = np.fft.irfft(np.abs(np.fft.rfft(on, 2 * len(on))) ** 2)[: len(on)]
    fps = 22050 / hop
    best = max(np.arange(70, 165, 0.5),
               key=lambda b: sum(np.interp(fps * 60 / b * k, np.arange(len(ac)), ac) for k in (1, 2, 4)))
    return float(best * 2 if best < 85 else best)


def plate(path, secs=1.6):
    from scipy.signal import butter, sosfilt
    import soundfile as sf
    n = int(secs * SR)
    t = np.arange(n) / SR
    ir = np.random.default_rng(713).standard_normal((n, 2)) * np.exp(-6.9 * t / secs)[:, None]
    ir = sosfilt(butter(2, [250, 7000], "band", fs=SR, output="sos"), ir, axis=0)
    k = int(0.02 * SR)
    ir[:k] *= np.linspace(0, 1, k)[:, None]
    sf.write(path, (ir / np.abs(ir).max()).astype(np.float32), SR)


def stage(stems, plan, out):
    os.makedirs(f"{out}/stems", exist_ok=True)
    res = []
    for i, s in enumerate(plan["stems"]):
        src = os.path.join(stems, s["file"])
        tmp = f"{out}/stems/_tmp.wav"
        dst = f"{out}/stems/{i + 1:02d}_{os.path.splitext(s['file'])[0].replace(' ', '_')}.wav"
        sh("-i", src, "-filter_complex", f"[0:a]aformat=channel_layouts=mono,{CHAINS[s['role']]}[o]",
           "-map", "[o]", "-ar", str(SR), "-c:a", "pcm_f32le", tmp)
        g = s["target_lufs"] - lufs(tmp)[0]
        pan = s.get("pan", 0.0)
        a = round((1 - max(0, pan)) ** 0.5, 4)
        b = round((1 - max(0, -pan)) ** 0.5, 4)
        haas = f",adelay=0|{s['haas_ms']}" if s.get("haas_ms") else ""
        sh("-i", tmp, "-af", f"volume={g:.1f}dB,pan=stereo|c0={a}*c0|c1={b}*c0{haas}",
           "-ar", str(SR), "-c:a", "pcm_s24le", dst)
        os.remove(tmp)
        res.append({**s, "gain_db": round(g, 1), "processed": os.path.basename(dst)})
        print(f"  {s['file']:<22} {s['role']:<5} {g:+.1f} dB")
    json.dump(res, open(f"{out}/stems.json", "w"), indent=2)


def bus(plan, out, bpm=None):
    st = json.load(open(f"{out}/stems.json"))
    if not bpm:
        bpm = plan.get("bpm") or tempo([f"{out}/stems/{s['processed']}" for s in st if s["role"] != "dbl"])
    q = round(60000 / bpm)
    plate(f"{out}/plate.wav")
    ins, parts, n = [], [], len(st)
    for i, s in enumerate(st):
        ins += ["-i", f"{out}/stems/{s['processed']}"]
        parts.append(f"[{i}:a]asplit=3[d{i}][r{i}][e{i}];[r{i}]volume={s.get('verb', 0.12)}[rs{i}];"
                     f"[e{i}]volume={s.get('delay', 0)}[es{i}]")
    g = ";".join(parts)
    g += ";" + "".join(f"[rs{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,highpass=f=300[rsum]"
    g += f";[rsum][{n}:a]afir=dry=0:wet=1:gtype=none,lowpass=f=8000,volume=0.5[rret]"
    g += (";" + "".join(f"[es{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,highpass=f=350,"
          f"lowpass=f=4500,aecho=0.001:1:{q}|{2 * q}|{3 * q}:0.45|0.22|0.1,volume=0.8[eret]")
    g += (";" + "".join(f"[d{i}]" for i in range(n)) + f"[rret][eret]amix=inputs={n + 2}:normalize=0,"
          "acompressor=threshold=-20dB:ratio=2:attack=30:release=200:knee=4,alimiter=limit=0.84:level=false[m]")
    name = plan.get("name", "VOCAL")
    mix = f"{out}/{name}_vocal_bus.wav"
    sh(*ins, "-i", f"{out}/plate.wav", "-filter_complex", g, "-map", "[m]", "-ar", str(SR), "-c:a", "pcm_s24le", mix)
    sh("-i", mix, "-af", "loudnorm=I=-14:TP=-1:LRA=9", "-ar", "44100", "-b:a", "320k", f"{out}/{name}_PREVIEW.mp3")
    json.dump({"bpm": bpm, "delay_ms": q}, open(f"{out}/bus.json", "w"))
    print(f"  bus done · {bpm} BPM · delay {q} ms")


def qc(out, files=None):
    import soundfile as sf
    from scipy.signal import welch
    rep = {}
    for p in files or [f for f in os.listdir(out) if f.endswith("_vocal_bus.wav")]:
        path = p if os.path.isabs(p) else f"{out}/{p}"
        y, sr = sf.read(path, frames=SR * 200)
        m, s = y.mean(1), (y[:, 0] - y[:, 1]) / 2
        f, P = welch(m[::2], sr / 2, nperseg=4096)
        band = lambda a, b: round(float(10 * np.log10(P[(f >= a) & (f < b)].mean())), 1)
        i, pk, lra = lufs(path)
        rep[os.path.basename(path)] = {
            "lufs": i, "peak_dbfs": pk, "lra": lra,
            "body_150_500": band(150, 500), "bite_2k_5k": band(2000, 5000),
            "sss_5k_9k": band(5000, 9000), "air_10k_11k": band(10000, 11000),
            "side_minus_mid_db": round(float(10 * np.log10((s ** 2).mean() / ((m ** 2).mean() + 1e-12))), 1),
            "mono_fold_db": round(float(10 * np.log10((m ** 2).mean() / (y ** 2).mean(1).mean())), 2),
            "lr_corr": round(float(np.corrcoef(y[:, 0], y[:, 1])[0, 1]), 2)}
    json.dump(rep, open(f"{out}/qc.json", "w"), indent=2)
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["stage", "bus", "qc", "all"])
    ap.add_argument("--stems"); ap.add_argument("--plan"); ap.add_argument("--out", required=True)
    ap.add_argument("--bpm", type=float); ap.add_argument("--files", nargs="*")
    a = ap.parse_args()
    plan = json.load(open(a.plan)) if a.plan else {}
    if a.cmd in ("stage", "all"): stage(a.stems, plan, a.out)
    if a.cmd in ("bus", "all"): bus(plan, a.out, a.bpm)
    if a.cmd in ("qc", "all"): qc(a.out, a.files)
