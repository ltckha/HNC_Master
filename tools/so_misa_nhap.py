"""So file MISA "Nhập kho mua hàng" giữa HNC và web (K12, 20/10) — CHỈ ĐỌC Sheet.
Dựng 22 cột từng dòng NHAP của 1 phiếu theo luật chung (LuatKho.giaMisa + misaNhapDong — khớp bot misaStockExport_ và
main.py task 8, ca mẫu 74/74), lấy NCC qua SANPHAM.supplier → bảng NCC ở SUB. Bỏ qua cờ misa_stock (để so được phiếu đã xuất).
  venv/bin/python tools/so_misa_nhap.py NK000025 15E [--sheet <id>] [--so <file web .xlsx|.json>]
Mặc định Sheet bản thử. --so: file web xuất (xlsx mẫu MISA từ dòng 9, hoặc JSON [{"1":…,"22":…}]) → so từng ô.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gspread  # noqa: E402
from tools.luat_kho_node import goi  # noqa: E402

TEST_ID = '1QwH7Y1A45Pb9S0JbfDSkrP-VeUmD_cA6FsKdI4Gmxcw'
KHO_MISA = {'15E': '15ETBH', 'Y3C': '3CTBH'}


def arg(name, default=''):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def rows_of(ws, header_row=1):
    v = ws.get_all_values()
    h = [c.strip() for c in v[header_row - 1]]
    return [dict(zip(h, r)) for r in v[header_row:]], h


def dung(so_ct, kho, sheet_id):
    sh = gspread.service_account(filename=os.path.join(ROOT, 'credentials.json')).open_by_key(sheet_id)
    nh, _ = rows_of(sh.worksheet('NHAP'))
    sp, _ = rows_of(sh.worksheet('SANPHAM'), 2)
    sub, _ = rows_of(sh.worksheet('SUB'))
    prod = {r['product_code'].strip().upper(): r for r in sp if r.get('product_code', '').strip()}
    sups = {r['supplier'].strip().lower(): r for r in sub if r.get('supplier', '').strip()}
    out = []
    for i, r in enumerate(nh, start=2):
        if r.get('Số chứng từ (*)', '').strip().upper() != so_ct.upper() or goi('khoChuan', r.get('KHO', '')) != kho:
            continue
        code = r['product_code'].strip().upper()
        p = prod.get(code, {})
        g = goi('giaMisa', {'don_gia_hd': r.get('don_gia_hd'), 'don_gia_phieu': r.get('don_gia_phieu'), 'invoice_price': p.get('invoice_price'),
                            'purchase_price': p.get('purchase_price'), 'so_hd': r.get('so_hd')})
        s = sups.get(p.get('supplier', '').strip().lower(), {})
        d = goi('misaNhapDong', {'so_ct': r['Số chứng từ (*)'].strip(), 'ngay': r['Ngày chứng từ (*)'].strip()[:10],
                                 'sku': code + goi('chuanSize', r.get('item_size')), 'kho_misa': KHO_MISA.get(kho, ''), 'dvt': p.get('product_unit', ''),
                                 'sl': float(r.get('Số lượng (*)') or 0), 'don_gia': g['gia'], 'ncc_ma': s.get('Mã đối tượng', ''), 'ncc_ten': s.get('Tên đối tượng', ''),
                                 'ck': s.get('% chiết khấu', ''), 'vat': s.get('Thuế suất', ''), 'so_hd': r.get('so_hd', '').strip(),
                                 'ngay_hd': r.get('ngay_hd', '').strip(), 'gia_cu': g['gia_cu']})
        out.append({'dong_sheet': i, 'gia': g, 'loi': d['loi'], 'cot': d['cot']})
    return out


def doc_web(path):
    if path.endswith('.json'):
        return json.load(open(path, encoding='utf-8'))
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    return [{str(c): row[c - 1] for c in range(1, 23)} for row in ws.iter_rows(min_row=9, values_only=True) if row and row[0]]


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 0.01
    except (TypeError, ValueError):
        return str(a or '').strip() == str(b or '').strip()


def main():
    so_ct, kho = sys.argv[1], sys.argv[2].upper()
    hnc = dung(so_ct, kho, arg('--sheet', TEST_ID))
    print(f"HNC dựng {len(hnc)} dòng cho {so_ct} kho {kho}")
    for x in hnc:
        print(f"  dòng {x['dong_sheet']}: giá {x['gia']['gia']} ({x['gia']['nguon']}) · NCC {x['cot'].get('5', '')} · lỗi {x['loi'] or '-'}")
    json.dump(hnc, open(f'/tmp/misa_hnc_{so_ct}_{kho}.json', 'w'), ensure_ascii=False, indent=1)
    web_path = arg('--so')
    if not web_path:
        print(f"Đã ghi /tmp/misa_hnc_{so_ct}_{kho}.json (chưa so — thêm --so <file web>)")
        return 0
    web = doc_web(web_path)
    lech = 0
    hnc_ok = [x['cot'] for x in hnc if not x['loi']]
    if len(hnc_ok) != len(web):
        print(f"❌ Số dòng khác: HNC {len(hnc_ok)} · web {len(web)}")
        lech += 1
    for i, (a, b) in enumerate(zip(hnc_ok, web), start=1):
        for c in range(1, 23):
            va, vb = a.get(str(c), ''), b.get(str(c), '')
            if not same(va, vb):
                print(f"❌ dòng {i} cột {c}: HNC {va!r} · web {vb!r}")
                lech += 1
    print('✅ 22 cột khớp từng dòng' if not lech else f'{lech} chỗ lệch')
    return 1 if lech else 0


if __name__ == '__main__':
    sys.exit(main())
