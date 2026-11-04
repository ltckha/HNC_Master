"""File dự phòng hằng ngày (anh Kha "làm" 04/11): web act du_phong_ds → 1 file .xlsx nhiều sheet ở Drive My Drive/HNC_du_phong/YYYY-MM-DD.xlsx.
Sheet: So_quy_quy · So_quy_phieu · So_quy_dau_ky · Cong_no_ncc / phieu / nhan / tra / hd / hd_cho / pc_hd · Nhap_hang_phieu · Nhap_hang_dong · Nhap_hang_dot · Nhap_hang_sua · Bu_tru.
Có giá nhập → thư mục riêng tư, không chia sẻ. Giữ 30 file gần nhất, cũ hơn chuyển vào cu/ (không xoá).
Ảnh chứng từ (link ký hết hạn 1 giờ): tải ngay vào HNC_du_phong/anh/<số phiếu>.<đuôi>, chỉ ảnh chưa có.
Chạy: venv/bin/python tools/export_backup.py [--beta]   (launchd vn.giayhainancy.hnc.backup_export 15:00, mã trực ca hnc.backup_export)
"""
import glob
import json
import os
import shutil
import sys
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from hnc_paths import drive_roots  # noqa: E402
from tools import cash_book, health_log  # noqa: E402

MA_JOB = 'hnc.backup_export'
GIU = 30
DIR_NAME = 'HNC_du_phong'
EXT = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'application/pdf': 'pdf'}


def backup_dir():
    roots = drive_roots()
    if not roots:
        raise RuntimeError('Không thấy Google Drive (My Drive) trên Mac — mở Google Drive rồi chạy lại.')
    d = os.path.join(roots[0], DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def sheets(data):
    """du_phong_ds → [(tên sheet, [dict, …])] theo thứ tự; dict lồng (khoan của bù trừ) trải thành cột."""
    sq, cn, nh = data.get('so_quy') or {}, data.get('cong_no') or {}, data.get('nhap_hang') or {}
    bt = [dict({k: v for k, v in x.items() if k != 'khoan'}, **{f'khoan_{k}': v for k, v in (x.get('khoan') or {}).items()}) for x in data.get('bu_tru') or []]
    return [('So_quy_quy', sq.get('quy')), ('So_quy_phieu', sq.get('phieu')), ('So_quy_dau_ky', sq.get('dau_ky')),
            ('Cong_no_ncc', cn.get('ncc')), ('Cong_no_phieu', cn.get('phieu')), ('Cong_no_nhan', cn.get('nhan')), ('Cong_no_tra', cn.get('tra_ncc')),
            ('Cong_no_hd', cn.get('hd')), ('Cong_no_hd_cho', cn.get('hd_cho')), ('Cong_no_pc_hd', cn.get('pc_hd')),
            ('Nhap_hang_phieu', nh.get('phieu')), ('Nhap_hang_dong', nh.get('dong')), ('Nhap_hang_dot', nh.get('dot')), ('Nhap_hang_sua', nh.get('sua')),
            ('Bu_tru', bt)]


def write_xlsx(path, data):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    info = wb.active
    info.title = 'Thong_tin'
    for r in [['Tạo lúc (web)', data.get('tao_luc')], ['Từ ngày', data.get('tu')], ['Ghi chú', data.get('ghi_chu')]] + \
             [['Luật sổ quỹ', x] for x in (data.get('so_quy') or {}).get('luat') or []] + [['Luật công nợ', x] for x in (data.get('cong_no') or {}).get('luat') or []]:
        info.append([str(v) if v is not None else '' for v in r])
    info.column_dimensions['A'].width, info.column_dimensions['B'].width = 16, 120
    for ten, rows in sheets(data):
        ws = wb.create_sheet(ten)
        rows = rows or []
        cols = list(dict.fromkeys(k for x in rows for k in x))
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
        for x in rows:
            ws.append([v if isinstance(v, (int, float, str)) or v is None else json.dumps(v, ensure_ascii=False) for v in (x.get(k) for k in cols)])
        ws.freeze_panes = 'A2'
    wb.save(path)
    return path


def rotate(d, today):
    """Giữ GIU file YYYY-MM-DD.xlsx gần nhất, cũ hơn chuyển vào cu/ (không xoá)."""
    fs = sorted(f for f in glob.glob(os.path.join(d, '????-??-??.xlsx')))
    cu = os.path.join(d, 'cu')
    moved = 0
    for f in fs[:-GIU]:
        os.makedirs(cu, exist_ok=True)
        shutil.move(f, os.path.join(cu, os.path.basename(f)))
        moved += 1
    return moved


def images(data):
    """[(tên file không đuôi, link)] — ảnh phiếu chi / thu sổ quỹ (theo số phiếu)."""
    out = []
    for p in (data.get('so_quy') or {}).get('phieu') or []:
        if p.get('anh') and p.get('so'):
            out.append((str(p['so']), p['anh']))
    return out


def save_images(d, data, beta=False):
    a = os.path.join(d, 'anh_beta' if beta else 'anh')  # số phiếu beta trùng bản chính → thư mục riêng
    os.makedirs(a, exist_ok=True)
    moi = loi = 0
    for ten, url in images(data):
        if glob.glob(os.path.join(a, ten + '.*')):
            continue
        try:
            req = urllib.request.Request(url, headers={'user-agent': 'Mozilla/5.0 hn-mac-du-phong'})
            with urllib.request.urlopen(req, timeout=60, context=cash_book._ssl()) as r:
                body, mime = r.read(), (r.headers.get('content-type') or '').split(';')[0].strip()
            with open(os.path.join(a, f"{ten}.{EXT.get(mime, 'bin')}"), 'wb') as f:
                f.write(body)
            moi += 1
        except Exception as e:  # noqa: BLE001
            loi += 1
            print(f'⚠ Ảnh {ten}: {e}')
    return moi, loi


def main():
    beta = '--beta' in sys.argv  # chạy thử với web beta: file <ngày>_beta.xlsx, không ghi sổ trực ca; ảnh chỉ khi --anh (vào anh_beta/)
    url = cash_book.URL_BETA if beta else cash_book.URL
    try:
        data = cash_book.fetch(url, 'du_phong_ds')
        if not isinstance(data, dict) or 'so_quy' not in data:
            raise RuntimeError(f'web trả lạ: {str(data)[:120]}')
        d = backup_dir()
        today = date.today().isoformat()
        path = write_xlsx(os.path.join(d, f"{today}{'_beta' if beta else ''}.xlsx"), data)
        moved = 0 if beta else rotate(d, today)
        moi, loi = save_images(d, data, beta) if not beta or '--anh' in sys.argv else (0, 0)
        n = {t: len(r or []) for t, r in sheets(data)}
        msg = f"{os.path.basename(path)} · phiếu quỹ {n['So_quy_phieu']} · nhập hàng {n['Nhap_hang_phieu']} · ảnh mới {moi}" + (f' · ảnh lỗi {loi}' if loi else '') + (f' · chuyển cu/ {moved}' if moved else '')
        print(f'✅ {path}\n   {msg}')
        if not beta:
            health_log.ghi(MA_JOB, 'loi' if loi else 'ok', msg)
        return 0
    except Exception as e:  # noqa: BLE001
        print(f'⛔ {e}')
        if not beta:
            health_log.ghi(MA_JOB, 'loi', str(e)[:150])
        return 1


if __name__ == '__main__':
    sys.exit(main())
