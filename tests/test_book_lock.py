"""Khoá sổ tháng Mac (tools/book_lock.py) theo web book_lock.ts — chạy: venv/bin/python tests/test_book_lock.py"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import book_lock as b  # noqa: E402

ok = fail = 0


def eq(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"❌ {name}\n   got:  {got}\n   want: {want}")


eq('khoá từ ngày 6 tháng sau (cả tháng 12)', [b.khoa_tu('2026-10'), b.khoa_tu('2026-12')], ['2026-11-06', '2027-01-06'])
eq('tới hết ngày 5 còn ghi được', b.loi_khoa('2026-10-31', '2026-11-05'), None)
eq('từ ngày 6 thì khoá', bool(b.loi_khoa('2026-10-31', '2026-11-06')), True)
eq('tháng đang mở lại thì ghi được', b.loi_khoa('2026-10-31', '2026-11-06', '2026-10'), None)
eq('tháng hiện tại không khoá; ngày trống bỏ qua', [b.loi_khoa('2026-11-01', '2026-11-20'), b.loi_khoa('', '2026-12-20')], [None, None])
now = datetime(2026, 11, 6, 3, tzinfo=timezone.utc)
eq('so_mo còn hạn / hết hạn / thiếu', [b.dang_mo({'thang': '2026-10', 'den': '2026-11-06T20:00:00.000Z'}, now),
                                      b.dang_mo({'thang': '2026-10', 'den': '2026-11-06T01:00:00Z'}, now), b.dang_mo(None, now)], ['2026-10', None, None])
print(f"{'✅' if not fail else '❌'} {ok}/{ok + fail} ca đạt")
sys.exit(1 if fail else 0)
