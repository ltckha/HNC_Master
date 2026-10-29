"""Thêm 1 giá trị vào cột TU_DIEN (cuối danh sách, bỏ qua nếu đã có). Ghi Sheet thử trước, chính sau.

  venv/bin/python tools/them_tu_dien.py <cot> "<giá trị>" [--sheet ID]
"""
import os
import sys

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import SHEET_ID  # noqa: E402


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    a = [x for x in a if x != sid]
    cot, gt = a[0], a[1]
    td = _mo(sid, ghi=True).spreadsheet.worksheet('TU_DIEN')
    h = [x.strip() for x in td.row_values(1)]
    j = h.index(cot) + 1
    cu = td.col_values(j)
    if gt in [x.strip() for x in cu[2:]]:
        print(f'Sheet {sid[:6]}…: TU_DIEN {cot} đã có "{gt}"')
        return 0
    if len(cu) + 1 > td.row_count:
        td.add_rows(len(cu) + 1 - td.row_count)
    td.update(range_name=gspread.utils.rowcol_to_a1(len(cu) + 1, j), values=[[gt]], value_input_option='RAW')
    print(f'✅ Sheet {sid[:6]}…: TU_DIEN {cot}: ' + ', '.join(td.col_values(j)[2:]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
