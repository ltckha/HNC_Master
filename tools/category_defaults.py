"""Mặc định thuộc tính theo ngành (anh Kha 29/10) — bảng chung shared/data_contract.json khoá mac_dinh_theo_nganh (Mac + web, luật 15).
Chỉ điền ô TRỐNG. Chạy thử: đếm ô theo ngành + liệt kê mã đang có giá trị KHÁC luật (để anh xem, không sửa) → docs/product_standard/category_defaults.csv.

  venv/bin/python tools/category_defaults.py [--ghi] [--sheet ID]
"""
import csv
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
BANG = json.load(open(os.path.join(ROOT, 'shared', 'data_contract.json'), encoding='utf-8'))['mac_dinh_theo_nganh']


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


GIAY_DEP_DVT = re.compile(r'giày|dép|sandal|bốt|sapo|guốc')


def dvt_da_so(cap):
    """[(ngành, ĐVT), …] của SANPHAM → {ngành chuẩn hoá: ĐVT chiếm đa số} (05/11, như web)."""
    dem = {}
    for nganh, dvt in cap:
        ng, d = _n(nganh), str(dvt or '').strip()
        if ng and d:
            dem.setdefault(ng, Counter())[d] += 1
    return {ng: c.most_common(1)[0][0] for ng, c in dem.items()}


def don_vi_tinh(nganh, ghi_ro='', da_so=None):
    """ĐVT mã mới: ghi rõ thì giữ → ĐVT đa số các mã cùng ngành → ngành giày / dép / sandal / bốt / sapo / guốc "Đôi", còn lại "Cái"."""
    if str(ghi_ro or '').strip():
        return str(ghi_ro).strip()
    ng = _n(nganh)
    return (da_so or {}).get(ng) or ('Đôi' if GIAY_DEP_DVT.search(ng) else 'Cái')


def main():
    import gspread
    from tools.split_product_columns import _mo
    from tools.product_dictionary import OUT, SHEET_ID
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
    with open(os.path.join(OUT, 'category_defaults.csv'), 'w', encoding='utf-8-sig', newline='') as f:
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
