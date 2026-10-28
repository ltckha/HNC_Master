"""P5b (21/10): Mac gửi cờ NHAP / SANPHAM lên web qua POST <gốc web>/api/bot-lenh — cùng luật bot p5bSend_ / nhapFlagsWeb_ /
spFlagsWeb_ (luật 15). Hợp đồng: repo web docs/vision/p5b_api_hnc.md mục "Chốt".
Bật khi META p5b_web = 1 (web ghi lúc P5b lên bản đó) VÀ sổ tương ứng = web: Sổ kho → co_nhap, Hàng hoá → co_sp.
Kết quả: None = ghi Sheet như cũ (P5b tắt / web trả du_phong / cột ngoài hợp đồng); {'ok': True} = web đã ghi;
{'ok': False, 'error'} = web lỗi → KHÔNG ghi Sheet (web là gốc).
Khoá ký (không in ra): biến HNC_BOT_KEY (env / .env), hoặc file HNC_BOT_KEY_FILE (JSON có BOT_CALLBACK_KEY).
Gốc web: HNC_WEB_ORIGIN, không có thì lấy từ SYNC_HINT_URL (.env).
"""
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone

import requests

CO_NHAP_COLS = ('misa_stock', 'web_label', 'kho_sync', 'web_stock')
THUOC_TINH = ('Tên Ngành Hàng', 'Đặc điểm', 'Thương hiệu', 'Giới tính', 'Size Plus', 'Size', 'Chất liệu', 'Nhấn mạnh', 'Chất liệu quai:',
              'Chất liệu đế:', 'Lót trong:', 'Mặt lót đế:', 'Dáng giày mũi:', 'Phần dưới giày:', 'Kết hợp trang phục:', 'Sử dụng:', 'Bonus:')
CO_SP_COLS = set(('shopee_upload', 'tiktok_upload', 'misa_upload', 'web_upload', 'web_url', 'get_images', 'content_path', 'content_url',
                  'content_files') + tuple(f'image_{i:02d}' for i in range(1, 11)) + THUOC_TINH)
CO_SP_MAX = 200


def meta(sh):
    """{key: value} của tab META (đọc mới mỗi lần — web đổi liên tục)."""
    try:
        rows = sh.worksheet('META').get_all_values()
    except Exception:
        return {}
    head = [str(h).strip() for h in (rows[0] if rows else [])]
    if 'key' not in head or 'value' not in head:
        return {}
    ck, cv = head.index('key'), head.index('value')
    return {r[ck].strip(): r[cv].strip() for r in rows[1:] if len(r) > max(ck, cv) and r[ck].strip()}


def bat(m, key):
    return str(m.get(key, '')).strip().lower() in ('1', 'web', 'true')


def p5b_on(m, so):
    """so = 'che_do_kho' | 'che_do_hh'."""
    return bat(m, 'p5b_web') and str(m.get(so, '')).strip().lower() == 'web'


def _env(name):
    v = os.getenv(name, '').strip()
    if v:
        return v
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    try:
        for line in open(p, encoding='utf-8'):
            if line.startswith(name + '='):
                return line.split('=', 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return ''


def _khoa():
    f = _env('HNC_BOT_KEY_FILE')
    if f:
        try:
            return str(json.load(open(os.path.expanduser(f), encoding='utf-8')).get('BOT_CALLBACK_KEY', ''))
        except (OSError, ValueError):
            return ''
    return _env('HNC_BOT_KEY')


def _goc():
    o = _env('HNC_WEB_ORIGIN')
    if not o:
        m = re.match(r'^(https?://[^/]+)', _env('SYNC_HINT_URL'))
        o = m.group(1) if m else ''
    return o.rstrip('/')


def _luc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _post(duong, payload, luc):
    """POST payload ký HMAC hex(khoá, luc + "." + thân) tới <gốc web><duong>. Trả (requests.Response | None, lỗi)."""
    key, goc = _khoa(), _goc()
    if len(key) < 16 or not goc:
        return None, 'Mac chưa có khoá ký / địa chỉ web (HNC_BOT_KEY hoặc HNC_BOT_KEY_FILE, HNC_WEB_ORIGIN)'
    raw = json.dumps(payload, ensure_ascii=False)
    sig = hmac.new(key.encode(), (luc + '.' + raw).encode('utf-8'), hashlib.sha256).hexdigest()
    try:
        return requests.post(goc + duong, data=raw.encode('utf-8'), timeout=60,
                             headers={'content-type': 'application/json', 'x-bot-time': luc, 'x-bot-sig': sig}), ''
    except requests.RequestException as e:
        return None, f'không gọi được web: {e}'


def gui(loai, body, chu=False, nguoi='mac', dry_run=False):
    """POST 1 gói ký HMAC (như bot webForward_). Trả dict web (thêm 'web': True) hoặc {'ok': False, 'error'}."""
    luc = _luc()
    payload = {'luc': luc, 'loai': loai, 'nguon': 'mac', 'nguoi': nguoi, 'body': body}
    if chu:
        payload['chu'] = True
    if dry_run:
        payload['dry_run'] = True
    r, loi = _post('/api/bot-lenh', payload, luc)
    if r is None:
        return {'ok': False, 'error': loi}
    try:
        out = r.json()
    except ValueError:
        out = {}
    if r.status_code != 200:
        return {'ok': False, 'du_phong': bool(out.get('du_phong')), 'error': f"web trả lỗi {r.status_code}" + (f": {str(out.get('error'))[:200]}" if out.get('error') else '')}
    out['web'] = True
    return out


def _ket_qua(w, loai):
    if not w.get('ok') and w.get('du_phong'):
        return None
    return w if w.get('ok') else dict(w, ok=False, error=f"web chưa ghi {loai}: {w.get('error') or 'không rõ'}")


def co_nhap(field, dong):
    """dong = [{'row', 'code', 'ma_dong'?, 'value'}] cùng 1 cột NHAP. Cột ngoài hợp đồng → None (ghi Sheet)."""
    if field not in CO_NHAP_COLS or not dong:
        return None
    out = []
    for d in dong:
        x = {'row': d['row'], 'code': d['code']}
        if d.get('ma_dong'):
            x['ma_dong'] = d['ma_dong']
        x[field] = str(d['value'])
        out.append(x)
    return _ket_qua(gui('co_nhap', {'dong': out}), 'co_nhap')


def co_sp(ds):
    """ds = [{'code', 'doi': {cột: giá trị}}], lô ≤ 200 mã. Có cột ngoài hợp đồng → None (ghi Sheet như cũ)."""
    ds = [x for x in ds if x.get('code')]
    if not ds or any(k.strip() not in CO_SP_COLS for x in ds for k in x['doi']):
        return None
    for i in range(0, len(ds), CO_SP_MAX):
        w = _ket_qua(gui('co_sp', {'ds': [{'code': x['code'], 'doi': {k.strip(): str(v) for k, v in x['doi'].items()}} for x in ds[i:i + CO_SP_MAX]]}), 'co_sp')
        if w is None:
            return None if i == 0 else {'ok': False, 'error': f'web chuyển Dự phòng giữa chừng (đã gửi {i} mã) — chạy lại'}
        if not w.get('ok'):
            return dict(w, da_gui=i)
    return {'ok': True, 'web': True, 'so_ma': len(ds)}


def ma_cho_duyet():
    """Mã đang chờ duyệt trên web (POST /api/mo-ta/mac act 'cho', cả mã đã có nháp). Trả (danh sách mã | None, lỗi)."""
    luc = _luc()
    r, loi = _post('/api/mo-ta/mac', {'luc': luc, 'nguon': 'mac', 'act': 'cho', 'tat_ca': True}, luc)
    if r is None:
        return None, loi
    try:
        out = r.json()
    except ValueError:
        out = {}
    if r.status_code != 200 or not out.get('ok'):
        return None, f"web trả lỗi {r.status_code}" + (f": {str(out.get('error'))[:200]}" if out.get('error') else '')
    return [str(x.get('code', '')).strip().upper() for x in out.get('ma', []) if x.get('code')], ''


GOI_Y_GIA_MAX = 200


def goi_y_gia(items, dry_run=False):
    """items = [{'code', 'gia', 'ly_do'}] → loai goi_y_gia, lô ≤ 200. Trả {'ok', 'so', 'loi': [...], 'text'} gộp các lô."""
    tong = {'ok': True, 'so': 0, 'loi': [], 'text': []}
    for i in range(0, len(items), GOI_Y_GIA_MAX):
        w = gui('goi_y_gia', {'items': items[i:i + GOI_Y_GIA_MAX]}, dry_run=dry_run)
        if not w.get('ok'):
            return dict(w, ok=False, da_gui=i)
        tong['so'] += int(w.get('so') or 0)
        tong['loi'] += list(w.get('loi') or [])
        if w.get('text'):
            tong['text'].append(str(w['text']))
    tong['text'] = ' · '.join(tong['text'])
    return tong
