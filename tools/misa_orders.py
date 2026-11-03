"""Đơn bán MISA dự phòng (anh Kha "làm" 03/11, luật 15): menu [4] MISA › [5] — cùng file với web Bán sàn › Đơn bán MISA.

Web gửi sẵn đơn qua act misa_don_ds {ho, tu, den} (cùng hàm màn web: từ mốc MISA, chưa đánh dấu, đã trừ số đôi Không xuất MISA).
Mac chỉ ghi vào tệp mẫu "Nhap_khau_don_hang <hộ>.xlsx" (HNC_Templates), sheet "Danh sách đơn hàng", dữ liệu từ hàng 4 —
cột như public/tools/san.js (md-x). Không đánh dấu "đã nhập lên MISA": việc đó vẫn bấm trên web.
Nhãn theo mã (khong_misa_ds) dùng cho [4][1] hàng hoá mới / [4][2] nhập kho: label_set + skip.
"""
import os
import re

SHEET = 'Danh sách đơn hàng'
ROW0 = 4


def tpl_name(ho):
    return f'Nhap_khau_don_hang {ho}.xlsx'


def file_name(data, stamp):
    return f"MISA_DON_HANG_{data['ho']}_{data['from']}_{data['to']}_{stamp}.xlsx"


def _dmy(d):
    return '/'.join(reversed(d.split('-')))


def rows(data):
    """→ list dòng, mỗi dòng {cột: giá trị} như web (đơn nhiều món: mã đơn lặp ở mọi dòng, phần đầu đơn chỉ ở dòng 1)."""
    out, stk = [], data.get('stk') or ''
    for o in data.get('orders') or []:
        for i, l in enumerate(o['lines']):
            w = {1: o['ma']}
            if i == 0:
                w[2] = w[3] = _dmy(o['day'])
                if o.get('ten'): w[6] = o['ten']
                if o.get('sdt'): w[7] = o['sdt']
                if o.get('note'): w[19] = o['note']
                w[20] = o['pay']
                if o['pay'] == 'Chuyển khoản' and stk: w[21] = stk
                inv = o.get('inv')
                if inv:
                    w[22] = 'Cá nhân' if re.fullmatch(r'\d{12}', str(inv.get('mst') or '')) else 'Công ty/Hộ kinh doanh'
                    w[23] = inv.get('mst')
                    w[26] = inv.get('ten_cty')
                    w[27] = inv.get('dia_chi')
                    if o.get('sdt'): w[28] = o['sdt']
                    if inv.get('email'): w[29] = inv['email']
            w[9] = l['sku']
            if l.get('unit'): w[12] = l['unit']
            w[13] = l['qty']
            if l.get('price'): w[14] = l['price']
            out.append(w)
    return out


def write(tpl_path, out_path, data):
    from openpyxl import load_workbook
    wb = load_workbook(tpl_path)
    ws = wb[SHEET]
    if ws.max_row >= ROW0:
        ws.delete_rows(ROW0, ws.max_row - ROW0 + 1)
    for r, w in enumerate(rows(data), ROW0):
        for c, v in w.items():
            if v not in (None, ''):
                ws.cell(r, c, v)
    wb.save(out_path)
    return out_path


def norm_size(z):
    """Như web: size trống → '-', bỏ '.0', chữ hoa."""
    z = re.sub(r'\.0+$', '', str(z if z is not None else '').strip()).upper()
    return z or '-'


def label_set(data, ho):
    """khong_misa_ds → {(CODE, SIZE)} của 1 hộ."""
    return {(str(m['code']).strip().upper(), norm_size(m['size'])) for m in (data.get('ma') or []) if m.get('ho') == ho}


def skip(labels, code, size):
    return (str(code or '').strip().upper(), norm_size(size)) in labels
