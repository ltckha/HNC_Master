"""Thuộc tính đọc được từ TÊN HÀNG (product_name / CON_NAME) cho ô cột mới đang trống (anh Kha 29/10: "có sẵn rồi sao bắt tôi chọn lại").
Từ khoá → giá trị TU_DIEN (chỉ từ khoá rõ nghĩa, không đoán). CHẠY THỬ → docs/sanpham_chuan/tu_ten.csv (ma, cot, tu_khoa, gia_tri, ten);
--ghi để ghi (Sheet thử trước, chính sau). Dùng chung với tools/nhom_trong.py (ô có từ tên thì không tính là trống).

  venv/bin/python tools/tu_ten.py [--ghi] [--sheet ID]
"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID  # noqa: E402

TU_KHOA = {  # cột mới → [(từ khoá trong tên, viết thường), giá trị TU_DIEN]; từ khoá dài đặt trước
    'kieu_dong': [('xỏ chân', 'xỏ chân'), ('cột dây', 'cột dây'), ('buộc dây', 'cột dây'), ('khoá kéo 2 bên', 'khoá kéo 2 bên'),
                  ('khóa kéo 2 bên', 'khoá kéo 2 bên'), ('khoá kéo', 'khoá kéo 1 bên'), ('khóa kéo', 'khoá kéo 1 bên'), ('xé dán', 'xé dán'),
                  ('cổ chun', 'cổ thun'), ('cổ thun', 'cổ thun')],
    'kieu_quai': [('quai ngang', 'quai ngang'), ('quai chéo', 'quai chéo'), ('quai kẹp', 'kẹp ngón (xỏ ngón)'), ('xỏ ngón', 'kẹp ngón (xỏ ngón)'),
                  ('quai hậu', 'quai hậu')],
    'dang_mui': [('mũi nhọn', 'nhọn'), ('mũi vuông', 'vuông'), ('mũi tròn', 'tròn')],
    'kieu_de': [('đế xuồng', 'đế xuồng'), ('đế bằng', 'đế bằng')],
    'be_mat': [('da lộn', 'da lộn'), ('da bóng', 'da bóng')],
    'co_giay': [('cổ lửng', 'cổ lửng'), ('cổ cao', 'cổ cao'), ('cổ thấp', 'cổ thấp')],
    'kieu_giay_tay': [('oxford', 'Oxford (buộc dây kín)'), ('derby', 'Derby (buộc dây hở)'), ('loafer', 'giày lười (loafer)'),
                      ('giày lười', 'giày lười (loafer)'), ('monk', 'khoá cài (monk)'), ('chelsea', 'bốt cổ chun (Chelsea)'),
                      ('brogue', 'đục lỗ (brogue)'), ('đục lỗ', 'đục lỗ (brogue)')],
}
CHI_GIAY_TAY = ('giày tây', 'giày mọi nam', 'sapo', 'bốt nam')  # kieu_giay_tay chỉ các ngành này
KHONG_AP = {'kieu_giay_tay': lambda ng: not any(x in ng for x in CHI_GIAY_TAY),
            'kieu_quai': lambda ng: not ('dép' in ng or 'sandal' in ng)}


CHO_ANH = set()  # 3 mã MT (kieu_de) dùng tên hàng "đế xuồng" — Phân tích 29/10


def tu_ten(r, h):
    """1 dòng SANPHAM → {cột: (giá trị, từ khoá)} cho cột mới đang TRỐNG mà tên hàng nói ra."""
    g = lambda c: r[h.index(c)].strip() if c in h and h.index(c) < len(r) else ''  # noqa: E731
    ten = (g('product_name') + ' ' + g('CON_NAME')).lower()
    ng = g('Tên Ngành Hàng').lower()
    out = {}
    for c, ds in TU_KHOA.items():
        if g(c) or (c in KHONG_AP and KHONG_AP[c](ng)) or (g('product_code').upper(), c) in CHO_ANH:
            continue
        for k, v in ds:
            if k in ten:
                out[c] = (v, k)
                break
    return out


def main():
    import gspread
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ghi = '--ghi' in sys.argv
    ws = _mo(sid, ghi=ghi)
    sp = ws.get_all_values()
    h = [x.strip() for x in sp[1]]
    ic = h.index('product_code')
    rows, up, dem = [], [], Counter()
    for i, r in enumerate(sp[2:], start=3):
        if not r[ic].strip():
            continue
        for c, (v, k) in tu_ten(r, h).items():
            rows.append([r[ic].strip(), c, k, v, r[h.index('product_name')].strip()])
            up.append({'range': gspread.utils.rowcol_to_a1(i, h.index(c) + 1), 'values': [[v]]})
            dem[c] += 1
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'tu_ten.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ma', 'cot', 'tu_khoa', 'gia_tri', 'ten'])
        w.writerows(rows)
    print(f'Sheet {sid[:6]}…: {len(up)} ô điền được từ tên hàng {dict(dem)} → {os.path.relpath(OUT, ROOT)}/tu_ten.csv')
    if ghi and up:
        ws.batch_update(up, value_input_option='RAW')
        print(f'✅ Đã ghi {len(up)} ô')
    return 0


if __name__ == '__main__':
    sys.exit(main())
