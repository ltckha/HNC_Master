"""Diễn tập P1 (20/10): ghi NHẬP KHO / CHUYỂN KHO vào Sheet BẢN THỬ, cùng luật bot (appendNhap_ / doTransfer_ + LuatKho).
CHỈ chạy trên bản thử HNC_Master_BAN_THU. ma_dong = MAC-<lần chạy>#n, nguon = mac.
  Nhập (như phiếu NCC: số NK theo LuatKho.soNhapKho, đơn giá phiếu = giá nhập SANPHAM):
    venv/bin/python tools/dien_tap_kho.py nhap 2DKN 42 15E [--ghi]
  Chuyển kho (XUAT ở kho đi + NHAP ở kho đến, ký gửi theo LuatKho.chuyenKhoKyGui):
    venv/bin/python tools/dien_tap_kho.py chuyen 8922V 41 Y3C 15E [--ghi]
Không có --ghi = chạy thử, chỉ in việc sẽ ghi.
"""
import os
import sys
from datetime import datetime

TEST_ID = '1QwH7Y1A45Pb9S0JbfDSkrP-VeUmD_cA6FsKdI4Gmxcw'
os.environ['HNC_SHEET_ID'] = TEST_ID
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import main  # noqa: E402
from tools.luat_kho_node import goi  # noqa: E402

KHO_TAB = {'15E': 'KHO15E', 'Y3C': 'KHOY3C'}
KY_COL = {'15E': 'cua_Y3C', 'Y3C': 'cua_15E'}  # kho đang ở → cột hàng của hộ kia


def money(v):
    d = ''.join(ch for ch in str(v or '') if ch.isdigit())
    return int(d) if d else 0


class Ghi:
    """Gom các dòng / ô cần ghi; chạy thử thì chỉ in."""
    def __init__(self, loader, ghi):
        self.L, self.ghi, self.n, self.sau = loader, ghi, 0, []
        self.today = datetime.now().strftime('%d/%m/%Y')

    def ma_dong(self):
        self.n += 1
        return f"MAC-{main.MAC_RUN_ID}#{self.n}"

    def append(self, tab, vals, formulas=None):
        ws = self.L.spreadsheet.worksheet(tab)
        v = ws.get_all_values()
        head = [c.strip() for c in v[0]]
        ic = head.index('product_code')
        row = max(i + 1 for i, r in enumerate(v) if i == 0 or (len(r) > ic and r[ic].strip())) + 1
        if tab == 'NHAP':  # hàng 2 là hàng kỹ thuật → dòng mới luôn sau dòng cuối có mã
            row = max(row, 3)
        out = [''] * len(head)
        for k, val in vals.items():
            if k not in head:
                raise RuntimeError(f'Tab {tab} thiếu cột {k}')
            out[head.index(k)] = val
        L = lambda n: main.gspread.utils.rowcol_to_a1(1, head.index(n) + 1).rstrip('1')
        if tab.startswith('KHO'):
            row = max(i + 1 for i, r in enumerate(v) if i == 0 or (len(r) > ic and r[ic].strip())) + 1
        for k, f in (formulas or {}).items():
            out[head.index(k)] = f(L, row)
        print(f"  {tab} dòng {row}: " + ' · '.join(f'{k}={out[head.index(k)]}' for k in vals))
        if self.ghi and not self.L.insert_rows_with_exact_range(tab, [out], row):
            raise RuntimeError(f'Không ghi được {tab}')

    def cell(self, tab, code, size, cot, delta):
        ws = self.L.spreadsheet.worksheet(tab)
        v = ws.get_all_values()
        head = [c.strip() for c in v[0]]
        r = next((i + 1 for i, x in enumerate(v) if x[head.index('product_code')].strip().upper() == code and str(x[head.index('item_size')]).strip() == size), None)
        if r is None:
            if not self.ghi:
                print(f"  {tab}: (dòng {code} size {size} sẽ được thêm ở bước nhập) {cot} 0 → {delta}")
                return
            raise RuntimeError(f'{tab} không có dòng {code} size {size}')
        cur = money(v[r - 1][head.index(cot)])
        print(f"  {tab} dòng {r}: {cot} {cur} → {cur + delta}")
        if self.ghi:
            ws.update_cell(r, head.index(cot) + 1, cur + delta)


def sp_info(loader, code):
    sp = loader.spreadsheet.worksheet('SANPHAM').get_all_values()
    h = [c.strip() for c in sp[1]]
    r = next((x for x in sp[2:] if x[h.index('product_code')].strip().upper() == code), None)
    if not r:
        raise RuntimeError(f'SANPHAM không có mã {code}')
    return {'color': r[h.index('product_color')].strip(), 'buy': money(r[h.index('purchase_price')])}


def kho_row(loader, kho, code, size):
    v = loader.spreadsheet.worksheet(KHO_TAB[kho]).get_all_values()
    h = [c.strip() for c in v[0]]
    return next((x for x in v[1:] if x[h.index('product_code')].strip().upper() == code and x[h.index('item_size')].strip() == size), None), h


def tao_dong_kho(g, kho, code, size, color):
    """Kho chưa có dòng mã + size → thêm dòng KHO có công thức (như bot appendKhoRow_ / hợp đồng cong_thuc_mau)."""
    tab = KHO_TAB[kho]
    hn = [c.strip() for c in g.L.spreadsheet.worksheet('NHAP').row_values(1)]
    hx = [c.strip() for c in g.L.spreadsheet.worksheet('XUAT').row_values(1)]
    hb = [c.strip() for c in g.L.spreadsheet.worksheet('BAN').row_values(1)]
    col = lambda h, n: main.gspread.utils.rowcol_to_a1(1, h.index(n) + 1).rstrip('1')
    g.append(tab, {'product_code': code, 'product_color': color, 'item_size': int(size) if size.isdigit() else size, 'opening_quantity': 0}, {
        kho: lambda L, r: f"=CONCATENATE(${L(kho)}$1;{L('product_code')}{r};{L('item_size')}{r})",
        'current_quantity': lambda L, r: (f"={L('opening_quantity')}{r} + SUMIF(NHAP!{col(hn, 'FSKU')}:{col(hn, 'FSKU')}; {L(kho)}{r}; NHAP!{col(hn, 'Số lượng (*)')}:{col(hn, 'Số lượng (*)')})"
                                          f" - SUMIF(XUAT!{col(hx, 'FSKU')}:{col(hx, 'FSKU')}; {L(kho)}{r}; XUAT!{col(hx, 'item_quantity')}:{col(hx, 'item_quantity')})"
                                          f" - SUMIF(BAN!{col(hb, 'FSKU')}:{col(hb, 'FSKU')}; {L(kho)}{r}; BAN!{col(hb, 'item_quantity')}:{col(hb, 'item_quantity')})")})


def nhap(g, code, size, kho, so='', marks=None):
    info = sp_info(g.L, code)
    if kho_row(g.L, kho, code, size)[0] is None:
        tao_dong_kho(g, kho, code, size, info['color'])
    nh = g.L.spreadsheet.worksheet('NHAP').get_all_values()
    h = [c.strip() for c in nh[0]]
    if not so:
        dong = [{'so': r[h.index('Số chứng từ (*)')], 'kho': r[h.index('KHO')], 'ngay_key': '', 'ncc': ''} for r in nh[2:]]
        cuoi = {r[0]: r[1] for r in g.L.spreadsheet.worksheet('META').get_all_values()[1:] if r}.get('nk_cuoi_' + kho, '')
        so = goi('soNhapKho', dong, [kho], '', datetime.now().strftime('%Y-%m-%d'), None, {kho: cuoi})[kho]  # không lùi (bộ đếm META chung với web / bot)
        if g.ghi:
            g.sau.append(lambda: main.set_meta(g.L, {'nk_cuoi_' + kho: so}))
    vals = {'Ngày chứng từ (*)': g.today, 'Số chứng từ (*)': so, 'product_code': code, 'product_color': info['color'], 'KHO': kho,
            'item_size': int(size) if size.isdigit() else size, 'Số lượng (*)': 1, 'ma_dong': g.ma_dong(), 'nguon': 'mac'}
    gia = goi('donGiaPhieuMoi', '', info['buy'])
    if gia:
        vals['don_gia_phieu'] = gia
    vals.update(marks or {})
    g.append('NHAP', vals, {'FSKU': lambda L, r: f"=CONCATENATE({L('KHO')}{r}; {L('product_code')}{r}; {L('item_size')}{r})"})


def chuyen(g, code, size, tu, den):
    info = sp_info(g.L, code)
    src, hs = kho_row(g.L, tu, code, size)
    if src is None:
        raise RuntimeError(f'{KHO_TAB[tu]} không có dòng {code} size {size} — không chuyển từ {tu} được')
    g.append('XUAT', {'Ngày': g.today, 'product_code': code, 'product_color': info['color'], 'KHO': tu,
                      'item_size': int(size) if size.isdigit() else size, 'item_quantity': 1, 'ma_dong': g.ma_dong(), 'nguon': 'mac'})
    # Phần nhập ở kho đến: như bot (nhập không số chứng từ → đánh dấu Zalo_Update để HNC bỏ qua khi xuất MISA / tem)
    nhap(g, code, size, den, so='', marks={'Số chứng từ (*)': '', 'web_stock': 'Zalo_Update', 'web_label': 'Zalo_Update', 'misa_stock': 'Zalo_Update'})
    ky = money(src[hs.index(KY_COL[tu])]) if KY_COL[tu] in hs else 0
    kq = goi('chuyenKhoKyGui', tu, den, 1, ky)
    for n in kq['ghi_chu']:
        print(f"  📒 {n['loai']}: {n['qty']} đôi của hộ {n['chu_hang']}")
    for d in kq['doi_cot']:
        g.cell(KHO_TAB[d['kho']], code, size, d['cot'], d['delta'])


def run():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    ghi = '--ghi' in sys.argv
    assert main.SPREADSHEET_ID == TEST_ID != main.SPREADSHEET_ID_THAT, 'chỉ chạy trên Sheet bản thử'
    L = main.EngineDataLoader()
    print(f"🧪 Sheet bản thử · sổ bán {L.che_do()} · sổ kho {L.che_do_kho()} · cho_chep = {L.cho_chep()} · {'GHI' if ghi else 'chạy thử'}")
    # K10 (dự phòng giữa chừng): chỉ ghi khi sổ kho đang Dự phòng và web đã chép xong (như bot / main.py)
    if ghi and L.che_do_kho() == 'web':
        print("⛔ Sổ kho đang ở Web — đổi về Dự phòng trước (menu [7] → 3 với HNC_SHEET_ID = bản thử, hoặc nút trên web).")
        return 1
    if ghi and L.cho_chep() > 0:
        print(f"⏳ Còn {L.cho_chep()} dòng web đang chép sang Sheet — chờ về 0 rồi chạy lại.")
        return 1
    g = Ghi(L, ghi)
    try:
        if args[:1] == ['nhap'] and len(args) == 4:
            nhap(g, args[1].upper(), args[2], args[3].upper())
        elif args[:1] == ['chuyen'] and len(args) == 5:
            chuyen(g, args[1].upper(), args[2], args[3].upper(), args[4].upper())
        else:
            print(__doc__)
            return 1
    except RuntimeError as e:
        print(f"⛔ {e}")
        return 1
    for f in g.sau:
        f()
    print(f"✅ Đã ghi lúc {datetime.now():%H:%M:%S}" if ghi else "Chạy thử — chưa ghi. Thêm --ghi để ghi vào bản thử.")
    return 0


if __name__ == '__main__':
    sys.exit(run())
