"""Cột chọn nhiều (anh Kha 29/10): danh sách thả theo TU_DIEN nhưng chỉ CẢNH BÁO, không chặn — ô ghi "a, b" theo thứ tự TU_DIEN.
Đặt lại kiểm tra ô cho các cột trong CHON_NHIEU (Sheet thử trước, chính sau). Chỉ đổi kiểm tra ô, không đổi dữ liệu.

  venv/bin/python tools/chon_nhieu.py [--sheet ID]          # in hiện trạng (strict) từng cột
  venv/bin/python tools/chon_nhieu.py --ghi [--sheet ID]    # GHI
"""
import os
import sys

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import SHEET_ID  # noqa: E402

CHON_NHIEU = ('chat_lieu', 'chat_lieu_de', 'lot_trong', 'lot_de', 'kieu_quai', 'dip')


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ghi = '--ghi' in sys.argv
    ws = _mo(sid, ghi=ghi)
    ss = ws.spreadsheet
    h = [x.strip() for x in ws.row_values(2)]
    th = [x.strip() for x in ss.worksheet('TU_DIEN').row_values(1)]
    rng = [f"SANPHAM!{gspread.utils.rowcol_to_a1(3, h.index(c) + 1)}" for c in CHON_NHIEU]
    meta = ss.fetch_sheet_metadata({'fields': 'sheets(data.rowData.values.dataValidation)', 'ranges': rng})
    hien = [((d.get('rowData') or [{}])[0].get('values') or [{}])[0].get('dataValidation', {}).get('strict', False)
            for d in meta['sheets'][0]['data']]
    print(f'Sheet {sid[:6]}…: ' + ', '.join(f"{c}={'chặn' if s else 'cảnh báo'}" for c, s in zip(CHON_NHIEU, hien)))
    if not ghi:
        return 0
    reqs = []
    for c in CHON_NHIEU:
        j = h.index(c)
        X = gspread.utils.rowcol_to_a1(1, th.index(c) + 1).rstrip('1')
        reqs.append({'setDataValidation': {
            'range': {'sheetId': ws.id, 'startRowIndex': 2, 'endRowIndex': ws.row_count, 'startColumnIndex': j, 'endColumnIndex': j + 1},
            'rule': {'condition': {'type': 'ONE_OF_RANGE', 'values': [{'userEnteredValue': f'=TU_DIEN!${X}$3:${X}'}]}, 'showCustomUi': True, 'strict': False}}})
    ss.batch_update({'requests': reqs})
    meta = ss.fetch_sheet_metadata({'fields': 'sheets(data.rowData.values.dataValidation)', 'ranges': rng})
    sau = [((d.get('rowData') or [{}])[0].get('values') or [{}])[0].get('dataValidation', {}).get('strict', False) for d in meta['sheets'][0]['data']]
    print('✅ Đã đặt chọn nhiều. Đọc lại: ' + ', '.join(f"{c}={'chặn' if s else 'cảnh báo'}" for c, s in zip(CHON_NHIEU, sau)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
