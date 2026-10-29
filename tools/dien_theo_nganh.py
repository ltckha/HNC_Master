"""Điền ô TRỐNG của hàng cũ theo chính dữ liệu sổ (anh Kha 29/10): với mỗi (ngành, cột), nếu ≥ 95% mã ĐÃ ghi cùng 1 giá trị
và ≥ 15 mã đã ghi → điền giá trị đó vào ô trống của ngành. Không đè ô đã có. Không áp cột số đo / riêng từng mẫu (BO_QUA).
Giá trị ô chọn nhiều so nguyên chuỗi. CHẠY THỬ → docs/sanpham_chuan/dien_theo_nganh.csv; --ghi để ghi (Sheet thử trước, chính sau).

  venv/bin/python tools/dien_theo_nganh.py [--ghi] [--sheet ID]
"""
import csv
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID  # noqa: E402

COT = ['gioi_tinh', 'chat_lieu', 'kieu_dong', 'kieu_quai', 'dang_mui', 'kieu_de', 'chat_lieu_de', 'lot_trong', 'lot_de', 'be_mat', 'co_giay', 'dip']
BO_QUA = ('do_om', 'chon_size', 'mau_phoi', 'kieu_giay_tay', 'cao_got_cm', 'tang_cao_cm')  # không áp (anh Kha 29/10)
TI_LE, TOI_THIEU = 0.95, 20  # nâng 15 → 20 (anh Kha 29/10)
# Cột cũ cùng ý có chữ mà không chuyển được (vd Mặt lót đế "mềm êm" — anh nói có loại mút, có loại cao su non) → để trống, không điền theo đa số
COT_CU = {'dang_mui': ['Dáng giày mũi:'], 'chat_lieu': ['Chất liệu', 'Chất liệu quai:'], 'chat_lieu_de': ['Chất liệu đế:'],
          'lot_trong': ['Lót trong:'], 'lot_de': ['Mặt lót đế:']}


def de_xuat(sp, h):
    """→ [(ngành, cột, giá trị, tỉ lệ, số mã đã ghi, [số hàng ô trống])]"""
    ic, ing = h.index('product_code'), h.index('Tên Ngành Hàng')
    nhom = defaultdict(list)
    for i, r in enumerate(sp[2:], start=3):
        if r[ic].strip() and r[ing].strip():
            nhom[r[ing].strip()].append((i, r))
    out = []
    for ng, ds in sorted(nhom.items()):
        for c in COT:
            j = h.index(c)
            co = Counter(r[j].strip() for _, r in ds if r[j].strip())
            n = sum(co.values())
            if n < TOI_THIEU:
                continue
            v, k = co.most_common(1)[0]
            cu = [h.index(x) for x in COT_CU.get(c, []) if x in h]
            trong = [i for i, r in ds if not r[j].strip() and not any(r[k].strip() for k in cu)]  # cột cũ cùng ý có chữ (vd "mềm êm") → không điền
            if k / n >= TI_LE and trong:
                out.append((ng, c, v, k / n, n, trong))
    return out


def main():
    import gspread
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ghi = '--ghi' in sys.argv
    ws = _mo(sid, ghi=ghi)
    sp = ws.get_all_values()
    h = [x.strip() for x in sp[1]]
    ds = de_xuat(sp, h)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'dien_theo_nganh.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['nganh', 'cot', 'gia_tri', 'ti_le', 'so_ma_da_ghi', 'so_o_se_dien'])
        for ng, c, v, tl, n, tr in ds:
            w.writerow([ng, c, v, f'{tl:.0%}', n, len(tr)])
    tong = sum(len(x[5]) for x in ds)
    print(f'Sheet {sid[:6]}…: {len(ds)} (ngành, cột) đạt ≥ {TI_LE:.0%} và ≥ {TOI_THIEU} mã → điền {tong} ô trống')
    dc = Counter()
    for _, c, _, _, _, tr in ds:
        dc[c] += len(tr)
    print('  theo cột: ' + ', '.join(f'{c} {n}' for c, n in dc.most_common()))
    print(f'→ {os.path.relpath(OUT, ROOT)}/dien_theo_nganh.csv')
    if ghi and ds:
        up = [{'range': gspread.utils.rowcol_to_a1(i, h.index(c) + 1), 'values': [[v]]} for _, c, v, _, _, tr in ds for i in tr]
        for k in range(0, len(up), 500):
            ws.batch_update(up[k:k + 500], value_input_option='RAW')
        print(f'✅ Đã ghi {len(up)} ô')
    return 0


if __name__ == '__main__':
    sys.exit(main())
