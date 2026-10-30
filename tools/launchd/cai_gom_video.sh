#!/bin/bash
# Cài / cài lại tự gom video sản phẩm (30/10). Chạy lại được nhiều lần. Gỡ: launchctl bootout gui/$(id -u)/vn.giayhainancy.hnc.gomvideo
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/vn.giayhainancy.hnc.gomvideo.plist"
cp "$REPO/tools/launchd/vn.giayhainancy.hnc.gomvideo.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/vn.giayhainancy.hnc.gomvideo" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Đã cài: $PLIST"
