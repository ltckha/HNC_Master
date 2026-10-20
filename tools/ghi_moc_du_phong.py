"""Ghi mốc dự phòng vào META (tối hôm trước ngày chuyển 4 sổ, sau đóng cửa — anh Kha duyệt tại phiên Thực thi – HNC_Master).
Mốc = giờ chạy + hàng cuối có mã của BAN / NHAP / XUAT → web nhập bù đúng các dòng bot / Mac ghi sau mốc.
Ghi: du_phong_tu, du_phong_hang (BAN), du_phong_kho_tu, du_phong_nhap_hang (NHAP), du_phong_xuat_hang (XUAT). Không đổi che_do.
  Chạy thử (không ghi):     venv/bin/python tools/ghi_moc_du_phong.py [--sheet thu|that]
  Ghi thật:                 venv/bin/python tools/ghi_moc_du_phong.py --sheet that --ghi
Mặc định Sheet bản thử."""
import os
import sys
from datetime import datetime

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEETS = {'thu': '1QwH7Y1A45Pb9S0JbfDSkrP-VeUmD_cA6FsKdI4Gmxcw', 'that': '1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0'}


def last_code_row(ws):
    v = ws.get_all_values()
    ic = [c.strip() for c in v[0]].index('product_code')
    return max(i + 1 for i, r in enumerate(v) if i == 0 or (len(r) > ic and r[ic].strip()))


def main():
    which = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else 'thu'
    sh = gspread.service_account(filename=os.path.join(ROOT, 'credentials.json')).open_by_key(SHEETS[which])
    luc = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pairs = {'du_phong_tu': luc, 'du_phong_hang': str(last_code_row(sh.worksheet('BAN'))),
             'du_phong_kho_tu': luc, 'du_phong_nhap_hang': str(last_code_row(sh.worksheet('NHAP'))),
             'du_phong_xuat_hang': str(last_code_row(sh.worksheet('XUAT')))}
    meta = {r[0]: r[1] for r in sh.worksheet('META').get_all_values()[1:] if r}
    print(f"Sheet {'CHÍNH' if which == 'that' else 'bản thử'} · che_do {meta.get('che_do', 'master')} / kho {meta.get('che_do_kho', 'master')} · mốc: {pairs}")
    if '--ghi' not in sys.argv:
        print('Chạy thử — chưa ghi. Thêm --ghi để ghi.')
        return 0
    ws = sh.worksheet('META')
    v = ws.get_all_values()
    head = [c.strip() for c in v[0]]
    ck, cv, cu = head.index('key'), head.index('value'), head.index('updated_at')
    cells, nxt = [], len(v) + 1
    for k, val in pairs.items():
        r = next((i + 1 for i in range(1, len(v)) if v[i] and v[i][ck].strip() == k), None)
        if r is None:
            r, nxt = nxt, nxt + 1
            cells.append(gspread.Cell(r, ck + 1, k))
        cells += [gspread.Cell(r, cv + 1, val), gspread.Cell(r, cu + 1, luc)]
    ws.update_cells(cells, value_input_option='RAW')
    print(f'✅ Đã ghi mốc lúc {luc}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
