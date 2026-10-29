"""Cột chọn nhiều (anh Kha 29/10): danh sách thả theo TU_DIEN nhưng chỉ CẢNH BÁO, không chặn — ô ghi "a, b" theo thứ tự TU_DIEN.
Đặt lại kiểm tra ô cho các cột trong CHON_NHIEU (Sheet thử trước, chính sau). Không đổi dữ liệu. Cùng lượt (anh Kha 29/10):
- nhãn hàng 1 chat_lieu → "Chất liệu quai / thân" (SANPHAM + TU_DIEN hàng 2);
- cột mới cuối SANPHAM mau_phoi ("Màu phối", để trống) + cột TU_DIEN mau_phoi = màu đang dùng ở product_color (viết thường, bỏ "nhiều màu").
  product_color KHÔNG đổi.

  venv/bin/python tools/chon_nhieu.py [--sheet ID]          # in hiện trạng (strict) từng cột
  venv/bin/python tools/chon_nhieu.py --ghi [--sheet ID]    # GHI
"""
import os
import sys

from collections import Counter

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.tach_cot_sanpham import _mo  # noqa: E402
from tools.tu_dien_sanpham import SHEET_ID  # noqa: E402

CHON_NHIEU = ('chat_lieu', 'chat_lieu_de', 'lot_trong', 'lot_de', 'kieu_quai', 'dip', 'mau_phoi')
NHAN = {'chat_lieu': 'Chất liệu quai / thân'}
MAU_PHOI = ('mau_phoi', 'Màu phối')


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ghi = '--ghi' in sys.argv
    ws = _mo(sid, ghi=ghi)
    ss = ws.spreadsheet
    td = ss.worksheet('TU_DIEN')
    sp = ws.get_all_values()
    h = [x.strip() for x in sp[1]]
    th = [x.strip() for x in td.row_values(1)]
    dem = Counter(' '.join(r[h.index('product_color')].split()).lower() for r in sp[2:] if r[h.index('product_code')].strip())
    mau = [m for m, _ in dem.most_common() if m and m != 'nhiều màu']
    print(f"Sheet {sid[:6]}…: mau_phoi {'đã có' if MAU_PHOI[0] in h else 'thêm cột ' + gspread.utils.rowcol_to_a1(1, len(h) + 1).rstrip('1')}"
          f" · TU_DIEN mau_phoi: {', '.join(mau)} · nhãn chat_lieu: \"{sp[0][h.index('chat_lieu')]}\" → \"{NHAN['chat_lieu']}\"")
    if ghi:
        if MAU_PHOI[0] not in th:
            if td.col_count < len(th) + 1:
                td.add_cols(len(th) + 1 - td.col_count)
            if td.row_count < len(mau) + 2:
                td.add_rows(len(mau) + 2 - td.row_count)
            td.update(range_name=gspread.utils.rowcol_to_a1(1, len(th) + 1), values=[[MAU_PHOI[0]], [MAU_PHOI[1]]] + [[m] for m in mau],
                      value_input_option='RAW')
            th = [x.strip() for x in td.row_values(1)]
        if MAU_PHOI[0] not in h:
            if ws.col_count < len(h) + 1:
                ws.add_cols(len(h) + 1 - ws.col_count)
            ws.update(range_name=gspread.utils.rowcol_to_a1(1, len(h) + 1), values=[[MAU_PHOI[1]], [MAU_PHOI[0]]], value_input_option='RAW')
            h = [x.strip() for x in ws.row_values(2)]
        for c, n in NHAN.items():
            ws.update(range_name=gspread.utils.rowcol_to_a1(1, h.index(c) + 1), values=[[n]], value_input_option='RAW')
            td.update(range_name=gspread.utils.rowcol_to_a1(2, th.index(c) + 1), values=[[n]], value_input_option='RAW')
    elif MAU_PHOI[0] not in h:
        print(f'  (chạy thử) mau_phoi chưa có cột → bỏ qua kiểm tra ô cột này')
    cot = [c for c in CHON_NHIEU if c in h and c in th]
    rng = [f"SANPHAM!{gspread.utils.rowcol_to_a1(3, h.index(c) + 1)}" for c in cot]
    meta = ss.fetch_sheet_metadata({'fields': 'sheets(data.rowData.values.dataValidation)', 'ranges': rng})
    hien = [((d.get('rowData') or [{}])[0].get('values') or [{}])[0].get('dataValidation', {}).get('strict', False)
            for d in meta['sheets'][0]['data']]
    print('  kiểm tra ô: ' + ', '.join(f"{c}={'chặn' if s else 'cảnh báo'}" for c, s in zip(cot, hien)))
    if not ghi:
        return 0
    reqs = []
    for c in cot:
        j = h.index(c)
        X = gspread.utils.rowcol_to_a1(1, th.index(c) + 1).rstrip('1')
        reqs.append({'setDataValidation': {
            'range': {'sheetId': ws.id, 'startRowIndex': 2, 'endRowIndex': ws.row_count, 'startColumnIndex': j, 'endColumnIndex': j + 1},
            'rule': {'condition': {'type': 'ONE_OF_RANGE', 'values': [{'userEnteredValue': f'=TU_DIEN!${X}$3:${X}'}]}, 'showCustomUi': True, 'strict': False}}})
    ss.batch_update({'requests': reqs})
    meta = ss.fetch_sheet_metadata({'fields': 'sheets(data.rowData.values.dataValidation)', 'ranges': rng})
    sau = [((d.get('rowData') or [{}])[0].get('values') or [{}])[0].get('dataValidation', {}).get('strict', False) for d in meta['sheets'][0]['data']]
    print('✅ Đã đặt chọn nhiều. Đọc lại: ' + ', '.join(f"{c}={'chặn' if s else 'cảnh báo'}" for c, s in zip(cot, sau)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
