#!/usr/bin/env python3
"""
BILLO TRAILER DNA · measure how a trailer is cut · BilloTech (free: yt-dlp + ffmpeg + numpy)

Input: a JSON like {"trailers": {"bad_boys": [{"title":..,"youtube_url":..}, ...], ...}}
       (YouTube search URLs are fine: the first result is used.)
Output per trailer, and per franchise:
  - every cut (timestamp) and shot length; cuts per 5 s across the runtime (the acceleration curve)
  - average / median shot, fastest run, longest held shot
  - loudness envelope, music drops (silence gaps), the hardest hits
  - color: warm/cool split per shot, an orange-teal score, brightness
  - title-card guesses (dark frames with text-like edges)
  -> dna.json + dna.html in --out, ready to load into the binder.

YouTube blocks cloud servers, so run it on Billy's Mac:
  python3 billo_trailer_dna.py trailers.json --out ~/BillySorrells/trailer-dna --cookies-from-browser chrome
"""
import argparse, json, os, re, subprocess, sys
import numpy as np

FF = os.environ.get("FFMPEG", "ffmpeg")


def fetch(entry, outdir, cookies):
    url = entry["youtube_url"]
    if "results?search_query=" in url:
        q = re.sub(r".*search_query=", "", url).replace("+", " ")
        url = f"ytsearch1:{q}"
    slug = re.sub(r"[^a-z0-9]+", "-", f"{entry['title']}-{entry.get('year','')}".lower()).strip("-")
    dst = os.path.join(outdir, slug + ".mp4")
    if not os.path.exists(dst):
        cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "-f", "b[height<=480]/bv*[height<=480]+ba",
               "--merge-output-format", "mp4", "-o", dst, url]
        if cookies:
            cmd[3:3] = ["--cookies-from-browser", cookies]
        subprocess.run(cmd, check=True)
    return slug, dst


def cuts(path, thresh=0.32):
    r = subprocess.run([FF, "-nostdin", "-i", path, "-vf", f"scale=320:-2,select='gt(scene,{thresh})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r)]


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def loudness(path):
    r = subprocess.run([FF, "-nostdin", "-i", path, "-af", "ebur128=metadata=1,ametadata=print:key=lavfi.r128.M",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    t = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r)]
    m = [float(x) for x in re.findall(r"lavfi\.r128\.M=(-?[\d.]+|-inf)", r.replace("-inf", "-120"))]
    n = min(len(t), len(m))
    return np.array(t[:n]), np.array(m[:n])


def color_per_shot(path, bounds):
    out = []
    for a, b in bounds:
        mid = (a + b) / 2
        r = subprocess.run([FF, "-nostdin", "-loglevel", "error", "-ss", f"{mid:.2f}", "-i", path, "-frames:v", "1",
                            "-vf", "scale=96:54", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        px = np.frombuffer(r.stdout, np.uint8).reshape(-1, 3).astype(float) / 255 if r.stdout else np.zeros((1, 3))
        R, G, B = px[:, 0], px[:, 1], px[:, 2]
        luma = 0.2126 * R + 0.7152 * G + 0.0722 * B
        warm = float(np.mean(R - B))
        hi, lo = luma > np.percentile(luma, 70), luma < np.percentile(luma, 30)
        ot = float(np.mean((R - B)[hi]) - np.mean((R - B)[lo])) if hi.any() and lo.any() else 0.0  # orange highs, teal lows
        edges = float(np.mean(np.abs(np.diff(luma.reshape(54, 96), axis=1))))
        out.append({"t": round(a, 2), "warm": round(warm, 3), "orange_teal": round(ot, 3),
                    "bright": round(float(luma.mean()), 3), "title_card": bool(luma.mean() < 0.12 and edges > 0.03)})
    return out


def analyze(path):
    D = duration(path)
    c = [x for x in cuts(path) if 0.2 < x < D - 0.2]
    edges = [0.0] + c + [D]
    shots = np.diff(edges)
    bounds = list(zip(edges[:-1], edges[1:]))
    rate = [sum(1 for x in c if w <= x < w + 5) for w in range(0, int(D), 5)]
    t, m = loudness(path)
    quiet = []
    if len(m):
        q = m < (np.median(m) - 15)
        start = None
        for ti, qi in zip(t, q):
            if qi and start is None: start = ti
            if not qi and start is not None:
                if ti - start >= 0.4: quiet.append([round(start, 2), round(ti - start, 2)])
                start = None
    hits = []
    if len(m) > 4:
        d = np.diff(m)
        for i in np.argsort(d)[-8:][::-1]:
            hits.append([round(float(t[i + 1]), 2), round(float(d[i]), 1)])
    col = color_per_shot(path, bounds)
    # fastest 5-second run and longest held shot
    fast = max(range(len(rate)), key=lambda i: rate[i]) * 5 if rate else 0
    return {"duration": round(D, 2), "shots": len(shots), "cuts": [round(x, 2) for x in c],
            "avg_shot": round(float(shots.mean()), 2), "median_shot": round(float(np.median(shots)), 2),
            "longest_shot": [round(float(edges[int(np.argmax(shots))]), 2), round(float(shots.max()), 2)],
            "cuts_per_5s": rate, "fastest_window_s": fast,
            "first_half_avg": round(float(np.mean(shots[: len(shots) // 2])), 2),
            "second_half_avg": round(float(np.mean(shots[len(shots) // 2:])), 2),
            "silences": quiet, "hardest_hits": sorted(hits),
            "orange_teal_avg": round(float(np.mean([x["orange_teal"] for x in col])), 3),
            "title_cards": [x["t"] for x in col if x["title_card"]], "color_by_shot": col}


def html(dna):
    rows = []
    for fr, items in dna.items():
        for it in items:
            a = it["dna"]
            bars = "".join(f'<i style="height:{min(100, v * 12)}%"></i>' for v in a["cuts_per_5s"])
            rows.append(f"<tr><td>{fr}</td><td>{it['title']} ({it.get('year','')})</td><td>{a['duration']}s</td><td>{a['shots']}</td>"
                        f"<td>{a['avg_shot']}s</td><td>{a['first_half_avg']} → {a['second_half_avg']}s</td><td>{len(a['silences'])}</td>"
                        f"<td>{a['orange_teal_avg']}</td><td><div class=b>{bars}</div></td></tr>")
    return ("<!doctype html><meta charset=utf-8><title>Trailer DNA</title><style>body{background:#07080B;color:#E9E7DF;font:14px system-ui;padding:20px}"
            "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #24242C;padding:6px;text-align:left}"
            ".b{display:flex;align-items:flex-end;gap:1px;height:40px;width:260px}.b i{flex:1;background:linear-gradient(#22D3EE,#A855F7)}</style>"
            "<h1>Trailer DNA</h1><table><tr><th>Franchise</th><th>Trailer</th><th>Length</th><th>Shots</th><th>Avg shot</th>"
            "<th>Avg shot 1st→2nd half</th><th>Music drops</th><th>Orange-teal</th><th>Cuts per 5 s</th></tr>" + "".join(rows) + "</table>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--out", required=True); ap.add_argument("--cookies-from-browser")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    spec = json.load(open(a.spec))["trailers"]
    dna = {}
    for fr, items in spec.items():
        dna[fr] = []
        for e in items:
            slug, path = fetch(e, a.out, a.cookies_from_browser)
            print("measuring", slug)
            dna[fr].append({**e, "file": os.path.basename(path), "dna": analyze(path)})
    json.dump(dna, open(os.path.join(a.out, "dna.json"), "w"), indent=2)
    open(os.path.join(a.out, "dna.html"), "w").write(html(dna))
    print("wrote", os.path.join(a.out, "dna.json"))


if __name__ == "__main__":
    main()
