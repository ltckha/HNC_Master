"""Test: xuất MISA / sàn / web cũ bỏ qua mã "CẦN BỔ SUNG" (mã tạo từ phiếu NCC).
Chạy: venv/bin/python tests/test_pending_info.py  → thoát mã 1 nếu có ca sai. Không gọi Google."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hnc_paths  # noqa: E402

hnc_paths.find_system_dir = lambda: "/tmp"  # main.py dò thư mục Drive lúc import → giả để chạy được trên máy không có Drive
import main  # noqa: E402

fail = 0


def eq(name, got, want):
    global fail
    if got != want:
        fail += 1
        print(f"❌ {name}\n   got:  {got!r}\n   want: {want!r}")


# SANPHAM giả: hàng 1 tên nhóm, hàng 2 tên cột kỹ thuật
df_sp = pd.DataFrame([
    ["Mã hàng hóa cha", "", ""],
    ["parent_product_code", "product_code", "product_name"],
    ["GT1782", "GT1782D", "Giày cột dây nam GT1782D"],
    ["32837", "32837D", "CẦN BỔ SUNG - Giày mọi da"],
    ["32837", "32837n\x08", "cần bổ sung - Giày mọi da"],
    ["", "", ""],
])
col_map = {"parent_product_code": 0, "product_code": 1, "product_name": 2}
codes = main.pending_info_codes(df_sp, col_map)
eq("tìm mã CẦN BỔ SUNG (không phân biệt hoa thường, bỏ ký tự ẩn)", sorted(codes), ["32837D", "32837N"])
eq("thiếu cột product_name → không bỏ gì", main.pending_info_codes(df_sp, {"product_code": 1}), set())

recs = [{"product_code": "GT1782D"}, {"product_code": "32837d"}, {"product_code": "32837N"}, {"product_code": "TH2040D"}]
kept, idx = main.drop_pending_info(recs, [3, 4, 5, 6], codes)
eq("bỏ dòng mã chưa bổ sung, giữ chỉ số dòng khớp", ([r["product_code"] for r in kept], idx), (["GT1782D", "TH2040D"], [3, 6]))
eq("không có mã chưa bổ sung → giữ nguyên", main.drop_pending_info(recs, [3, 4, 5, 6], set()), (recs, [3, 4, 5, 6]))
eq("tác vụ bỏ qua: MISA, Shopee, TikTok đăng mới, web cũ; KHÔNG bỏ in tem / đồng bộ kho", sorted(main.PENDING_INFO_SKIP_TASKS), [1, 2, 3, 4, 5, 8])

print("❌ có ca sai" if fail else "✅ test_pending_info đạt")
sys.exit(1 if fail else 0)
