#!/bin/bash
# Cài / cài lại lịch gợi ý giá 13:30 (Agent đăng SP GĐ3b). Chạy lại được nhiều lần. Gỡ: launchctl bootout gui/$(id -u)/vn.giayhainancy.hnc.goiygia
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/vn.giayhainancy.hnc.goiygia.plist"
cp "$REPO/tools/launchd/vn.giayhainancy.hnc.goiygia.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/vn.giayhainancy.hnc.goiygia" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Đã cài: $PLIST"
