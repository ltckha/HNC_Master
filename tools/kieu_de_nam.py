"""Giày nam: kieu_de chỉ còn "đế bằng" hoặc "có gót" (+ số cm ở cao_got_cm) — anh Kha 29/10 (cả giày nam tăng chiều cao; tang_cao_cm giữ).
CHẠY THỬ (chỉ đọc Sheet): mã gioi_tinh = nam có kieu_de khác đế bằng / có gót / trống → docs/sanpham_chuan/kieu_de_nam.csv
(ma, nganh, kieu_de_hien, cao_got_cm, de_xuat: "có gót" khi cao_got_cm > 0, còn lại trống = Phân tích xem).
Gồm cả mã kieu_de TRỐNG mà cao_got_cm > 0 (điền được "có gót").

  venv/bin/python tools/kieu_de_nam.py [--sheet ID]         # chạy thử
  venv/bin/python tools/kieu_de_nam.py --ghi [--sheet ID]   # GHI TU_DIEN thêm giá trị + 284 ô "có gót" (anh Kha 29/10)
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID  # noqa: E402

GIU = ('', 'đế bằng', 'có gót')


def so(v):
    try:
        return float(str(v).replace(',', '.'))
    except ValueError:
        return 0.0


# Thêm giá trị TU_DIEN (anh Kha 29/10, Phân tích soát): (đầu danh sách theo thứ tự hay dùng, thêm cuối)
TU_DIEN_THEM = {
    'kieu_de': ([], ['có gót']),
    'lot_de': (['da bò', 'microfiber', 'da heo', 'da cừu', 'mút'],
               ['da dê', 'da lộn', 'vải', 'nỉ', 'mút PU', 'EVA', 'cao su non (latex)', 'da heo cán mút', 'bần (cork)']),
    'lot_trong': ([], ['da dê', 'da lộn', 'vải', 'nỉ']),
}


def ghi(sid):
    """GHI THẬT: thêm giá trị TU_DIEN (TU_DIEN_THEM) + kieu_de = "có gót" cho mã nam đề xuất. Đọc lại kiểm."""
    import gspread
    from tools.tach_cot_sanpham import _mo as mo
    ws = mo(sid, ghi=True)
    td = ws.spreadsheet.worksheet('TU_DIEN')
    luoi = td.get_all_values()
    h = [x.strip() for x in luoi[0]]
    up = []
    for cot, (dau, them) in TU_DIEN_THEM.items():
        j = h.index(cot)
        cu = [r[j].strip() for r in luoi[2:] if j < len(r) and r[j].strip()]
        moi = [v for v in dau if v in cu] + [v for v in cu if v not in dau] + [v for v in them if v not in cu]
        if len(moi) + 2 > td.row_count:
            td.add_rows(len(moi) + 2 - td.row_count)
        L = gspread.utils.rowcol_to_a1(1, j + 1).rstrip('1')
        up.append({'range': f'{L}3:{L}{2 + len(moi)}', 'values': [[v] for v in moi]})
    td.batch_update(up, value_input_option='RAW')
    sp = ws.get_all_values()
    hs = [x.strip() for x in sp[1]]
    c = {k: hs.index(k) for k in ('product_code', 'gioi_tinh', 'kieu_de', 'cao_got_cm')}
    o = []
    for i, r in enumerate(sp[2:], start=3):
        if r[c['product_code']].strip() and r[c['gioi_tinh']].strip() == 'nam' and not r[c['kieu_de']].strip() and so(r[c['cao_got_cm']]) > 0:
            o.append({'range': gspread.utils.rowcol_to_a1(i, c['kieu_de'] + 1), 'values': [['có gót']]})
    if o:
        ws.batch_update(o, value_input_option='RAW')
    lai = td.get_all_values()
    for cot in TU_DIEN_THEM:
        j = h.index(cot)
        print(f"  TU_DIEN {cot}: {', '.join(r[j] for r in lai[2:] if j < len(r) and r[j].strip())}")
    sp2 = ws.get_all_values()
    n = sum(1 for r in sp2[2:] if r[c['gioi_tinh']].strip() == 'nam' and r[c['kieu_de']].strip() == 'có gót')
    print(f'✅ Sheet {sid[:6]}…: ghi {len(o)} ô kieu_de "có gót" · đọc lại mã nam "có gót": {n}')
    return 0


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    if '--ghi' in sys.argv:
        return ghi(sid)
    sp = _mo(sid).get_all_values()
    h = [x.strip() for x in sp[1]]
    c = {k: h.index(k) for k in ('product_code', 'Tên Ngành Hàng', 'gioi_tinh', 'kieu_de', 'cao_got_cm')}
    ds = []
    for r in sp[2:]:
        if not r[c['product_code']].strip() or r[c['gioi_tinh']].strip() != 'nam':
            continue
        kd = r[c['kieu_de']].strip()
        cm = r[c['cao_got_cm']].strip()
        if kd in GIU[1:] or (not kd and not so(cm) > 0):  # trống + có số cm gót → cũng đề xuất "có gót"
            continue
        ds.append([r[c['product_code']].strip(), r[c['Tên Ngành Hàng']].strip(), kd, cm, 'có gót' if so(cm) > 0 else ''])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'kieu_de_nam.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ma', 'nganh', 'kieu_de_hien', 'cao_got_cm', 'de_xuat'])
        w.writerows(ds)
    co = sum(1 for x in ds if x[4])
    print(f'Sheet {sid[:6]}…: {len(ds)} mã nam (kieu_de khác đế bằng / có gót, hoặc trống mà có cm gót) · đề xuất "có gót" {co} · để Phân tích xem {len(ds) - co}')
    print(f'→ {os.path.relpath(OUT, ROOT)}/kieu_de_nam.csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
