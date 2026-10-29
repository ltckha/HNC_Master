"""Bộ chuẩn SANPHAM GĐ C bước 1 (anh Kha "Làm" 29/10): điền ô TRỐNG của cột mới bằng giá trị của mã CÙNG MÃ CHA
(parent_product_code; trống thì mã bỏ ký tự màu cuối) — chỉ cột không phụ thuộc màu. Các mã cùng cha ghi khác nhau → mo_ho, không điền.
CHẠY THỬ (chỉ đọc Sheet) → docs/sanpham_chuan/gd_c1_dien.csv (ma, cot, gia_tri, lay_tu, trang_thai) + gd_c1_dem.csv.

  venv/bin/python tools/dien_theo_cha.py [--sheet ID]          # chạy thử
  venv/bin/python tools/dien_theo_cha.py --ghi [--sheet ID]    # GHI (Phân tích soát + anh cho ghi 29/10)
"""
import csv
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID  # noqa: E402

COT_CHA = ['kieu_dong', 'kieu_quai', 'dang_mui', 'kieu_de', 'cao_got_cm', 'tang_cao_cm', 'chat_lieu', 'chat_lieu_de', 'lot_trong', 'lot_de',
           'be_mat', 'co_giay', 'dip', 'gioi_tinh']  # không có form và cột phụ thuộc màu (Phân tích 29/10)


def cha_cua(r, head):
    ma = r[head.index('product_code')].strip().upper()
    p = r[head.index('parent_product_code')].strip().upper() if 'parent_product_code' in head else ''
    return p or ma[:-1]


def de_xuat(sp, head):
    """→ [(ma, cot, gia_tri | 'a | b', lay_tu [mã], trang_thai dien | mo_ho)]"""
    ic = head.index('product_code')
    dong = [r + [''] * (len(head) - len(r)) for r in sp[2:] if r[ic].strip()]
    nhom = defaultdict(list)
    for r in dong:
        nhom[cha_cua(r, head)].append(r)
    out = []
    for r in dong:
        ma = r[ic].strip().upper()
        anh_em = [x for x in nhom[cha_cua(r, head)] if x[ic].strip().upper() != ma]
        for c in COT_CHA:
            j = head.index(c)
            if r[j].strip() or not anh_em:
                continue
            co = defaultdict(list)
            for x in anh_em:
                if x[j].strip():
                    co[x[j].strip()].append(x[ic].strip().upper())
            if len(co) == 1:
                (v, tu), = co.items()
                out.append((ma, c, v, tu, 'dien'))
            elif len(co) > 1:
                out.append((ma, c, ' | '.join(sorted(co)), sorted(m for t in co.values() for m in t), 'mo_ho'))
    return out


def ghi(sid):
    """GHI THẬT các ô 'dien' (đọc lại Sheet ngay trước khi ghi, chỉ ô còn trống), 1 lần batch_update, rồi đọc lại đếm."""
    import gspread
    ws = _mo(sid, ghi=True)
    sp = ws.get_all_values()
    head = [h.strip() for h in sp[1]]
    ic = head.index('product_code')
    hang = {r[ic].strip().upper(): i + 1 for i, r in enumerate(sp) if i >= 2 and r[ic].strip()}
    ds = [(ma, c, v) for ma, c, v, _, tt in de_xuat(sp, head) if tt == 'dien']
    up = [{'range': gspread.utils.rowcol_to_a1(hang[ma], head.index(c) + 1), 'values': [[v]]} for ma, c, v in ds]
    if up:
        ws.batch_update(up, value_input_option='USER_ENTERED')  # số (cao_got_cm) vào đúng kiểu số
    lai = ws.get_all_values()
    khop = sum(1 for ma, c, v in ds if str(lai[hang[ma] - 1][head.index(c)]).strip() == str(v))
    print(f'✅ Sheet {sid[:6]}…: ghi {len(up)} ô, đọc lại khớp {khop}')
    return 0


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    if '--ghi' in sys.argv:
        return ghi(sid)
    ws = _mo(sid)
    sp = ws.get_all_values()
    head = [h.strip() for h in sp[1]]
    thieu = [c for c in COT_CHA + ['product_code'] if c not in head]
    if thieu:
        raise RuntimeError(f'SANPHAM thiếu cột {thieu}')
    ds = de_xuat(sp, head)
    ic = head.index('product_code')
    dong = [r for r in sp[2:] if r[ic].strip()]
    dem = {c: Counter() for c in COT_CHA}
    for _, c, _, _, tt in ds:
        dem[c][tt] += 1
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'gd_c1_dien.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ma', 'cot', 'gia_tri', 'lay_tu', 'trang_thai'])
        for ma, c, v, tu, tt in ds:
            w.writerow([ma, c, v, ' '.join(tu), tt])
    with open(os.path.join(OUT, 'gd_c1_dem.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cot', 'trong_truoc', 'dien', 'mo_ho', 'con_trong'])
        print(f'Sheet {sid[:6]}…: {len(dong)} mã · cột: trống trước / điền / mơ hồ / còn trống')
        for c in COT_CHA:
            j = head.index(c)
            tr = sum(1 for r in dong if not (r[j].strip() if j < len(r) else ''))
            w.writerow([c, tr, dem[c]['dien'], dem[c]['mo_ho'], tr - dem[c]['dien']])
            print(f"  {c}: {tr} / {dem[c]['dien']} / {dem[c]['mo_ho']} / {tr - dem[c]['dien']}")
    print(f'→ {os.path.relpath(OUT, ROOT)}/ gd_c1_dien.csv, gd_c1_dem.csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
