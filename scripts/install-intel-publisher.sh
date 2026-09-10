#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.quickcommerce.intel.publisher.plist"
LABEL="com.quickcommerce.intel.publisher"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT_DIR/logs"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$ROOT_DIR/scripts/publish-pending-intel.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartCalendarInterval</key>
  <array>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>15</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>17</integer>
      <key>Minute</key>
      <integer>15</integer>
    </dict>
  </array>
  <key>StandardOutPath</key>
  <string>$ROOT_DIR/logs/intel-publisher.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$ROOT_DIR/logs/intel-publisher.launchd.err.log</string>
</dict>
</plist>
PLIST

chmod +x "$ROOT_DIR/scripts/publish-pending-intel.sh"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Installed the intel publisher."
echo "It runs at 10:15 and 17:15 while this Mac is awake."
echo "Log file: $ROOT_DIR/logs/intel-publisher.log"
