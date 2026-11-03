"""Khoá sổ tháng (luật 15, như web src/worker/book_lock.ts d10686ac, GĐ3 04/11): hết ngày 5 tháng sau thì sổ tháng trước khoá.
Mac chặn ghi dòng có ngày thuộc tháng đã khoá (chốt chung ở main.py khi thêm dòng tab BAN).
Tháng đang mở lại 24 giờ: đọc `so_mo` {thang, den} trong số liệu sổ quỹ web gửi Mac (act so_quy_ds) nếu web có gửi; không có = coi như đang khoá.
"""
from datetime import datetime, timezone

NGAY_KHOA = 5


def _thang_sau(m):
    y, mo = map(int, m.split('-'))
    return f'{y + 1}-01' if mo == 12 else f'{y}-{mo + 1:02d}'


def khoa_tu(m):
    """Ngày bắt đầu khoá sổ tháng m (YYYY-MM): ngày 6 tháng sau."""
    return f'{_thang_sau(m)}-{NGAY_KHOA + 1:02d}'


def dang_mo(so_mo, now=None):
    """so_mo = {thang, den (ISO)} từ web → tháng đang mở lại, hoặc None."""
    if not isinstance(so_mo, dict) or not so_mo.get('thang') or not so_mo.get('den'):
        return None
    try:
        den = datetime.fromisoformat(str(so_mo['den']).replace('Z', '+00:00'))
    except ValueError:
        return None
    return so_mo['thang'] if den > (now or datetime.now(timezone.utc)) else None


def loi_khoa(ngay, hom_nay, mo_thang=None):
    """Lỗi nếu ngày `ngay` (YYYY-MM-DD) thuộc tháng đã khoá và chưa mở lại; None = ghi được."""
    if not ngay or len(ngay) < 10:
        return None
    m = ngay[:7]
    if hom_nay < khoa_tu(m) or mo_thang == m:
        return None
    k = khoa_tu(m)
    return f"Sổ tháng {m[5:]}/{m[:4]} đã khoá từ {k[8:]}/{k[5:7]} — mở lại 24 giờ trên web (Sổ thuế / Sổ quỹ) rồi chạy lại"
