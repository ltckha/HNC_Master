"""Tên sản phẩm (CON_NAME) theo quy tắc anh Kha chốt 19/11 — bản Mac của hàm web ghepTen
(Website-giayhainancy src/worker/products/source.ts). Luật 15: 2 đường ra cùng tên; ca thử chung shared/product_name_cases.json.

Tên = Ngành (tăng chiều cao thêm "<tang_cao_cm>cm") · 1 điểm phân biệt · Thương hiệu · Chất liệu · Bề mặt da · (Big Size) · Mã.
Ô trống bỏ qua, không 2 dấu cách, KHÔNG "cao cấp". Từ 19/11 CON_NAME trên Sheet là GIÁ TRỊ (web ghi), không còn công thức TEXTJOIN.
"""
import re
import unicodedata

MAT = {'tron', 'hat mem', 'van', 'da lon', 'lon'}


def _s(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def _dau1(v):
    """Nhiều giá trị (ngăn , hoặc ;) → giá trị đầu."""
    return re.split(r'[,;]', _s(v))[0].strip()


def _fd(t):
    """Bỏ dấu, đ → d, chữ thường, gộp khoảng trắng."""
    t = unicodedata.normalize('NFD', t)
    t = re.sub('[̀-ͯ]', '', t)
    t = re.sub('đ', 'd', t, flags=re.I)
    return re.sub(r'\s+', ' ', t.lower()).strip()


def _co_trong(ng, t):
    """Chữ t đã có trong tên ngành (cả cụm, bỏ dấu)."""
    return bool(t) and (' ' + _fd(t) + ' ') in (' ' + _fd(ng) + ' ')


def _so(v):
    try:
        return float(_s(v).strip().replace(',', '.', 1))
    except ValueError:
        return 0.0


def ghep_ten(r):
    """Dòng SANPHAM (dict tên cột → giá trị) → tên sản phẩm."""
    def g(k):
        return _s(r.get(k)).strip()
    ng = g('Tên Ngành Hàng')
    tc = _so(g('tang_cao_cm'))
    if tc > 0 and re.search('tăng chiều cao', ng, re.I):
        ng = re.sub('tăng chiều cao', 'tăng chiều cao ' + ('%g' % tc).replace('.', ',') + 'cm', ng, count=1, flags=re.I)
    fn, cu = _fd(ng), _dau1(r.get('Đặc điểm'))
    if re.match(r'(dep|sandal)', fn):
        pb = re.sub(r'^kẹp ngón.*$', 'quai kẹp ngón', _dau1(r.get('kieu_quai')), flags=re.I)
    elif re.search(r'bup be|cao got|de xuong', fn):
        pb = ('mũi ' + _dau1(r.get('dang_mui'))) if _dau1(r.get('dang_mui')) else ''
    elif re.match(r'(giay|sapo|bot|boot)', fn):
        pb = _dau1(r.get('kieu_dong'))
    else:
        pb = cu
    if not pb:
        pb = cu
    if re.fullmatch(r'nam|nữ', pb, re.I):
        pb = pb.lower()
    if _co_trong(ng, pb):
        pb = ''
    cl = re.sub(r'\s*cao cấp\s*', ' ', _dau1(r.get('chat_lieu')) or _dau1(r.get('Chất liệu')), flags=re.I).strip()  # bỏ hẳn "cao cấp" (Chất liệu cũ "da bò cao cấp", web 3263d324)
    la_da = bool(re.search(r'\bda\b', _fd(cl), re.I | re.A))
    mat = _dau1(r.get('be_mat')) if la_da else ''
    if not mat and la_da and _fd(_dau1(r.get('Nhấn mạnh'))) in MAT:
        mat = _dau1(r.get('Nhấn mạnh'))  # bề mặt cũ ghi ở Nhấn mạnh (trơn / hạt mềm / vân)
    if _fd(mat) == 'da lon':
        mat = 'lộn'
    big = 'Big Size' if re.search('big size', g('Nhấn mạnh'), re.I) else ''
    return re.sub(r'\s+', ' ', ' '.join(x for x in (ng, pb, g('Thương hiệu'), cl, mat, big, g('product_code')) if x)).strip()
