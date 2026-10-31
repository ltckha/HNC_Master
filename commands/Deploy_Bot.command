#!/bin/bash
# Cập nhật bot Zalo HNC: test bot → clasp push → cập nhật ĐÚNG bản triển khai đang chạy
# (link /exec giữ nguyên, không cần setupWebhook lại). Quay về bản cũ: xem zalo_bot/README.md mục "Cập nhật bot bằng clasp".
cd "$(dirname "$0")/.."  # chạy từ thư mục commands → về gốc repo
set -e
pause() { echo ""; read -t 30 -n 1 -s -r -p "Tự động đóng sau 30s hoặc nhấn phím bất kỳ để đóng..."; }
trap 'echo ""; echo "❌ Dừng — bot thật KHÔNG đổi (hoặc chỉ mã đã đẩy, bản triển khai chưa đổi)."; pause' ERR
[ -f zalo_bot/.clasp.json ] || { echo "❌ Chưa có zalo_bot/.clasp.json (scriptId)."; pause; exit 1; }
DEP=$(node -e 'try{console.log(require("./zalo_bot/deploy.json").deployment_id||"")}catch{console.log("")}')
[ -n "$DEP" ] || { echo "❌ Chưa có deployment_id trong zalo_bot/deploy.json."; pause; exit 1; }
echo "1/3 Test bot…"
node zalo_bot/tests/test_zalo_bot.js
cd zalo_bot
echo "2/3 Đẩy Code.gs + appsscript.json…"
clasp push --force
echo "3/3 Cập nhật bản triển khai đang chạy…"
clasp create-deployment -i "$DEP" -d "HNC $(date '+%Y-%m-%d %H:%M') $(git -C .. rev-parse --short HEAD)"
echo ""
echo "✅ Đã cập nhật bot Zalo HNC (link /exec giữ nguyên). Thử: nhắn hd, rồi TH2040D 40."
pause
