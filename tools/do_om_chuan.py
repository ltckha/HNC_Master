"""Hàng CŨ (anh Kha 29/10): mọi mã giày dép, ô do_om trống → "chuẩn", ô chon_size trống → "đúng size" (anh nhớ mẫu nào khác thì tự sửa).
Không đè ô đã có; ví / túi / thắt lưng / phụ kiện không áp. Hàng MỚI không tự điền 2 ô này (main.py không chép từ mẫu cha).

  venv/bin/python tools/do_om_chuan.py [--ghi] [--sheet ID]
"""
import os
import re
import sys
from collections import Counter

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import SHEET_ID  # noqa: E402

GIA_TRI = {'do_om': 'chuẩn', 'chon_size': 'đúng size'}
GIAY_DEP = re.compile(r'^(giày|dép|sandal|sapo|guốc)|bốt', re.I)


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ghi = '--ghi' in sys.argv
    ws = _mo(sid, ghi=ghi)
    sp = ws.get_all_values()
    h = [x.strip() for x in sp[1]]
    ic, ing = h.index('product_code'), h.index('Tên Ngành Hàng')
    up, dem, co = [], Counter(), Counter()
    for i, r in enumerate(sp[2:], start=3):
        if not r[ic].strip() or not GIAY_DEP.search(' '.join(r[ing].split())):
            continue
        for c, v in GIA_TRI.items():
            j = h.index(c)
            cur = r[j].strip() if j < len(r) else ''
            if cur:
                co[(c, cur)] += 1
            else:
                up.append({'range': gspread.utils.rowcol_to_a1(i, j + 1), 'values': [[v]]})
                dem[c] += 1
    print(f'Sheet {sid[:6]}…: điền {len(up)} ô {dict(dem)} · giữ ô đã có {dict(co)}')
    if ghi and up:
        for k in range(0, len(up), 500):
            ws.batch_update(up[k:k + 500], value_input_option='RAW')
        print(f'✅ Đã ghi {len(up)} ô')
    return 0


if __name__ == '__main__':
    sys.exit(main())
