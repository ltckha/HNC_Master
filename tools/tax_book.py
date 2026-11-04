"""Sổ thuế dự phòng trên Mac (luật 15, anh Kha "làm" 04/11) — ra CÙNG số với web Sổ sách › Sổ thuế (src/worker/bookkeeping.ts):
- Doanh thu từng hộ × tháng = tab BAN (Giá × SL, bỏ BU_DOI_HANG từ MOC_DOI_TRA) + cột "Thành tiền" tab BAN_DIEU_CHINH
  (bo_sung_misa: dòng bổ sung theo MISA · dieu_chinh: tiền điều chỉnh · khong_misa: phần đôi Không xuất MISA của 1 dòng BAN, số âm).
- Hộ = chủ hàng (chu_hang), trống thì theo kho ("3C" = Y3C, còn lại 15E). Tính cả dòng ngày đoán (Sheet đã có ngày). Không bỏ kênh sàn.
- File Excel S1a-HKD theo hộ / tháng: mỗi ngày × kênh 1 dòng, như nút tải S1a của web.
Đọc theo tên cột (luật 4). Không ghi Sheet.
"""
import re

from tools.cash_book import _day, _money, _qty, ho_of

MOC_DOI_TRA = '2026-11-04'
BU_MA = 'BU_DOI_HANG'
HO_KHO = {  # như web src/config/households.ts
    '15E': {'ten': 'HỘ KINH DOANH LƯU THÁI CHÍ KHA (HIỆU GIÀY HẢI NANCY 2)', 'mst': '082086007441', 'dia_chi': '15E Tăng Bạt Hổ, Phường Xuân Hương – Đà Lạt, Lâm Đồng'},
    'Y3C': {'ten': 'HỘ KINH DOANH ĐỒ DA THỦ CÔNG YẾN', 'mst': '068188011506', 'dia_chi': '3C Tăng Bạt Hổ, Phường Xuân Hương – Đà Lạt, Lâm Đồng'},
}
CH_ALL = {'cua_hang_15e': 'Tiệm 15E', 'cua_hang_3c': 'Tiệm 3C', 'cua_hang': 'Tiệm (chưa rõ)', 'web': 'Web', 'shopee': 'Shopee', 'tiktok': 'TikTok Shop',
          'lazada': 'Lazada', 'zalo': 'Zalo', 'facebook': 'Facebook', 'dien_thoai': 'Điện thoại', 'tra_hang': 'Trả hàng'}  # web allsales.ts
TT152 = '(Kèm theo Thông tư số 152/2025/TT-BTC ngày 31 tháng 12 năm 2025 của Bộ trưởng Bộ Tài chính)'


def _cols(values, need, tab):
    h = [str(c).strip() for c in values[0]]
    miss = [c for c in need if c not in h]
    if miss:
        raise RuntimeError(f'Tab {tab} thiếu cột {miss}')
    ix = {c: h.index(c) for c in h}
    return lambda r, c: r[ix[c]] if c in ix and ix[c] < len(r) else ''


def lines(ban_values, dc_values):
    """→ [{day, ho, code, qty, tien, k}] (k = kênh / 'tra_hang' / 'doi' / 'dieu_chinh') — mỗi dòng 1 khoản doanh thu."""
    g = _cols(ban_values, ['Ngày', 'product_code', 'Giá', 'item_quantity', 'KHO'], 'BAN')
    out = []
    for r in ban_values[1:]:
        code = str(g(r, 'product_code')).strip().upper()
        day = _day(g(r, 'Ngày'))
        if not code or not day:
            continue
        qty = _qty(g(r, 'item_quantity'))
        tien = 0 if code == BU_MA and day >= MOC_DOI_TRA else _money(g(r, 'Giá')) * qty
        k = 'tra_hang' if qty < 0 else 'doi' if code == BU_MA else str(g(r, 'channel')).strip()
        out.append({'day': day, 'ho': ho_of(str(g(r, 'chu_hang')).strip(), str(g(r, 'KHO')).strip()), 'code': code, 'qty': qty, 'tien': tien, 'k': k,
                    'md': str(g(r, 'ma_dong')).strip()})
    if not dc_values:
        return out
    d = _cols(dc_values, ['Ngày', 'Thành tiền', 'Kho', 'loai'], 'BAN_DIEU_CHINH')
    by_md = {x['md']: x for x in out if x['md']}
    for r in dc_values[1:]:
        day = _day(d(r, 'Ngày'))
        if not day:
            continue
        loai, tien, sl = str(d(r, 'loai')).strip(), _money(d(r, 'Thành tiền')), _qty(d(r, 'SL'))
        if loai == 'khong_misa':  # bớt số đôi Không xuất MISA khỏi dòng BAN gốc (ma_dong "<gốc>#KM"), như web qty − khong_misa
            goc = by_md.get(str(d(r, 'ma_dong')).strip().split('#KM')[0])
            if goc:
                goc['qty'] += sl
                goc['tien'] += tien
                continue
        ho = ho_of(str(d(r, 'chu_hang')).strip(), str(d(r, 'Kho')).strip())
        k = 'dieu_chinh' if loai == 'dieu_chinh' else 'tra_hang' if sl < 0 else str(d(r, 'Kênh')).strip()
        out.append({'day': day, 'ho': ho, 'code': str(d(r, 'Mã')).strip().upper(), 'qty': sl, 'tien': tien, 'k': k, 'md': ''})
    return out


def by_month(ds, den=None):
    """→ {ho: {YYYY-MM: tiền}} (tới ngày den nếu có)."""
    t = {'15E': {}, 'Y3C': {}}
    for x in ds:
        if den and x['day'] > den:
            continue
        m = x['day'][:7]
        t[x['ho']][m] = t[x['ho']].get(m, 0) + x['tien']
    return t


def _dien(k, sl):
    sl = int(sl) if float(sl).is_integer() else sl
    if k == 'dieu_chinh':
        return 'Điều chỉnh doanh thu theo MISA'
    if k == 'tra_hang':
        return f'Khách trả hàng ({sl} món)'
    if k == 'doi':
        return 'Tiền chênh đổi hàng'
    qua = f" qua {CH_ALL[k]}" if k and k in CH_ALL and not k.startswith('cua_hang') else ''
    return f'Bán hàng hoá{qua} ({sl} món)'


def s1a_rows(ds, ho, thang):
    """Sổ S1a-HKD 1 hộ 1 tháng (như web s1a): mỗi ngày × kênh 1 dòng. Dòng đã trừ hết đôi Không xuất MISA (SL 0, không điều chỉnh) bỏ."""
    g = {}
    for x in ds:
        if x['ho'] != ho or x['day'][:7] != thang or (x['qty'] == 0 and x['k'] != 'dieu_chinh'):
            continue
        o = g.setdefault((x['day'], x['k']), {'tien': 0, 'sl': 0})
        o['tien'] += x['tien']
        o['sl'] += abs(x['qty'])
    rows = [['/'.join(reversed(d.split('-'))), _dien(k, o['sl']), round(o['tien'])] for (d, k), o in sorted(g.items())]
    h, ky = HO_KHO[ho], f"Tháng {thang[5:]}/{thang[:4]}"
    return [[f"HỘ, CÁ NHÂN KINH DOANH: {h['ten']}", '', 'Mẫu số S1a-HKD'], [f"Địa chỉ: {h['dia_chi']}", '', TT152], [f"Mã số thuế: {h['mst']}"], [],
            ['', 'SỔ DOANH THU BÁN HÀNG HÓA, DỊCH VỤ'], ['', f"Địa điểm kinh doanh: {h['dia_chi']}"], ['', f'Kỳ kê khai: {ky}'], ['', '', 'Đơn vị tính: đồng'], [],
            ['Ngày tháng', 'Diễn giải', 'Số tiền'], ['A', 'B', '1'], *rows, ['Tổng cộng', '', sum(r[2] for r in rows)], [],
            ['', '', 'Ngày ..... tháng ..... năm ......'], ['', '', 'NGƯỜI ĐẠI DIỆN HỘ KINH DOANH/ CÁ NHÂN KINH DOANH'], ['', '', '(Ký, ghi rõ họ tên, đóng dấu (nếu có))']]


def file_name(ho, thang):
    return f"S1a-HKD_{'3C' if ho == 'Y3C' else '15E'}_{thang}.xlsx"


def write_xlsx(path, rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = 'S1a-HKD'
    bold = {(0, 0), (0, 2), (4, 1)}
    for i, r in enumerate(rows, 1):
        for j, v in enumerate(r, 1):
            if v not in (None, ''):
                c = ws.cell(i, j, v)
                if (i - 1, j - 1) in bold or (r and r[0] in ('Ngày tháng', 'Tổng cộng')) or str(v).startswith('NGƯỜI ĐẠI DIỆN'):
                    c.font = Font(bold=True)
                if isinstance(v, (int, float)):
                    c.number_format = '#,##0'
    for col, w in zip('ABC', (14, 60, 18)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return path


def valid_month(m):
    return bool(re.match(r'^\d{4}-\d{2}$', m or ''))
