"""Công nợ nhà cung cấp dự phòng trên Mac (luật 15, GĐ1 thay MISA, 03/11) — ra CÙNG số với web Sổ quỹ › Công nợ NCC (supplier_orders.ts congNo):
- Dữ liệu gốc đọc act cong_no_ds (khoá Mac, bản sao như sổ quỹ): ncc (nợ đầu kỳ), nhan (lần nhận, huy), tra_ncc, hd (chiết khấu / phí, bi_thay).
- Đã trả = phiếu PC có ncc trong so_quy_ds (bỏ phiếu huỷ, kể cả đặt cọc; PT không tính).
- Tiền hàng đã nhận / phiếu = Σ sl × gia_nhap (lần không huỷ) − Σ trả NCC × gia_nhap + Σ (chiết khấu + phí) HĐ không bị thay, làm tròn theo phiếu.
- Bỏ mọi phiếu ở trạng thái nhap (theo mảng phieu, dù act đã lọc sẵn).
- Còn nợ = nợ đầu kỳ + tiền hàng − đã trả. Tên NCC so khớp không dấu / không hoa thường / gộp khoảng trắng. Xếp còn nợ giảm dần rồi theo tên.
"""
import re
import unicodedata

COT = ['Nhà cung cấp', 'Nợ đầu kỳ', 'Tiền hàng đã nhận', 'Đã trả', 'Còn nợ']


def ncc_key(t):
    s = str(t or '').replace('đ', 'd').replace('Đ', 'd')
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s.lower()).strip()


def _round(x):
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)  # như Math.round (nửa lên)


def cong_no(cn, phieu_quy):
    by = {}

    def get(ten):
        k = ncc_key(ten)
        if k not in by:
            by[k] = {'ncc': ten, 'dau_ky': 0, 'tien_hang': 0, 'da_tra': 0}
        return by[k]

    for p in phieu_quy:  # web: phiếu chi trước (tên hiện theo lần gặp đầu)
        if p.get('loai') == 'PC' and p.get('ncc') and not p.get('huy_luc'):
            get(p['ncc'])['da_tra'] += p['so_tien'] or 0
    nhap = {p['phieu'] for p in cn.get('phieu', []) if p.get('trang_thai') == 'nhap'}
    tien, ncc_phieu = {}, {p['phieu']: p['ncc'] for p in cn.get('phieu', []) if p['phieu'] not in nhap}
    for n in (x for x in cn.get('nhan', []) if x['phieu'] not in nhap):
        ncc_phieu.setdefault(n['phieu'], n['ncc'])
        if not n.get('huy'):
            tien[n['phieu']] = tien.get(n['phieu'], 0) + (n['sl'] or 0) * (n['gia_nhap'] or 0)
    for t in (x for x in cn.get('tra_ncc', []) if x['phieu'] not in nhap):
        ncc_phieu.setdefault(t['phieu'], t['ncc'])
        tien[t['phieu']] = tien.get(t['phieu'], 0) - (t['sl'] or 0) * (t['gia_nhap'] or 0)
    for h in (x for x in cn.get('hd', []) if x['phieu'] not in nhap):
        ncc_phieu.setdefault(h['phieu'], h['ncc'])
        if not h.get('bi_thay'):
            tien[h['phieu']] = tien.get(h['phieu'], 0) + (h['chiet_khau'] or 0) + (h['phi'] or 0)
    for x in cn.get('ncc', []):
        get(x['ten'])
    for ph, ncc in ncc_phieu.items():
        if ncc:
            get(ncc)['tien_hang'] += _round(tien.get(ph, 0))
    for x in cn.get('ncc', []):
        get(x['ten'])['dau_ky'] += x.get('no_dau') or 0
    out = [dict(o, con=o['dau_ky'] + o['tien_hang'] - o['da_tra']) for o in by.values()]
    out.sort(key=lambda o: (-o['con'], ncc_key(o['ncc']), o['ncc']))
    return out


def xlsx_rows(ds):
    return [COT] + [[o['ncc'], o['dau_ky'], o['tien_hang'], o['da_tra'], o['con']] for o in ds]
