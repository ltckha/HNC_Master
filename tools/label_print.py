"""In tem tự động qua Brother QL-700 (V34 mục 6, anh Kha "làm" 18/10). Chạy trên Mac mini (máy in cắm USB ở 15E).

Luồng: bot (cửa in_tem) ghi My Drive/IN Mini Code/IN_<kho>.csv + cờ IN_<kho>.can_in (JSON: kho, dong, so_tem…)
→ launchd gọi file này mỗi 30 giây → dựng tem (tools/label_render.py) → brother_ql in qua USB (không cần driver Brother)
→ in được hết thì ghi NHAP.web_label = "Done - <giờ>" cho đúng các dòng → ghi IN_<kho>.ket_qua.json → xoá cờ.
Lỗi (máy tắt, chưa cắm USB, Editor Lite còn bật, hết giấy) → KHÔNG đánh dấu, ghi lỗi vào ket_qua.json, giữ cờ để thử lại.
Không gửi Zalo. Chạy tay: venv/bin/python tools/label_print.py [--thu]   (--thu: dựng ảnh tem vào /tmp, không in)
"""
import csv
import fcntl
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from hnc_paths import in_csv_path  # noqa: E402
import label_render  # noqa: E402

MODEL = 'QL-700'
KHOS = ('15E', 'Y3C')
SHEET_ID = '1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0'
MAX_AGE_MIN = 30  # cờ cũ hơn thì bỏ, không để máy in vừa bật lên in tem của sáng nay
ERR_HINT = 'Không thấy máy in QL-700: kiểm máy đã bật, cắm USB vào Mac mini, và đã TẮT Editor Lite (giữ nút Editor Lite tới khi đèn tắt).'


def folder():
    return os.path.dirname(in_csv_path())


def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def csv_matches(req, records):
    """IN_<kho>.csv đã đồng bộ đúng lần yêu cầu này chưa (cùng mã hàng, cùng tổng số tem)."""
    codes = [r.get('Code128', '').strip().upper() for r in records]
    try:
        total = sum(max(1, int(float(r.get('F6') or 1))) for r in records)
    except ValueError:
        return False
    return sorted(codes) == sorted(str(x).upper() for x in req.get('ma_hang', [])) and total == int(req.get('so_tem') or total)


def find_printer():
    """Địa chỉ USB của QL-700 (brother_ql + pyusb). None nếu không thấy."""
    from brother_ql.backends.helpers import discover
    devs = [d for d in discover(backend_identifier='pyusb') if 'usb://' in str(d.get('identifier', ''))]
    return devs[0]['identifier'] if devs else None


def print_records(records, kho, dry=False):
    """In các dòng tem (mỗi dòng in F6 tờ). Trả {ok, so_tem, loi}."""
    images = []
    for r in records:
        try:
            n = max(1, int(float(r.get('F6') or 1)))
        except ValueError:
            n = 1
        img = label_render.render_label(r, kho)
        images.extend([img] * n)
    if not images:
        return {'ok': False, 'so_tem': 0, 'loi': 'không có tem nào'}
    if dry:
        for i, im in enumerate(images[:3]):
            im.save(f'/tmp/tem_thu_{kho}_{i + 1}.png')
        return {'ok': True, 'so_tem': len(images), 'loi': '', 'thu': True}
    try:
        from brother_ql.raster import BrotherQLRaster
        from brother_ql.conversion import convert
        from brother_ql.backends.helpers import send
    except ImportError as e:
        return {'ok': False, 'so_tem': len(images), 'loi': f'thiếu thư viện brother_ql ({e})'}
    ident = find_printer()
    if not ident:
        return {'ok': False, 'so_tem': len(images), 'loi': ERR_HINT}
    qlr = BrotherQLRaster(MODEL)
    instructions = convert(qlr=qlr, images=images, label=label_render.LABEL_ID, rotate='0', threshold=70.0,
                           dither=False, compress=False, red=False, dpi_600=False, hq=True, cut=True)
    try:
        st = send(instructions=instructions, printer_identifier=ident, backend_identifier='pyusb', blocking=True)
    except Exception as e:  # mất kết nối giữa chừng
        return {'ok': False, 'so_tem': len(images), 'loi': f'lỗi gửi tới máy in: {e}'}
    errs = (st.get('printer_state') or {}).get('errors') or []
    if errs or not st.get('did_print'):
        return {'ok': False, 'so_tem': len(images), 'loi': 'máy in báo: ' + (', '.join(errs) if errs else str(st.get('outcome')))}
    return {'ok': True, 'so_tem': len(images), 'loi': ''}


def mark_done(rows, codes):
    """Ghi NHAP.web_label = Done cho các dòng đã in (kiểm đúng mã hàng trước khi ghi). Theo tên cột hàng 1 (luật 4)."""
    import gspread
    gc = gspread.service_account(filename=os.path.join(ROOT, 'credentials.json'))
    ws = gc.open_by_key(SHEET_ID).worksheet('NHAP')
    head = [h.strip() for h in ws.row_values(1)]
    for name in ('product_code', 'item_size', 'web_label'):
        if name not in head:
            raise RuntimeError(f'Tab NHAP thiếu cột {name}')
    ip, isz, iw = head.index('product_code'), head.index('item_size'), head.index('web_label')
    stamp = 'Done - ' + datetime.now().strftime('%Y-%m-%d %H:%M')
    marked, cells = [], []
    for r in rows:
        vals = ws.row_values(r)
        code = (vals[ip] if ip < len(vals) else '').strip().upper()
        size = (vals[isz] if isz < len(vals) else '').strip()
        if size.endswith('.0'):
            size = size[:-2]
        if code + size in codes:
            cells.append(gspread.Cell(r, iw + 1, stamp))
            marked.append(r)
    if cells:
        ws.update_cells(cells)
    return marked


def process_flag(kho, dry=False):
    d = folder()
    flag = os.path.join(d, f'IN_{kho}.can_in')
    out = os.path.join(d, f'IN_{kho}.ket_qua.json')
    try:
        req = json.load(open(flag, encoding='utf-8'))
    except (OSError, ValueError):
        req = {}
    csv_path = os.path.join(d, f'IN_{kho}.csv')
    records = read_csv(csv_path) if os.path.exists(csv_path) else []
    expired = False
    if req.get('luc') and not dry:
        try:
            expired = (datetime.now() - datetime.strptime(req['luc'], '%Y-%m-%d %H:%M:%S')).total_seconds() > MAX_AGE_MIN * 60
        except ValueError:
            pass
    if expired:
        res = {'ok': False, 'so_tem': int(req.get('so_tem') or 0), 'loi': f'yêu cầu in quá {MAX_AGE_MIN} phút chưa in được, đã bỏ — bấm In tem lại'}
        os.remove(flag)
    elif req.get('ma_hang') and not dry and not csv_matches(req, records):
        return None  # Drive chưa đồng bộ xong IN_<kho>.csv, lần sau thử lại
    else:
        res = print_records(records, kho, dry=dry)
    result = {'luc': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'kho': kho, 'yeu_cau_luc': req.get('luc', ''),
              'so_chung_tu': req.get('so_chung_tu', ''), 'ngay': req.get('ngay', ''), 'so_tem': res['so_tem'],
              'so_tem_da_in': res['so_tem'] if res['ok'] else 0, 'ok': res['ok'], 'loi': res['loi'], 'dong_da_danh_dau': []}
    if res['ok'] and not dry:
        try:
            result['dong_da_danh_dau'] = mark_done([int(x) for x in req.get('dong', [])], {r.get('Code128', '').strip().upper() for r in records})
        except Exception as e:
            result['loi'] = f'in xong nhưng chưa đánh dấu được trên Sheet: {e}'
        os.remove(flag)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    dry = '--thu' in sys.argv
    lock = open('/tmp/hnc_label_print.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return  # lần chạy trước chưa xong
    d = folder()
    for kho in KHOS:  # mỗi kho 1 đợt riêng, không trộn (anh Kha 18/10)
        if os.path.exists(os.path.join(d, f'IN_{kho}.can_in')) or (dry and os.path.exists(os.path.join(d, f'IN_{kho}.csv'))):
            process_flag(kho, dry=dry)
            time.sleep(1)


if __name__ == '__main__':
    main()
