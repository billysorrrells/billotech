# Obscura in Billo OS
Agent browser (Rust + V8, no Chromium, Apache-2.0) from github.com/h4ckf0r0day/obscura, v0.2.4.
1. `bash install_obscura.sh` on the Mac and the EMF hub — checksum-checked, runs always-on at ws://127.0.0.1:9222, adds it to Claude Code as `obscura`.
2. `python3 race.py urls.txt` — Obscura vs Chrome on real pages. Keep it only where it wins.
3. Swap-in for any Billo scraper: replace `chromium.launch()` with `chromium.connect_over_cdp('ws://127.0.0.1:9222')`.
Use for: Fan Finder, creator intel, directories/leads, overnight agent runs. Not for: visual QA (rendering differs from Chrome), anything needing real logins (it doesn't carry your Chrome sessions).
Loopback only. Don't expose 9222 on the network.
