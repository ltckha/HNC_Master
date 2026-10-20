"""Thử P0 mục 4–5 trên Sheet BẢN THỬ (HNC_Master_BAN_THU, có ghi vào bản thử — không đụng Sheet thật).
KHÔNG chạy lúc web đang diễn tập (bài này tạm đổi che_do); cuối bài trả META như lúc đầu.
Chạy: venv/bin/python tests/test_p0_ban_thu.py"""
import os
import sys

TEST_ID = '1QwH7Y1A45Pb9S0JbfDSkrP-VeUmD_cA6FsKdI4Gmxcw'
os.environ['HNC_SHEET_ID'] = TEST_ID
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hnc_paths  # noqa: E402
hnc_paths.find_system_dir = lambda: '/tmp'
import main  # noqa: E402

assert main.SPREADSHEET_ID == TEST_ID != main.SPREADSHEET_ID_THAT
fails = []


def eq(name, got, want):
    if got != want:
        fails.append(name)
        print(f'❌ {name}: {got!r} != {want!r}')


def set_che_do(L, v):
    ws = L.spreadsheet.worksheet('META')
    rows = ws.get_all_values()
    r = next(i + 1 for i, x in enumerate(rows) if x and x[0] == 'che_do')
    ws.update_acell(f'B{r}', v)


L = main.EngineDataLoader()
# Bản thử dùng chung với web diễn tập → nhớ trạng thái META lúc đầu, cuối bài trả lại y nguyên
_meta0 = {r[0]: r[1] for r in L.spreadsheet.worksheet('META').get_all_values()[1:] if r and r[0] in ('che_do', 'che_do_luc', 'che_do_boi', 'cho_chep')}
main.set_meta(L, {'che_do': 'master', 'cho_chep': '0'})
L = main.EngineDataLoader()
eq('bản thử: che_do master', L.che_do(), 'master')
eq('master: được ghi', L._write_ok('BAN'), True)
n0 = len(L.spreadsheet.worksheet('BAN').get_all_values())
set_che_do(L, 'web')
try:
    L2 = main.EngineDataLoader()
    eq('đổi META che_do = web → đọc web', L2.che_do(), 'web')
    eq('web: chặn ghi BAN', L2.append_rows_to_sheet('BAN', [['thử']]), False)
    eq('web (P1 chỉ sổ bán): NHAP vẫn ghi được', L2._write_ok('NHAP'), True)
    eq('web: chặn update_status BAN', L2.update_status('BAN', [5], 9, 'x'), False)
    eq('web: META vẫn ghi được (không khoá)', L2._write_ok('META'), True)
    eq('web: BAN không thêm dòng', len(L2.spreadsheet.worksheet('BAN').get_all_values()), n0)
finally:
    set_che_do(L, 'master')
eq('trả lại master', main.EngineDataLoader().che_do(), 'master')
# META cho_chep (web ghi): > 0 → chưa ghi BAN / NHAP / XUAT; về 0 → ghi được
main.set_meta(L, {'cho_chep': '3'})
try:
    eq('cho_chep 3 → chặn BAN', main.EngineDataLoader()._write_ok('BAN'), False)
    eq('cho_chep 3 → KHO vẫn ghi được', main.EngineDataLoader()._write_ok('KHO15E'), True)
finally:
    main.set_meta(L, {'cho_chep': '0'})
eq('cho_chep 0 → ghi được', main.EngineDataLoader()._write_ok('BAN'), True)
# Menu [7] đổi che_do (gõ 2 lần)
import builtins  # noqa: E402
ans = iter(['2', '2'])
builtins.input = lambda *_: next(ans)
L3 = main.EngineDataLoader()
main.change_che_do(L3)
eq('menu 7: gõ 2 rồi 2 → META che_do = web', main.EngineDataLoader().che_do(), 'web')
ans = iter(['1', 'x'])
main.change_che_do(main.EngineDataLoader())
eq('menu 7: gõ lại sai → không đổi', main.EngineDataLoader().che_do(), 'web')
ans = iter(['1', '1'])
main.change_che_do(main.EngineDataLoader())
eq('menu 7: đổi lại master', main.EngineDataLoader().che_do(), 'master')
# Sổ kho (P2): [4] Kho → Web → chặn THÊM dòng NHAP, sửa ô trạng thái vẫn được; [3] về Dự phòng ghi mốc NHAP / XUAT
_kho0 = {r[0]: r[1] for r in L.spreadsheet.worksheet('META').get_all_values()[1:] if r and r[0].startswith(('che_do_kho', 'che_do_ton', 'che_do_hh', 'du_phong_'))}
ans = iter(['4', '4'])
main.change_che_do(main.EngineDataLoader())
L4 = main.EngineDataLoader()
eq('kho Web: chặn thêm dòng NHAP', L4.insert_rows_with_exact_range('NHAP', [['x']], 99999), False)
eq('kho Web: sửa ô trạng thái NHAP vẫn được', L4._write_ok('NHAP'), True)
ans = iter(['3', '3'])
main.change_che_do(main.EngineDataLoader())
_m = {r[0]: r[1] for r in L.spreadsheet.worksheet('META').get_all_values()[1:] if r}
eq('kho → Dự phòng: che_do_kho master + mốc NHAP / XUAT', [_m.get('che_do_kho'), bool(_m.get('du_phong_nhap_hang')), bool(_m.get('du_phong_xuat_hang')), bool(_m.get('du_phong_kho_tu'))], ['master', True, True, True])
if _kho0:
    main.set_meta(L, _kho0)
a = main.acquire_mac_lock()
b = main.acquire_mac_lock()
eq('khoá: cửa sổ 2 bị chặn', [a is not None, b is None], [True, True])
a.close()
eq('khoá: tắt cửa sổ 1 thì mở lại được', main.acquire_mac_lock() is not None, True)
main.set_meta(L, _meta0 or {'che_do': 'master'})
print('↩️ Trả META bản thử như lúc đầu:', _meta0)
if fails:
    sys.exit(1)
print('✅ test_p0_ban_thu đạt (Sheet bản thử)')
