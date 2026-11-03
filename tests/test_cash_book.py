"""Sổ quỹ Mac (tools/cash_book.py) theo luật web cash_book.ts — chạy: venv/bin/python tests/test_cash_book.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import cash_book as c  # noqa: E402

QUY = [
    {'id': 1, 'ho': '15E', 'loai': 'tien_mat', 'ten': 'Tiền mặt tiệm 15E', 'kho': '15E', 'nhan_ck': 0, 'du_dau': 2000000, 'ngay_dau': '2026-11-01', 'an': 0},
    {'id': 3, 'ho': '15E', 'loai': 'ngan_hang', 'ten': 'TK 15E', 'kho': None, 'nhan_ck': 1, 'du_dau': 5000000, 'ngay_dau': '2026-11-01', 'an': 0},
    {'id': 2, 'ho': 'Y3C', 'loai': 'tien_mat', 'ten': 'Tiền mặt tiệm 3C', 'kho': 'Y3C', 'nhan_ck': 0, 'du_dau': 0, 'ngay_dau': '2026-11-01', 'an': 0},
]
PHIEU = [
    {'so': 'PT000001', 'loai': 'PT', 'quy_id': 1, 'quy_den': None, 'ngay': '2026-11-02', 'so_tien': 300000, 'nhom': None, 'ghi_chu': 'Thử thu khác', 'huy_luc': None},
    {'so': 'CQNB000001', 'loai': 'CQNB', 'quy_id': 1, 'quy_den': 2, 'ngay': '2026-11-03', 'so_tien': 100000, 'nhom': None, 'ghi_chu': 'Thử chuyển quỹ', 'huy_luc': None},
    {'so': 'PC000001', 'loai': 'PC', 'quy_id': 1, 'quy_den': None, 'ngay': '2026-11-03', 'so_tien': 45000, 'nhom': 'Ăn uống, nước', 'ghi_chu': 'Thử: nước uống', 'huy_luc': None},
    {'so': 'PC000009', 'loai': 'PC', 'quy_id': 1, 'quy_den': None, 'ngay': '2026-11-03', 'so_tien': 999, 'nhom': None, 'ghi_chu': '', 'huy_luc': '2026-11-03T10:00:00Z'},
    {'so': 'PC000003', 'loai': 'PC', 'quy_id': 1, 'quy_den': None, 'ngay': '2026-10-20', 'so_tien': 5, 'nhom': None, 'ncc': 'X', 'huy_luc': None},  # trước ngay_dau
]
BAN = [
    ['Ngày', 'product_code', 'Giá', 'item_quantity', 'KHO', 'channel', 'chu_hang', 'payment_method'],
    ['01/11/2026', 'A1', '3.000.000 đ', '2', '15E', '', '', ''],            # trống = Tiền mặt → tiệm 15E
    ['01/11/2026', 'A2', '500000', '1', '15ETBH', 'shopee', '', 'CK'],      # sàn: bỏ
    ['1/11/2026', 'A3', '400000', '1', 'Y3C', '', 'Y3C', 'Chuyển khoản'],    # CK hộ Y3C: chưa có tài khoản
    ['01/11/2026', 'A4', '700000', '1', 'Y3C', '', '15E', 'Thẻ'],            # ký gửi hộ 15E bán ở 3C: thẻ → TK 15E
    ['01/11/2026', 'A5', '200000', '1', 'Y3C', '', '15E', ''],               # tiền mặt → két tiệm 3C
    ['02/11/2026', 'A6', '800000', '-1', '15E', '', '', 'Tiền mặt'],         # trả hàng: tổng ngày âm → Chi
    ['02/11/2026', 'A7', '300000', '1', '15E', '', '', 'COD'],               # chưa vào quỹ
    ['', 'A8', '999999', '1', '15E', '', '', ''],                            # Ngày trống (day_inf): bỏ
]
ok = fail = 0


def eq(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"❌ {name}\n   got:  {got}\n   want: {want}")


data = {'quy': QUY, 'phieu': PHIEU}
ban = c.ban_rows(BAN)
so, ngoai, chua = c.so_quy(data, ban, '15E', '2026-11', today='2026-11-03')
tm = c.xlsx_rows(so[0])
eq('tiền mặt 15E: đầu kỳ + bán + trả hàng + phiếu (bỏ huỷ, bỏ trước ngày bắt đầu)', tm, [
    c.COT,
    [None, None, 'Số dư đầu kỳ', None, None, None, 2000000],
    ['01/11/2026', None, 'Tiền bán hàng (tiền mặt)', None, 6000000, None, 8000000],
    ['02/11/2026', None, 'Trả tiền khách trả hàng (tiền mặt)', None, None, 800000, 7200000],
    ['02/11/2026', 'PT000001', 'Thử thu khác', None, 300000, None, 7500000],
    ['03/11/2026', 'CQNB000001', 'Chuyển sang Tiền mặt tiệm 3C · Thử chuyển quỹ', None, None, 100000, 7400000],
    ['03/11/2026', 'PC000001', 'Ăn uống, nước · Thử: nước uống', 'Ăn uống, nước', None, 45000, 7355000],
])
eq('TK 15E nhận thẻ của hàng ký gửi bán ở 3C', c.xlsx_rows(so[1])[2], ['01/11/2026', None, 'Tiền bán hàng (chuyển khoản / thẻ)', None, 700000, None, 5700000])
eq('hộ 15E: COD chưa vào quỹ', ngoai, {'COD': 300000})
so3, _, chua3 = c.so_quy(data, ban, 'Y3C', '2026-11', today='2026-11-03')
eq('két 3C: tiền mặt bán ở 3C (cả hàng ký gửi) + nhận chuyển quỹ', [r[2:7] for r in c.xlsx_rows(so3[0])[2:]],
   [['Tiền bán hàng (tiền mặt)', None, 200000, None, 200000], ['Nhận từ Tiền mặt tiệm 15E · Thử chuyển quỹ', None, 100000, None, 300000]])
eq('hộ Y3C: CK chưa có tài khoản nhận', chua3, 400000)
so12, _, _ = c.so_quy(data, ban, '15E', '2026-12', today='2026-12-05')
eq('tháng sau: đầu kỳ = cuối kỳ tháng trước', so12[0]['dau_ky'], 7355000)
eq('tên file như web', c.file_name(QUY[0], '2026-11'), 'So_quy_Tiền_mặt_tiệm_15E_2026-11.xlsx')
eq('dòng chỉ sổ thuế không vào quỹ (như web CHI_SO_THUE)', len(c.ban_rows([
    ['Ngày', 'product_code', 'Giá', 'item_quantity', 'KHO', 'seller', 'ma_dong'],
    ['01/11/2026', 'A1', '1', '1', '15E', 'doi_tra', 'DT1-TRA'], ['01/11/2026', 'A1', '1', '1', '15E', 'Kha', 'MISA1103D-1'],
    ['01/11/2026', 'A1', '1', '1', '15E', '', 'DC-MISA-2'], ['01/11/2026', 'A1', '1', '1', '15E', 'Kha', 'X#1']])), 1)
eq('cách thu như web', [c.payment_method(x) for x in ['', 'ck', 'Thẻ', 'momo', 'ghi nợ', 'ship thu hộ', 'abc']],
   ['', 'Chuyển khoản', 'Thẻ', 'Ví', 'Ghi nợ', 'COD', 'Tiền mặt'])
QUY2 = QUY + [{'id': 8, 'ho': '15E', 'loai': 'cho_the', 'ten': 'Tiền thẻ chờ về', 'kho': None, 'nhan_ck': 0, 'du_dau': 0, 'ngay_dau': '2026-11-05', 'an': 0},
              {'id': 9, 'ho': '15E', 'loai': 'cho_cod', 'ten': 'Tiền COD chờ về', 'kho': None, 'nhan_ck': 0, 'du_dau': 0, 'ngay_dau': '2026-11-05', 'an': 0}]
BAN2 = BAN[:1] + [
    ['04/11/2026', 'B1', '500000', '1', '15E', '', '', 'Thẻ'],   # trước ngày bật: như CK → TK 15E
    ['05/11/2026', 'B2', '600000', '1', '15E', '', '', 'Thẻ'],   # từ ngày bật → quỹ thẻ chờ về
    ['05/11/2026', 'B3', '400000', '1', 'Y3C', '', 'Y3C', 'Thẻ'],  # hàng hộ 3C cũng vào quỹ chờ về 15E
    ['05/11/2026', 'B4', '300000', '1', '15E', '', '', 'COD'],   # COD → quỹ COD chờ về
    ['04/11/2026', 'B5', '200000', '1', '15E', '', '', 'COD'],   # trước ngày bật: chưa vào quỹ
]
so5, ngoai5, _ = c.so_quy({'quy': QUY2, 'phieu': []}, c.ban_rows(BAN2), '15E', '2026-11', today='2026-11-05')
by5 = {s['quy']['id']: [r[2:5] for r in c.xlsx_rows(s)[2:]] for s in so5}
eq('GĐ2: thẻ trước ngày bật vào TK 15E', by5[3], [['Tiền bán hàng (chuyển khoản / thẻ)', None, 500000]])
eq('GĐ2: thẻ từ ngày bật (mọi hộ chủ hàng) vào quỹ chờ về', by5[8], [['Tiền bán hàng (thẻ, chờ về)', None, 1000000]])
eq('GĐ2: COD từ ngày bật vào quỹ chờ về, trước đó chưa vào quỹ', (by5[9], ngoai5), ([['Tiền bán hàng (COD, chờ về)', None, 300000]], {'COD': 200000}))
print(f"{'✅' if not fail else '❌'} {ok}/{ok + fail} ca đạt")
sys.exit(1 if fail else 0)
