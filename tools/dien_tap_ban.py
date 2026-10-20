"""Diễn tập dự phòng P0 (20/10): menu Mac ghi 3 dòng BÁN vào Sheet BẢN THỬ khi che_do = master.
CHỈ chạy trên bản thử HNC_Master_BAN_THU — trỏ Sheet thật thì dừng.
Mỗi dòng có ma_dong = MAC-<lần chạy>#n, nguon = mac (cùng luật LuatKho.maDong / main.py).
Chạy thử (không ghi):  venv/bin/python tools/dien_tap_ban.py
Ghi thật vào bản thử:  venv/bin/python tools/dien_tap_ban.py --ghi
"""
import os
import sys

TEST_ID = '1QwH7Y1A45Pb9S0JbfDSkrP-VeUmD_cA6FsKdI4Gmxcw'
os.environ['HNC_SHEET_ID'] = TEST_ID
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import main  # noqa: E402

SO_DONG = 3


def money(v):
    d = ''.join(ch for ch in str(v or '') if ch.isdigit())
    return int(d) if d else 0


def pick_rows(loader):
    """3 dòng còn tồn (mã có giá bán trong SANPHAM), lấy xen kẽ 2 kho."""
    sp = loader.spreadsheet.worksheet('SANPHAM').get_all_values()
    h = [c.strip() for c in sp[1]]
    price = {r[h.index('product_code')].strip().upper(): money(r[h.index('product_price')]) for r in sp[2:] if r[h.index('product_code')].strip()}
    out = []
    for tab, kho in (('KHO15E', '15E'), ('KHOY3C', 'Y3C')):
        v = loader.spreadsheet.worksheet(tab).get_all_values()
        hk = [c.strip() for c in v[0]]
        for r in v[1:]:
            code = r[hk.index('product_code')].strip().upper()
            try:
                ton = float(r[hk.index('current_quantity')] or 0)
            except ValueError:
                ton = 0
            if code and ton > 0 and price.get(code, 0) > 0:
                out.append({'kho': kho, 'code': code, 'color': r[hk.index('product_color')].strip(), 'size': r[hk.index('item_size')].strip(), 'gia': price[code]})
                if len([x for x in out if x['kho'] == kho]) >= 2:
                    break
    return out[:SO_DONG]


def main_():
    ghi = '--ghi' in sys.argv
    assert main.SPREADSHEET_ID == TEST_ID != main.SPREADSHEET_ID_THAT, 'chỉ chạy trên Sheet bản thử'
    loader = main.EngineDataLoader()
    print(f"🧪 Sheet bản thử {TEST_ID} · che_do = {loader.che_do()}")
    if loader.che_do() != 'master':
        print("⛔ che_do đang là web — đổi master trước (menu Mac [7] với HNC_SHEET_ID = bản thử) rồi chạy lại.")
        return 1
    rows = pick_rows(loader)
    if len(rows) < SO_DONG:
        print("⛔ Không đủ 3 mã còn tồn trong bản thử.")
        return 1
    ws = loader.spreadsheet.worksheet('BAN')
    v = ws.get_all_values()
    head = [c.strip() for c in v[0]]
    for c in ('Ngày', 'product_code', 'product_color', 'Giá', 'item_size', 'item_quantity', 'KHO', 'seller', 'ma_dong', 'nguon'):
        if c not in head:
            print(f"⛔ Tab BAN bản thử thiếu cột {c}")
            return 1
    ic = head.index('product_code')
    last = max(i + 1 for i, r in enumerate(v) if i == 0 or (len(r) > ic and r[ic].strip()))
    today = main.datetime.now().strftime('%d/%m/%Y')
    new = []
    for i, x in enumerate(rows, start=1):
        r = [''] * len(head)
        vals = {'Ngày': today, 'product_code': x['code'], 'product_color': x['color'], 'Giá': x['gia'], 'item_size': x['size'],
                'item_quantity': 1, 'KHO': x['kho'], 'seller': 'dien-tap-mac', 'ma_dong': f"MAC-{main.MAC_RUN_ID}#{i}", 'nguon': 'mac'}
        for k, val in vals.items():
            r[head.index(k)] = val
        new.append(r)
        print(f"  dòng {last + i}: {x['kho']} {x['code']} size {x['size']} · {x['gia']:,}đ · {vals['ma_dong']}")
    if not ghi:
        print("Chạy thử — chưa ghi. Thêm --ghi để ghi vào bản thử.")
        return 0
    if not loader.insert_rows_with_exact_range('BAN', new, last + 1):
        return 1
    print(f"✅ Đã ghi {len(new)} dòng BAN vào bản thử (dòng {last + 1}–{last + len(new)}).")
    return 0


if __name__ == '__main__':
    sys.exit(main_())
