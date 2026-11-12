#!/bin/bash
# Billo Roast Room — one-time engine setup for the Mac (bash 3.2-safe).
# Installs Ollama, lets the Roast Room pages talk to it, pulls an abliterated writing model sized to this Mac.
# Free and local: nothing here creates an account or sends your writing anywhere.
set -eu
ORIGINS="https://billysorrells.com,https://billo-os.netlify.app,https://billotech-page-preview.netlify.app,tauri://localhost,http://localhost,http://localhost:*"
say() { printf '\n\033[1;36m%s\033[0m\n' "$1"; }

[ "$(uname -s)" = "Darwin" ] || { echo "This script is for macOS. On Windows or Linux: install Ollama, set OLLAMA_ORIGINS to the list in this file, pull the model."; exit 1; }

if ! command -v ollama >/dev/null 2>&1 && [ ! -d "/Applications/Ollama.app" ]; then
  say "Installing Ollama"
  if command -v brew >/dev/null 2>&1; then brew install --cask ollama
  else
    T="$(mktemp -d)"; curl -fL --progress-bar -o "$T/Ollama.dmg" "https://ollama.com/download/Ollama.dmg"
    M="$(hdiutil attach -nobrowse "$T/Ollama.dmg" | awk -F'\t' '/\/Volumes\//{print $NF}' | tail -1)"
    cp -R "$M/Ollama.app" /Applications/ && hdiutil detach "$M" >/dev/null; rm -rf "$T"
  fi
fi
OLLAMA="$(command -v ollama || true)"; [ -n "$OLLAMA" ] || OLLAMA="/Applications/Ollama.app/Contents/Resources/ollama"

say "Letting the Roast Room pages reach the engine (stays on after restart)"
launchctl setenv OLLAMA_ORIGINS "$ORIGINS"
P="$HOME/Library/LaunchAgents/com.billo.roast-room-origins.plist"; mkdir -p "$HOME/Library/LaunchAgents"
cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.billo.roast-room-origins</string>
<key>ProgramArguments</key><array><string>/bin/launchctl</string><string>setenv</string><string>OLLAMA_ORIGINS</string><string>$ORIGINS</string></array>
<key>RunAtLoad</key><true/>
</dict></plist>
PL
launchctl unload "$P" >/dev/null 2>&1 || true; launchctl load "$P"

say "Restarting Ollama"
osascript -e 'quit app "Ollama"' >/dev/null 2>&1 || true; sleep 2; open -a Ollama
i=0; until curl -fsS -m 2 http://localhost:11434/api/version >/dev/null 2>&1; do i=$((i+1)); [ "$i" -gt 45 ] && { echo "Ollama did not start. Open the Ollama app, then run this again."; exit 1; }; sleep 1; done

GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
if   [ "$GB" -ge 32 ]; then MODEL="huihui_ai/qwen3.5-abliterated:27b"
elif [ "$GB" -ge 12 ]; then MODEL="huihui_ai/qwen3.5-abliterated:9b"
else                        MODEL="huihui_ai/qwen3.5-abliterated:4b"; fi
say "This Mac has ${GB} GB of memory. Pulling ${MODEL} (one time)"
"$OLLAMA" pull "$MODEL"

say "Done. Opening the Roast Room"
URL="https://billotech-page-preview.netlify.app/billotech/apps/roast/"
open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL"
