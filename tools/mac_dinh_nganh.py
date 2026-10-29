"""Mặc định thuộc tính theo ngành (anh Kha 29/10) — bảng chung shared/hop_dong_du_lieu.json khoá mac_dinh_theo_nganh (Mac + web, luật 15).
Chỉ điền ô TRỐNG. Chạy thử: đếm ô theo ngành + liệt kê mã đang có giá trị KHÁC luật (để anh xem, không sửa) → docs/sanpham_chuan/mac_dinh_nganh.csv.

  venv/bin/python tools/mac_dinh_nganh.py [--ghi] [--sheet ID]
"""
import csv
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
BANG = json.load(open(os.path.join(ROOT, 'shared', 'hop_dong_du_lieu.json'), encoding='utf-8'))['mac_dinh_theo_nganh']


def _n(s):
    return ' '.join(str(s or '').split()).lower()


def mac_dinh(nganh):
    """Ngành → {cột: giá trị mặc định} theo bảng chung."""
    ng = _n(nganh)
    gd = bool(re.search(BANG['giay_dep'], ng))
    out = {}
    for l in BANG['luat']:
        if l['cot'] in out:
            continue
        if ('nganh' in l and ng in [_n(x) for x in l['nganh']]) or ('nganh_chua' in l and gd and any(x in ng for x in l['nganh_chua'])) \
                or (l.get('giay_dep') and gd):
            out[l['cot']] = l['gia_tri']
    return out


def main():
    import gspread
    from tools.tach_cot_sanpham import _mo
    from tools.tu_dien_sanpham import OUT, SHEET_ID
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ghi = '--ghi' in sys.argv
    ws = _mo(sid, ghi=ghi)
    sp = ws.get_all_values()
    h = [x.strip() for x in sp[1]]
    ic, ing = h.index('product_code'), h.index('Tên Ngành Hàng')
    up, dem, khac = [], Counter(), []
    for i, r in enumerate(sp[2:], start=3):
        if not r[ic].strip():
            continue
        for cot, v in mac_dinh(r[ing]).items():
            cur = r[h.index(cot)].strip()
            if not cur:
                up.append({'range': gspread.utils.rowcol_to_a1(i, h.index(cot) + 1), 'values': [[v]]})
                dem[(cot, r[ing].strip())] += 1
            elif cur != v:
                khac.append([r[ic].strip(), r[ing].strip(), cot, cur, v])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'mac_dinh_nganh.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['loai', 'ma / nganh', 'nganh', 'cot', 'hien_tai / so_o', 'luat'])
        for (cot, ng), n in sorted(dem.items()):
            w.writerow(['dien', ng, ng, cot, n, ''])
        for ma, ng, cot, cur, v in khac:
            w.writerow(['khac_luat', ma, ng, cot, cur, v])
    print(f'Sheet {sid[:6]}…: điền {len(up)} ô trống · {len(khac)} ô đang KHÁC luật (không sửa)')
    for cot in dict.fromkeys(l['cot'] for l in BANG['luat']):
        print(f'  {cot}: ' + ', '.join(f'{ng} {n}' for (c, ng), n in sorted(dem.items(), key=lambda x: -x[1]) if c == cot))
    print('  khác luật: ' + ', '.join(f'{ma} {cot}={cur}' for ma, _, cot, cur, _ in khac[:30]) + (' …' if len(khac) > 30 else ''))
    if ghi and up:
        for k in range(0, len(up), 500):
            ws.batch_update(up[k:k + 500], value_input_option='RAW')
        print(f'✅ Đã ghi {len(up)} ô')
    return 0


if __name__ == '__main__':
    sys.exit(main())
