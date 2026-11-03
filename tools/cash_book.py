"""Sổ quỹ dự phòng trên Mac (luật 15, GĐ1 thay MISA, anh Kha "làm" 03/11) — ra CÙNG số với web /admin/so-quy (src/worker/cash_book.ts):
- Quỹ, phiếu tay (PT / PC / CQNB, có huy_luc) và số dư đầu kỳ của web: đọc act so_quy_ds ở /api/tach-nen/mac (khoá Mac ~/.hnc_mac_key.json),
  mỗi lần đọc được lưu bản sao vào HNC_Exported_Files/cash_book_copy/. Web hỏng → dùng bản sao gần nhất, ghi rõ "phiếu tay tới …".
- Tiền vào từ bán: tự tính từ tab BAN (Sheet) theo đúng LUAT web trả về:
  bỏ kênh sàn (shopee / tiktok / lazada); cách thu = payment_method (trống = Tiền mặt), Ví / COD / Ghi nợ chưa vào quỹ;
  Tiền mặt → quỹ tiền mặt của tiệm bán (KHO chứa "3C" = 3C, còn lại 15E); Chuyển khoản / Thẻ → tài khoản nhan_ck = 1 của hộ chủ hàng (chu_hang, trống thì KHO);
  gộp 1 dòng / quỹ / ngày, tổng âm → cột Chi "Trả tiền khách trả hàng (…)"; Ngày trống (web day_inf) bỏ; chỉ tính từ ngay_dau của từng quỹ.
- File Excel: cùng cột / tên file như nút "Tải Excel" của web (Ngày · Số chứng từ · Diễn giải · Nhóm chi · Thu · Chi · Tồn).
"""
import calendar
import glob
import hashlib
import hmac
import json
import os
import re
import ssl
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

URL_BETA = 'https://beta.giayhainancy.vn/api/tach-nen/mac'
URL_MAIN = 'https://giayhainancy.vn/api/tach-nen/mac'
URL = URL_MAIN  # 03/11: web Sổ quỹ đã Lên bản chính (02c1c4e); thử beta thì truyền url=URL_BETA
KEY_FILE = os.path.expanduser('~/.hnc_mac_key.json')
COPY_DIR = 'cash_book_copy'
SAN = re.compile(r'shopee|tiktok|lazada', re.I)
CACH_THU_NGOAI = ('Ví', 'COD', 'Ghi nợ')
TEN_LOAI = {'PT': 'Thu', 'PC': 'Chi', 'CQNB': 'Chuyển quỹ'}
COT = ['Ngày', 'Số chứng từ', 'Diễn giải', 'Nhóm chi', 'Thu', 'Chi', 'Tồn']


def payment_method(text):
    """Như web sheet_copy.paymentMethod: chữ tự do → 6 giá trị; không đoán được → Tiền mặt."""
    n = str(text or '').replace('đ', 'd').replace('Đ', 'd')
    n = ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn').lower().strip()
    if not n:
        return ''
    A = re.A
    if re.search(r'\b(ck|chuyen|bank|qr|vietqr|techcom|vcb|acb|mb)\b', n, A): return 'Chuyển khoản'
    if re.search(r'\bthe\b|\bcard\b|\bpos\b', n, A): return 'Thẻ'
    if re.search(r'\bvi\b|momo|zalopay|shopeepay', n, A): return 'Ví'
    if re.search(r'\bno\b|ghi no|cong no', n, A): return 'Ghi nợ'
    if re.search(r'\bcod\b|thu\s*ho|ship\s*thu', n, A): return 'COD'
    if re.search(r'shopee|tiktok|lazada|san', n, A): return 'Chuyển khoản'
    return 'Tiền mặt'


def kho_ho(kho):
    return 'Y3C' if '3C' in str(kho or '').upper() else '15E'


def ho_of(chu, kho):
    return 'Y3C' if '3C' in str(chu or kho or '15E').upper() else '15E'


def homnay():
    return (datetime.now(timezone.utc) + timedelta(hours=7)).strftime('%Y-%m-%d')


def cuoi_thang(m):
    y, mo = map(int, m.split('-'))
    return f"{m}-{calendar.monthrange(y, mo)[1]:02d}"


def ngay_truoc(d):
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()


def _money(v):
    if isinstance(v, (int, float)):
        return v
    s = str(v or '').strip()
    neg = s.startswith('-')
    d = ''.join(ch for ch in s if ch.isdigit())
    return (-int(d) if neg else int(d)) if d else 0


def _qty(v):
    try:
        return float(str(v).replace(',', '.')) if str(v).strip() else 0
    except ValueError:
        return 0


def _day(v):
    """Ô Ngày của BAN (dd/mm/yyyy, d/m/yyyy, yyyy-mm-dd) → yyyy-mm-dd; trống / sai → '' (= web day_inf, bỏ)."""
    s = str(v or '').strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    return m.group(0) if m else ''


def ban_rows(values):
    """get_all_values() của tab BAN → [{day, kho, chu, ch, pay, t}] (t = Giá × SL), đọc theo tên cột (luật 4)."""
    h = [str(c).strip() for c in values[0]]
    need = ['Ngày', 'Giá', 'item_quantity', 'KHO', 'product_code']
    miss = [c for c in need if c not in h]
    if miss:
        raise RuntimeError(f'Tab BAN thiếu cột {miss}')
    ix = {c: h.index(c) for c in h}
    g = lambda r, c: r[ix[c]] if c in ix and ix[c] < len(r) else ''
    out = []
    for r in values[1:]:
        if not str(g(r, 'product_code')).strip():
            continue
        out.append({'day': _day(g(r, 'Ngày')), 'kho': str(g(r, 'KHO')).strip(), 'chu': str(g(r, 'chu_hang')).strip(),
                    'ch': str(g(r, 'channel')).strip(), 'pay': str(g(r, 'payment_method')).strip(), 't': _money(g(r, 'Giá')) * _qty(g(r, 'item_quantity'))})
    return out


def tien_ban(qs, ban, tu, den):
    """Như web tienBan: gộp (ngày, kho, chủ, kênh, cách thu) → dòng tiền bán / quỹ / ngày + phần chưa vào quỹ."""
    grp = {}
    for r in ban:
        if r['day'] and tu <= r['day'] <= den:
            k = (r['day'], r['kho'], r['chu'], r['ch'], r['pay'])
            grp[k] = grp.get(k, 0) + r['t']
    tm = lambda h: next((q for q in qs if q['loai'] == 'tien_mat' and kho_ho(q.get('kho')) == h), None)
    ck = lambda h: next((q for q in qs if q['loai'] == 'ngan_hang' and q['ho'] == h and q.get('nhan_ck')), None)
    by, ngoai, chua_tk = {}, {'15E': {}, 'Y3C': {}}, {'15E': 0, 'Y3C': 0}
    for (day, kho, chu, ch, pay), t in grp.items():
        if SAN.search(ch or '') or not t:
            continue
        p = payment_method(pay) or 'Tiền mặt'
        ho = ho_of(chu, kho)
        if p in CACH_THU_NGOAI:
            ngoai[ho][p] = ngoai[ho].get(p, 0) + t
            continue
        q = tm(kho_ho(kho)) if p == 'Tiền mặt' else ck(ho)
        if not q:
            chua_tk[ho] += t
            continue
        d = by.setdefault((q['id'], day), {'quy': q['id'], 'ngay': day, 'so': 'BH', 'vao': 0, 'ra': 0, 'nhom': '',
                                           'dien': 'Tiền bán hàng (tiền mặt)' if p == 'Tiền mặt' else 'Tiền bán hàng (chuyển khoản / thẻ)'})
        d['vao'] += t
    dong = []
    for d in by.values():
        if d['vao'] < 0:
            d = dict(d, ra=-d['vao'], vao=0, dien=d['dien'].replace('Tiền bán hàng', 'Trả tiền khách trả hàng'))
        dong.append(d)
    return dong, ngoai, chua_tk


def dong_tien(qs, ten_moi, phieu, ban, tu, den):
    """Như web dongTien: tiền bán + phiếu tay (bỏ phiếu huỷ) trong [tu, den], cắt theo ngay_dau từng quỹ, xếp ngày → BH trước → số phiếu."""
    if tu > den:
        return [], {'15E': {}, 'Y3C': {}}, {'15E': 0, 'Y3C': 0}
    dong, ngoai, chua_tk = tien_ban(qs, ban, tu, den)
    for p in phieu:
        if p.get('huy_luc') or not (tu <= p['ngay'] <= den):
            continue
        if p['loai'] in ('PT', 'PC'):
            dien = ' · '.join(x for x in [f"Trả NCC {p['ncc']}{' (đặt cọc)' if p.get('dat_coc') else ''}" if p.get('ncc') else '',
                                         p.get('nhom') or '', p.get('ghi_chu') or ''] if x) or TEN_LOAI[p['loai']]
            v = p['so_tien']
            dong.append({'quy': p['quy_id'], 'ngay': p['ngay'], 'so': p['so'], 'dien': dien, 'vao': v if p['loai'] == 'PT' else 0,
                         'ra': v if p['loai'] == 'PC' else 0, 'nhom': p.get('nhom') or ''})
        else:
            gc = f" · {p['ghi_chu']}" if p.get('ghi_chu') else ''
            dong.append({'quy': p['quy_id'], 'ngay': p['ngay'], 'so': p['so'], 'dien': f"Chuyển sang {ten_moi.get(p.get('quy_den') or 0, '?')}{gc}",
                         'vao': 0, 'ra': p['so_tien'], 'nhom': ''})
            if p.get('quy_den'):
                dong.append({'quy': p['quy_den'], 'ngay': p['ngay'], 'so': p['so'], 'dien': f"Nhận từ {ten_moi.get(p['quy_id'], '?')}{gc}",
                             'vao': p['so_tien'], 'ra': 0, 'nhom': ''})
    dau = {q['id']: q['ngay_dau'] for q in qs}
    dong = [d for d in dong if d['quy'] in dau and d['ngay'] >= dau[d['quy']]]
    dong.sort(key=lambda d: (d['ngay'], 0 if d['so'] == 'BH' else 1, d['so']))
    return dong, ngoai, chua_tk


def so_quy(data, ban, ho, thang, today=None):
    """Sổ từng quỹ của hộ `ho` tháng `thang` (như trang web Hộ 15E / Hộ 3C) → [{quy, dau_ky, rows, ngoai, chua_tk}]."""
    hn = today or homnay()
    qs = [q for q in data['quy'] if not q.get('an') and (q['ho'] == ho or (q['loai'] == 'tien_mat' and kho_ho(q.get('kho')) == ho))]
    ten_moi = {q['id']: q['ten'] for q in data['quy'] if not q.get('an')}
    tu, den = f"{thang}-01", min(cuoi_thang(thang), hn)
    dong, ngoai, chua_tk = dong_tien(qs, ten_moi, data['phieu'], ban, tu, den)
    truoc = ngay_truoc(tu)
    du_truoc = {q['id']: q['du_dau'] for q in qs}
    if qs:
        cu, _, _ = dong_tien(qs, ten_moi, data['phieu'], ban, min(q['ngay_dau'] for q in qs), truoc)
        for d in cu:
            du_truoc[d['quy']] += d['vao'] - d['ra']
    out = []
    for q in qs:
        du = q['du_dau'] if q['ngay_dau'] > truoc else du_truoc[q['id']]
        dau_ky, rows = du, []
        for d in (x for x in dong if x['quy'] == q['id']):
            du += d['vao'] - d['ra']
            rows.append(dict(d, du=du))
        out.append({'quy': q, 'dau_ky': dau_ky, 'rows': rows})
    return out, ngoai[ho], chua_tk[ho]


def xlsx_rows(s):
    dmy = lambda d: '/'.join(reversed(d.split('-')))
    n = lambda v: (int(v) if float(v).is_integer() else v) if v else None
    return [COT, [None, None, 'Số dư đầu kỳ', None, None, None, n(s['dau_ky']) or 0]] + [
        [dmy(r['ngay']), None if r['so'] == 'BH' else r['so'], r['dien'], r['nhom'] or None, n(r['vao']), n(r['ra']), n(r['du']) or 0] for r in s['rows']]


def file_name(quy, thang):
    ten = re.sub(r'\s+', '_', quy['ten'])
    return f"So_quy_{ten}_{thang}.xlsx"


# ---------------- Đọc web (khoá Mac) + bản sao ----------------

def _ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context(cafile='/etc/ssl/cert.pem')


def fetch(url=URL, act='so_quy_ds'):
    with open(KEY_FILE) as f:
        key = json.load(f)['BOT_CALLBACK_KEY']
    raw = json.dumps({'act': act}, separators=(',', ':'))
    t = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    sig = hmac.new(key.encode(), f'{t}.{raw}'.encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=raw.encode(), method='POST', headers={
        'content-type': 'application/json', 'x-bot-time': t, 'x-bot-sig': sig, 'user-agent': 'Mozilla/5.0 hn-mac-so-quy'})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ssl()) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Lỗi {e.code}: {e.read().decode(errors="replace")[:200]}')


def load(export_dir, url=URL, act='so_quy_ds', need='quy'):
    """Đọc web act (so_quy_ds / cong_no_ds), lưu bản sao <act>_<lúc>.json; lỗi thì lấy bản sao gần nhất. → (data, ghi_chu)."""
    d = os.path.join(export_dir, COPY_DIR)
    os.makedirs(d, exist_ok=True)
    try:
        data = fetch(url, act)
        if not isinstance(data, dict) or need not in data:
            raise RuntimeError(f'web trả lạ: {str(data)[:120]}')
        path = os.path.join(d, f"{act}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        for old in sorted(glob.glob(os.path.join(d, f'{act}_*.json')))[:-30]:  # giữ 30 bản gần nhất
            os.remove(old)
        return data, ''
    except Exception as e:  # noqa: BLE001 — web hỏng / mạng: dùng bản sao
        cs = sorted(glob.glob(os.path.join(d, f'{act}_*.json')))
        if not cs:
            raise RuntimeError(f'Không đọc được web ({e}) và chưa có bản sao nào trong {d}')
        with open(cs[-1], encoding='utf-8') as f:
            data = json.load(f)
        luc = datetime.fromtimestamp(os.path.getmtime(cs[-1])).strftime('%d/%m/%Y %H:%M')
        return data, f'⚠ Không đọc được web ({e}) — dùng bản sao lúc {luc}: số liệu web (phiếu tay / nhập hàng) tới {luc}.'


def write_xlsx(path, rows, widths=(12, 14, 46, 16, 13, 13, 13)):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'So'
    for r in rows:
        ws.append(r)
    for col, w in zip('ABCDEFG', widths):
        ws.column_dimensions[col].width = w
    wb.save(path)
