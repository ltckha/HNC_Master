#!/bin/bash
# Cài / cài lại file dự phòng hằng ngày 15:00 (04/11). Chạy lại được nhiều lần. Gỡ: launchctl bootout gui/$(id -u)/vn.giayhainancy.hnc.backup_export
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/vn.giayhainancy.hnc.backup_export.plist"
cp "$REPO/tools/launchd/vn.giayhainancy.hnc.backup_export.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/vn.giayhainancy.hnc.backup_export" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Đã cài: $PLIST"
