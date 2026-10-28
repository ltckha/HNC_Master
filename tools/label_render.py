"""Dựng tem mã hàng 62×29 mm (giấy DK-11209) giống mẫu P-touch Minicode.lbx — dùng chung cho in tự động (tools/label_print.py)
và menu Mac (main.py task 10), luật 15. Chỉ dùng Pillow + font Helvetica của macOS, không cần thư viện mã vạch.

Bố cục lấy từ Minicode.lbx (khung 175.7 × 81.8 pt):
  - Tên       : x 4, y 2.4, 130.7 × 53.3 pt (trái trên, nhiều dòng)
  - Mã vạch   : CODE128 xoay 270°, x 138.4, y 8, 32.9 × 54.5 pt (mép phải), có số bên dưới vạch
  - Size Color: x 64.8, y 56, 69.6 × 17.6 pt (dưới giữa)
  - Không in tên kho trên tem (anh Kha 18/10); 2 kho vẫn in 2 đợt riêng
"""
from PIL import Image, ImageDraw, ImageFont

LABEL_ID = '62x29'          # brother_ql: nhãn cắt sẵn 62 × 29 mm
DOTS = (696, 271)           # vùng in của nhãn 62x29 ở 300 dpi (brother_ql dots_printable)
PAPER_PT = (175.7, 81.8)    # khung mẫu P-touch
FONT_PATHS = [('/System/Library/Fonts/Helvetica.ttc', 1), ('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 0)]  # chữ đậm (anh Kha 18/10)

# CODE128: mẫu vạch 0–106 (bộ chuẩn), mỗi số là độ rộng vạch / khoảng trắng xen kẽ
CODE128 = ['212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312', '132212', '221213', '221312', '231212', '112232',
           '122132', '122231', '113222', '123122', '123221', '223211', '221132', '221231', '213212', '223112', '312131', '311222', '321122',
           '321221', '312212', '322112', '322211', '212123', '212321', '232121', '111323', '131123', '131321', '112313', '132113', '132311',
           '211313', '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121', '313121', '211331', '231131', '213113',
           '213311', '213131', '311123', '311321', '331121', '312113', '312311', '332111', '314111', '221411', '431111', '111224', '111422',
           '121124', '121421', '141122', '141221', '112214', '112412', '122114', '122411', '142112', '142211', '241211', '221114', '413111',
           '241112', '134111', '111242', '121142', '121241', '114212', '124112', '124211', '411212', '421112', '421211', '212141', '214121',
           '412121', '111143', '111341', '131141', '114113', '114311', '411113', '411311', '113141', '114131', '311141', '411131', '211412',
           '211214', '211232', '2331112']
START_B, STOP = 104, 106


def code128_modules(text):
    """Chuỗi độ rộng (module) CODE128 bộ B cho text ASCII 32–126, kèm số kiểm tra."""
    codes = [START_B] + [ord(ch) - 32 for ch in text]
    check = (START_B + sum((i + 1) * c for i, c in enumerate(codes[1:]))) % 103
    return ''.join(CODE128[c] for c in codes + [check, STOP])


def _font(size):
    for p, idx in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size, index=idx)
        except OSError:
            continue
    return ImageFont.load_default()


def _box(x, y, w, h):
    sx, sy = DOTS[0] / PAPER_PT[0], DOTS[1] / PAPER_PT[1]
    return int(x * sx), int(y * sy), int(w * sx), int(h * sy)


def _wrap(draw, text, font, width):
    words, lines, cur = str(text).split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_text(draw, text, box, max_size=40, min_size=14):
    x, y, w, h = box
    for size in range(max_size, min_size - 1, -2):
        f = _font(size)
        lines = _wrap(draw, text, f, w)
        if len(lines) * (size + 4) <= h:
            for i, ln in enumerate(lines):
                draw.text((x, y + i * (size + 4)), ln, font=f, fill=0)
            return
    f = _font(min_size)
    for i, ln in enumerate(_wrap(draw, text, f, w)[: max(1, h // (min_size + 4))]):
        draw.text((x, y + i * (min_size + 4)), ln, font=f, fill=0)


MAU_MAC_DINH = 'A'  # mẫu tem đang dùng: 'goc' (giống Minicode) hoặc 'A' / 'B' / 'C' (mã vạch ngang to, có giá) · 'QR' (B18, 28/10: in thử)
WEB_SP = 'https://giayhainancy.vn/product/'  # QR = trang sản phẩm theo mã cha, ?s=<size> (B18)


def _render_qr(rec):
    """B18 (anh Kha "làm" 28/10, Phân tích · Bán hàng mục 13 + chốt iii): QR phiên bản 4 (33 ô) mức M, 6 điểm / ô = 198 px,
    góc trái trên lề 14; dưới QR "Quét QR xem sản phẩm"; cột phải x 236 → 682: mã cha to + ô size đen, tên + màu 2 dòng, giá to."""
    import segno
    img = Image.new('L', DOTS, 255)
    d = ImageDraw.Draw(img)
    W, H = DOTS
    code, size = str(rec.get('Code128', '')).strip(), str(rec.get('Size', '')).strip()
    ma = code[:-len(size)] if size and code.endswith(size) else code
    q = segno.make(WEB_SP + ma + (f'?s={size}' if size else ''), error='m', version=4, boost_error=False)
    for y, row in enumerate(q.matrix):
        for x, on in enumerate(row):
            if on:
                d.rectangle([14 + x * 6, 14 + y * 6, 14 + x * 6 + 5, 14 + y * 6 + 5], fill=0)
    f = _font(19)
    cap = 'Quét QR xem sản phẩm'
    d.text((14 + (198 - d.textlength(cap, font=f)) / 2, 218), cap, font=f, fill=0)
    x0, x1 = 236, 682
    box = 78
    if size:
        d.rectangle([x1 - box, 8, x1, 8 + box], fill=0)
        for fs in range(60, 20, -4):
            fz = _font(fs)
            tw = d.textlength(size, font=fz)
            if tw <= box - 8:
                bb = d.textbbox((0, 0), size, font=fz)
                d.text((x1 - box + (box - tw) / 2, 8 + (box - (bb[3] - bb[1])) / 2 - bb[1]), size, font=fz, fill=255)
                break
    _one_line(d, ma, x0, 8, x1 - x0 - (box + 12 if size else 0), 76, bold_min=30)
    ten = str(rec.get('Tên', '')).strip()
    if ma and ten.upper().endswith(ma.upper()):
        ten = ten[:-len(ma)].strip()  # tên SANPHAM thường kèm mã ở cuối — mã đã in to ở hàng 1
    mau = str(rec.get('Màu', '')).strip()
    ten = (ten + (' màu ' + mau if mau else '')).strip()
    f = _font(25)
    lines = _wrap(d, ten, f, x1 - x0)
    if len(lines) > 2:
        lines = lines[:2]
        while lines[1] and d.textlength(lines[1] + '…', font=f) > x1 - x0:
            lines[1] = lines[1][:-1]
        lines[1] += '…'
    y = 110 if len(lines) == 2 else 126
    for i, ln in enumerate(lines):
        d.text((x0, y + i * 31), ln, font=f, fill=0)
    gia = _price(rec).replace(' đ', 'đ')
    f = _font(58)
    d.text((x1 - d.textlength(gia, font=f), 190), gia, font=f, fill=0)
    return img.point(lambda v: 0 if v < 128 else 255, '1')


def _barcode_h(img, code, y, h, human=24):
    """CODE128 nằm ngang, rộng nhất có thể (module 3–5 điểm), căn giữa, chừa vùng trắng 10 module mỗi bên."""
    d = ImageDraw.Draw(img)
    mods = code128_modules(code)
    total = sum(int(m) for m in mods) + 20
    unit = max(2, min(5, DOTS[0] // total))
    x = (DOTS[0] - unit * total) // 2 + unit * 10
    bar = True
    for m in mods:
        w = int(m) * unit
        if bar:
            d.rectangle([x, y, x + w - 1, y + h - human - 4], fill=0)
        x += w
        bar = not bar
    f = _font(human)
    tw = d.textlength(code, font=f)
    d.text(((DOTS[0] - tw) // 2, y + h - human), code, font=f, fill=0)


def _one_line(draw, text, x, y, w, size, bold_min=14):
    """1 dòng chữ, thu nhỏ đến khi vừa w."""
    for s in range(size, bold_min - 1, -2):
        f = _font(s)
        if draw.textlength(text, font=f) <= w:
            draw.text((x, y), text, font=f, fill=0)
            return s
    f = _font(bold_min)
    while text and draw.textlength(text + '…', font=f) > w:
        text = text[:-1]
    draw.text((x, y), text + '…', font=f, fill=0)
    return bold_min


def _price(rec):
    return str(rec.get('Gía') or rec.get('Giá') or '').strip()


def _render_new(rec, kho, mau):
    img = Image.new('L', DOTS, 255)
    d = ImageDraw.Draw(img)
    W, H = DOTS
    name, sc, price, code = str(rec.get('Tên', '')).strip(), str(rec.get('Size Color', '')).strip(), _price(rec), str(rec.get('Code128', '')).strip()
    tag = ''  # không in tên kho trên tem (anh Kha 18/10)
    if mau == 'A':      # tên 2 dòng · màu-size trái, giá phải · mã vạch ngang dưới
        _fit_text(d, name, (8, 2, W - 16, 82), max_size=30, min_size=20)  # tên dài xuống dòng 2
        _one_line(d, sc + tag, 8, 92, W // 2, 30)
        f = _font(38)
        d.text((W - 8 - d.textlength(price, font=f), 86), price, font=f, fill=0)
        if code:
            _barcode_h(img, code, 138, 130)
    elif mau == 'B':    # giá thật to trên cùng · tên 1 dòng · mã vạch ngang dưới
        f = _font(56)
        d.text((8, 0), price, font=f, fill=0)
        pw = d.textlength(price, font=f)
        _one_line(d, sc + tag, int(pw) + 24, 16, W - int(pw) - 32, 30)
        _one_line(d, name, 8, 66, W - 16, 26)
        if code:
            _barcode_h(img, code, 104, 164)
    else:               # C: gọn, không tên · mã + size to · giá · mã vạch cao nhất
        _one_line(d, sc + tag, 8, 4, W // 2 + 40, 34)
        f = _font(44)
        d.text((W - 8 - d.textlength(price, font=f), 0), price, font=f, fill=0)
        if code:
            _barcode_h(img, code, 60, 208, human=28)
    return img.point(lambda v: 0 if v < 128 else 255, '1')


def render_label(rec, kho='', mau=None):
    mau = mau or MAU_MAC_DINH
    if mau == 'QR':
        return _render_qr(rec)
    if mau in ('A', 'B', 'C'):
        return _render_new(rec, kho, mau)
    return _render_goc(rec, kho)


def _render_goc(rec, kho=''):
    """rec: 1 dòng tem (cột LABEL_COLUMNS: 'Tên', 'Size Color', 'Code128'…) → ảnh 1-bit 696 × 271 cho brother_ql."""
    img = Image.new('L', DOTS, 255)
    d = ImageDraw.Draw(img)
    _fit_text(d, rec.get('Tên', ''), _box(4, 2.4, 130.7, 53.3))
    # Size Color dưới giữa
    sx, sy, sw, sh = _box(64.8, 56, 69.6, 17.6)
    _fit_text(d, rec.get('Size Color', ''), (sx, sy, sw, sh), max_size=34, min_size=16)
    # Mã vạch xoay 270° ở mép phải: vẽ ngang rồi xoay
    code = str(rec.get('Code128', '')).strip()
    bx, by, bw, bh = _box(138.4, 8, 32.9, 54.5)
    if code:
        mods = code128_modules(code)
        total = sum(int(m) for m in mods)
        # Vạch tối thiểu 2 điểm (≈0.17 mm, như barWidth 0.6pt của mẫu) để máy quét đọc được; mã dài thì dùng hết chiều cao tem
        avail = DOTS[1] - 12
        unit = max(2, min(3, avail // (total + 10)))
        by = max(4, (DOTS[1] - unit * (total + 10)) // 2)
        human = 22
        strip = Image.new('L', (unit * (total + 10), bw), 255)
        sd = ImageDraw.Draw(strip)
        pos, bar = unit * 5, True
        for m in mods:
            wdt = int(m) * unit
            if bar:
                sd.rectangle([pos, 0, pos + wdt - 1, bw - human - 4], fill=0)
            pos += wdt
            bar = not bar
        sd.text((unit * 5, bw - human), code, font=_font(human - 2), fill=0)
        rot = strip.rotate(270, expand=True)
        img.paste(rot, (bx + max(0, (bw - rot.width) // 2), by))
    return img.point(lambda v: 0 if v < 128 else 255, '1')
