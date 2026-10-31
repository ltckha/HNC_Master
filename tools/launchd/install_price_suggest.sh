#!/bin/bash
# Cài / cài lại lịch gợi ý giá 13:30 (Agent đăng SP GĐ3b). Chạy lại được nhiều lần. Gỡ: launchctl bootout gui/$(id -u)/vn.giayhainancy.hnc.price_suggest
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/vn.giayhainancy.hnc.price_suggest.plist"
cp "$REPO/tools/launchd/vn.giayhainancy.hnc.price_suggest.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/vn.giayhainancy.hnc.price_suggest" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Đã cài: $PLIST"
