"""Bộ chuẩn SANPHAM GĐ B — CHẠY THỬ (chỉ đọc Sheet, chưa ghi): tách cột cũ sang 15 cột mới theo bảng GOP / SO_TU
(tools/tu_dien_sanpham.py, bản đã soát 06e7bdb) + dọn chữ nguồn của tên hàng. Xuất docs/sanpham_chuan/:
  gd_b_tach.csv     — ma, cot_moi, cu (cột cũ: chữ), moi, trang_thai: dien | mo_ho (2 cột cũ cho 2 giá trị khác nhau)
  gd_b_dem.csv      — theo cột mới: dien / mo_ho / trong (+ ô cột mới đã có chữ thì giữ, không đè)
  gd_b_chua_chuyen.csv — chữ cũ không có trong bảng gộp (giữ ở cột cũ): cot_cu, chu, so_ma
  gd_b_don_ten.csv  — ô CHỮ (không phải công thức) có khoảng trắng thừa / ký tự ẩn / chữ sai: ma, cot, cu, moi, loi
  + 1 dòng đề xuất sửa công thức CON_NAME (TEXTJOIN bỏ ô trống → hết 2 khoảng trắng), số mã đổi tên.

  venv/bin/python tools/tach_cot_sanpham.py [--sheet ID]
"""
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

import gspread
from google.oauth2.service_account import Credentials

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tu_dien_sanpham import COT_MOI, GOP, SO_TU, OUT, SHEET_ID, chuan, so_dep  # noqa: E402

SUA_CHU = [('Hải nancy', 'Hải Nancy'), ('TÚi', 'Túi')]  # chữ sai đã gặp (Phân tích rà 29/10)
AN = re.compile(r'[\x00-\x08\x0b-\x1f\x7f ​-‏  ⁠﻿]')


def don(v):
    """Bỏ ký tự ẩn, xuống dòng, khoảng trắng thừa; sửa chữ sai. Trả (mới, [lỗi])."""
    loi, x = [], v
    if AN.search(x) or '\n' in x or '\r' in x:
        loi.append('ký tự ẩn')
        x = AN.sub('', x).replace('\r', ' ').replace('\n', ' ')
    y = ' '.join(x.split())
    if y != x:
        loi.append('khoảng trắng')
    for a, b in SUA_CHU:
        if a in y:
            loi.append(f'"{a}" → "{b}"')
            y = y.replace(a, b)
    return y, loi


def tach(r, head):
    """1 dòng SANPHAM → {cot_moi: (moi | None, [nguồn], trang_thai)}."""
    o = lambda c: r[head.index(c)] if c in head and head.index(c) < len(r) else ''  # noqa: E731
    kq = {}
    for ten, _, kieu in COT_MOI:
        ds = []  # (giá trị, nguồn)
        if ten in SO_TU:
            cot, mau = SO_TU[ten]
            m = re.search(mau, chuan(o(cot)))
            if m:
                ds.append((so_dep(float(m.group(1).replace(',', '.'))), f'{cot}: {o(cot).strip()}'))
        else:
            for cot, bang in GOP.get(ten, {}).items():
                moi = bang.get(chuan(o(cot)))
                if moi is not None:
                    ds.append((moi, f'{cot}: {o(cot).strip()}'))
        gt = {v for v, _ in ds}
        if not gt:
            kq[ten] = (None, [], 'trong')
        elif len(gt) == 1:
            kq[ten] = (ds[0][0], [n for _, n in ds], 'dien')
        else:
            kq[ten] = (' | '.join(str(v) for v in sorted(gt, key=str)), [n for _, n in ds], 'mo_ho')
    return kq


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    creds = Credentials.from_service_account_file(os.path.join(ROOT, 'credentials.json'),
                                                  scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    ws = gspread.authorize(creds).open_by_key(sid).worksheet('SANPHAM')
    sp = ws.get_all_values()
    fm = ws.get_all_values(value_render_option='FORMULA')
    head = [h.strip() for h in sp[1]]
    ic = head.index('product_code')
    os.makedirs(OUT, exist_ok=True)

    dem = {t: Counter() for t, _, _ in COT_MOI}
    chua = Counter()
    nguon_cu = sorted({c for g in GOP.values() for c in g} | {c for c, _ in SO_TU.values()})
    da_gop = {c: set() for c in nguon_cu}
    for t, g in GOP.items():
        for c, bang in g.items():
            da_gop[c] |= set(bang)
    for c, mau in SO_TU.values():
        da_gop.setdefault(c, set())

    with open(os.path.join(OUT, 'gd_b_tach.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ma', 'cot_moi', 'cu', 'moi', 'trang_thai'])
        for i, r in enumerate(sp[2:], start=2):
            ma = r[ic].strip()
            if not ma:
                continue
            for ten, (moi, nguon, tt) in tach(r, head).items():
                if ten in head and r[head.index(ten)].strip():
                    dem[ten]['da_co'] += 1  # cột mới đã có chữ → giữ, không đè
                    continue
                dem[ten][tt] += 1
                if tt != 'trong':
                    w.writerow([ma, ten, ' ; '.join(nguon), moi, tt])
            for c in nguon_cu:
                v = chuan(r[head.index(c)])
                if v and v not in da_gop[c] and not any(re.search(m, v) for cc, m in SO_TU.values() if cc == c):
                    chua[(c, v)] += 1

    with open(os.path.join(OUT, 'gd_b_dem.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cot_moi', 'dien', 'mo_ho', 'trong', 'da_co'])
        for t, _, _ in COT_MOI:
            w.writerow([t, dem[t]['dien'], dem[t]['mo_ho'], dem[t]['trong'], dem[t]['da_co']])

    with open(os.path.join(OUT, 'gd_b_chua_chuyen.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cot_cu', 'chu', 'so_ma'])
        for (c, v), n in sorted(chua.items(), key=lambda x: (x[0][0], -x[1])):
            w.writerow([c, v, n])

    # Dọn chữ: chỉ ô CHỮ (công thức để nguyên — tên hàng sửa bằng công thức CON_NAME bên dưới)
    don_dem = Counter()
    with open(os.path.join(OUT, 'gd_b_don_ten.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ma', 'cot', 'cu', 'moi', 'loi'])
        het = head.index('content_path') if 'content_path' in head else len(head)  # cột thuộc tính / tên / giá / màu / NCC
        for i in range(2, len(sp)):
            ma = sp[i][ic].strip()
            if not ma:
                continue
            for j, v in enumerate(sp[i][:het]):
                if not v or not head[j] or head[j] in ('CON_DES', 'product_description'):  # mô tả web đã duyệt: giữ xuống dòng
                    continue
                f0 = fm[i][j] if i < len(fm) and j < len(fm[i]) else ''
                if str(f0).startswith('='):
                    continue
                moi, loi = don(v)
                if loi and moi != v:
                    w.writerow([ma, head[j], v, moi, ', '.join(loi)])
                    don_dem[head[j]] += 1
        # CON_NAME: =CONCATENATE(B;" ";C;" ";D;" ";H;" ";I;" ";W) → ô trống tạo 2 khoảng trắng
        cn = head.index('CON_NAME')
        n2 = sum(1 for r in sp[2:] if r[ic].strip() and '  ' in r[cn])
        w.writerow(['(công thức)', 'CON_NAME', '=CONCATENATE(B;" ";C;" ";D;" ";H;" ";I;" ";W)',
                    '=TEXTJOIN(" ";TRUE;B;C;D;H;I;W) (bỏ ô trống; cần Web goc.ts ghepTen làm cùng)', f'{n2} mã đang có 2 khoảng trắng'])

    print(f'Sheet {sid[:6]}…: {sum(1 for r in sp[2:] if r[ic].strip())} mã')
    print('cot_moi: điền / mơ hồ / trống / đã có')
    for t, _, _ in COT_MOI:
        print(f"  {t}: {dem[t]['dien']} / {dem[t]['mo_ho']} / {dem[t]['trong']} / {dem[t]['da_co']}")
    print(f'chữ cũ chưa chuyển: {len(chua)} loại, {sum(chua.values())} ô · dọn chữ: {dict(don_dem)} · CON_NAME 2 khoảng trắng: {n2}')
    print(f'→ {os.path.relpath(OUT, ROOT)}/ gd_b_tach.csv, gd_b_dem.csv, gd_b_chua_chuyen.csv, gd_b_don_ten.csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
