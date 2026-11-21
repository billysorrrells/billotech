# Billo Grab — any link → MP4, wired into Billo Style Lab
Free, no API keys. Engines tried in order: **yt-dlp** (1,800+ sites, with browser impersonation, YouTube PO-token plugin and your Chrome login) → **cobalt** (optional self-hosted, `COBALT_API`) → **gallery-dl** (photo posts) → direct file links. Output is always H.264/AAC MP4 in the clip's own shape (16:9, 9:16, 1:1, 4:5…). Cache + log in `~/BillySorrells/grab`.

**Install (Mac / EMF hub, once):** `bash forge/billo_grab/install.sh` → always-on at http://127.0.0.1:8765, updates the downloaders daily at 4:10am.

**Style Lab:** open http://127.0.0.1:8765 (or billo-os.netlify.app/stylelab.html once this page is deployed there).
- Step 2: paste one or many links → **Add from link**. Optional "only this part" (e.g. `1:05-1:22`) pulls just that section.
- Step 3: pick the output — 9:16, 16:9, 1:1, 4:5, 2.39:1 or Match first clip — and Fill (crop) or Fit (blurred edges).
- "Turn any reel into a style" takes a link too.

**Command line / Grok bot:** `python3 billo_grab.py get URL [URL…] --out ~/BillySorrells/grab/out --clip 65-82`
**API:** `/health` · `/info?url=` · `/grab?url=&max=1080&clip=a-b` (loopback only; CORS for billo-os / billysorrells.com).

Why local: YouTube blocks downloads from cloud servers; your own machine and login get through.
