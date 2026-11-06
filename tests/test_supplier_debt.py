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
        ['Chú Dũng', 1000000, 10 * 300000 - 300000 - 20000 + 100000, 500000, 1000000 + 2780000 - 500000, 2780000 - 500000, 0],
        ['NCC trống', 0, 0, 0, 0, 0, 0],
        ['NCC chỉ có trả', 0, 0, 200000, -200000, -200000, 0]]
ok = rows == want
if not ok:
    print(f'❌ công nợ\n   got:  {rows}\n   want: {want}')
# 04/11 (web d6181484): theo hộ — nhận theo kho, HĐ theo hộ mua, phải trả = max(hàng + thuế, tổng HĐ); trả gắn HĐ tính cho hộ của HĐ
CN2 = {'ncc': [], 'phieu': [{'phieu': 5, 'ncc': 'Yen NCC', 'trang_thai': 'xong'}],
       'nhan': [{'ncc': 'Yen NCC', 'phieu': 5, 'kho': 'Y3C', 'sl': 2, 'gia_nhap': 1000000, 'huy': 0}, {'ncc': 'Yen NCC', 'phieu': 5, 'kho': '15E', 'sl': 1, 'gia_nhap': 500000, 'huy': 0}],
       'tra_ncc': [], 'hd': [{'ncc': 'Yen NCC', 'phieu': 5, 'so_hd': 'K-146', 'chiet_khau': 0, 'phi': 0, 'tien_thue': 160000, 'tong_tt': 2200000, 'ho': 'Y3C', 'bi_thay': 0}],
       'hd_cho': [{'ncc': 'Yen NCC', 'phieu': 5, 'so_hd': 'K-9', 'ho': '15E', 'tien_thue': 40000, 'tong_tt': 540000}]}
PQ2 = [{'loai': 'PC', 'ncc': 'Yen NCC', 'so_tien': 1000000, 'ho': '15E', 'phieu_ncc': 5, 'hd_ncc': 'K-146', 'huy_luc': None},   # 15E trả thay HĐ hộ 3C
       {'loai': 'PC', 'ncc': 'Yen NCC', 'so_tien': 300000, 'ho': '15E', 'phieu_ncc': 5, 'hd_ncc': None, 'huy_luc': None}]
r2 = s.xlsx_rows(s.cong_no(CN2, PQ2))[1]
w2 = ['Yen NCC', 0, 2200000 + 540000, 1300000, 2740000 - 1300000, 540000 - 300000, 2200000 - 1000000]
if r2 != w2:
    ok = False
    print(f'❌ công nợ theo hộ\n   got:  {r2}\n   want: {w2}')
# 05/11 (web chu_ncc_ten_phu): phiếu tên ngắn + phiếu / NCC tên đầy đủ + PC tên phụ → 1 dòng tên chính
CN3 = {'ncc': [{'ten': 'CÔNG TY TNHH THƯƠNG MẠI TỔNG HỢP TUẤN PHONG', 'no_dau': 100000}],
       'ten_phu': [{'khoa': 'dai phong', 'ncc': 'Tuấn Phong'}, {'khoa': 'cong ty tnhh thuong mai tong hop tuan phong', 'ncc': 'Tuấn Phong'}],
       'phieu': [{'phieu': 7, 'ncc': 'CÔNG TY TNHH THƯƠNG MẠI TỔNG HỢP TUẤN PHONG', 'trang_thai': 'xong'}, {'phieu': 8, 'ncc': 'tuan phong', 'trang_thai': 'xong'}],
       'nhan': [{'phieu': 7, 'kho': '15E', 'sl': 1, 'gia_nhap': 400000, 'huy': 0}, {'phieu': 8, 'kho': 'Y3C', 'sl': 2, 'gia_nhap': 100000, 'huy': 0}],
       'tra_ncc': [], 'hd': []}
r3 = s.xlsx_rows(s.cong_no(CN3, [{'loai': 'PC', 'ncc': 'ĐẠI PHONG', 'so_tien': 250000, 'ho': '15E', 'huy_luc': None}]))
w3 = [s.COT, ['Tuấn Phong', 100000, 600000, 250000, 450000, 150000, 200000]]
if r3 != w3:
    ok = False
    print(f'❌ tên phụ NCC\n   got:  {r3}\n   want: {w3}')
# 06/11 (web 0fecb344): 2 sổ — 'hd' Sổ NCC = chỉ HĐ có thuế + đầu kỳ MISA · 'thuc' Công nợ NCC = nhận × giá nhập − trả NCC, không HĐ / thuế / đầu kỳ
for cach, cn, pq, w in [
        ('thuc', CN, PHIEU, ['Chú Dũng', 0, 3000000 - 300000 + 100000, 500000, 2300000, 2300000, 0]),
        ('hd', CN, PHIEU, ['Chú Dũng', 1000000, 0, 500000, 500000, -500000, 0]),
        ('thuc', CN2, PQ2, ['Yen NCC', 0, 2500000 + 160000 + 40000, 1300000, 1400000, 240000, 1160000]),  # + thuế HĐ K-146 (3C) + HĐ gửi trước K-9 (15E)
        ('hd', CN2, PQ2, ['Yen NCC', 0, 2740000, 1300000, 1440000, 240000, 1200000])]:
    r = s.xlsx_rows(s.cong_no(cn, pq, cach), cach)
    got = next(x for x in r[1:] if x[0] == w[0])
    if got != w or r[0][2] != s.PHAI[cach]:
        ok = False
        print(f'❌ sổ {cach} {w[0]}\n   got:  {got} {r[0][2]}\n   want: {w}')
# MISA nhập kho (06/11, như web 14e418c2): tên công ty dài / chuỗi tên phụ → tên ngắn; NCC theo phiếu NH khi mã chưa có NCC
ch = s.ncc_chuan_fn([{'khoa': 'cong ty tnhh thuong mai tong hop tuan phong', 'ncc': 'Đại Phong'}, {'khoa': 'dai phong', 'ncc': 'Tuấn Phong'},
                     {'khoa': 'tuan phong', 'ncc': 'Tuấn Phong'}])
tp = s.ncc_theo_phieu({'phieu': [{'phieu': 10, 'ncc': 'CÔNG TY TNHH THƯƠNG MẠI TỔNG HỢP TUẤN PHONG'}], 'nhan': [{'phieu': 11, 'ncc': 'Chú Dũng'}]})
for got, want in [(ch('CÔNG TY TNHH THƯƠNG MẠI TỔNG HỢP TUẤN PHONG'), 'Tuấn Phong'), (ch('Công ty TNHH Thương mại, Tổng hợp Tuấn Phong'), 'Tuấn Phong'),
                  (ch('Chú Dũng'), 'Chú Dũng'), (s.phieu_cua_dong('NH10-1#2'), 10), (s.phieu_cua_dong('abc'), None),
                  (tp.get(s.phieu_cua_dong('NH11-2#1')), 'Chú Dũng'), (ch(tp.get(10)), 'Tuấn Phong')]:
    if got != want:
        ok = False
        print(f'❌ gộp tên / phiếu: {got!r} ≠ {want!r}')
print('✅ 8/8 ca đạt' if ok else '❌')
sys.exit(0 if ok else 1)
