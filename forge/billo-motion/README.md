# Billo Motion v1 — code-built motion graphics (our own Claude Motion)

One deterministic canvas engine (`engine/billo-motion.js`) draws show banners and motion cards.
The same file runs in the browser (billysorrells.com/billotech/apps/showdesk/) and headless here.

    pip install playwright   # uses system Chrome
    python3 engine/render.py                  # every card in cards/cards.json, 6 still sizes
    python3 engine/render.py beast-after-the-feast-2026 --motion   # + 7.5 s MP4 (story + 16:9)

Sizes: story 1080x1920 · feed 1080x1350 · square 1080x1080 · wide 1920x1080 · event 2160x1080 · site strip 1600x500.
Brand: ink/bone/gold, Anton + Outfit + JetBrains Mono (fonts/). Real photos of Billy only; Bad Turkeys plates for backgrounds.
Cards mirror Billo OS `os.shows`. Edit a card, re-render, the Show Desk pack updates.
Put `assets/` (photos) next to `engine/` before rendering (kept out of git: see showdesk/img for the same files).
