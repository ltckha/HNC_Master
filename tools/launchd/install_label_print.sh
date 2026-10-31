#!/bin/bash
# Cài / cài lại dịch vụ in tem khi bấm QL-700 (V34 mục 6). Chạy lại được nhiều lần.
# Từ 18/10 lệnh in đi qua tab ẩn in_tem_lenh (gspread), không đọc Drive nên launchd chạy thẳng python được.
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/vn.giayhainancy.hnc.label_print.plist"
cp "$REPO/tools/launchd/vn.giayhainancy.hnc.label_print.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/vn.giayhainancy.hnc.label_print" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Đã cài: $PLIST"
