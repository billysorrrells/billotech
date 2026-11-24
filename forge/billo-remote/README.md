# Billo Remote (Rust)

Drive the Billo Browser on Billy's Mac from any phone. Streams the main display as JPEG frames
(~1.4 fps) and sends taps, typing, Enter/Tab/⌫/Esc, scroll and "Billo Browser to front" back.

- Binds 127.0.0.1 only. Every route needs `?k=<token>` (403 without it).
- Exposed to the phone with Tailscale Funnel: `tailscale funnel --bg 8651`
  → `https://blahirs-macbook-pro.tailbbe234.ts.net/?k=<token>`
- Token lives in `~/BillySorrells/tools/billo-remote/.token` (chmod 600). Rotate by restarting with a new `BILLO_REMOTE_TOKEN`.
- Passwords: Billy types them himself from the phone. Agents never send credentials through `/input`.

## Build (Mac)
```
source ~/.cargo/env
CARGO_TARGET_DIR="/Volumes/Monterey OS - Data/BILLO_SCRATCH/cargo-target/billo-remote" cargo build --release
```
Build output goes to the SSD scratch, not the near-full internal disk.

## Run
```
BILLO_REMOTE_TOKEN=$(cat ~/BillySorrells/tools/billo-remote/.token) \
  nohup ~/BillySorrells/tools/billo-remote/bin/billo_remote 8651 > /tmp/billo_remote.log 2>&1 &
```
Stop: `pkill -f bin/billo_remote` · Close the public door: `tailscale funnel --https=443 off`

macOS permissions: Screen Recording (frames) and Accessibility (taps/typing) for the process that launches it.
Note: xcap 0.0.14 fails to compile against current core-foundation; use xcap 0.7.
