"""Test: in tem tự động QL-700 (tools/label_print.py + label_render.py). Không gọi máy in, không ghi Sheet.
Chạy: venv/bin/python tests/test_label_print.py"""
import json
import os
import sys
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
img = label_render.render_label({'Tên': 'Giày tây nam da bò TH2040D', 'Size Color': 'Đen (Size 40)', 'Code128': 'TH2040D40', 'Gía': '800.000 đ'}, 'Y3C')
eq('tem 62x29: ảnh 1-bit 696x271', (img.size, img.mode), ((696, 271), '1'))

COT = ['QR code', 'Tên', 'Màu', 'Size', 'Size Color', 'F6', 'Code128', 'Gía']


class FakeWS:
    """Tab in_tem_lenh giả: kho | lenh | ket_qua | cap_nhat."""
    def __init__(self):
        self.v = [['kho', 'lenh', 'ket_qua', 'cap_nhat'], ['15E', '', '', ''], ['Y3C', '', '', '']]

    def get_all_values(self):
        return [list(r) for r in self.v]

    def update_cells(self, cells):
        for c in cells:
            self.v[c.row - 1][c.col - 1] = c.value

    def kq(self, kho):
        r = next(x for x in self.v if x[0] == kho)
        return json.loads(r[2]) if r[2] else None

    def lenh(self, kho):
        return next(x for x in self.v if x[0] == kho)[1]


def job(kho='15E', luc=None, dong=(120,), so_tem=3):
    return json.dumps({'kho': kho, 'luc': luc or datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'dong': list(dong), 'so_tem': so_tem, 'cot': COT,
                       'tem': [['', 'Giày tây', 'Đen', '40', 'Đen (Size 40)', so_tem, 'TH2040D40', '800.000 đ']]})


calls = {'print': 0, 'mark': []}


def fake_print(ok, loi='', da_gui=None):
    def _p(records, kho, dry=False):
        calls['print'] += 1
        return {'ok': ok, 'so_tem': sum(int(r['F6']) for r in records), 'loi': loi, 'da_gui': ok if da_gui is None else da_gui}
    return _p


label_print.mark_done = lambda rows, codes: calls['mark'].append((rows, sorted(codes))) or rows
ws = FakeWS()

# 1. In được → đánh dấu đúng dòng, xoá lệnh, ket_qua ok
label_print.print_records = fake_print(True)
ws.v[1][1] = job()
label_print.poll_once(ws)
eq('in xong: đánh dấu + xoá lệnh', [ws.kq('15E')['ok'], ws.kq('15E')['so_tem_da_in'], ws.kq('15E')['dong_da_danh_dau'], ws.lenh('15E'), calls['mark'][-1]],
   [True, 3, [120], '', ([120], ['TH2040D40'])])

# 2. Không thấy máy in (chưa gửi) → không đánh dấu, giữ lệnh, ghi lỗi
n_mark = len(calls['mark'])
label_print.print_records = fake_print(False, label_print.ERR_HINT)
ws.v[2][1] = job('Y3C')
label_print.poll_once(ws)
eq('chưa tới máy in: giữ lệnh, không đánh dấu', [ws.kq('Y3C')['ok'], len(calls['mark']) == n_mark, bool(ws.lenh('Y3C')), 'Editor Lite' in ws.kq('Y3C')['loi']], [False, True, True, True])

# 3. Đã gửi rồi máy báo lỗi (hết giấy) → xoá lệnh (không in lặp), không đánh dấu
label_print.print_records = fake_print(False, 'máy in báo: hết giấy', da_gui=True)
label_print.poll_once(ws)
eq('lỗi sau khi gửi: xoá lệnh, không đánh dấu', [ws.lenh('Y3C'), len(calls['mark']) == n_mark], ['', True])

# 4. Lệnh quá 30 phút → bỏ, không in
n_print = calls['print']
ws.v[1][1] = job(luc=(datetime.now() - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S'))
label_print.poll_once(ws)
eq('lệnh cũ → bỏ, không in', [ws.kq('15E')['ok'], calls['print'] == n_print, ws.lenh('15E')], [False, True, ''])

# 5. In bù: không có dòng NHAP → không đánh dấu
label_print.print_records = fake_print(True)
ws.v[1][1] = job(dong=())
label_print.poll_once(ws)
eq('in bù: in xong, không đánh dấu', [ws.kq('15E')['ok'], len(calls['mark']) == n_mark], [True, True])

# 6. Bot ghi lệnh mới trong lúc đang in → không xoá lệnh mới
newer = job(so_tem=1)
orig = label_print.process_job


def racing(lenh, dry=False):
    ws.v[1][1] = newer
    return orig(lenh, dry)


label_print.process_job = racing
ws.v[1][1] = job()
label_print.poll_once(ws)
label_print.process_job = orig
eq('lệnh mới đến giữa chừng → giữ lại', ws.lenh('15E'), newer)

# 7. Cắt cuối đợt: 1 lệnh, "cắt sau N tem" = N
from brother_ql.conversion import convert  # noqa: E402
imgs = [img] * 4
data = convert(qlr=label_print.batch_raster('QL-700', 4, False), images=imgs, label='62x29', rotate='0', cut=True)
eq('cắt cuối đợt: ESC i A 4, 1 lần kết thúc', [data.count(b'\x1biA\x04'), data.count(b'\x1biA\x01'), data.endswith(b'\x1a')], [4, 0, True])
data1 = convert(qlr=label_print.batch_raster('QL-700', 4, True), images=imgs, label='62x29', rotate='0', cut=True)
eq('cắt từng tem: ESC i A 1', data1.count(b'\x1biA\x01'), 4)

if fails:
    sys.exit(1)
print("✅ test_label_print đạt")
