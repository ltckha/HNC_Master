"""Khoá ghi Sheet Mac (14/11): tools/sheet_guard chặn hàm ghi gspread khi DU_PHONG_CONG=1 và cả 4 sổ ở Web; chừa tab META.
Không gọi mạng, không đụng Sheet thật.  venv/bin/python tests/test_sheet_guard.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gspread  # noqa: E402
from tools import sheet_guard, web_commands  # noqa: E402

fails = 0


def eq(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(('✅ ' if ok else '❌ ') + name + ('' if ok else f'\n   được {got!r}\n   cần  {want!r}'))


class SS:
    id = 'SHEET_GIA'


ENV, META, WEB = {}, {}, {'du_phong': False}
web_commands._env = lambda n: ENV.get(n, '')
web_commands.meta = lambda sh: dict(META)
web_commands.du_phong = lambda: dict(WEB)


def ws(title):
    w = gspread.Worksheet.__new__(gspread.Worksheet)
    w._properties, w._spreadsheet = {'title': title}, SS()
    return w


def thu(title, ham='update_cell', *a):
    sheet_guard._NHO.clear()
    try:
        getattr(ws(title), ham)(*(a or (1, 1, 'x')))
    except sheet_guard.KhoaGhi:
        return 'khoa'
    except Exception:
        return 'ghi'  # qua chốt, tới gọi mạng (Sheet giả) → coi như được ghi
    return 'ghi'


eq('công tắc tắt → ghi như cũ', thu('BAN'), 'ghi')
ENV['DU_PHONG_CONG'] = '1'
eq('bật + web không Dự phòng → chặn update_cell BAN', thu('BAN'), 'khoa')
eq('chặn append_rows SANPHAM', thu('SANPHAM', 'append_rows', [['a']]), 'khoa')
eq('chặn batch_update KHO15E', thu('KHO15E', 'batch_update', []), 'khoa')
eq('chừa META (đổi chế độ menu [7])', thu('META'), 'ghi')
WEB['du_phong'] = True
eq('web Dự phòng → ghi', thu('BAN'), 'ghi')
WEB.clear()
WEB['loi'] = 'web không trả lời'
META.update(che_do='web', che_do_kho='web', che_do_ton='web', che_do_hh='web')
eq('web sập + META web → chặn', thu('NHAP'), 'khoa')
META['che_do_kho'] = 'master'
eq('web sập + Chủ mở 1 sổ (META master) → mở', thu('NHAP'), 'ghi')
try:
    sheet_guard._NHO.clear()
    META['che_do_kho'] = 'web'
    gspread.Spreadsheet.values_update(SS(), 'BAN!A1', params={}, body={})
    r = 'ghi'
except sheet_guard.KhoaGhi:
    r = 'khoa'
except Exception:
    r = 'ghi'
eq('chặn cả lệnh ghi cấp Spreadsheet (values_update BAN!A1)', r, 'khoa')
print(('❌ ' if fails else '✅ ') + 'test_sheet_guard ' + ('lỗi ' + str(fails) if fails else 'đạt'))
sys.exit(1 if fails else 0)
