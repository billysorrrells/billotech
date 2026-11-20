# IG reel · @nateherkai · Obscura (2026-11-18)
Source: https://www.instagram.com/reel/Df4rvtlCeZV/
Pulled 2026-11-20 (video 10.5 MB kept off-repo; transcript, contact sheet, metadata here).

What it pitches: Obscura (github.com/h4ckf0r0day/obscura), a free headless browser built for AI agents.
Rust + embedded V8, no Chromium. Apache-2.0. CDP on :9222 (Puppeteer/Playwright connect as if it were Chrome), MCP via `obscura mcp`.
Self-reported: ~51 ms vs ~500 ms Chrome page load, ~30 MB RAM vs 200+ MB; reel claims 40 pages vs Chrome's 3 in one benchmark (not verified).
Stealth build: randomized fingerprints, navigator.webdriver=false, tracker blocking.
Limits: rendering can differ from Chrome on edge CSS/media; private IPs blocked unless --allow-private-network.

Billo fit: swap-in browser for the headless jobs (CDP test harness, Fan Finder / creator-intel scrapes, overnight agent runs). Run skillspector-gate on it before install.
