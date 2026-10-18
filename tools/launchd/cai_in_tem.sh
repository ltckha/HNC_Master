#!/bin/bash
# Cài dịch vụ in tem tự động QL-700 (V34 mục 6). Chạy lại được nhiều lần.
# launchd không được macOS cho tải file Google Drive chưa có trên máy (lỗi "Resource deadlock avoided"),
# nên launchd mở 1 app nhỏ (HNC_InTem.app) và app đó chạy tools/label_print.py.
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$HOME/Applications/HNC_InTem.app"
PLIST="$HOME/Library/LaunchAgents/vn.giayhainancy.hnc.intem.plist"
mkdir -p "$HOME/Applications"
rm -rf "$APP"
osacompile -o "$APP" -e "do shell script \"cd '$REPO' && PYTHONWARNINGS=ignore '$REPO/venv/bin/python' '$REPO/tools/label_print.py' >> '$HOME/Library/Logs/hnc_in_tem.log' 2>&1\""
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$APP/Contents/Info.plist"  # không hiện trên Dock
codesign --force --sign - "$APP" >/dev/null 2>&1 || true
sed "s#__APP__#$APP#" "$REPO/tools/launchd/vn.giayhainancy.hnc.intem.plist" > "$PLIST"
launchctl bootout "gui/$(id -u)/vn.giayhainancy.hnc.intem" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Đã cài: $APP + $PLIST"
