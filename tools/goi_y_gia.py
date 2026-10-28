"""Gợi ý giá bán mã mới (Agent đăng SP GĐ3b, anh Kha "LÀM" 28/10) — chạy 13:30 hằng ngày (launchd vn.giayhainancy.hnc.goiygia).
Mã cần gợi ý: mã đang chờ duyệt trên web (POST /api/mo-ta/mac act 'cho'); web không trả được thì mã có phiếu nhập đầu tiên trong 7 ngày.
Luật: shared/luat_gia.js (chung Mac / bot / web) — giá nhập lô mới nhất (don_gia_hd → don_gia_phieu) rồi giá theo mã (purchase_price →
invoice_price, anh Kha 28/10); tỷ lệ trung vị cùng NCC + nhóm hàng (≥ 5 mã), thiếu thì cùng nhóm; làm tròn theo giá tem.
Gửi web: loai goi_y_gia qua /api/bot-lenh (ký khoá Mac). Chỉ ĐỌC Sheet, không ghi.

  venv/bin/python tools/goi_y_gia.py [--dry] [--khong-gui] [--ma MÃ,MÃ]
  --dry: web chỉ kiểm (dry_run), --khong-gui: chỉ in. Gốc web: HNC_WEB_ORIGIN (thử beta) hoặc SYNC_HINT_URL (.env).
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import web_lenh  # noqa: E402
from tools.luat_kho_node import goi_gia  # noqa: E402

SHEET_ID = os.getenv("HNC_SHEET_ID", "").strip() or "1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0"  # như main.py
NGAY_MOI = 7
# Tên cột (luật 4) — SANPHAM tên kỹ thuật ở hàng 2, NHAP ở hàng 1
SP_COT = {'code': 'product_code', 'gia_ban': 'product_price', 'inv': 'invoice_price', 'pur': 'purchase_price', 'ncc': 'supplier', 'nhom': 'Tên Ngành Hàng'}
NH_COT = {'code': 'product_code', 'ngay': 'Ngày chứng từ (*)', 'hd': 'don_gia_hd', 'phieu': 'don_gia_phieu'}


def mo_sheet():
    creds = Credentials.from_service_account_file(os.path.join(ROOT, 'credentials.json'),
                                                  scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    return gspread.authorize(creds).open_by_key(SHEET_ID)


def _idx(head, cot, tab):
    thieu = [n for n in cot.values() if n not in head]
    if thieu:
        raise RuntimeError(f'Tab {tab} thiếu cột {thieu}')
    return {k: head.index(n) for k, n in cot.items()}


def _o(r, i):
    return str(r[i]).strip() if i < len(r) else ''


def doc(sh):
    sp = sh.worksheet('SANPHAM').get_all_values()
    i = _idx([c.strip() for c in sp[1]], SP_COT, 'SANPHAM')
    ma = {}
    for r in sp[2:]:
        code = _o(r, i['code']).upper()
        if code:
            ma[code] = {'code': code, 'ncc': _o(r, i['ncc']), 'nhom': _o(r, i['nhom']), 'gia_ban': _o(r, i['gia_ban']),
                        'invoice_price': _o(r, i['inv']), 'purchase_price': _o(r, i['pur'])}
    nh = sh.worksheet('NHAP').get_all_values()
    j = _idx([c.strip() for c in nh[0]], NH_COT, 'NHAP')
    lo, dau = {}, {}
    for r in nh[1:]:
        code = _o(r, j['code']).upper()
        if not code or code == 'PRODUCT_CODE':
            continue
        if _o(r, j['hd']) or _o(r, j['phieu']):
            lo[code] = {'don_gia_hd': _o(r, j['hd']), 'don_gia_phieu': _o(r, j['phieu'])}  # dòng sau = lô mới hơn
        try:
            d = datetime.strptime(_o(r, j['ngay']), '%d/%m/%Y')
            dau[code] = min(dau.get(code, d), d)
        except ValueError:
            pass
    return ma, lo, dau


def ma_can(dau, chi_ma):
    if chi_ma:
        return chi_ma, 'chỉ định'
    ds, loi = web_lenh.ma_cho_duyet()
    if ds is not None:
        return ds, 'web: mã chờ duyệt'
    moc = datetime.now() - timedelta(days=NGAY_MOI)
    print(f'⚠ Không lấy được mã chờ duyệt từ web ({loi}) → dùng mã nhập lần đầu trong {NGAY_MOI} ngày')
    return sorted(c for c, d in dau.items() if d >= moc), f'mã mới {NGAY_MOI} ngày'


def tinh(ma, lo, can):
    can = set(can)
    mau = [x for c, x in ma.items() if c not in can]  # gia_nhap tính trong luat_gia.js (giá theo mã)
    ds, khong = [], []
    for c in sorted(can):
        x = ma.get(c)
        if not x:
            khong.append({'code': c, 'loi': 'chưa có trong SANPHAM'})
            continue
        ds.append(dict(x, lo=lo.get(c, {})))
    kq = goi_gia('goiYGiaLo', ds, mau) if ds else []
    return [k for k in kq if 'gia' in k], [k for k in kq if 'gia' not in k] + khong


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry', action='store_true', help='web chỉ kiểm (dry_run), không lưu')
    ap.add_argument('--khong-gui', action='store_true', help='chỉ tính và in, không gọi web')
    ap.add_argument('--ma', default='', help='mã cách nhau dấu phẩy (bỏ qua danh sách chờ duyệt)')
    a = ap.parse_args()
    print(f"— Gợi ý giá {datetime.now():%d/%m/%Y %H:%M} · web {web_lenh._goc() or '(chưa đặt)'}")
    ma, lo, dau = doc(mo_sheet())
    can, nguon = ma_can(dau, [x.strip().upper() for x in a.ma.split(',') if x.strip()])
    print(f'Mã cần gợi ý ({nguon}): {len(can)}')
    if not can:
        return 0
    co, loi = tinh(ma, lo, can)
    for k in co:
        print(f"  {k['code']}: " + f"{k['gia']:,}".replace(',', '.') + f"đ — {k['ly_do']}")
    for k in loi:
        print(f"  {k['code']}: bỏ — {k['loi']}")
    if a.khong_gui or not co:
        return 0
    w = web_lenh.goi_y_gia([{'code': k['code'], 'gia': k['gia'], 'ly_do': k['ly_do']} for k in co], dry_run=a.dry)
    if not w.get('ok'):
        print(f"❌ Web chưa nhận: {w.get('error')}")
        return 1
    print(f"✅ Web {'kiểm (dry_run)' if a.dry else 'đã lưu'}: {w.get('so')} mã" + (f" · {w.get('text')}" if w.get('text') else ''))
    for x in w.get('loi') or []:
        print(f"  web bỏ {x.get('code')}: {x.get('ly_do')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
