"""Sổ thuế Mac (tools/tax_book.py) theo web bookkeeping.ts — chạy: venv/bin/python tests/test_tax_book.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import tax_book as t  # noqa: E402

ok = fail = 0


def eq(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"❌ {name}\n   got:  {got}\n   want: {want}")


BAN = [
    ['Ngày', 'product_code', 'Giá', 'item_quantity', 'KHO', 'channel', 'chu_hang', 'ma_dong'],
    ['01/10/2026', 'A1', '500.000 đ', '2', '15E', '', '', 'X#1'],            # 1.000.000 hộ 15E
    ['01/10/2026', 'A2', '300000', '1', 'Y3C', 'shopee', '15E', 'X#2'],     # ký gửi: hộ chủ hàng 15E, sàn vẫn tính
    ['02/10/2026', 'A3', '400000', '-1', '15E', '', '', 'X#3'],             # trả hàng âm
    ['27/10/2026', 'BU_DOI_HANG', '-200000', '1', 'Y3C', '', 'Y3C', 'B#1'],  # trước mốc 04/11: tính
    ['05/11/2026', 'BU_DOI_HANG', '-100000', '1', '15E', '', '', 'B#2'],     # từ mốc: bỏ
    ['05/11/2026', 'A4', '600000', '2', 'Y3C', '', '', 'K#1'],               # 1 đôi Không xuất MISA
]
DC = [
    ['ma_dong', 'Ngày', 'Mã', 'size', 'SL', 'Giá', 'Thành tiền', 'Kênh', 'Kho', 'chu_hang', 'khong_misa', 'loai', 'ghi_chu'],
    ['MISA1103D-1', '03/10/2026', 'HT1', '40', '1', '800000', '800000', '', '15E', '15E', '0', 'bo_sung_misa', ''],
    ['DC-MISA-1', '31/10/2026', '', '', '0', '', '-50000', '', 'Y3C', 'Y3C', '0', 'dieu_chinh', ''],
    ['K#1#KM', '05/11/2026', 'A4', '40', '-1', '600000', '-600000', '', 'Y3C', '', '1', 'khong_misa', 'bỏ khỏi sổ thuế: dòng BAN K#1'],
]
ds = t.lines(BAN, DC)
eq('doanh thu hộ × tháng = BAN + Thành tiền BAN_DIEU_CHINH, bỏ BU_DOI_HANG từ 04/11', t.by_month(ds),
   {'15E': {'2026-10': 1000000 + 300000 - 400000 + 800000, '2026-11': 0}, 'Y3C': {'2026-10': -200000 - 50000, '2026-11': 600000}})
eq('tới ngày', t.by_month(ds, '2026-11-04')['Y3C'], {'2026-10': -250000})
r = t.s1a_rows(ds, '15E', '2026-10')
eq('S1a 15E: mỗi ngày × kênh 1 dòng', r[11:-5], [['01/10/2026', 'Bán hàng hoá (2 món)', 1000000], ['01/10/2026', 'Bán hàng hoá qua Shopee (1 món)', 300000],
                                                 ['02/10/2026', 'Khách trả hàng (1 món)', -400000], ['03/10/2026', 'Bán hàng hoá (1 món)', 800000]])
eq('S1a tổng cộng', r[-5], ['Tổng cộng', '', 1700000])
r3 = t.s1a_rows(ds, 'Y3C', '2026-10')
eq('S1a 3C: đổi hàng + điều chỉnh MISA', r3[11:-5], [['27/10/2026', 'Tiền chênh đổi hàng', -200000], ['31/10/2026', 'Điều chỉnh doanh thu theo MISA', -50000]])
eq('S1a 3C tháng 11: đã trừ đôi Không xuất MISA', t.s1a_rows(ds, 'Y3C', '2026-11')[11:-5], [['05/11/2026', 'Bán hàng hoá (1 món)', 600000]])
eq('tên file như web', t.file_name('Y3C', '2026-10'), 'S1a-HKD_3C_2026-10.xlsx')
print(f"{'✅' if not fail else '❌'} {ok}/{ok + fail} ca đạt")
sys.exit(1 if fail else 0)
