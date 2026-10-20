"""Kiểm shared/hop_dong_du_lieu.json khớp tiêu đề Sheet HNC thật (CHỈ ĐỌC). Chạy: venv/bin/python tools/kiem_hop_dong.py
Báo: cột hợp đồng thiếu trên Sheet (trừ cột du_kien), cột Sheet chưa có trong hợp đồng."""
import json
import os
import sys

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET_ID = '1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0'


def main():
    hd = json.load(open(os.path.join(ROOT, 'shared', 'hop_dong_du_lieu.json'), encoding='utf-8'))
    sh = gspread.service_account(filename=os.path.join(ROOT, 'credentials.json')).open_by_key(SHEET_ID)
    lech = 0
    for ws in sh.worksheets():
        t = hd['tab'].get(ws.title)
        if not t:
            print(f'⚠️ Tab {ws.title} chưa có trong hợp đồng'); lech += 1; continue
        head = [c.strip() for c in ws.row_values(t['hang_tieu_de']) if c.strip()]
        meta_keys = [r[0].strip() for r in ws.get_all_values()[1:]] if ws.title == 'META' else []
        thieu = [c for c, x in t['cot'].items() if not x.get('du_kien') and c not in head]
        thua = [c for c in head if c not in t['cot']]
        if ws.title == 'META':
            thieu = [c for c in thieu if c not in meta_keys]
        for c in thieu:
            print(f'❌ {ws.title}: thiếu cột {c}'); lech += 1
        for c in thua:
            print(f'⚠️ {ws.title}: cột {c} chưa có trong hợp đồng'); lech += 1
    print('✅ Hợp đồng khớp Sheet' if not lech else f'{lech} chỗ lệch')
    return 1 if lech else 0


if __name__ == '__main__':
    sys.exit(main())
