"""Đổi tên giá trị thuộc tính chuẩn (anh Kha duyệt 29/10 — Website docs/vision/ten_thuoc_tinh_de_xuat.md mục cuối).
Chỉ đụng 15+ cột mới và tab TU_DIEN; cột cũ (tiếng Việt) KHÔNG đổi.
- Đổi: quai kẹp → kẹp ngón (xỏ ngón); lộn → da lộn; bóng → da bóng; đi làm → công sở (dip chọn nhiều: thay trong chuỗi).
- Gộp: nỉ + vải nhung → "nỉ / nhung" (lot_trong / lot_de). Bỏ "da heo cán mút" (ô có → da heo). chat_lieu_de thêm cao su đúc, PU.
- "quai hậu" chỉ ở kieu_quai: ô kieu_dong = quai hậu → chuyển sang kieu_quai nếu trống (còn lại báo).
- form → do_om (chuẩn / ôm / rộng ngang) + cột mới chon_size (đúng size / lên 1 size / xuống 1 size); thêm cột kieu_giay_tay.
Chạy thử in số ô sẽ đổi + docs/sanpham_chuan/doi_ten.csv; --ghi để ghi (Sheet thử trước, chính sau).

  venv/bin/python tools/doi_ten_thuoc_tinh.py [--ghi] [--sheet ID]
"""
import csv
import os
import sys
from collections import Counter

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID  # noqa: E402

DOI = {  # cột mới → {giá trị cũ: giá trị mới}
    'kieu_quai': {'quai kẹp': 'kẹp ngón (xỏ ngón)'},
    'be_mat': {'lộn': 'da lộn', 'bóng': 'da bóng'},
    'dip': {'đi làm': 'công sở'},
    'lot_trong': {'nỉ': 'nỉ / nhung', 'vải nhung': 'nỉ / nhung'},
    'lot_de': {'nỉ': 'nỉ / nhung', 'vải nhung': 'nỉ / nhung', 'da heo cán mút': 'da heo'},
}
NHIEU = ('dip',)
TD_THEM = {'chat_lieu_de': ['cao su đúc', 'PU']}
TD_BO = {'kieu_dong': ['quai hậu']}
FORM_DO_OM = {'chuẩn': 'chuẩn', 'ôm': 'ôm', 'rộng ngang': 'rộng ngang'}
FORM_CHON_SIZE = {'nên lên 1 size': 'lên 1 size', 'nên xuống 1 size': 'xuống 1 size'}
COT_THEM = [  # (tên hàng 2, nhãn hàng 1, giá trị TU_DIEN)
    ('chon_size', 'Chọn size', ['đúng size', 'lên 1 size', 'xuống 1 size']),
    ('kieu_giay_tay', 'Kiểu giày tây', ['Oxford (buộc dây kín)', 'Derby (buộc dây hở)', 'giày lười (loafer)', 'khoá cài (monk)',
                                        'bốt cổ chun (Chelsea)', 'đục lỗ (brogue)']),
]
DO_OM = ('do_om', 'Độ ôm', ['chuẩn', 'ôm', 'rộng ngang'])


def doi_o(cot, v):
    v = v.strip()
    if cot in NHIEU:
        ds = [DOI[cot].get(x.strip(), x.strip()) for x in v.split(',') if x.strip()]
        return ', '.join(dict.fromkeys(ds))
    return DOI.get(cot, {}).get(v, v)


def doi_tu_dien(td_cot, ten):
    """Danh sách giá trị TU_DIEN mới của 1 cột (giữ thứ tự, bỏ trùng sau khi đổi)."""
    moi = [DOI.get(ten, {}).get(v, v) for v in td_cot if v not in TD_BO.get(ten, [])]
    moi += TD_THEM.get(ten, [])
    return list(dict.fromkeys(moi))


def lam(sid, ghi=False):
    ws = _mo(sid, ghi=ghi)
    ss = ws.spreadsheet
    sp = ws.get_all_values()
    h1, h = [x.strip() for x in sp[0]], [x.strip() for x in sp[1]]
    ic = h.index('product_code')
    co_form = 'form' in h
    jf = h.index('form') if co_form else h.index('do_om')
    o, dem, bao, log, tach_form = [], Counter(), [], [], []
    for i, r in enumerate(sp[2:], start=3):
        r = r + [''] * (len(h) - len(r))
        ma = r[ic].strip()
        if not ma:
            continue
        for cot in DOI:
            j = h.index(cot)
            if r[j].strip() and doi_o(cot, r[j]) != r[j].strip():
                o.append({'range': gspread.utils.rowcol_to_a1(i, j + 1), 'values': [[doi_o(cot, r[j])]]})
                dem[cot] += 1
                log.append([ma, cot, r[j], doi_o(cot, r[j])])
        jd, jq = h.index('kieu_dong'), h.index('kieu_quai')
        if r[jd].strip() == 'quai hậu':
            o.append({'range': gspread.utils.rowcol_to_a1(i, jd + 1), 'values': [['']]})
            dem['kieu_dong bỏ quai hậu'] += 1
            if not r[jq].strip():
                o.append({'range': gspread.utils.rowcol_to_a1(i, jq + 1), 'values': [['quai hậu']]})
                log.append([ma, 'kieu_dong → kieu_quai', 'quai hậu', 'quai hậu'])
            else:
                bao.append(f'{ma}: kieu_dong quai hậu, kieu_quai đã có "{r[jq]}"')
        fv = r[jf].strip()
        if fv:
            dem['form có chữ'] += 1
            tach_form.append((i, FORM_DO_OM.get(fv, ''), FORM_CHON_SIZE.get(fv, '')))
            log.append([ma, 'form', fv, f'do_om={FORM_DO_OM.get(fv, "")} chon_size={FORM_CHON_SIZE.get(fv, "")}'])
    # Tab TU_DIEN
    td = ss.worksheet('TU_DIEN')
    luoi = td.get_all_values()
    th = [x.strip() for x in luoi[0]]
    td_up = []
    for ten in set(DOI) | set(TD_THEM) | set(TD_BO):
        j = th.index(ten)
        cu = [r[j].strip() for r in luoi[2:] if j < len(r) and r[j].strip()]
        moi = doi_tu_dien(cu, ten)
        if moi != cu:
            L = gspread.utils.rowcol_to_a1(1, j + 1).rstrip('1')
            td_up.append({'range': f'{L}3:{L}{2 + max(len(cu), len(moi))}', 'values': [[v] for v in moi] + [[''] for _ in range(len(cu) - len(moi))]})
            log.append(['TU_DIEN', ten, ', '.join(cu), ', '.join(moi)])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'doi_ten.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ma', 'cot', 'cu', 'moi'])
        w.writerows(log)
    print(f'Sheet {sid[:6]}…: SANPHAM {len(o)} ô sẽ đổi {dict(dem)} · TU_DIEN {len(td_up)} cột đổi'
          f" · cột: {'form → do_om' if co_form else 'do_om đã có'}, thêm {[c for c, _, _ in COT_THEM if c not in h]}")
    for b in bao:
        print('  ⚠ ' + b)
    if not ghi:
        print(f'→ {os.path.relpath(OUT, ROOT)}/doi_ten.csv (chạy thử, chưa ghi)')
        return 0
    if any(not a and not b for _, a, b in tach_form):
        raise RuntimeError('Cột form có chữ ngoài bảng tách — xem doi_ten.csv, DỪNG')
    # 1. Dữ liệu 15 cột
    for k in range(0, len(o), 500):
        ws.batch_update(o[k:k + 500], value_input_option='RAW')
    # 2. TU_DIEN: đổi giá trị + form → do_om + thêm cột
    if td_up:
        td.batch_update(td_up, value_input_option='RAW')
    jtf = th.index('form') if 'form' in th else th.index('do_om')
    L = gspread.utils.rowcol_to_a1(1, jtf + 1).rstrip('1')
    td.update(range_name=f'{L}1:{L}{2 + max(5, len(DO_OM[2]))}',
              values=[[DO_OM[0]], [DO_OM[1]]] + [[v] for v in DO_OM[2]] + [[''] for _ in range(max(5, len(DO_OM[2])) - len(DO_OM[2]))],
              value_input_option='RAW')
    them_td = [c for c in COT_THEM if c[0] not in th]
    if them_td:
        if td.col_count < len(th) + len(them_td):
            td.add_cols(len(th) + len(them_td) - td.col_count)
        a = gspread.utils.rowcol_to_a1(1, len(th) + 1)
        cao = max(len(c[2]) for c in them_td)
        td.update(range_name=a, value_input_option='RAW',
                  values=[[c[0] for c in them_td], [c[1] for c in them_td]] + [[c[2][i] if i < len(c[2]) else '' for c in them_td] for i in range(cao)])
    th2 = [x.strip() for x in td.row_values(1)]
    # 3. SANPHAM: form → do_om (hàng 1–2), thêm cột cuối + kiểm tra ô
    if co_form:
        ws.update(range_name=gspread.utils.rowcol_to_a1(1, jf + 1), values=[[DO_OM[1]], [DO_OM[0]]], value_input_option='RAW')
    them = [c for c in COT_THEM if c[0] not in h]
    if them:
        dau = len(h) + 1
        if ws.col_count < dau + len(them) - 1:
            ws.add_cols(dau + len(them) - 1 - ws.col_count)
        a0 = gspread.utils.rowcol_to_a1(1, dau)
        ws.update(range_name=a0, values=[[c[1] for c in them], [c[0] for c in them]], value_input_option='RAW')
        reqs = []
        for k, c in enumerate(them):
            X = gspread.utils.rowcol_to_a1(1, th2.index(c[0]) + 1).rstrip('1')
            reqs.append({'setDataValidation': {'range': {'sheetId': ws.id, 'startRowIndex': 2, 'endRowIndex': ws.row_count,
                                                         'startColumnIndex': dau - 1 + k, 'endColumnIndex': dau + k},
                                               'rule': {'condition': {'type': 'ONE_OF_RANGE', 'values': [{'userEnteredValue': f'=TU_DIEN!${X}$3:${X}'}]},
                                                        'showCustomUi': True, 'strict': True}}})
        ss.batch_update({'requests': reqs})
    # form có chữ → tách: do_om (cùng cột) + chon_size
    if tach_form:
        hc = [x.strip() for x in ws.row_values(2)]
        jc = hc.index('chon_size')
        ws.batch_update([u for i, a, b in tach_form for u in (
            {'range': gspread.utils.rowcol_to_a1(i, jf + 1), 'values': [[a]]},
            {'range': gspread.utils.rowcol_to_a1(i, jc + 1), 'values': [[b]]})], value_input_option='RAW')
    # Đọc lại
    sp2 = ws.get_all_values()
    h2 = [x.strip() for x in sp2[1]]
    con = sum(1 for r in sp2[2:] for cot in DOI if cot in h2 and r[h2.index(cot)].strip()
              and doi_o(cot, r[h2.index(cot)]) != r[h2.index(cot)].strip())
    qh = sum(1 for r in sp2[2:] if r[h2.index('kieu_dong')].strip() == 'quai hậu')
    print(f'✅ Đã ghi. Đọc lại: còn {con} ô chữ cũ, kieu_dong "quai hậu" còn {qh}; cột: '
          f"{[x for x in h2 if x in ('do_om', 'form', 'chon_size', 'kieu_giay_tay')]} · TU_DIEN: {th2[-3:]}")
    return 0


if __name__ == '__main__':
    sys.exit(lam(sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID, ghi='--ghi' in sys.argv))
