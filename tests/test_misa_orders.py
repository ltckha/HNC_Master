"""Đơn bán MISA Mac (tools/misa_orders.py) theo web san.js md-x — chạy: venv/bin/python tests/test_misa_orders.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import misa_orders as m  # noqa: E402

ok = fail = 0


def eq(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"❌ {name}\n   got:  {got}\n   want: {want}")


DATA = {'ho': '15E', 'from': '2026-11-01', 'to': '2026-11-02', 'moc': '2026-10-21', 'stk': '0123', 'orders': [
    {'ma': 'HN-1', 'day': '2026-11-01', 'ten': 'Chị A', 'sdt': '0909', 'pay': 'Chuyển khoản', 'note': 'web · HN-1',
     'inv': {'mst': '012345678901', 'ten_cty': 'Chị A', 'dia_chi': 'Đà Lạt', 'email': 'a@x.vn'},
     'lines': [{'sku': '1033N42', 'qty': 1, 'price': 650000, 'unit': 'Đôi'}, {'sku': 'TUI1', 'qty': 2, 'price': 0, 'unit': ''}]},
    {'ma': 'BL-20261102-15E', 'day': '2026-11-02', 'ten': 'Khách lẻ', 'sdt': '', 'pay': 'Tiền mặt', 'payDef': True, 'inv': None,
     'note': 'Bán khác (bot / gõ tay) ngày 2026-11-02', 'lines': [{'sku': '1564N41', 'qty': 1, 'price': 650000, 'unit': 'Đôi'}]},
]}
r = m.rows(DATA)
eq('đơn nhiều món: dòng 1 có đầu đơn + STK + hoá đơn cá nhân (MST 12 số)', r[0], {
    1: 'HN-1', 2: '01/11/2026', 3: '01/11/2026', 6: 'Chị A', 7: '0909', 19: 'web · HN-1', 20: 'Chuyển khoản', 21: '0123',
    22: 'Cá nhân', 23: '012345678901', 26: 'Chị A', 27: 'Đà Lạt', 28: '0909', 29: 'a@x.vn', 9: '1033N42', 12: 'Đôi', 13: 1, 14: 650000})
eq('dòng 2 cùng đơn: chỉ mã đơn + hàng (giá 0 / ĐVT trống để trống)', r[1], {1: 'HN-1', 9: 'TUI1', 13: 2})
eq('khách lẻ tiền mặt: không STK', r[2], {1: 'BL-20261102-15E', 2: '02/11/2026', 3: '02/11/2026', 6: 'Khách lẻ', 19: 'Bán khác (bot / gõ tay) ngày 2026-11-02',
                                          20: 'Tiền mặt', 9: '1564N41', 12: 'Đôi', 13: 1, 14: 650000})
eq('tên file như web', m.file_name(DATA, '20261103_120000'), 'MISA_DON_HANG_15E_2026-11-01_2026-11-02_20261103_120000.xlsx')
L = m.label_set({'ma': [{'ho': '15E', 'code': '2032D', 'size': '39'}, {'ho': '15E', 'code': 'TUI1', 'size': '-'}, {'ho': 'Y3C', 'code': 'Y1', 'size': '38'}]}, '15E')
eq('nhãn theo hộ', L, {('2032D', '39'), ('TUI1', '-')})
eq('size 39.0 / chữ thường / không size', [m.skip(L, '2032d', '39.0'), m.skip(L, 'TUI1', ''), m.skip(L, '2032D', '40'), m.skip(L, 'Y1', '38')], [True, True, False, False])
print(f"{'✅' if not fail else '❌'} {ok}/{ok + fail} ca đạt")
sys.exit(1 if fail else 0)
