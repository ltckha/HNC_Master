"""Test: xuất MISA / sàn / web cũ bỏ qua mã "cần bổ sung" (trống Tên Ngành Hàng hoặc giá bán).
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
    ["Mã hàng hóa cha", "", "", ""],
    ["parent_product_code", "Tên Ngành Hàng", "product_code", "product_price"],
    ["GT1782", "Giày tây nam", "GT1782D", "800000"],
    ["32837", "", "32837D", "1200000"],
    ["32837", "Giày mọi nam", "32837n\x08", ""],
    ["32837", "Giày mọi nam", "32837X", "0"],
    ["", "", "", ""],
])
col_map = {"parent_product_code": 0, "Tên Ngành Hàng": 1, "product_code": 2, "product_price": 3}
codes = main.pending_info_codes(df_sp, col_map)
eq("mã cần bổ sung: trống ngành hoặc giá bán (bỏ ký tự ẩn)", sorted(codes), ["32837D", "32837N", "32837X"])
eq("thiếu cả 2 cột → không bỏ gì", main.pending_info_codes(df_sp, {"product_code": 2}), set())

recs = [{"product_code": "GT1782D"}, {"product_code": "32837d"}, {"product_code": "32837N"}, {"product_code": "TH2040D"}]
kept, idx = main.drop_pending_info(recs, [3, 4, 5, 6], codes)
eq("bỏ dòng mã chưa bổ sung, giữ chỉ số dòng khớp", ([r["product_code"] for r in kept], idx), (["GT1782D", "TH2040D"], [3, 6]))
eq("không có mã chưa bổ sung → giữ nguyên", main.drop_pending_info(recs, [3, 4, 5, 6], set()), (recs, [3, 4, 5, 6]))
eq("tác vụ bỏ qua: MISA (15E + Y3C), Shopee, TikTok đăng mới, web cũ; KHÔNG bỏ in tem / đồng bộ kho", sorted(main.PENDING_INFO_SKIP_TASKS), [1, 2, 3, 4, 5, 8, 12])

print("❌ có ca sai" if fail else "✅ test_pending_info đạt")
sys.exit(1 if fail else 0)
