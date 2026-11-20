#!/usr/bin/env python3
"""Race Obscura vs Chrome on Billy's real URLs. pip install playwright && playwright install chromium
python3 race.py urls.txt   -> race.json + a printed scoreboard (pages done, avg ms, blocked)."""
import asyncio, json, sys, time
from playwright.async_api import async_playwright
URLS = [u.strip() for u in open(sys.argv[1]) if u.strip() and not u.startswith('#')]
BLOCK = ('access denied', 'verify you are human', 'captcha', 'unusual traffic', 'are you a robot')

async def run(browser, name):
    out = []
    for u in URLS:
        page = await browser.new_page(); t = time.time(); ok = blocked = False
        try:
            await page.goto(u, timeout=30000, wait_until='domcontentloaded')
            txt = (await page.inner_text('body'))[:4000].lower()
            blocked = any(b in txt for b in BLOCK); ok = not blocked
        except Exception as e:
            txt = str(e)
        out.append({'url': u, 'ms': int((time.time() - t) * 1000), 'ok': ok, 'blocked': blocked})
        await page.close()
    return out

async def main():
    async with async_playwright() as p:
        res = {}
        ob = await p.chromium.connect_over_cdp('ws://127.0.0.1:9222'); res['obscura'] = await run(ob, 'obscura'); await ob.close()
        ch = await p.chromium.launch(headless=True); res['chrome'] = await run(ch, 'chrome'); await ch.close()
    for k, v in res.items():
        good = [r for r in v if r['ok']]
        print(f"{k:8} ok {len(good)}/{len(v)}  blocked {sum(r['blocked'] for r in v)}  avg {sum(r['ms'] for r in good)//max(1,len(good))} ms")
    json.dump(res, open('race.json', 'w'), indent=2)
asyncio.run(main())
