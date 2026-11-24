#!/usr/bin/env python3
"""
BILLO GRAB · any link -> clean MP4 on your machine. Free, open source, no API keys.
Engines, tried in order (first win is kept):
  1. yt-dlp            (1,800+ sites: YouTube, IG, TikTok, X, FB, Vimeo, Twitch, Reddit…)
                        + curl_cffi browser impersonation, + bgutil PO-token plugin for YouTube bot checks,
                        + your own browser cookies (BILLO_COOKIES=chrome) for logged-in/private posts
  2. cobalt            (self-hosted cobalt API, set COBALT_API=http://127.0.0.1:9000) — optional fallback
  3. gallery-dl        (photo/carousel posts: IG, X, Pinterest, Tumblr…)
  4. direct            (plain .mp4/.mov/.jpg links)
Every video comes out H.264/AAC .mp4 (plays in any browser and NLE), any shape: 16:9, 9:16, 1:1, 4:5…

Run as a service for Billo Style Lab / Billo OS (loopback only):
  python3 billo_grab.py serve            -> http://127.0.0.1:8765  (opens Billo Style Lab at /)
     GET /health                         engines + versions
     GET /info?url=…                     title, size, aspect, duration (no download)
     GET /grab?url=…&max=1080            downloads, normalises, streams the MP4 back
     GET /grab?url=…&clip=12-27          only that section (seconds)
Or as a command:
  python3 billo_grab.py get URL [URL…] --out ~/BillySorrells/grab [--max 1080] [--clip 12-27]
"""
import argparse, hashlib, json, mimetypes, os, re, shutil, subprocess, sys, threading, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~/BillySorrells/grab")
CACHE = os.path.join(HOME, "cache")
LOG = os.path.join(HOME, "grab-log.jsonl")
ALLOWED_ORIGINS = {"https://billo-os.netlify.app", "https://www.billysorrells.com", "https://billysorrells.com",
                   "https://kehlin-billy-workbench.netlify.app", "http://localhost", "http://127.0.0.1", "null"}
os.makedirs(CACHE, exist_ok=True)
LOCK = threading.Lock()
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def have(mod):
    try:
        __import__(mod); return True
    except Exception:
        return False


def ver(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
    except Exception:
        return None


def key(url, mx, clip):
    return hashlib.sha1(f"{url}|{mx}|{clip}".encode()).hexdigest()[:16]


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
    except Exception:
        return {}
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    w, h = v.get("width") or 0, v.get("height") or 0
    return {"vcodec": v.get("codec_name"), "acodec": a.get("codec_name"), "width": w, "height": h,
            "duration": float(j.get("format", {}).get("duration") or 0), "aspect": aspect(w, h)}


def aspect(w, h):
    if not w or not h: return None
    r = w / h
    for name, val in (("9:16", 9 / 16), ("4:5", .8), ("1:1", 1), ("4:3", 4 / 3), ("16:9", 16 / 9), ("2.39:1", 2.39)):
        if abs(r - val) / val < .04: return name
    return f"{w}:{h}"


def normalize(src, dst):
    """Browser/NLE-safe MP4. Copies when already H.264+AAC, else re-encodes (keeps the original shape)."""
    p = probe(src)
    if src.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        shutil.copy(src, dst); return dst
    if p.get("vcodec") == "h264" and p.get("acodec") in ("aac", None):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c", "copy", "-movflags", "+faststart", dst]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)
    return dst


def ytdlp(url, outdir, mx, clip):
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist", "--restrict-filenames",
           "-f", f"bv*[height<={mx}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={mx}]+ba/b[height<={mx}]/b",
           "--merge-output-format", "mp4", "-o", os.path.join(outdir, "%(id)s.%(ext)s"),
           "--write-info-json", "--retries", "5", "--fragment-retries", "5", "--concurrent-fragments", "4"]
    if have("curl_cffi"): cmd += ["--impersonate", "chrome"]
    ck = os.environ.get("BILLO_COOKIES")
    if ck: cmd += ["--cookies-from-browser", ck]
    if clip: cmd += ["--download-sections", f"*{clip}", "--force-keyframes-at-cuts"]
    subprocess.run(cmd + [url], check=True, capture_output=True, text=True, timeout=1800)
    files = [f for f in os.listdir(outdir) if not f.endswith((".json", ".part", ".ytdl"))]
    if not files: raise RuntimeError("yt-dlp produced no file")
    info = {}
    js = [f for f in os.listdir(outdir) if f.endswith(".info.json")]
    if js:
        i = json.load(open(os.path.join(outdir, js[0])))
        info = {k: i.get(k) for k in ("title", "uploader", "webpage_url", "extractor_key", "upload_date")}
    return os.path.join(outdir, sorted(files, key=lambda f: -os.path.getsize(os.path.join(outdir, f)))[0]), info


def cobalt(url, outdir, mx, clip):
    api = os.environ.get("COBALT_API")
    if not api: raise RuntimeError("COBALT_API not set")
    req = urllib.request.Request(api.rstrip("/") + "/", data=json.dumps({"url": url, "videoQuality": str(mx)}).encode(),
                                 headers={"Accept": "application/json", "Content-Type": "application/json"})
    j = json.load(urllib.request.urlopen(req, timeout=60))
    link = j.get("url") or ((j.get("picker") or [{}])[0].get("url"))
    if not link: raise RuntimeError(f"cobalt: {j.get('status')} {j.get('error')}")
    return direct(link, outdir, mx, clip)


def gallerydl(url, outdir, mx, clip):
    subprocess.run([sys.executable, "-m", "gallery_dl", "-D", outdir] +
                   (["--cookies-from-browser", os.environ["BILLO_COOKIES"]] if os.environ.get("BILLO_COOKIES") else []) + [url],
                   check=True, capture_output=True, text=True, timeout=600)
    files = sorted(os.listdir(outdir), key=lambda f: -os.path.getsize(os.path.join(outdir, f)))
    if not files: raise RuntimeError("gallery-dl produced no file")
    return os.path.join(outdir, files[0]), {}


def direct(url, outdir, mx, clip):
    name = os.path.basename(urllib.parse.urlparse(url).path) or "file"
    if "." not in name: name += mimetypes.guess_extension(urllib.request.urlopen(urllib.request.Request(url, method="HEAD")).headers.get_content_type() or "") or ".mp4"
    p = os.path.join(outdir, name)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r, open(p, "wb") as f:
        shutil.copyfileobj(r, f)
    return p, {}


ENGINES = [("yt-dlp", ytdlp), ("cobalt", cobalt), ("gallery-dl", gallerydl), ("direct", direct)]


def grab(url, mx=1080, clip=None):
    if not re.match(r"^https?://", url or ""): raise ValueError("not a link")
    k = key(url, mx, clip)
    final = os.path.join(CACHE, k + ".mp4")
    meta = final + ".json"
    if os.path.exists(final) and os.path.exists(meta):
        return final, json.load(open(meta))
    errors = []
    for name, fn in ENGINES:
        work = os.path.join(CACHE, k + "." + name)
        shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
        try:
            src, info = fn(url, work, mx, clip)
            if name != "yt-dlp" and clip and not src.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                a, b = clip.split("-"); cut = src + ".cut.mp4"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", a, "-to", b, "-i", src, "-c:v", "libx264", "-crf", "18", "-c:a", "aac", cut], check=True)
                src = cut
            ext = ".jpg" if src.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) else ".mp4"
            final = os.path.join(CACHE, k + ext)
            normalize(src, final)
            m = {"url": url, "engine": name, "file": os.path.basename(final), "max": mx, "clip": clip,
                 "grabbed": time.strftime("%Y-%m-%dT%H:%M:%S"), **info, **probe(final)}
            json.dump(m, open(final + ".json", "w"), indent=2)
            with open(LOG, "a") as f: f.write(json.dumps(m) + "\n")
            shutil.rmtree(work, ignore_errors=True)
            return final, m
        except Exception as e:
            errors.append(f"{name}: {getattr(e, 'stderr', '') or e}"[-400:])
            shutil.rmtree(work, ignore_errors=True)
    raise RuntimeError(" | ".join(errors))


def info_only(url):
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-J", "--no-playlist", "--no-warnings", url] +
                       (["--impersonate", "chrome"] if have("curl_cffi") else []) +
                       (["--cookies-from-browser", os.environ["BILLO_COOKIES"]] if os.environ.get("BILLO_COOKIES") else []),
                       capture_output=True, text=True, timeout=120)
    i = json.loads(r.stdout)
    w, h = i.get("width") or 0, i.get("height") or 0
    return {"title": i.get("title"), "uploader": i.get("uploader"), "duration": i.get("duration"), "width": w, "height": h,
            "aspect": aspect(w, h), "site": i.get("extractor_key"), "thumbnail": i.get("thumbnail")}


class H(BaseHTTPRequestHandler):
    def cors(self):
        o = self.headers.get("Origin") or ""
        base = re.sub(r":\d+$", "", o)
        if o in ALLOWED_ORIGINS or base in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Expose-Headers", "X-Billo-Meta")
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204); self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*"); self.end_headers()

    def j(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.cors()
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path == "/health":
                return self.j(200, {"ok": True, "service": "billo-grab", "yt_dlp": ver([sys.executable, "-m", "yt_dlp", "--version"]),
                                    "gallery_dl": ver([sys.executable, "-m", "gallery_dl", "--version"]), "ffmpeg": ver(["ffmpeg", "-version"]),
                                    "impersonate": have("curl_cffi"), "cookies": os.environ.get("BILLO_COOKIES"), "cobalt": os.environ.get("COBALT_API")})
            if u.path == "/info":
                return self.j(200, info_only(q["url"]))
            if u.path == "/grab":
                with LOCK:
                    path, m = grab(q["url"], int(q.get("max", 1080)), q.get("clip"))
                self.send_response(200); self.cors()
                self.send_header("Content-Type", "image/jpeg" if path.endswith(".jpg") else "video/mp4")
                self.send_header("Content-Length", str(os.path.getsize(path)))
                self.send_header("X-Billo-Meta", urllib.parse.quote(json.dumps({k: m.get(k) for k in ("title", "engine", "width", "height", "aspect", "duration", "file")})))
                self.end_headers()
                with open(path, "rb") as f: shutil.copyfileobj(f, self.wfile)
                return
            # Billo Style Lab, served from this machine (same page as billo-os.netlify.app/stylelab.html + link import)
            rel = (u.path.lstrip("/") or "stylelab.html")
            fp = os.path.realpath(os.path.join(WEB, rel))
            if fp.startswith(os.path.realpath(WEB)) and os.path.isfile(fp):
                b = open(fp, "rb").read(); self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(fp)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
            self.j(404, {"error": "unknown path"})
        except Exception as e:
            self.j(502, {"error": str(e)[-1200:]})

    def log_message(self, *a): pass


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("serve"); s.add_argument("--port", type=int, default=8765)
    g = sp.add_parser("get"); g.add_argument("urls", nargs="+"); g.add_argument("--out", default=os.path.join(HOME, "out"))
    g.add_argument("--max", type=int, default=1080); g.add_argument("--clip")
    a = ap.parse_args()
    if a.cmd == "serve":
        print(f"billo-grab on http://127.0.0.1:{a.port}"); ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
    else:
        os.makedirs(a.out, exist_ok=True)
        for url in a.urls:
            try:
                p, m = grab(url, a.max, a.clip)
                name = re.sub(r"[^\w.-]+", "_", (m.get("title") or m["file"]))[:80] + os.path.splitext(p)[1]
                shutil.copy(p, os.path.join(a.out, name))
                print(f"OK  {m['engine']:10} {m.get('aspect')}  {name}")
            except Exception as e:
                print(f"ERR {url}: {e}")


if __name__ == "__main__":
    main()
