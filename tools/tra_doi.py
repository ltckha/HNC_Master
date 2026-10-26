"""Trả hàng / Đổi hàng dự phòng trên Mac (luật 15, anh Kha "làm" đổi / trả 26/10) — ra CÙNG dòng như bot / web:
- Trả: 1 dòng NHAP, Số chứng từ TRA-<ddMMyy> (LuatKho.soTraHang), web_stock / web_label / misa_stock = Tra_hang
  (như bot appendNhap_(isReturn)); chủ hàng theo LuatKho.traHangChuHang (chủ gửi kèm, không có thì dòng BAN gần nhất
  cùng mã / size / kho); chủ là hộ kia → cộng lại ô ký gửi cua_<hộ> (như bot kyguiReturn_). KHO chưa có dòng mã + size → thêm dòng có công thức.
- Đổi: trả như trên + 1 dòng BAN bán mới (ký gửi hộ kia bán trước, LuatKho.banTachChuHang; như bot kyguiSale_).
  Sheet BAN chưa có cột liên kết phiếu gốc → chưa ghi liên kết (đã báo Phân tích · Bán hàng).
ma_dong = MAC-<lần chạy>#n, nguon = mac. Chỉ ghi khi sổ tương ứng đang Dự phòng (loader._write_ok chặn như mọi lệnh Mac).
"""
from datetime import datetime

from gspread.utils import rowcol_to_a1

from tools.luat_kho_node import goi

KHO_TAB = {'15E': 'KHO15E', 'Y3C': 'KHOY3C'}
KY_COL = {'15E': 'cua_Y3C', 'Y3C': 'cua_15E'}  # cột hàng của hộ kia đang ở kho này
NHAP_MARK = ('web_stock', 'web_label', 'misa_stock')
TRA_MARK = 'Tra_hang'


def _money(v):
    d = ''.join(ch for ch in str(v or '') if ch.isdigit())
    return int(d) if d else 0


def _col(head, name):
    return rowcol_to_a1(1, head.index(name) + 1).rstrip('1')


def _last_row(v, head):
    ic = head.index('product_code')
    return max(i + 1 for i, r in enumerate(v) if i == 0 or (len(r) > ic and r[ic].strip()))


class TraDoi:
    def __init__(self, loader, run_id):
        self.L, self.run, self.n = loader, run_id, 0
        self.ss = loader.spreadsheet
        self.ops = []      # (mô tả, hàm ghi)
        self.ghi_chu = []

    def ma_dong(self):
        self.n += 1
        return f"MAC-{self.run}#{self.n}"

    def sp(self, code):
        v = self.ss.worksheet('SANPHAM').get_all_values()
        h = [c.strip() for c in v[1]]  # SANPHAM: tên cột ở hàng 2 (luật 4)
        r = next((x for x in v[2:] if x[h.index('product_code')].strip().upper() == code), None)
        if not r:
            raise RuntimeError(f'SANPHAM không có mã {code}')
        return {'color': r[h.index('product_color')].strip(), 'gia': _money(r[h.index('product_price')])}

    def kho_row(self, kho, code, size):
        v = self.ss.worksheet(KHO_TAB[kho]).get_all_values()
        h = [c.strip() for c in v[0]]
        r = next((i + 1 for i, x in enumerate(v) if i and x[h.index('product_code')].strip().upper() == code
                  and goi('chuanSize', x[h.index('item_size')]) == size), None)
        return r, v, h

    def _append(self, tab, vals, formulas=None, label=''):
        ws = self.ss.worksheet(tab)
        v = ws.get_all_values()
        h = [c.strip() for c in v[0]]
        miss = [k for k in list(vals) + list(formulas or {}) if k not in h]
        if miss:
            raise RuntimeError(f'Tab {tab} thiếu cột {miss}')
        row = _last_row(v, h) + 1
        if tab == 'NHAP':
            row = max(row, 3)  # hàng 2 NHAP là tiêu đề kỹ thuật
        out = [''] * len(h)
        for k, val in vals.items():
            out[h.index(k)] = val
        for k, f in (formulas or {}).items():
            out[h.index(k)] = f(lambda n: _col(h, n), row)
        self.ops.append((f"{tab} dòng {row}: {label}", lambda: self._write_row(tab, out, row)))

    def _write_row(self, tab, out, row):
        if not self.L.insert_rows_with_exact_range(tab, [out], row):
            raise RuntimeError(f'Không ghi được {tab} (sổ đang ở Web hoặc web còn dòng chờ chép?)')

    def _cell(self, tab, row, col_name, new, label):
        def w():
            ws = self.ss.worksheet(tab)
            ws.update_cell(row, [c.strip() for c in ws.row_values(1)].index(col_name) + 1, new)
            self.L._mark_sync(tab)
        self.ops.append((f"{tab} dòng {row}: {label}", w))

    def _kho_moi(self, kho, code, size, color):
        tab = KHO_TAB[kho]
        hn = [c.strip() for c in self.ss.worksheet('NHAP').row_values(1)]
        hx = [c.strip() for c in self.ss.worksheet('XUAT').row_values(1)]
        hb = [c.strip() for c in self.ss.worksheet('BAN').row_values(1)]
        c = _col
        self._append(tab, {'product_code': code, 'product_color': color, 'item_size': int(size) if size.isdigit() else size, 'opening_quantity': 0}, {
            kho: lambda L, r: f"=CONCATENATE(${L(kho)}$1;{L('product_code')}{r};{L('item_size')}{r})",
            'current_quantity': lambda L, r: (
                f"={L('opening_quantity')}{r} + SUMIF(NHAP!{c(hn, 'FSKU')}:{c(hn, 'FSKU')}; {L(kho)}{r}; NHAP!{c(hn, 'Số lượng (*)')}:{c(hn, 'Số lượng (*)')})"
                f" - SUMIF(XUAT!{c(hx, 'FSKU')}:{c(hx, 'FSKU')}; {L(kho)}{r}; XUAT!{c(hx, 'item_quantity')}:{c(hx, 'item_quantity')})"
                f" - SUMIF(BAN!{c(hb, 'FSKU')}:{c(hb, 'FSKU')}; {L(kho)}{r}; BAN!{c(hb, 'item_quantity')}:{c(hb, 'item_quantity')})")},
            label=f'thêm dòng kho {code} size {size}')

    def tra(self, code, size, kho, qty, chu_gui=''):
        code, size = code.strip().upper(), goi('chuanSize', size)
        info = self.sp(code)
        r, v, h = self.kho_row(kho, code, size)
        if r is None:
            self._kho_moi(kho, code, size, info['color'])
        ban = self.ss.worksheet('BAN').get_all_values()
        hb = [c.strip() for c in ban[0]]
        dongs = [{'code': x[hb.index('product_code')], 'size': x[hb.index('item_size')], 'kho': x[hb.index('KHO')],
                  'chu_hang': x[hb.index('chu_hang')] if 'chu_hang' in hb else ''} for x in ban[1:] if x[hb.index('product_code')].strip()]
        kq = goi('traHangChuHang', kho, code, size, qty, chu_gui, dongs)
        vals = {'Ngày chứng từ (*)': datetime.now().strftime('%d/%m/%Y'), 'Số chứng từ (*)': goi('soTraHang', datetime.now().strftime('%Y-%m-%d')),
                'product_code': code, 'product_color': info['color'], 'KHO': kho, 'item_size': int(size) if size.isdigit() else size,
                'Số lượng (*)': qty, 'ma_dong': self.ma_dong(), 'nguon': 'mac'}
        vals.update({m: TRA_MARK for m in NHAP_MARK})
        self._append('NHAP', vals, {'FSKU': lambda L, row: f"=CONCATENATE({L('KHO')}{row}; {L('product_code')}{row}; {L('item_size')}{row})"},
                     label=f"TRẢ {code} size {size} × {qty} về {kho} ({vals['Số chứng từ (*)']}, chủ {kq['chu_hang']})")
        for d in kq['doi_cot']:
            if r is None:
                self.ghi_chu.append(f"⚠ Hàng hộ {kq['chu_hang']}: dòng kho mới chưa có — cộng tay {d['delta']} vào {d['cot']} sau khi ghi.")
                continue
            cur = _money(v[r - 1][h.index(d['cot'])]) if d['cot'] in h else 0
            self._cell(KHO_TAB[d['kho']], r, d['cot'], cur + d['delta'], f"{d['cot']} {cur} → {cur + d['delta']} (trả về sổ ký gửi hộ {kq['chu_hang']})")
        return kq

    def ban(self, code, size, kho, qty, gia=0, tt='Tiền mặt'):
        code, size = code.strip().upper(), goi('chuanSize', size)
        info = self.sp(code)
        r, v, h = self.kho_row(kho, code, size)
        if r is None:
            raise RuntimeError(f'{KHO_TAB[kho]} không có {code} size {size} — không bán được')
        ky = _money(v[r - 1][h.index(KY_COL[kho])]) if KY_COL[kho] in h else 0
        tach = goi('banTachChuHang', kho, qty, ky)
        stamp = 'mac ' + datetime.now().strftime('%Y-%m-%d %H:%M')
        for ph in tach['phan']:
            self._append('BAN', {'Ngày': datetime.now().strftime('%d/%m/%Y'), 'product_code': code, 'product_color': info['color'],
                                 'Giá': gia or info['gia'], 'item_size': size, 'item_quantity': ph['qty'], 'KHO': kho, 'seller': 'mac',
                                 'ma_dong': self.ma_dong(), 'nguon': 'mac', 'chu_hang': ph['chu_hang'], 'payment_method': tt,
                                 'ky_gui_tru': stamp if ph['chu_hang'] != kho else ''},
                         label=f"BÁN {code} size {size} × {ph['qty']} ở {kho}, chủ {ph['chu_hang']}, " + f"{gia or info['gia']:,}đ".replace(',', '.'))
        for d in tach['doi_cot']:
            self._cell(KHO_TAB[d['kho']], r, d['cot'], ky + d['delta'], f"{d['cot']} {ky} → {ky + d['delta']} (bán hàng ký gửi)")
        return tach

    def ghi(self):
        for _, f in self.ops:
            f()
