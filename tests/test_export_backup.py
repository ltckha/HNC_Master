"""File dự phòng hằng ngày (tools/export_backup.py) — chạy: venv/bin/python tests/test_export_backup.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import export_backup as b  # noqa: E402

ok = fail = 0


def eq(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"❌ {name}\n   got:  {got}\n   want: {want}")


DATA = {'tao_luc': '2026-11-04T05:52:24Z', 'tu': '2000-01-01', 'ghi_chu': 'x',
        'so_quy': {'quy': [{'id': 1}], 'phieu': [{'so': 'PC000008', 'anh': 'https://x/a'}, {'so': 'PT000001', 'anh': None}], 'dau_ky': [], 'luat': ['l1']},
        'cong_no': {'ncc': [], 'phieu': [], 'nhan': [{'sl': 2, 'gia_nhap': 300000}], 'tra_ncc': [], 'hd': [], 'hd_cho': [], 'luat': []},
        'nhap_hang': {'phieu': [{'id': 18}], 'dong': [], 'dot': [], 'sua': []},
        'bu_tru': [{'thang': '2026-11', 'khoan': {'the': 700000, 'doi': 950000}, 'tong': 1650000}]}
s = dict(b.sheets(DATA))
eq('bù trừ: khoản trải thành cột', s['Bu_tru'], [{'thang': '2026-11', 'tong': 1650000, 'khoan_the': 700000, 'khoan_doi': 950000}])
eq('đủ sheet', list(s), ['So_quy_quy', 'So_quy_phieu', 'So_quy_dau_ky', 'Cong_no_ncc', 'Cong_no_phieu', 'Cong_no_nhan', 'Cong_no_tra', 'Cong_no_hd', 'Cong_no_hd_cho',
                        'Nhap_hang_phieu', 'Nhap_hang_dong', 'Nhap_hang_dot', 'Nhap_hang_sua', 'Bu_tru'])
eq('ảnh: chỉ phiếu có link, tên theo số phiếu', b.images(DATA), [('PC000008', 'https://x/a')])
with tempfile.TemporaryDirectory() as d:
    for i in range(1, 33):
        open(os.path.join(d, f'2026-10-{i:02d}.xlsx' if i <= 31 else '2026-11-01.xlsx'), 'w').close()
    open(os.path.join(d, '2026-11-04_beta.xlsx'), 'w').close()
    n = b.rotate(d, '2026-11-01')
    eq('giữ 30 file gần nhất, 2 file cũ nhất chuyển cu/ (file _beta không tính)', (n, sorted(os.listdir(os.path.join(d, 'cu'))), len([f for f in os.listdir(d) if f.endswith('.xlsx')])),
       (2, ['2026-10-01.xlsx', '2026-10-02.xlsx'], 31))
    p = b.write_xlsx(os.path.join(d, 'x.xlsx'), DATA)
    from openpyxl import load_workbook
    wb = load_workbook(p)
    eq('xlsx: sheet Thong_tin + 14 sheet, cột theo khoá', (len(wb.sheetnames), [c.value for c in wb['Cong_no_nhan'][1]], wb['Cong_no_nhan']['B2'].value), (15, ['sl', 'gia_nhap'], 300000))
print(f"{'✅' if not fail else '❌'} {ok}/{ok + fail} ca đạt")
sys.exit(1 if fail else 0)
