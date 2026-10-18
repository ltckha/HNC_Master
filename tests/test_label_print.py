"""Test: in tem tự động QL-700 (tools/label_print.py + label_render.py). Không gọi máy in, không ghi Sheet.
Chạy: venv/bin/python tests/test_label_print.py"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import label_render  # noqa: E402
import label_print  # noqa: E402

fails = []


def eq(name, got, want):
    if got != want:
        fails.append(name)
        print(f"❌ {name}: {got!r} != {want!r}")


# CODE128: mỗi ký tự 11 module, cộng start + check (11 mỗi cái) + stop 13
mods = label_render.code128_modules('TH2040D40')
eq('code128 tổng module', sum(int(m) for m in mods), 11 * (9 + 2) + 13)
eq('code128 số kiểm tra', (104 + sum((i + 1) * (ord(c) - 32) for i, c in enumerate('TH2040D40'))) % 103, 76)  # tính tay: (104 + 1002) % 103
eq('code128 ký hiệu kiểm tra nằm trước stop', mods[-13:-7], label_render.CODE128[76])
img = label_render.render_label({'Tên': 'Giày tây nam da bò TH2040D', 'Size Color': 'Đen (Size 40)', 'Code128': 'TH2040D40'}, 'Y3C')
eq('tem 62x29: ảnh 1-bit 696x271', (img.size, img.mode), ((696, 271), '1'))

d = tempfile.mkdtemp()
label_print.folder = lambda: d
calls = {'print': 0, 'mark': []}


def write_job(luc=None, so_tem=3, codes=('TH2040D40',)):
    with open(os.path.join(d, 'IN_15E.csv'), 'w', encoding='utf-8') as f:
        f.write('QR code,Tên,Màu,Size,Size Color,F6,Code128,Gía\n,Giày tây,Đen,40,Đen (Size 40),3,TH2040D40,800.000 đ\n')
    with open(os.path.join(d, 'IN_15E.can_in'), 'w', encoding='utf-8') as f:
        json.dump({'kho': '15E', 'luc': luc or datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'dong': [120], 'ma_hang': list(codes), 'so_tem': so_tem}, f)


def fake_print(ok, loi=''):
    def _p(records, kho, dry=False):
        calls['print'] += 1
        return {'ok': ok, 'so_tem': sum(int(r['F6']) for r in records), 'loi': loi}
    return _p


label_print.mark_done = lambda rows, codes: calls['mark'].append((rows, sorted(codes))) or rows
flag = os.path.join(d, 'IN_15E.can_in')

# 1. In được → đánh dấu đúng dòng, xoá cờ, ket_qua ok
label_print.print_records = fake_print(True)
write_job()
r = label_print.process_flag('15E')
eq('in xong: đánh dấu + xoá cờ', [r['ok'], r['so_tem_da_in'], r['dong_da_danh_dau'], os.path.exists(flag), calls['mark'][-1]], [True, 3, [120], False, ([120], ['TH2040D40'])])
kq = json.load(open(os.path.join(d, 'IN_15E.ket_qua.json'), encoding='utf-8'))
eq('ket_qua.json có số tem, lỗi trống', [kq['kho'], kq['so_tem_da_in'], kq['loi']], ['15E', 3, ''])

# 2. Lỗi máy in → KHÔNG đánh dấu, giữ cờ, ghi lỗi
n_mark = len(calls['mark'])
label_print.print_records = fake_print(False, label_print.ERR_HINT)
write_job()
r = label_print.process_flag('15E')
eq('lỗi: không đánh dấu, giữ cờ', [r['ok'], r['so_tem_da_in'], len(calls['mark']) == n_mark, os.path.exists(flag), 'Editor Lite' in r['loi']], [False, 0, True, True, True])

# 3. CSV chưa đồng bộ (mã khác cờ) → chưa in, chờ lần sau
n_print = calls['print']
write_job(codes=('KHAC41',))
eq('CSV chưa khớp cờ → chờ', [label_print.process_flag('15E'), calls['print'] == n_print, os.path.exists(flag)], [None, True, True])

# 4. Cờ quá 30 phút → bỏ, không in
write_job(luc=(datetime.now() - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S'))
r = label_print.process_flag('15E')
eq('cờ cũ → bỏ, không in, không đánh dấu', [r['ok'], calls['print'] == n_print, os.path.exists(flag), len(calls['mark']) == n_mark], [False, True, False, True])

if fails:
    sys.exit(1)
print("✅ test_label_print đạt")
