#!/usr/bin/env bash
# BILLO · Obscura agent browser — install + wire (Mac / EMF hub / Linux). Free, Apache-2.0.
# Usage: bash install_obscura.sh            (stealth build, CDP on :9222, Claude MCP added)
#        NO_STEALTH=1 bash install_obscura.sh
set -euo pipefail
VER=v0.2.4
OS=$(uname -s); ARCH=$(uname -m)
case "$OS-$ARCH" in
  Darwin-arm64)  T=aarch64-macos ;;
  Linux-aarch64) T=aarch64-linux ;;
  Linux-x86_64)  T=x86_64-linux ;;
  *) echo "No pinned build for $OS-$ARCH (Intel Mac / Windows: grab from the Releases page)"; exit 1 ;;
esac
V=$([ -n "${NO_STEALTH:-}" ] && echo "" || echo "-stealth")
F="obscura-$T$V.tar.gz"
# SHA-256 pinned from the v0.2.4 release page (2026-11-20)
sum_for(){ case "$1" in
 obscura-aarch64-macos-stealth.tar.gz) echo 183ce21fc9caf421c4e027cd8043970224a24d9921d8bf27105153ca74f0e3ae;;
 obscura-aarch64-macos.tar.gz) echo 456210fe48e77324a064477fe450452a58709940a50e71678ae6638a3e5095ec;;
 obscura-aarch64-linux-stealth.tar.gz) echo 56eacea66e4a5b0ab0f39343183c308816b426f604259b9cc41402488bf998f7;;
 obscura-aarch64-linux.tar.gz) echo d9ba3719c2442a227567d7664b5505b38ab68236f3f5388884eee2e27f55db28;;
 *) echo "";; esac; }  # bash 3.2-safe (stock macOS)
DIR="$HOME/BillySorrells/tools/obscura"; mkdir -p "$DIR/bin" "$DIR/logs"; cd "$DIR"
curl -fL -o "$F" "https://github.com/h4ckf0r0day/obscura/releases/download/$VER/$F"
WANT=$(sum_for "$F")
if [ -n "$WANT" ]; then
  GOT=$(shasum -a 256 "$F" 2>/dev/null | cut -d' ' -f1 || sha256sum "$F" | cut -d' ' -f1)
  [ "$GOT" = "$WANT" ] || { echo "CHECKSUM MISMATCH — not installing"; exit 1; }
  echo "checksum ok"
else echo "WARN: no pinned checksum for $F — verify on the release page"; fi
tar -xzf "$F" -C bin; BIN=$(find bin -type f -name obscura | head -1); chmod +x "$BIN"
[ "$OS" = Darwin ] && xattr -dr com.apple.quarantine "$BIN" 2>/dev/null || true
ln -sf "$DIR/$BIN" /usr/local/bin/obscura 2>/dev/null || ln -sf "$DIR/$BIN" "$HOME/.local/bin/obscura"
obscura --version || true

# 1) Always-on CDP endpoint on loopback :9222 (Playwright/Puppeteer swap-in for Chrome)
FLAGS="serve --port 9222 ${V:+--stealth}"
if [ "$OS" = Darwin ]; then
  P="$HOME/Library/LaunchAgents/com.billo.obscura.plist"
  cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.billo.obscura</string>
<key>ProgramArguments</key><array><string>$(command -v obscura)</string>$(for a in $FLAGS; do printf '<string>%s</string>' "$a"; done)</array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$DIR/logs/obscura.log</string><key>StandardErrorPath</key><string>$DIR/logs/obscura.err</string>
</dict></plist>
PL
  launchctl unload "$P" 2>/dev/null || true; launchctl load "$P"
else
  mkdir -p ~/.config/systemd/user
  printf '[Unit]\nDescription=Billo Obscura CDP\n[Service]\nExecStart=%s %s\nRestart=always\n[Install]\nWantedBy=default.target\n' "$(command -v obscura)" "$FLAGS" > ~/.config/systemd/user/billo-obscura.service
  systemctl --user daemon-reload && systemctl --user enable --now billo-obscura
fi

# 2) Claude Code on this machine gets it as a browser tool
command -v claude >/dev/null && claude mcp add --scope user obscura -- obscura mcp ${V:+--stealth} || echo "(claude CLI not found — skip MCP)"

sleep 2; curl -s http://127.0.0.1:9222/json/version && echo && echo "OBSCURA LIVE on ws://127.0.0.1:9222"
