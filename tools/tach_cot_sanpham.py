"""Bộ chuẩn SANPHAM GĐ B — CHẠY THỬ (chỉ đọc Sheet, chưa ghi): tách cột cũ sang 15 cột mới theo bảng GOP / SO_TU
(tools/tu_dien_sanpham.py, bản đã soát 06e7bdb) + dọn chữ nguồn của tên hàng. Xuất docs/sanpham_chuan/:
  gd_b_tach.csv     — ma, cot_moi, cu (cột cũ: chữ), moi, trang_thai: dien | mo_ho (2 cột cũ cho 2 giá trị khác nhau)
  gd_b_dem.csv      — theo cột mới: dien / mo_ho / trong (+ ô cột mới đã có chữ thì giữ, không đè)
  gd_b_chua_chuyen.csv — chữ cũ không có trong bảng gộp (giữ ở cột cũ): cot_cu, chu, so_ma
  gd_b_don_ten.csv  — ô CHỮ (không phải công thức) có khoảng trắng thừa / ký tự ẩn / chữ sai: ma, cot, cu, moi, loi
  + 1 dòng đề xuất sửa công thức CON_NAME (TEXTJOIN bỏ ô trống → hết 2 khoảng trắng), số mã đổi tên.

  venv/bin/python tools/tach_cot_sanpham.py [--sheet ID]             # chạy thử, chỉ đọc
  venv/bin/python tools/tach_cot_sanpham.py --ghi [--sheet ID]       # GHI 15 cột mới (anh Kha xác nhận 29/10)
  venv/bin/python tools/tach_cot_sanpham.py --ghi-ten [--sheet ID]   # GHI công thức CON_NAME + dọn chữ (Sheet chính: chờ web "Lên")
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


def moi_tu_cu(cot_cu, chu):
    """1 ô cột cũ → [(cột mới, giá trị)] theo cùng bảng gộp (dùng khi Mac ghi cột cũ, chạy song song — luật 15)."""
    out = []
    for ten, g in GOP.items():
        moi = g.get(cot_cu, {}).get(chuan(chu))
        if moi is not None:
            out.append((ten, moi))
    for ten, (cot, mau) in SO_TU.items():
        m = re.search(mau, chuan(chu)) if cot == cot_cu else None
        if m:
            out.append((ten, so_dep(float(m.group(1).replace(',', '.')))))
    return out


# 7 ô mơ hồ: Phân tích xem ảnh 29/10 (MT288D / MT291N / MT289V kieu_de để trống chờ ảnh)
CHON_TAY = {('HE304D', 'dang_mui'): 'nhọn', ('HE308D', 'dang_mui'): 'tròn', ('HE312K', 'dang_mui'): 'nhọn', ('SX4N', 'dang_mui'): 'tròn'}


def _mo(sid, ghi=False):
    scope = 'https://www.googleapis.com/auth/spreadsheets' + ('' if ghi else '.readonly')
    creds = Credentials.from_service_account_file(os.path.join(ROOT, 'credentials.json'), scopes=[scope])
    return gspread.authorize(creds).open_by_key(sid).worksheet('SANPHAM')


def ghi_cot_moi(sid):
    """GHI THẬT 15 cột mới: chỉ ô 'dien' + CHON_TAY, đọc lại Sheet ngay trước khi ghi, ô cột mới đã có chữ thì giữ. Không đụng cột cũ.
    1 lần ghi cả khối BA3:BO<n> (ô giữ nguyên ghi lại đúng giá trị đang có)."""
    ws = _mo(sid, ghi=True)
    sp = ws.get_all_values()
    head = [h.strip() for h in sp[1]]
    ic = head.index('product_code')
    cot = [t for t, _, _ in COT_MOI]
    thieu = [t for t in cot if t not in head]
    if thieu:
        raise RuntimeError(f'SANPHAM chưa có cột {thieu} — ghi GĐ A trước')
    j0 = head.index(cot[0])
    if [head[j0 + k] for k in range(len(cot))] != cot:
        raise RuntimeError('15 cột mới không liền nhau đúng thứ tự — DỪNG')
    khoi, dem = [], Counter()
    for r in sp[2:]:
        r = r + [''] * (len(head) - len(r))
        hien = [r[j0 + k] for k in range(len(cot))]
        ma = r[ic].strip().upper()
        out = list(hien)
        if ma:
            for k, (ten, (moi, _, tt)) in enumerate(tach(r, head).items()):
                if hien[k].strip():
                    dem['giu'] += 1
                    continue
                if (ma, ten) in CHON_TAY:
                    moi, tt = CHON_TAY[(ma, ten)], 'dien'
                if tt == 'dien':
                    out[k] = moi
                    dem[ten] += 1
        khoi.append(out)
    L0 = gspread.utils.rowcol_to_a1(3, j0 + 1)
    L1 = gspread.utils.rowcol_to_a1(2 + len(khoi), j0 + len(cot))
    ws.update(range_name=f'{L0}:{L1}', values=khoi, value_input_option='RAW')
    # Đọc lại đếm
    lai = ws.get(f'{L0}:{L1}')
    dl = Counter()
    for r in lai:
        for k, v in enumerate(r):
            if str(v).strip():
                dl[cot[k]] += 1
    print(f'✅ Sheet {sid[:6]}…: ghi {sum(dem[t] for t in cot)} ô mới vào {L0}:{L1} (giữ {dem["giu"]} ô đã có)')
    for t in cot:
        print(f'  {t}: ghi {dem[t]} · đọc lại có chữ {dl[t]}')
    return 0


def ghi_ten(sid):
    """GHI THẬT: CON_NAME =CONCATENATE(…) → =TEXTJOIN(" ";TRUE;…) (ô công thức) + dọn chữ theo don() (ô chữ, như gd_b_don_ten.csv)."""
    ws = _mo(sid, ghi=True)
    sp = ws.get_all_values()
    fm = ws.get_all_values(value_render_option='FORMULA')
    head = [h.strip() for h in sp[1]]
    ic, cn = head.index('product_code'), head.index('CON_NAME')
    het = head.index('content_path') if 'content_path' in head else len(head)
    ds, dem = [], Counter()
    for i in range(2, len(sp)):
        if not sp[i][ic].strip():
            continue
        f0 = str(fm[i][cn]) if cn < len(fm[i]) else ''
        m = re.fullmatch(r'=CONCATENATE\((.*)\)', f0.strip(), re.I)
        if m:
            refs = [x.strip() for x in m.group(1).split(';') if x.strip() != '" "']
            ds.append({'range': gspread.utils.rowcol_to_a1(i + 1, cn + 1), 'values': [['=TEXTJOIN(" ";TRUE;' + ';'.join(refs) + ')']]})
            dem['CON_NAME'] += 1
        for j, v in enumerate(sp[i][:het]):
            if not v or not head[j] or head[j] in ('CON_DES', 'product_description') or str(fm[i][j]).startswith('='):
                continue
            moi, loi = don(v)
            if loi and moi != v:
                ds.append({'range': gspread.utils.rowcol_to_a1(i + 1, j + 1), 'values': [[moi]]})
                dem[head[j]] += 1
    for k in range(0, len(ds), 500):
        ws.batch_update(ds[k:k + 500], value_input_option='USER_ENTERED')
    print(f'✅ Sheet {sid[:6]}…: {len(ds)} ô — {dict(dem)}')
    return 0


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    if '--ghi' in sys.argv:
        return ghi_cot_moi(sid)
    if '--ghi-ten' in sys.argv:
        return ghi_ten(sid)
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
