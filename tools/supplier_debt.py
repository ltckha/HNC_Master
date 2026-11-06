"""Công nợ nhà cung cấp dự phòng trên Mac (luật 15, GĐ1 thay MISA, 03/11) — ra CÙNG số với web Nhập hàng › Công nợ NCC (supplier_orders.ts congNo):
- Dữ liệu gốc đọc act cong_no_ds (khoá Mac, bản sao như sổ quỹ): ncc (nợ đầu kỳ), nhan (lần nhận, huy), tra_ncc, hd (chiết khấu / phí, bi_thay).
- Đã trả = phiếu PC có ncc trong so_quy_ds (bỏ phiếu huỷ, kể cả đặt cọc; PT không tính).
- 04/11 (web d6181484): tính riêng phiếu × hộ (kho nhận / hộ mua trên HĐ theo MST), phải trả = max(tiền hàng + thuế, tổng HĐ có thuế), làm tròn theo phiếu × hộ;
  trả gắn HĐ tính cho hộ của HĐ (hộ kia trả thay → Bù trừ 2 hộ trên web). Còn nợ từng hộ = phải trả − đã trả của hộ đó.
- Bỏ mọi phiếu ở trạng thái nhap (theo mảng phieu, dù act đã lọc sẵn).
- 06/11 (web 0fecb344, 2 sổ): cach='hd' Sổ NCC = chỉ tổng HĐ có thuế + nợ đầu kỳ MISA (khớp MISA); cach='thuc' Công nợ NCC = nhận × giá nhập − trả NCC
  + thuế GTGT HĐ (06/11 f8491339, chỉ phiếu đã nhập kho; không cộng chiết khấu / phí, không đầu kỳ); cach='max' (cũ) còn dùng cho Trả tiền phiếu trên web. Đã trả trừ ở cả 3.
- Còn nợ = nợ đầu kỳ + tiền hàng − đã trả. Tên NCC so khớp không dấu / không hoa thường / gộp khoảng trắng. Xếp còn nợ giảm dần rồi theo tên.
- 05/11 (web chu_ncc_ten_phu): tên phụ (cn.ten_phu [{khoa, ncc}], vd tên công ty đầy đủ / "ĐẠI PHONG") gộp vào NCC chính, dòng hiện tên chính.
"""
import re
import unicodedata

COT = ['Nhà cung cấp', 'Nợ đầu kỳ', 'Phải trả (hàng / HĐ có thuế)', 'Đã trả', 'Còn nợ', 'Còn nợ hộ 15E', 'Còn nợ hộ 3C']
PHAI = {'max': 'Phải trả (hàng / HĐ có thuế)', 'hd': 'Phải trả (hoá đơn có thuế)', 'thuc': 'Phải trả (hàng đã nhập × giá nhập)'}  # như web
HO = ('15E', 'Y3C')


def ncc_key(t):
    s = str(t or '').replace('đ', 'd').replace('Đ', 'd')
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s.lower()).strip()


def _round(x):
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)  # như Math.round (nửa lên)


def _ho(k):
    return 'Y3C' if k == 'Y3C' else '15E'


def cong_no(cn, phieu_quy, cach='max'):
    """Như web congNo (04/11 thuế + hộ, d6181484): mỗi phiếu × hộ — hàng = Σ nhận × giá nhập (theo kho) − trả NCC + chiết khấu / phí / thuế HĐ (theo hộ mua);
    HĐ = Σ tong_tt (hd + hd_cho, theo hộ mua); phải trả = max(hàng, HĐ). Đã trả: PC gắn HĐ (pc_hd) tính cho hộ của HĐ, còn lại hộ của quỹ."""
    by = {}
    chinh = {ncc_key(x['khoa']): x['ncc'] for x in cn.get('ten_phu') or [] if x.get('khoa') and x.get('ncc')}
    chinh.update({ncc_key(t): t for t in set(chinh.values())})

    def get(ten):
        ten = chinh.get(ncc_key(ten), ten)
        k = ncc_key(ten)
        if k not in by:
            by[k] = {'ncc': ten, 'dau_ky': 0, 'tien_hang': 0, 'da_tra': 0, 'ho': {h: {'phai': 0, 'tra': 0} for h in HO}}
        return by[k]

    def cong(m, p, h, v):
        o = m.setdefault(p, {x: 0 for x in HO})
        o[h] += v

    nhap = {p['phieu'] for p in cn.get('phieu', []) if p.get('trang_thai') == 'nhap'}
    hang, hang_t, hd_t, hd_ho, co_nhan, thue = {}, {}, {}, {}, {}, {}
    for n in (x for x in cn.get('nhan', []) if x['phieu'] not in nhap and not x.get('huy')):
        v = (n['sl'] or 0) * (n['gia_nhap'] or 0)
        cong(hang, n['phieu'], _ho(n.get('kho')), v)
        cong(co_nhan, n['phieu'], _ho(n.get('kho')), v)
        cong(hang_t, n['phieu'], _ho(n.get('kho')), v)
    for t in (x for x in cn.get('tra_ncc', []) if x['phieu'] not in nhap):
        v = -(t['sl'] or 0) * (t['gia_nhap'] or 0)
        cong(hang, t['phieu'], _ho(t.get('kho')), v)
        cong(hang_t, t['phieu'], _ho(t.get('kho')), v)
    for h in (x for x in cn.get('hd', []) if x['phieu'] not in nhap and not x.get('bi_thay')):
        ho = _ho(h.get('ho'))
        hd_ho[(h['phieu'], h['so_hd'])] = ho
        cong(hd_t, h['phieu'], ho, h.get('tong_tt') or 0)
        cong(hang, h['phieu'], ho, (h['chiet_khau'] or 0) + (h['phi'] or 0) + (h.get('tien_thue') or 0))
        cong(thue, h['phieu'], ho, h.get('tien_thue') or 0)
    co = {p for p, o in co_nhan.items() if any(o.values())}  # web: phiếu có ít nhất 1 nhóm (phiếu, kho) nhận có tiền
    for h in (x for x in cn.get('hd_cho', []) if x['phieu'] not in nhap):
        ho = _ho(h.get('ho'))
        hd_ho[(h['phieu'], h['so_hd'])] = ho
        cong(hd_t, h['phieu'], ho, h.get('tong_tt') or 0)
        if h['phieu'] in co:
            cong(hang, h['phieu'], ho, h.get('tien_thue') or 0)
            cong(thue, h['phieu'], ho, h.get('tien_thue') or 0)
    for p0, v in thue.items():  # 'thuc': thuế GTGT HĐ chỉ cho phiếu đã nhập kho
        if p0 in co:
            for h in HO:
                cong(hang_t, p0, h, v[h])
    tra_p = {}
    for p in phieu_quy:  # web: phiếu chi trước (tên hiện theo lần gặp đầu)
        if p.get('loai') == 'PC' and p.get('ncc') and not p.get('huy_luc'):
            ph, v = p.get('phieu_ncc'), p['so_tien'] or 0
            ho = (ph and p.get('hd_ncc') and hd_ho.get((ph, p['hd_ncc']))) or _ho(p.get('ho'))
            o = get(p['ncc'])
            if ph:
                cong(tra_p, ph, ho, v)
            o['da_tra'] += v
            o['ho'][ho]['tra'] += v
    for x in cn.get('ncc', []):
        get(x['ten'])
    for p in cn.get('phieu', []):
        if p['phieu'] in nhap or not p.get('ncc'):
            continue
        o = get(p['ncc'])
        for h in HO:
            a, b = _round((hang_t if cach == 'thuc' else hang).get(p['phieu'], {}).get(h, 0)), _round(hd_t.get(p['phieu'], {}).get(h, 0))
            phai = b if cach == 'hd' else a if cach == 'thuc' else max(a, b)
            o['ho'][h]['phai'] += phai
            o['tien_hang'] += phai
    for x in cn.get('ncc', []) if cach != 'thuc' else []:  # đầu kỳ MISA là số sổ sách
        get(x['ten'])['dau_ky'] += x.get('no_dau') or 0
    out = [dict(o, con=o['dau_ky'] + o['tien_hang'] - o['da_tra']) for o in by.values()]
    out.sort(key=lambda o: (-o['con'], ncc_key(o['ncc']), o['ncc']))
    return out


def xlsx_rows(ds, cach='max'):
    return [COT[:2] + [PHAI[cach]] + COT[3:]] + [[o['ncc'], o['dau_ky'], o['tien_hang'], o['da_tra'], o['con'], o['ho']['15E']['phai'] - o['ho']['15E']['tra'], o['ho']['Y3C']['phai'] - o['ho']['Y3C']['tra']] for o in ds]
