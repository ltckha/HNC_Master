"""Khoá ghi Sheet HNC phía Mac (14/11, anh Kha: "zalo và sheet bây giờ chỉ cho hướng chạy dự phòng").

Công tắc DU_PHONG_CONG=1 (.env) và cả 4 sổ ở Web (tools/web_commands.che_do: web trả lời cổng /api/du-phong → theo cờ web;
web sập → theo META) → mọi lệnh ghi Sheet của Mac (menu main.py + mọi công cụ tools/ dùng gspread) dừng với câu báo.
Chỉ chừa tab META (đổi chế độ ở menu [7], mốc Dự phòng). Chủ mở tay 1 sổ (META master) → mở; từng sổ vẫn qua cổng riêng.
Cùng luật bot khoaGhi_ (luật 15). Dùng: `from tools import sheet_guard  # noqa: F401` ở đầu công cụ có ghi Sheet.
"""
import time

import gspread

from tools import web_commands

SO = ('che_do', 'che_do_kho', 'che_do_ton', 'che_do_hh')
TAB_DUOC_GHI = {'META'}
_NHO = {}


class KhoaGhi(RuntimeError):
    pass


def khoa(sh):
    """True = đang khoá ghi Sheet. Nhớ 60 giây mỗi Sheet."""
    if web_commands._env('DU_PHONG_CONG') != '1':
        return False
    k = getattr(sh, 'id', '')
    v = _NHO.get(k)
    if v and time.time() < v[1]:
        return v[0]
    m = web_commands.meta(sh)
    kq = all(web_commands.che_do(m, so) == 'web' for so in SO)
    _NHO[k] = (kq, time.time() + 60)
    return kq


def cau_bao(tab):
    return (f'⛔ Đang khoá ghi Sheet (web là sổ gốc): không ghi tab {tab}. Làm trên web https://giayhainancy.vn/admin, '
            'hoặc bật Dự phòng khi web hỏng (menu Mac [7] / bot "che do").')


def _boc_ws(ten):
    goc = getattr(gspread.Worksheet, ten)
    if getattr(goc, '_khoa', False):
        return

    def f(self, *a, **k):
        if self.title not in TAB_DUOC_GHI and khoa(self.spreadsheet):
            raise KhoaGhi(cau_bao(self.title))
        return goc(self, *a, **k)
    f._khoa = True
    setattr(gspread.Worksheet, ten, f)


def _boc_ss(ten):
    goc = getattr(gspread.Spreadsheet, ten)
    if getattr(goc, '_khoa', False):
        return

    def f(self, *a, **k):
        vung = str(a[0] if a else k.get('range', k.get('range_name', '')))
        if not vung.lstrip("'").startswith('META') and khoa(self):
            raise KhoaGhi(cau_bao(vung.split('!')[0] or 'Sheet'))
        return goc(self, *a, **k)
    f._khoa = True
    setattr(gspread.Spreadsheet, ten, f)


for _t in ('update', 'update_cells', 'batch_update', 'append_row', 'append_rows', 'insert_row', 'insert_rows', 'update_acell',
           'update_cell', 'delete_rows', 'clear', 'batch_clear', 'resize', 'add_rows', 'format'):
    if hasattr(gspread.Worksheet, _t):
        _boc_ws(_t)
for _t in ('batch_update', 'values_update', 'values_append', 'values_batch_update', 'values_clear', 'add_worksheet', 'del_worksheet'):
    if hasattr(gspread.Spreadsheet, _t):
        _boc_ss(_t)
