# billo — agent side of Billo Browser (no Chromium)
Billy's law (23 Nov 2026): agents never spin up Chrome/Chromium. On the Mac, use Billo Browser itself
(`~/BillySorrells/tools/billo-browser-rs`, CLI `billo`, bridge 127.0.0.1:7788). In cloud sessions that can't
reach the Mac, use this: same commands, WebKit engine, and every page is journaled so the next session can mine it.

Install once: `pip install playwright && python3 -m playwright install --with-deps webkit`
Use: `BILLO_SESSION="what this run is" python3 billo.py text|dump|links|shot URL`
Data: `~/BillySorrells/billo-agent/journal.jsonl` + `pages/`; pushed to `os.habit_events` (app=billo-agent)
when `BILLO_AGENT_KEY` (an os.agents key) is set; `billo sync` catches up.
