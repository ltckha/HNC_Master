"""ĐVT mã mới theo ngành (tools/category_defaults.don_vi_tinh, 05/11 như web) — chạy: venv/bin/python tests/test_category_defaults.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.category_defaults import don_vi_tinh, dvt_da_so  # noqa: E402

ok = fail = 0


def eq(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"❌ {name}\n   got:  {got}\n   want: {want}")


ds = dvt_da_so([('Thắt lưng nam', 'Cái'), ('Thắt lưng nam', 'Cái'), ('Thắt lưng nam', 'Đôi'), ('Giày tây nam', 'Đôi'), ('Ví nữ', ''), ('', 'Cái')])
eq('đa số theo ngành (bỏ ô trống)', ds, {'thắt lưng nam': 'Cái', 'giày tây nam': 'Đôi'})
eq('thắt lưng theo đa số ra Cái', don_vi_tinh('Thắt lưng  NAM', '', ds), 'Cái')
eq('ghi rõ thì giữ', don_vi_tinh('Thắt lưng nam', 'Sợi', ds), 'Sợi')
eq('ngành chưa có mã: giày / dép / sandal / bốt / sapo / guốc → Đôi', [don_vi_tinh(n, '', ds) for n in ('Giày cao gót nữ', 'Dép nam', 'Sandal nữ', 'Bốt nữ', 'Sapo nam', 'Guốc nữ')], ['Đôi'] * 6)
eq('ngành chưa có mã khác → Cái', [don_vi_tinh(n, None, ds) for n in ('Ví nữ', 'Túi xách', 'Ba lô')], ['Cái'] * 3)
print(f"{'✅' if not fail else '❌'} {ok}/{ok + fail} ca đạt")
sys.exit(1 if fail else 0)
