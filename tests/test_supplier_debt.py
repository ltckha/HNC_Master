"""Công nợ NCC Mac (tools/supplier_debt.py) theo luật web congNo — chạy: venv/bin/python tests/test_supplier_debt.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import supplier_debt as s  # noqa: E402

CN = {
    'ncc': [{'ten': 'Chú Dũng', 'no_dau': 1000000, 'ngay_dau': '2026-11-01'}, {'ten': 'NCC trống', 'no_dau': 0, 'ngay_dau': None}],
    'nhan': [
        {'ncc': 'Chú Dũng', 'phieu': 1, 'dong': 1, 'ngay': '2026-11-02', 'sl': 10, 'gia_nhap': 300000, 'huy': 0},
        {'ncc': 'Chú Dũng', 'phieu': 1, 'dong': 1, 'ngay': '2026-11-02', 'sl': 5, 'gia_nhap': 300000, 'huy': 1},   # lần huỷ: bỏ
        {'ncc': 'Chú Dũng', 'phieu': 1, 'dong': 2, 'ngay': '2026-11-02', 'sl': 2, 'gia_nhap': 0, 'huy': 0},        # hàng tặng
        {'ncc': 'Chú Dũng', 'phieu': 9, 'dong': 9, 'ngay': '2026-11-03', 'sl': 3, 'gia_nhap': 50000, 'huy': 0},  # phiếu nhap: bỏ
        {'ncc': 'chu dung ', 'phieu': 2, 'dong': 3, 'ngay': '2026-11-03', 'sl': 1, 'gia_nhap': 100000.4, 'huy': 0},  # cùng NCC (không dấu), làm tròn theo phiếu
    ],
    'phieu': [{'phieu': 1, 'ncc': 'Chú Dũng', 'trang_thai': 'xong'}, {'phieu': 2, 'ncc': 'Chú Dũng', 'trang_thai': 've_thieu'},
              {'phieu': 9, 'ncc': 'Chú Dũng', 'trang_thai': 'nhap'}],
    'tra_ncc': [{'ncc': 'Chú Dũng', 'phieu': 1, 'ngay': '2026-11-03', 'ma': 'X', 'sl': 1, 'gia_nhap': 300000}],
    'hd': [
        {'ncc': 'Chú Dũng', 'phieu': 9, 'so_hd': 'N-1', 'ngay': '2026-11-03', 'chiet_khau': 0, 'phi': 70000, 'bi_thay': 0, 'thay_the_boi': None},  # phiếu nhap: bỏ
        {'ncc': 'Chú Dũng', 'phieu': 1, 'so_hd': 'A-1', 'ngay': '2026-11-03', 'chiet_khau': -50000, 'phi': 20000, 'bi_thay': 1, 'thay_the_boi': 'A-2'},
        {'ncc': 'Chú Dũng', 'phieu': 1, 'so_hd': 'A-2', 'ngay': '2026-11-03', 'chiet_khau': -30000, 'phi': 10000, 'bi_thay': 0, 'thay_the_boi': None},
    ],
}
PHIEU = [
    {'so': 'PC000001', 'loai': 'PC', 'ncc': 'Chú Dũng', 'so_tien': 500000, 'dat_coc': 1, 'huy_luc': None},
    {'so': 'PC000002', 'loai': 'PC', 'ncc': 'Chú Dũng', 'so_tien': 999, 'huy_luc': '2026-11-03T01:00:00Z'},  # huỷ
    {'so': 'PT000001', 'loai': 'PT', 'ncc': 'Chú Dũng', 'so_tien': 777, 'huy_luc': None},                    # PT không tính
    {'so': 'PC000003', 'loai': 'PC', 'ncc': 'NCC chỉ có trả', 'so_tien': 200000, 'huy_luc': None},
]
rows = s.xlsx_rows(s.cong_no(CN, PHIEU))
want = [s.COT,
        ['Chú Dũng', 1000000, 10 * 300000 - 300000 - 20000 + 100000, 500000, 1000000 + 2780000 - 500000],
        ['NCC trống', 0, 0, 0, 0],
        ['NCC chỉ có trả', 0, 0, 200000, -200000]]
print('✅ 1/1 ca đạt' if rows == want else f'❌ công nợ\n   got:  {rows}\n   want: {want}')
sys.exit(0 if rows == want else 1)
