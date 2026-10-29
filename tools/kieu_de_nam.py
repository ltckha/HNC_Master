"""Giày nam: kieu_de chỉ còn "đế bằng" hoặc "có gót" (+ số cm ở cao_got_cm) — anh Kha 29/10 (cả giày nam tăng chiều cao; tang_cao_cm giữ).
CHẠY THỬ (chỉ đọc Sheet): mã gioi_tinh = nam có kieu_de khác đế bằng / có gót / trống → docs/sanpham_chuan/kieu_de_nam.csv
(ma, nganh, kieu_de_hien, cao_got_cm, de_xuat: "có gót" khi cao_got_cm > 0, còn lại trống = Phân tích xem).
Gồm cả mã kieu_de TRỐNG mà cao_got_cm > 0 (điền được "có gót").

  venv/bin/python tools/kieu_de_nam.py [--sheet ID]
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


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
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
