"""Mã cột cũ "Mặt lót đế:" ghi "mềm êm…" (523 mã — có loại mút, có loại cao su non, anh Kha 29/10): gom theo NCC + ngành để anh chọn theo nhóm.
CHẠY THỬ (chỉ đọc Sheet) → docs/sanpham_chuan/nhom_mem_em.csv: nhom, ncc (nội bộ), nganh, so_ma, so_mau_cha, ma_vi_du, lot_de_moi (đang có ở
cột mới trong nhóm), cung_nhom_khac (mã cùng NCC + ngành KHÔNG ghi "mềm êm": lot_de mới / chữ cột cũ → số mã).

  venv/bin/python tools/nhom_mem_em.py [--sheet ID]
"""
import csv
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID, chuan  # noqa: E402


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    sp = _mo(sid).get_all_values()
    h = [x.strip() for x in sp[1]]
    c = {k: h.index(k) for k in ('product_code', 'parent_product_code', 'supplier', 'Tên Ngành Hàng', 'Mặt lót đế:', 'lot_de')}
    dong = [r for r in sp[2:] if r[c['product_code']].strip()]
    khoa = lambda r: (r[c['supplier']].strip() or '(trống)', r[c['Tên Ngành Hàng']].strip() or '(trống)')  # noqa: E731
    mem = defaultdict(list)
    khac = defaultdict(Counter)
    for r in dong:
        cu = chuan(r[c['Mặt lót đế:']])
        if cu.startswith('mềm êm'):
            mem[khoa(r)].append(r)
        else:
            moi = r[c['lot_de']].strip()
            if moi or cu:
                khac[khoa(r)][f"{moi or '-'} / {cu or '-'}"] += 1
    nhom = sorted(mem.items(), key=lambda x: -len(x[1]))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'nhom_mem_em.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['nhom', 'ncc', 'nganh', 'so_ma', 'so_mau_cha', 'ma_vi_du', 'lot_de_moi', 'cung_nhom_khac (lot_de mới / cột cũ: số mã)'])
        for i, ((ncc, ng), rs) in enumerate(nhom, start=1):
            cha = {r[c['parent_product_code']].strip() or r[c['product_code']].strip()[:-1] for r in rs}
            vd = []
            for r in rs:  # ví dụ khác mẫu cha
                p = r[c['parent_product_code']].strip() or r[c['product_code']].strip()[:-1]
                if p not in {x[0] for x in vd}:
                    vd.append((p, r[c['product_code']].strip()))
                if len(vd) == 3:
                    break
            moi = Counter(r[c['lot_de']].strip() for r in rs if r[c['lot_de']].strip())
            w.writerow([i, ncc, ng, len(rs), len(cha), ' '.join(m for _, m in vd), '; '.join(f'{k}: {n}' for k, n in moi.most_common()),
                        '; '.join(f'{k}: {n}' for k, n in khac[(ncc, ng)].most_common(4))])
    print(f'Sheet {sid[:6]}…: {sum(len(v) for v in mem.values())} mã "mềm êm…" → {len(nhom)} nhóm NCC + ngành '
          f'(nhóm ≥ 10 mã: {sum(1 for _, v in nhom if len(v) >= 10)}, có mã cùng nhóm ghi khác: {sum(1 for k, _ in nhom if khac[k])})')
    print(f'→ {os.path.relpath(OUT, ROOT)}/nhom_mem_em.csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
