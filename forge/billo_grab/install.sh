#!/usr/bin/env bash
# BILLO GRAB — install on the Mac / EMF hub. Free. Runs at http://127.0.0.1:8765 (Style Lab at /).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; PY=$(command -v python3)
command -v ffmpeg >/dev/null || { command -v brew >/dev/null && brew install ffmpeg || { echo "Install ffmpeg first"; exit 1; }; }
command -v deno >/dev/null || { command -v brew >/dev/null && brew install deno || true; }   # yt-dlp's YouTube JS solver
$PY -m pip install --user -U "yt-dlp[default,curl-cffi]" gallery-dl bgutil-ytdlp-pot-provider 2>/dev/null \
 || $PY -m pip install --user --break-system-packages -U "yt-dlp[default,curl-cffi]" gallery-dl bgutil-ytdlp-pot-provider
COOK="${BILLO_COOKIES:-chrome}"   # uses your logged-in Chrome for private/age-gated/IG posts
mkdir -p ~/BillySorrells/grab
if [ "$(uname -s)" = Darwin ]; then
  P=~/Library/LaunchAgents/com.billo.grab.plist
  cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.billo.grab</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$HERE/billo_grab.py</string><string>serve</string></array>
<key>EnvironmentVariables</key><dict><key>BILLO_COOKIES</key><string>$COOK</string><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardErrorPath</key><string>$HOME/BillySorrells/grab/service.err</string></dict></plist>
PL
  launchctl unload "$P" 2>/dev/null || true; launchctl load "$P"
  # keep the downloaders current (sites change weekly): every day 4:10am
  U=~/Library/LaunchAgents/com.billo.grab.update.plist
  cat > "$U" <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.billo.grab.update</string>
<key>ProgramArguments</key><array><string>$PY</string><string>-m</string><string>pip</string><string>install</string><string>--user</string><string>-U</string><string>yt-dlp[default,curl-cffi]</string><string>gallery-dl</string><string>bgutil-ytdlp-pot-provider</string></array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>4</integer><key>Minute</key><integer>10</integer></dict></dict></plist>
PL
  launchctl unload "$U" 2>/dev/null || true; launchctl load "$U"
else
  mkdir -p ~/.config/systemd/user
  printf '[Unit]\nDescription=Billo Grab\n[Service]\nEnvironment=BILLO_COOKIES=%s\nExecStart=%s %s/billo_grab.py serve\nRestart=always\n[Install]\nWantedBy=default.target\n' "$COOK" "$PY" "$HERE" > ~/.config/systemd/user/billo-grab.service
  systemctl --user daemon-reload && systemctl --user enable --now billo-grab
fi
sleep 2; curl -s http://127.0.0.1:8765/health && echo && echo "Billo Grab live → open http://127.0.0.1:8765 for Style Lab"
