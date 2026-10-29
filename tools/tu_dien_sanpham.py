"""Bộ chuẩn SANPHAM GĐ A (anh Kha "Làm" 29/10 tại Phân tích · Bán hàng; kế hoạch Website docs/vision/thuoc_tinh_sanpham.md mục 4.2, 6–7).
Soạn tab TU_DIEN (cột mới → giá trị cho phép) + tiêu đề 15 cột mới thêm ở CUỐI SANPHAM. CHỈ ĐỌC Sheet, xuất file để soát:
  docs/sanpham_chuan/tu_dien.json      — đủ: nhãn, kiểu ô, giá trị, số mã đang có, gộp từ chữ cũ nào, nguồn (sheet / ke_hoach)
  docs/sanpham_chuan/TU_DIEN.csv       — đúng bố cục tab TU_DIEN: hàng 1 tên cột snake_case, hàng 2 nhãn Việt, từ hàng 3 giá trị
  docs/sanpham_chuan/cot_moi_sanpham.csv — cột Sheet, hàng 1 (nhãn), hàng 2 (tên), kiểm tra ô (danh sách thả TU_DIEN / số)
Giá trị lấy từ chữ đang có trong SANPHAM / SUB, gộp cách ghi cùng nghĩa (bảng GOP); chất liệu bỏ "cao cấp" (tên hàng giữ).
Giá trị "ke_hoach" = có trong danh sách kế hoạch 4.2 nhưng Sheet chưa có mã nào — Phân tích soát giữ / bỏ.
Bảng GOP dùng lại ở GĐ B (tách cột cũ sang cột mới).

  venv/bin/python tools/tu_dien_sanpham.py          # chỉ soạn file
  venv/bin/python tools/tu_dien_sanpham.py --ghi    # GHI THẬT (anh Kha xác nhận 29/10)
"""
import csv
import json
import os
import re
import sys
from collections import Counter

import gspread
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET_ID = os.getenv("HNC_SHEET_ID", "").strip() or "1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0"  # như main.py
OUT = os.path.join(ROOT, 'docs', 'sanpham_chuan')

# Cột mới (thứ tự thêm ở cuối SANPHAM): tên hàng 2, nhãn hàng 1, kiểu ô (ds = 1 giá trị TU_DIEN, nhieu = chọn nhiều, so = số)
COT_MOI = [
    ('gioi_tinh', 'Giới tính (chuẩn)', 'ds'),
    ('chat_lieu', 'Chất liệu mũ / thân', 'ds'),
    ('kieu_dong', 'Kiểu mang', 'ds'),
    ('kieu_quai', 'Kiểu quai (dép / sandal)', 'ds'),
    ('dang_mui', 'Dáng mũi', 'ds'),
    ('kieu_de', 'Kiểu đế', 'ds'),
    ('cao_got_cm', 'Cao gót (cm)', 'so'),
    ('tang_cao_cm', 'Tăng chiều cao (cm)', 'so'),
    ('chat_lieu_de', 'Chất liệu đế (chuẩn)', 'ds'),
    ('lot_trong', 'Lót thân', 'ds'),
    ('lot_de', 'Mặt lót đế (chất liệu)', 'ds'),
    ('be_mat', 'Bề mặt da', 'ds'),
    ('co_giay', 'Cổ giày', 'ds'),
    ('form', 'Form chân', 'ds'),
    ('dip', 'Dịp mang', 'nhieu'),
]
SO_GIOI_HAN = {'cao_got_cm': (0, 10), 'tang_cao_cm': (0, 15)}

# Gộp chữ cũ (đã bỏ khoảng trắng thừa, viết thường) → giá trị chuẩn, theo cột cũ nguồn. Không có trong bảng = không đưa sang cột mới.
GOP = {
    'gioi_tinh': {'Giới tính': {'male': 'nam', 'female': 'nữ'}, 'Đặc điểm': {'nam': 'nam', 'nữ': 'nữ'}},
    'chat_lieu': {c: {'da bò': 'da bò', 'da bò cao cấp': 'da bò', 'vải bố': 'vải bố', 'vải bố cao cấp': 'vải bố',
                      'vải lưới': 'vải lưới', 'vải lưới cao cấp': 'vải lưới', 'vải sợi': 'vải sợi', 'vải sợi cao cấp': 'vải sợi',
                      'da cừu': 'da cừu', 'microfiber': 'microfiber'} for c in ('Chất liệu', 'Chất liệu quai:')},
    'kieu_dong': {'Đặc điểm': {'xỏ chân': 'xỏ chân', 'cột dây': 'cột dây', 'cổ thun': 'cổ thun', 'khoá kéo 1 bên': 'khoá kéo 1 bên',
                               'khoá kéo 2 bên': 'khoá kéo 2 bên', 'xé dán': 'xé dán',
                               'khoá kéo': 'khoá kéo 1 bên', 'dây kéo': 'khoá kéo 1 bên'}},
    'kieu_quai': {'Đặc điểm': {'quai ngang': 'quai ngang', 'quai chéo': 'quai chéo', 'quai kẹp': 'quai kẹp', 'dép h': 'quai chữ H'}},
    'dang_mui': {'Dáng giày mũi:': {'tròn': 'tròn', 'vuông': 'vuông', 'nhọn': 'nhọn'},
                 'Đặc điểm': {'mũi tròn': 'tròn', 'mũi vuông': 'vuông', 'mũi nhọn': 'nhọn'}},
    'kieu_de': {'Phần dưới giày:': {'đế bằng': 'đế bằng'}, 'Đặc điểm': {'đế bằng': 'đế bằng', 'đế xuồng': 'đế xuồng'}},
    'chat_lieu_de': {'Chất liệu đế:': {'cao su nhiệt tpr': 'cao su nhiệt TPR', 'da mộc, cao su': 'da mộc + cao su', 'eva cao cấp': 'EVA',
                                       'trấu mặt cao su': 'trấu mặt cao su', 'cao su vỏ xe': 'cao su vỏ xe', 'phylon siêu nhẹ': 'phylon',
                                       'cao su bi cá': 'cao su bi cá'}},
    'lot_trong': {'Lót trong:': {'da heo': 'da heo', 'da bò': 'da bò', 'vải nhung': 'vải nhung', 'microfiber': 'microfiber', 'da cừu': 'da cừu'}},
    'lot_de': {'Mặt lót đế:': {'da bò hút ẩm': 'da bò', 'microfiber': 'microfiber', 'da cừu': 'da cừu'}},
    'be_mat': {'Nhấn mạnh': {'trơn': 'trơn', 'hạt mềm': 'hạt mềm', 'vân': 'vân'}},
    'co_giay': {'Bonus:': {'cổ giày cao nửa ống chân.': 'cổ cao nửa ống'}},
    'dip': {'Sử dụng:': {'hằng ngày': 'hằng ngày', 'hằng ngày, dự tiệc...': 'hằng ngày, dự tiệc'}},
}
# Cột số: lấy số trong chữ cũ (vd "gót 3cm" → 3; "… cao thêm 5,5cm." → 5.5)
SO_TU = {'cao_got_cm': ('Phần dưới giày:', r'gót\s*(\d+(?:[.,]\d+)?)\s*cm'), 'tang_cao_cm': ('Bonus:', r'cao thêm\s*(\d+(?:[.,]\d+)?)\s*cm')}
# Giá trị trong danh sách kế hoạch 4.2 mà Sheet chưa có mã nào (Phân tích soát giữ / bỏ)
KE_HOACH = {
    'gioi_tinh': ['unisex'], 'chat_lieu': ['da bò lộn', 'da heo'], 'kieu_dong': ['khoá cài', 'quai hậu'], 'kieu_quai': ['quai hậu', 'nhiều quai'],
    'dang_mui': ['hở mũi'], 'kieu_de': ['gót vuông', 'gót nhọn', 'đế độn', 'có gót'],  # có gót: giày nam (anh Kha 29/10) 'lot_de': ['da heo', 'mút'], 'be_mat': ['lộn', 'bóng'], 'co_giay': ['cổ thấp', 'cổ lửng', 'cổ cao'],
    'form': ['chuẩn', 'ôm', 'rộng ngang', 'nên lên 1 size', 'nên xuống 1 size'], 'dip': ['đi làm', 'cưới', 'dạo phố', 'du lịch'],
}
# Ghi chú cho Phân tích soát (chữ cũ chưa có chỗ ở cột mới, hoặc gộp có chọn)
GHI_CHU = {
    'chat_lieu': 'Bỏ "cao cấp" (tên hàng giữ). "microfiber" giữ chữ đang dùng (kế hoạch ghi "da tổng hợp (microfiber)").',
    'kieu_dong': '"khoá kéo" / "dây kéo" gộp vào "khoá kéo 1 bên" (Phân tích 29/10). Bonus "giày giả cột dây có thun hai bên" chưa đưa vào.',
    'kieu_quai': '"dép h" (1 mã) → "quai chữ H".',
    'chat_lieu_de': 'Gộp theo kế hoạch: "EVA cao cấp" → "EVA", "phylon siêu nhẹ" → "phylon", "da mộc, cao su" → "da mộc + cao su".',
    'lot_de': '"mềm êm" / "mềm êm, có độ đàn hồi" giữ ở cột cũ, không có cột mới (lời hứa cảm giác — Phân tích 29/10, không thêm lot_de_em).',
    'be_mat': 'Nhấn mạnh "cao cấp" / "mix màu" giữ cột cũ; big size do máy tính từ size, không có cột.',
    'co_giay': 'Theo kế hoạch 4.2; Bonus "cổ giày cao nửa ống chân." → "cổ cao nửa ống".',
    'dip': 'Chọn nhiều: ô ghi các giá trị cách nhau dấu phẩy (vd "hằng ngày, dự tiệc"); TU_DIEN liệt kê từng giá trị lẻ.',
    'cao_got_cm': 'Số 0–10. "đế bằng" chưa tự ghi 0 (GĐ B chốt).',
    'tang_cao_cm': 'Số; chỉ ngành tăng chiều cao.',
    'form': 'Cột mới, tiệm điền dần mẫu bán chạy.',
}


def chuan(v):
    return ' '.join(str(v or '').split()).lower()


def doc():
    creds = Credentials.from_service_account_file(os.path.join(ROOT, 'credentials.json'),
                                                  scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)
    sp = sh.worksheet('SANPHAM').get_all_values()
    return sp, [h.strip() for h in sp[1]], [h.strip() for h in sp[0]]


def so_dep(x):
    return int(x) if float(x).is_integer() else x


def soan(sp, head):
    can = sorted({c for g in GOP.values() for c in g} | {c for c, _ in SO_TU.values()} | {'product_code'})
    thieu = [c for c in can if c not in head]
    if thieu:
        raise RuntimeError(f'SANPHAM thiếu cột {thieu} (hàng 2)')
    dong = [r for r in sp[2:] if r[head.index('product_code')].strip()]
    out = []
    for ten, nhan, kieu in COT_MOI:
        dem, gop = Counter(), {}
        if ten in SO_TU:
            cot, mau = SO_TU[ten]
            for r in dong:
                m = re.search(mau, chuan(r[head.index(cot)]))
                if m:
                    v = so_dep(float(m.group(1).replace(',', '.')))
                    dem[v] += 1
                    gop.setdefault(v, set()).add(f'{cot} "{chuan(r[head.index(cot)])}"')
            gt = [{'gia_tri': v, 'so_ma': n, 'nguon': 'sheet', 'gop_tu': sorted(gop[v])} for v, n in sorted(dem.items())]
        else:
            for r in dong:
                da = set()  # 1 mã đếm 1 lần cho mỗi giá trị dù có ở 2 cột cũ
                for cot, bang in GOP.get(ten, {}).items():
                    cu = chuan(r[head.index(cot)])
                    moi = bang.get(cu)
                    if moi is None:
                        continue
                    gop.setdefault(moi, set()).add(f'{cot} "{cu}"')
                    for x in [s.strip() for s in moi.split(',')] if kieu == 'nhieu' else [moi]:
                        da.add(x)
                for x in da:
                    dem[x] += 1
            for moi, nguon in list(gop.items()):
                for x in [s.strip() for s in moi.split(',')] if kieu == 'nhieu' else [moi]:
                    gop.setdefault(x, set()).update(nguon)
            gt = [{'gia_tri': v, 'so_ma': n, 'nguon': 'sheet', 'gop_tu': sorted(gop.get(v, ()))} for v, n in dem.most_common()]
            co = {g['gia_tri'] for g in gt}
            gt += [{'gia_tri': v, 'so_ma': 0, 'nguon': 'ke_hoach', 'gop_tu': []} for v in KE_HOACH.get(ten, []) if v not in co]
        x = {'cot': ten, 'nhan': nhan, 'kieu': kieu, 'gia_tri': gt, 'ghi_chu': GHI_CHU.get(ten, '')}
        if kieu == 'so':
            x['gioi_han'] = list(SO_GIOI_HAN[ten])
        out.append(x)
    return out, len(dong)


def ghi(tu_dien, head, hang1, so_ma):
    os.makedirs(OUT, exist_ok=True)
    trung = [c for c, _, _ in COT_MOI if c in head] + [n for _, n, _ in COT_MOI if n in head or n in hang1]
    if trung:
        raise RuntimeError(f'Tên / nhãn cột mới trùng cột đang có: {trung}')
    with open(os.path.join(OUT, 'tu_dien.json'), 'w', encoding='utf-8') as f:
        json.dump({'nguon': 'tools/tu_dien_sanpham.py', 'so_ma_sanpham': so_ma, 'tab': 'TU_DIEN', 'cot': tu_dien}, f, ensure_ascii=False, indent=1)
    ds = [c for c in tu_dien if c['kieu'] != 'so']
    cao = max(len(c['gia_tri']) for c in ds)
    with open(os.path.join(OUT, 'TU_DIEN.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow([c['cot'] for c in ds])
        w.writerow([c['nhan'] for c in ds])
        for i in range(cao):
            w.writerow([c['gia_tri'][i]['gia_tri'] if i < len(c['gia_tri']) else '' for c in ds])
    cot_td = {c['cot']: rowcol_to_a1(1, i + 1).rstrip('1') for i, c in enumerate(ds)}
    with open(os.path.join(OUT, 'cot_moi_sanpham.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cot_sheet', 'hang_1_nhan', 'hang_2_ten', 'kiem_tra_o'])
        for i, (ten, nhan, kieu) in enumerate(COT_MOI):
            L = rowcol_to_a1(1, len(head) + i + 1).rstrip('1')
            if kieu == 'so':
                kt = f'số {SO_GIOI_HAN[ten][0]}–{SO_GIOI_HAN[ten][1]}'
            else:
                kt = f"danh sách thả TU_DIEN!{cot_td[ten]}3:{cot_td[ten]}" + (' (chọn nhiều)' if kieu == 'nhieu' else '')
            w.writerow([L, nhan, ten, kt])


def ghi_sheet():
    """Ghi THẬT theo docs/sanpham_chuan/tu_dien.json (bản đã soát): tab TU_DIEN + tiêu đề cột mới ở cuối SANPHAM + kiểm tra ô.
    Ô dữ liệu cột mới để trống (GĐ B). Dừng nếu SANPHAM không còn đúng 52 cột / ô đích đã có chữ / tab TU_DIEN đã có dữ liệu."""
    td = json.load(open(os.path.join(OUT, 'tu_dien.json'), encoding='utf-8'))['cot']
    if [c['cot'] for c in td] != [c for c, _, _ in COT_MOI]:
        raise RuntimeError('tu_dien.json khác COT_MOI — chạy lại bản soạn trước')
    creds = Credentials.from_service_account_file(os.path.join(ROOT, 'credentials.json'), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)
    ws = sh.worksheet('SANPHAM')
    head = [h.strip() for h in ws.row_values(2)]
    dau = len(head) + 1  # cột đầu tiên còn trống ở hàng 2
    if set(head) & {c['cot'] for c in td}:
        raise RuntimeError('SANPHAM đã có cột mới — DỪNG')
    print(f'Sheet {SHEET_ID[:6]}…: SANPHAM {len(head)} cột → ghi từ cột {dau}')
    L0, L1 = rowcol_to_a1(1, dau).rstrip('1'), rowcol_to_a1(1, dau + len(td) - 1).rstrip('1')
    if ws.col_count < dau + len(td) - 1:
        ws.add_cols(dau + len(td) - 1 - ws.col_count)
    if any(x for r in ws.get(f'{L0}1:{L1}{ws.row_count}') for x in r):
        raise RuntimeError(f'SANPHAM {L0}:{L1} đã có chữ — DỪNG')
    ds = [c for c in td if c['kieu'] != 'so']
    if 'TU_DIEN' in [w.title for w in sh.worksheets()]:
        tdw = sh.worksheet('TU_DIEN')
        if any(x for r in tdw.get_all_values() for x in r):
            raise RuntimeError('Tab TU_DIEN đã có dữ liệu — DỪNG')
    else:
        tdw = sh.add_worksheet('TU_DIEN', rows=50, cols=len(ds))
    cao = max(len(c['gia_tri']) for c in ds)
    luoi = [[c['cot'] for c in ds], [c['nhan'] for c in ds]] + \
           [[str(c['gia_tri'][i]['gia_tri']) if i < len(c['gia_tri']) else '' for c in ds] for i in range(cao)]
    tdw.update(range_name='A1', values=luoi, value_input_option='RAW')
    ws.update(range_name=f'{L0}1:{L1}2', values=[[c['nhan'] for c in td], [c['cot'] for c in td]], value_input_option='RAW')
    cot_td = {c['cot']: rowcol_to_a1(1, i + 1).rstrip('1') for i, c in enumerate(ds)}
    reqs = []
    for i, c in enumerate(td):
        if c['kieu'] == 'so':
            lo, hi = c['gioi_han']
            rule = {'condition': {'type': 'NUMBER_BETWEEN', 'values': [{'userEnteredValue': str(lo)}, {'userEnteredValue': str(hi)}]},
                    'strict': True, 'inputMessage': f"{c['nhan']}: số {lo}–{hi}"}
        else:
            X = cot_td[c['cot']]
            rule = {'condition': {'type': 'ONE_OF_RANGE', 'values': [{'userEnteredValue': f'=TU_DIEN!${X}$3:${X}'}]},
                    'showCustomUi': True, 'strict': c['kieu'] != 'nhieu'}  # chọn nhiều: cho gõ "a, b" (chỉ cảnh báo)
        reqs.append({'setDataValidation': {'range': {'sheetId': ws.id, 'startRowIndex': 2, 'endRowIndex': ws.row_count,
                                                     'startColumnIndex': dau - 1 + i, 'endColumnIndex': dau + i}, 'rule': rule}})
    sh.batch_update({'requests': reqs})
    print(f'✅ Đã ghi: tab TU_DIEN ({len(ds)} cột × {cao} giá trị), SANPHAM {L0}:{L1} hàng 1–2, kiểm tra ô {len(reqs)} cột (hàng 3–{ws.row_count})')
    return 0


def main():
    if '--ghi' in sys.argv:
        return ghi_sheet()
    sp, head, hang1 = doc()
    tu_dien, so_ma = soan(sp, head)
    ghi(tu_dien, head, hang1, so_ma)
    print(f'SANPHAM {so_ma} mã, {len(head)} cột → thêm {len(COT_MOI)} cột từ '
          f'{rowcol_to_a1(1, len(head) + 1).rstrip("1")} đến {rowcol_to_a1(1, len(head) + len(COT_MOI)).rstrip("1")}')
    for c in tu_dien:
        print(f"  {c['cot']}: " + ', '.join(f"{g['gia_tri']}({g['so_ma']})" for g in c['gia_tri']))
    print(f'→ {os.path.relpath(OUT, ROOT)}/ tu_dien.json, TU_DIEN.csv, cot_moi_sanpham.csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
