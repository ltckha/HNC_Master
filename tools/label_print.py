"""In tem tự động qua Brother QL-700 (V34 mục 6, anh Kha "làm" 18/10). Chạy trên Mac mini (máy in cắm USB).

Luồng (anh Kha 18/10: bỏ chờ Drive, tem ra trong ~10–15 giây):
bot (cửa in_tem / in_bu) ghi lệnh vào tab ẩn `in_tem_lenh` (1 dòng / kho: kho | lenh | ket_qua | cap_nhat)
→ dịch vụ này (launchd, chạy liên tục) đọc tab mỗi 4 giây trong giờ mở cửa → nhận lệnh (xoá ô lenh) → dựng tem
(tools/label_render.py) → in cả đợt qua USB, cắt 1 lần cuối → ghi NHAP.web_label = "Done - <giờ>" cho đúng dòng
→ ghi ô ket_qua (JSON). Lỗi trước khi gửi máy in (máy tắt, chưa cắm) → giữ lệnh, thử lại; quá 30 phút thì bỏ.
Đã gửi máy in thì không gửi lại (tránh in trùng). Bot vẫn ghi IN_<kho>.csv lên Drive cho P-touch dự phòng.
Chạy tay: venv/bin/python tools/label_print.py [--mot-lan]
In thử (25/10, không ghi Sheet, không đánh Done; chỉ ĐỌC SANPHAM): tối đa 5 mã dạng MÃ/SIZE
  venv/bin/python tools/label_print.py thu TH2040D/40 DXED/41 [--mau A|B|C|D|goc] [--in]
  Mặc định chỉ xuất PNG xem trước vào .data/tem_thu/; thêm --in mới gửi máy QL-700 (1 tem / mã).
"""
import fcntl
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import label_render  # noqa: E402

MODEL = 'QL-700'
KHOS = ('15E', 'Y3C')
SHEET_ID = '1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0'
CAT = 'cuoi_dot'  # 'cuoi_dot' = in liền cả đợt, cắt 1 lần ở cuối (anh Kha 18/10, như P-touch) · 'moi_tem' = cắt từng tem
BATCH_MAX = 255   # máy chỉ đếm "cắt sau N tem" tới 255 → đợt dài hơn thì chia
MAX_AGE_MIN = 30  # lệnh cũ hơn thì bỏ, không để máy in vừa bật lên in tem của sáng nay
ERR_HINT = 'Không thấy máy in QL-700: kiểm đèn nguồn sáng xanh, dây USB cắm vào Mac mini, đèn Editor Lite tắt.'


def batch_raster(model, n, cut_each):
    """BrotherQLRaster cho 1 đợt n tem trong 1 lệnh: các trang nối nhau (0x0C), chỉ trang cuối kết thúc (0x1A);
    cut_each=False → cắt sau n tem + cắt ở cuối = 1 lần cắt cho cả đợt."""
    from brother_ql.raster import BrotherQLRaster

    class _Batch(BrotherQLRaster):
        page = 0

        def add_cut_every(self, k=1):
            super().add_cut_every(1 if cut_each else n)

        def add_print(self, last_page=True):
            super().add_print(last_page=self.page >= n - 1)
            self.page += 1

    return _Batch(model)


def find_printer():
    """Địa chỉ USB của QL-700 (brother_ql + pyusb). None nếu không thấy."""
    from brother_ql.backends.helpers import discover
    devs = [d for d in discover(backend_identifier='pyusb') if 'usb://' in str(d.get('identifier', ''))]
    # Bỏ phần số serial (QL-700 có máy trả serial lỗi ký tự) — chỉ có 1 máy in Brother cắm vào
    return devs[0]['identifier'].split('_')[0] if devs else None


def print_records(records, kho, dry=False, mau=None, out_dir='/tmp'):
    """In các dòng tem (mỗi dòng in F6 tờ). mau = mẫu tem (mặc định label_render.MAU_MAC_DINH). dry → chỉ lưu PNG. Trả {ok, so_tem, loi}."""
    images, names = [], []
    for r in records:
        try:
            n = max(1, int(float(r.get('F6') or 1)))
        except ValueError:
            n = 1
        img = label_render.render_label(r, kho, mau)
        images.extend([img] * n)
        names.extend([str(r.get('Code128') or 'tem').replace('/', '-')] * n)
    if not images:
        return {'ok': False, 'so_tem': 0, 'loi': 'không có tem nào'}
    if dry:
        files = []
        for i, im in enumerate(images[:5]):
            files.append(os.path.join(out_dir, f'tem_{mau or label_render.MAU_MAC_DINH}_{names[i]}.png'))
            im.save(files[-1])
        return {'ok': True, 'so_tem': len(images), 'loi': '', 'thu': True, 'files': files}
    try:
        from brother_ql.conversion import convert
        from brother_ql.backends.helpers import send
    except ImportError as e:
        return {'ok': False, 'so_tem': len(images), 'loi': f'thiếu thư viện brother_ql ({e})'}
    ident = find_printer()
    if not ident:
        return {'ok': False, 'so_tem': len(images), 'loi': ERR_HINT}
    done = 0
    for k in range(0, len(images), BATCH_MAX):
        part = images[k:k + BATCH_MAX]
        qlr = batch_raster(MODEL, len(part), CAT == 'moi_tem')
        instructions = convert(qlr=qlr, images=part, label=label_render.LABEL_ID, rotate='0', threshold=70.0,
                               dither=False, compress=False, red=False, dpi_600=False, hq=True, cut=True)
        try:
            st = send(instructions=instructions, printer_identifier=ident, backend_identifier='pyusb', blocking=True)
        except Exception as e:  # mất kết nối giữa chừng
            return {'ok': False, 'so_tem': len(images), 'da_gui': done > 0, 'so_tem_da_in': done, 'loi': f'lỗi gửi tới máy in: {e}'}
        # QL-700 không phải lúc nào cũng báo "in xong" trong 10 giây → chỉ coi là lỗi khi máy báo lỗi thật (hết giấy, kẹt…)
        errs = (st.get('printer_state') or {}).get('errors') or []
        if errs:
            return {'ok': False, 'so_tem': len(images), 'da_gui': True, 'so_tem_da_in': done, 'loi': 'máy in báo: ' + ', '.join(errs)}
        done += len(part)
    return {'ok': True, 'so_tem': len(images), 'da_gui': True, 'so_tem_da_in': done, 'loi': ''}


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
    marked, cells, got = [], [], {}
    for r in rows:
        vals = got[r] = ws.row_values(r)
        code = (vals[ip] if ip < len(vals) else '').strip().upper()
        size = (vals[isz] if isz < len(vals) else '').strip()
        if size.endswith('.0'):
            size = size[:-2]
        if code + size in codes:
            cells.append(gspread.Cell(r, iw + 1, stamp))
            marked.append(r)
    if cells:
        # P5b: Sổ kho Web + META p5b_web = 1 → gửi web_label lên web (co_nhap, cùng luật bot nhapFlagsWeb_); Dự phòng → ghi Sheet như cũ
        sys.path.insert(0, ROOT)
        from tools import web_lenh
        w = None
        if web_lenh.p5b_on(web_lenh.meta(ws.spreadsheet), 'che_do_kho'):
            im = head.index('ma_dong') if 'ma_dong' in head else None
            dong = []
            for r in marked:
                vals = got[r]
                dong.append({'row': r, 'code': vals[ip].strip().upper(), 'ma_dong': (vals[im] if im is not None and im < len(vals) else '').strip(), 'value': stamp})
            w = web_lenh.co_nhap('web_label', dong)
        if w is None:
            ws.update_cells(cells)
        elif not w.get('ok'):
            raise RuntimeError(w.get('error'))
    return marked


QUEUE_TAB = 'in_tem_lenh'
POLL_SEC, POLL_IDLE_SEC = 4, 30
GIO_MO = (7, 22)  # đọc nhanh trong giờ mở cửa, ngoài giờ 30 giây / lần


def queue_sheet():
    import gspread
    gc = gspread.service_account(filename=os.path.join(ROOT, 'credentials.json'))
    return gc.open_by_key(SHEET_ID).worksheet(QUEUE_TAB)


def queue_rows(ws):
    """{kho: (số hàng, lenh, chỉ số cột)} theo tên cột hàng 1 (luật 4)."""
    v = ws.get_all_values()
    head = [h.strip() for h in v[0]]
    for name in ('kho', 'lenh', 'ket_qua', 'cap_nhat'):
        if name not in head:
            raise RuntimeError(f'Tab {QUEUE_TAB} thiếu cột {name}')
    col = {n: head.index(n) for n in ('kho', 'lenh', 'ket_qua', 'cap_nhat')}
    out = {}
    for i, r in enumerate(v[1:], start=2):
        kho = (r[col['kho']] if col['kho'] < len(r) else '').strip().upper()
        out[kho] = (i, (r[col['lenh']] if col['lenh'] < len(r) else '').strip())
    return out, col


def queue_write(ws, row, col, **fields):
    import gspread
    fields['cap_nhat'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ws.update_cells([gspread.Cell(row, col[k] + 1, v) for k, v in fields.items()])


def process_job(lenh_txt, dry=False):
    """1 lệnh (JSON bot ghi) → in → kết quả dict. Trả (result, giữ_lệnh)."""
    req = json.loads(lenh_txt)
    kho = req.get('kho', '')
    cot = req.get('cot') or []
    records = [dict(zip(cot, [str(x) for x in t])) for t in req.get('tem', [])]
    expired = False
    try:
        expired = (datetime.now() - datetime.strptime(req.get('luc', ''), '%Y-%m-%d %H:%M:%S')).total_seconds() > MAX_AGE_MIN * 60
    except ValueError:
        pass
    if expired:
        res = {'ok': False, 'so_tem': int(req.get('so_tem') or 0), 'loi': f'yêu cầu in quá {MAX_AGE_MIN} phút chưa in được, đã bỏ — bấm In tem lại'}
    else:
        res = print_records(records, kho, dry=dry)
    result = {'luc': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'kho': kho, 'yeu_cau_luc': req.get('luc', ''), 'in_bu': bool(req.get('in_bu')),
              'so_chung_tu': req.get('so_chung_tu', ''), 'ngay': req.get('ngay', ''), 'so_tem': res['so_tem'],
              'so_tem_da_in': res.get('so_tem_da_in', res['so_tem'] if res['ok'] else 0), 'ok': res['ok'], 'loi': res['loi'], 'dong_da_danh_dau': []}
    if res['ok'] and not dry and req.get('dong'):
        try:
            result['dong_da_danh_dau'] = mark_done([int(x) for x in req['dong']], {r.get('Code128', '').strip().upper() for r in records})
        except Exception as e:
            result['loi'] = f'in xong nhưng chưa đánh dấu được trên Sheet: {e}'
    keep = not expired and not res['ok'] and not res.get('da_gui')  # chưa tới máy in → thử lại lần sau
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result, keep


def poll_once(ws):
    rows, col = queue_rows(ws)
    for kho in KHOS:  # mỗi kho 1 đợt riêng, không trộn (anh Kha 18/10)
        if kho not in rows or not rows[kho][1]:
            continue
        row, lenh = rows[kho]
        try:
            result, keep = process_job(lenh)
        except (ValueError, KeyError) as e:
            result, keep = {'luc': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'kho': kho, 'ok': False, 'so_tem': 0, 'so_tem_da_in': 0,
                            'loi': f'lệnh in hỏng: {e}', 'dong_da_danh_dau': []}, False
        # Bot có thể đã ghi lệnh mới trong lúc in → chỉ xoá ô lenh nếu vẫn là lệnh vừa xử lý
        cur, _ = queue_rows(ws)
        fields = {'ket_qua': json.dumps(result, ensure_ascii=False)}
        if not keep and cur.get(kho, (0, ''))[1] == lenh:
            fields['lenh'] = ''
        queue_write(ws, row, col, **fields)


THU_MAX = 5
THU_DIR = os.path.join(ROOT, '.data', 'tem_thu')


def arg_val(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else default


def thu(items, mau=None, in_that=False):
    """In thử / xem trước tem cho tối đa 5 mã 'MÃ/SIZE' — cùng luật dòng tem main.label_record (luật 15). Chỉ đọc SANPHAM."""
    import gspread
    import main as hnc
    if not items or len(items) > THU_MAX:
        return {'ok': False, 'loi': f'cần 1–{THU_MAX} mã dạng MÃ/SIZE'}
    if mau and mau not in ('A', 'B', 'C', 'D', 'goc'):
        return {'ok': False, 'loi': 'mẫu phải là A, B, C, D hoặc goc'}
    sp = gspread.service_account(filename=os.path.join(ROOT, 'credentials.json')).open_by_key(SHEET_ID).worksheet('SANPHAM').get_all_values()
    head = [h.strip() for h in sp[1]]  # SANPHAM: tên cột kỹ thuật ở hàng 2 (luật 4)
    need = ('product_code', 'product_name', 'product_color', 'product_price', 'web_url')
    miss = [c for c in need if c not in head]
    if miss:
        return {'ok': False, 'loi': f'SANPHAM thiếu cột {miss}'}
    pmap = {r[head.index('product_code')].strip().upper(): {c: r[head.index(c)] for c in need} for r in sp[2:] if r[head.index('product_code')].strip()}
    cl = {r[head.index('product_code')].strip().upper(): next((r[head.index(c)].strip() for c in ('Chất liệu', 'Chất liệu quai:') if c in head and r[head.index(c)].strip()), '')
          for r in sp[2:] if r[head.index('product_code')].strip()}  # mẫu D: màu · chất liệu
    recs, khong = [], []
    for it in items:
        code, _, size = it.partition('/')
        code = code.strip().upper()
        if code not in pmap:
            khong.append(code)
            continue
        recs.append(dict(hnc.label_record({'product_code': code, 'item_size': size.strip(), 'item_quantity': 1}, pmap), **{'Chất liệu': cl.get(code, '')}))
    if khong:
        return {'ok': False, 'loi': 'SANPHAM không có mã: ' + ', '.join(khong)}
    if not in_that:
        os.makedirs(THU_DIR, exist_ok=True)
        return print_records(recs, '', dry=True, mau=mau, out_dir=THU_DIR)
    return print_records(recs, '', mau=mau)  # in thật, KHÔNG mark_done, không ghi Sheet


def main():
    if sys.argv[1:2] == ['thu']:
        items = [a for a in sys.argv[2:] if not a.startswith('--') and a != arg_val('--mau')]
        print(json.dumps(thu(items, arg_val('--mau'), '--in' in sys.argv), ensure_ascii=False))
        return
    import logging
    logging.getLogger('brother_ql').setLevel(logging.ERROR)  # QL-700 không gửi "printing completed" — đã biết, không phải lỗi
    lock = open('/tmp/hnc_label_print.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return  # đang có 1 bản chạy
    ws = None
    while True:
        try:
            ws = ws or queue_sheet()
            poll_once(ws)
        except Exception as e:  # mất mạng / quota Sheet: chờ rồi thử lại, kết nối lại từ đầu
            print(f'{datetime.now():%Y-%m-%d %H:%M:%S} lỗi đọc tab {QUEUE_TAB}: {e}', flush=True)
            ws = None
            time.sleep(POLL_IDLE_SEC)
        if '--mot-lan' in sys.argv:
            return
        time.sleep(POLL_SEC if GIO_MO[0] <= datetime.now().hour < GIO_MO[1] else POLL_IDLE_SEC)


if __name__ == '__main__':
    main()
