"""Test: tem mã hàng main.py (label_record) ra đúng cột / luật như cửa bot in_tem (luật 15). Không gọi mạng.
Chạy: venv/bin/python tests/test_label.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hnc_paths  # noqa: E402

hnc_paths.find_system_dir = lambda: "/tmp"
import main  # noqa: E402

pm = {'TH2040D': {'product_name': 'Giày tây TH2040D', 'product_color': 'Đen', 'product_price': '800000', 'web_url': 'https://giayhainancy.vn/sp/th2040d'}}
r = main.label_record({'product_code': 'TH2040D', 'item_size': '40.0', 'Số lượng (*)': '3', 'product_color': ''}, pm)
want = {'QR code': 'https://giayhainancy.vn/sp/th2040d', 'Tên': 'Giày tây TH2040D', 'Màu': 'Đen', 'Size': '40', 'Size Color': 'Đen (Size 40)',
        'F6': 3, 'Code128': 'TH2040D40', 'Gía': '800.000 đ'}
ok = r == want and main.LABEL_COLUMNS == ['QR code', 'Tên', 'Màu', 'Size', 'Size Color', 'F6', 'Code128', 'Gía']
if not ok:
    print("❌", r)
    sys.exit(1)
print("✅ test_label đạt")
