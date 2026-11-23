"""Billo Motion headless renderer: stills (PNG) + motion (MP4) from cards.json.
usage: python3 render.py [card_id ...] [--motion] [--only SIZE]"""
import json, sys, base64, subprocess, pathlib, asyncio
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
SIZES_FLYER = {"letter":(2550,3300)}
SIZES = {"story":(1080,1920),"feed":(1080,1350),"square":(1080,1080),"wide":(1920,1080),"event":(2160,1080),"strip":(1600,500)}
MOTION = {"story":(1080,1920),"wide":(1920,1080)}
FPS, DUR = 30, 7.5
async def main():
    args=[a for a in sys.argv[1:] if not a.startswith('--')]
    motion='--motion' in sys.argv
    cards=json.loads((ROOT/'cards/cards.json').read_text())
    ids=args or list(cards)
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--allow-file-access-from-files'])
        pg=await b.new_page(); await pg.goto((ROOT/'engine/harness.html').as_uri()); await pg.evaluate('ready()')
        for cid in ids:
            card=cards[cid]; out=ROOT/'out'/cid; out.mkdir(parents=True,exist_ok=True)
            for name,(W,H) in (SIZES_FLYER if cid.endswith('-letter') else SIZES).items():
                await pg.evaluate('([c,w,h])=>setup(c,w,h)',[card,W,H])
                d=await pg.evaluate('frame(99)')
                y=await pg.evaluate('window.__lastY')
                (out/f'{cid}_{name}_{W}x{H}.png').write_bytes(base64.b64decode(d.split(',')[1]))
                print(cid,name,'type bottom',round(y),'/',H, 'OVERFLOW' if y>H*0.9 else '')
            if motion:
                for name,(W,H) in MOTION.items():
                    await pg.evaluate('([c,w,h])=>setup(c,w,h)',[card,W,H])
                    tmp=out/f'.{cid}_{name}_motion.tmp.mp4'; final=out/f'{cid}_{name}_motion_{W}x{H}.mp4'
                    ff=subprocess.Popen(['ffmpeg','-v','error','-y','-f','image2pipe','-framerate',str(FPS),'-c:v','mjpeg','-i','-','-f','lavfi','-t',str(DUR),'-i','anullsrc=r=48000:cl=stereo','-shortest','-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-f','mp4',str(tmp)],stdin=subprocess.PIPE)
                    for i in range(int(FPS*DUR)):
                        d=await pg.evaluate(f'frame({i/FPS},"image/jpeg",0.94)')
                        ff.stdin.write(base64.b64decode(d.split(',')[1]))
                    ff.stdin.close(); ff.wait()
                    if ff.returncode==0: tmp.rename(final); print('motion',final.name)
        await b.close()
asyncio.run(main())
