"""Ô trống ở cột mới (bộ chuẩn SANPHAM) — gom nhóm để anh Kha TỰ CHỌN theo nhóm (anh Kha 29/10: không dùng máy đoán).
CHẠY THỬ (chỉ đọc Sheet). Chỉ mã giày / dép CÒN HÀNG (current_quantity > 0 ở KHO15E hoặc KHOY3C, theo Sheet), gom theo ngành + NCC + mẫu cha;
nhóm < 3 mã gộp vào nhóm ngành + NCC. Cột chỉ áp cho 1 loại thì bỏ loại khác (ADP). Gợi ý = giá trị các mã cùng ngành + NCC đã có ở cột đó.
→ docs/sanpham_chuan/nhom_trong.csv (cot, nhom, nganh, ncc (nội bộ), so_ma, so_mau_cha, ma_vi_du, goi_y) + bảng đếm theo cột.

  venv/bin/python tools/nhom_trong.py [--sheet ID]
"""
import csv
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID  # noqa: E402

COT = ['kieu_dong', 'kieu_quai', 'dang_mui', 'kieu_de', 'cao_got_cm', 'tang_cao_cm', 'chat_lieu', 'chat_lieu_de', 'lot_trong', 'lot_de',
       'be_mat', 'co_giay', 'kieu_giay_tay', 'do_om', 'chon_size']
GIAY = re.compile(r'giày|dép|sandal|sapo|bốt', re.I)  # ví / túi / thắt lưng / phụ kiện: không có thuộc tính giày
ADP = {  # cột → điều kiện áp (ngành, kieu_de)
    'kieu_quai': lambda ng, kd: bool(re.search(r'dép|sandal', ng, re.I)),
    'kieu_giay_tay': lambda ng, kd: bool(re.search(r'giày tây|giày mọi nam|sapo|bốt nam', ng, re.I)),
    'cao_got_cm': lambda ng, kd: (bool(kd) and kd != 'đế bằng') or 'cao gót' in ng.lower(),
    'tang_cao_cm': lambda ng, kd: 'tăng chiều cao' in ng.lower(),
}
NHO = 3


def ton(ss):
    t = Counter()
    for tab in ('KHO15E', 'KHOY3C'):
        v = ss.worksheet(tab).get_all_values()
        h = [x.strip() for x in v[0]]
        ic, iq = h.index('product_code'), h.index('current_quantity')
        for r in v[1:]:
            try:
                t[r[ic].strip().upper()] += float(str(r[iq]).replace(',', '.') or 0)
            except ValueError:
                pass
    return t


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ws = _mo(sid)
    sp = ws.get_all_values()
    h = [x.strip() for x in sp[1]]
    g = lambda r, c: r[h.index(c)].strip() if h.index(c) < len(r) else ''  # noqa: E731
    tn = ton(ws.spreadsheet)
    dong = [r for r in sp[2:] if g(r, 'product_code')]
    con = [r for r in dong if tn[g(r, 'product_code').upper()] > 0 and GIAY.search(g(r, 'Tên Ngành Hàng'))]
    cha = lambda r: g(r, 'parent_product_code') or g(r, 'product_code')[:-1]  # noqa: E731
    out, dem = [], {}
    for c in COT:
        goi_y = defaultdict(Counter)
        for r in dong:
            if g(r, c):
                for v in [x.strip() for x in g(r, c).split(',') if x.strip()]:
                    goi_y[(g(r, 'Tên Ngành Hàng'), g(r, 'supplier'))][v] += 1
        trong = [r for r in con if not g(r, c) and ADP.get(c, lambda ng, kd: True)(g(r, 'Tên Ngành Hàng'), g(r, 'kieu_de'))]
        to = defaultdict(list)
        for r in trong:
            to[(g(r, 'Tên Ngành Hàng'), g(r, 'supplier'), cha(r))].append(r)
        nhom = defaultdict(list)
        for (ng, ncc, p), rs in to.items():
            nhom[(ng, ncc, p if len(rs) >= NHO else '*')].extend(rs)
        ds = sorted(nhom.items(), key=lambda x: -len(x[1]))
        for i, ((ng, ncc, p), rs) in enumerate(ds, start=1):
            vd, da = [], set()
            for r in rs:
                if cha(r) not in da:
                    da.add(cha(r))
                    vd.append(g(r, 'product_code'))
                if len(vd) == 3:
                    break
            out.append([c, i, ng, ncc or '(trống)', len(rs), len({cha(r) for r in rs}), ' '.join(vd),
                        '; '.join(f'{v}: {n}' for v, n in goi_y[(ng, ncc)].most_common(4))])
        dem[c] = (len(ds), len(trong))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'nhom_trong.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cot', 'nhom', 'nganh', 'ncc', 'so_ma', 'so_mau_cha', 'ma_vi_du', 'goi_y (cùng ngành + NCC: số mã)'])
        w.writerows(out)
    print(f'Sheet {sid[:6]}…: {len(con)} mã giày / dép còn hàng (trên {len(dong)} mã) · cột: số nhóm / số mã trống')
    for c in COT:
        print(f'  {c}: {dem[c][0]} / {dem[c][1]}')
    print(f'→ {os.path.relpath(OUT, ROOT)}/nhom_trong.csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
