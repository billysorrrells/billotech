#!/usr/bin/env python3
"""
billo — the agent side of Billo Browser. Same commands as Billy's Mac CLI (billo text|dump|shot <url>),
for sessions that can't reach the Mac. Engine: WebKit (Safari's engine, same family as Billo Browser's
WKWebView). NEVER Chromium/Chrome (Billy's law, 23 Nov 2026).

Every page an agent touches is journaled so it can be mined later instead of forgotten:
  - local journal  ~/BillySorrells/billo-agent/journal.jsonl  (always)
  - page text      ~/BillySorrells/billo-agent/pages/<sha>.txt
  - Billo OS       os.habit_events via public.os_habit_ingest when BILLO_AGENT_KEY is set
                   (app='billo-agent', kind='visit', meta: action, session, words, links, status, excerpt)
  `billo sync` pushes anything not yet sent.

  billo text  URL            readable text of the page
  billo dump  URL            text + links + title as JSON
  billo shot  URL out.png    full-page screenshot (--w 1280 --h 800 --mobile)
  billo links URL            every link on the page
  billo sync                 push unsent journal rows to Billo OS
Env: BILLO_SESSION (label for this conversation/run), BILLO_AGENT_KEY, BILLO_PROFILE (persistent sign-in dir)
"""
import argparse, datetime, hashlib, json, os, sys, time, urllib.parse, urllib.request

HOME = os.path.expanduser("~/BillySorrells/billo-agent")
JOURNAL = os.path.join(HOME, "journal.jsonl")
PAGES = os.path.join(HOME, "pages")
SB = "https://hnzekejoaamsnmtqtwie.supabase.co"
PUB = "sb_publishable_51ybFNizblfWMqL_qdekcg_kZT7nXHy"
os.makedirs(PAGES, exist_ok=True)
JS_TEXT = """() => { const kill=['script','style','noscript','svg','iframe']; const c=document.body.cloneNode(true);
  c.querySelectorAll(kill.join(',')).forEach(e=>e.remove()); return c.innerText.replace(/\\n{3,}/g,'\\n\\n').trim(); }"""
JS_LINKS = """() => [...document.querySelectorAll('a[href]')].map(a=>({text:(a.innerText||a.title||'').trim().slice(0,120),href:a.href})).filter(l=>/^https?:/.test(l.href))"""


def journal(row):
    row.setdefault("at", datetime.datetime.now(datetime.timezone.utc).isoformat())
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(row) + "\n")
    push([row])


def push(rows):
    key = os.environ.get("BILLO_AGENT_KEY")
    if not key or not rows:
        return False
    ev = [{"at": r["at"], "url": r["url"], "title": r.get("title"), "app": "billo-agent", "kind": "visit",
           "device": os.environ.get("BILLO_DEVICE", os.uname().nodename)[:80], "dwell_s": r.get("secs"),
           "meta": {**{k: r.get(k) for k in ("session", "words", "links", "status", "excerpt", "page_file", "engine")}, "action": r["action"], "by": "agent"}} for r in rows]
    req = urllib.request.Request(SB + "/rest/v1/rpc/os_habit_ingest", method="POST",
                                 data=json.dumps({"p_key": key, "p_events": ev}).encode(),
                                 headers={"apikey": PUB, "Authorization": "Bearer " + PUB, "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
        with open(os.path.join(HOME, "sent.txt"), "a") as f:
            f.write("".join(r["at"] + "\n" for r in rows))
        return True
    except Exception as e:
        print(f"(journal kept locally; Billo OS push failed: {e})", file=sys.stderr)
        return False


def open_page(url, w=1280, h=800, mobile=False):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    prof = os.environ.get("BILLO_PROFILE")
    opts = dict(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
    if prof:
        ctx = pw.webkit.launch_persistent_context(prof, headless=True, **opts); br = None
    else:
        br = pw.webkit.launch(headless=True); ctx = br.new_context(**opts)
    page = ctx.new_page()
    t = time.time()
    resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    return pw, br, ctx, page, (resp.status if resp else None), t


def close(pw, br, ctx):
    ctx.close()
    if br: br.close()
    pw.stop()


def read(url, action, shot=None, w=1280, h=800, mobile=False):
    pw, br, ctx, page, status, t = open_page(url, w, h, mobile)
    title = page.title()
    text = page.evaluate(JS_TEXT) or ""
    links = page.evaluate(JS_LINKS) or []
    if shot:
        page.screenshot(path=shot, full_page=True)
    close(pw, br, ctx)
    sha = hashlib.sha1(text.encode()).hexdigest()[:16]
    pf = os.path.join(PAGES, sha + ".txt")
    open(pf, "w").write(f"URL: {url}\nTITLE: {title}\n\n{text}")
    journal({"url": url, "title": title, "action": action, "status": status, "secs": round(time.time() - t, 1),
             "words": len(text.split()), "links": len(links), "excerpt": text[:600], "page_file": pf,
             "engine": "webkit", "session": os.environ.get("BILLO_SESSION", "")})
    return title, text, links, status


def main():
    ap = argparse.ArgumentParser(prog="billo")
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("text", "dump", "links"):
        sp.add_parser(c).add_argument("url")
    s = sp.add_parser("shot"); s.add_argument("url"); s.add_argument("out", nargs="?", default="shot.png")
    s.add_argument("--w", type=int, default=1280); s.add_argument("--h", type=int, default=800); s.add_argument("--mobile", action="store_true")
    sp.add_parser("sync")
    a = ap.parse_args()
    if a.cmd == "sync":
        sent = set(open(os.path.join(HOME, "sent.txt")).read().split()) if os.path.exists(os.path.join(HOME, "sent.txt")) else set()
        rows = [json.loads(l) for l in open(JOURNAL)] if os.path.exists(JOURNAL) else []
        todo = [r for r in rows if r["at"] not in sent]
        ok = push(todo) if todo else True
        print(f"{len(todo)} unsent rows · {'pushed' if ok and todo else 'nothing pushed (set BILLO_AGENT_KEY)' if todo else 'up to date'}")
        return
    url = a.url if a.url.startswith("http") else "https://" + a.url
    if a.cmd == "shot":
        title, *_ = read(url, "shot", a.out, a.w, a.h, a.mobile); print(f"{a.out}  ·  {title}")
    else:
        title, text, links, status = read(url, a.cmd)
        if a.cmd == "text": print(f"# {title}\n\n{text}")
        elif a.cmd == "links": print("\n".join(f"{l['text'][:60]:60}  {l['href']}" for l in links))
        else: print(json.dumps({"url": url, "status": status, "title": title, "text": text, "links": links}, indent=1))


if __name__ == "__main__":
    main()
