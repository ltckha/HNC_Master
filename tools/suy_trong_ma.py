"""Anh Kha 29/10: "điền từ các thuộc tính đã có của chính mã đó", KHÔNG theo ngành.
1) Trả lại (về trống) các ô đã ghi theo đa số ngành (dien_theo_nganh, 0047fdd). Danh sách dựng từ phiên bản Drive TRƯỚC lượt ghi
   (ô trống ở bản cũ, nay = giá trị đa số; bỏ "đế bằng" = mặc định ngành): docs/sanpham_chuan/tra_lai_2008_<chinh|thu>.json.
   Chỉ xoá khi ô hiện tại còn đúng giá trị đã ghi (ai sửa rồi thì giữ).
2) Suy trong cùng 1 mã (chỉ ô trống):
   - cao_got_cm > 0, kieu_de trống, giới tính nam → "có gót" (nữ để trống: không biết gót vuông / nhọn)
   - chat_lieu có "da bò lộn" → be_mat "da lộn"; be_mat có "da lộn" → chat_lieu "da bò lộn"
   - cột cũ của chính mã (Phần dưới giày / Đặc điểm / Nhấn mạnh / Bonus…) theo bảng gộp GĐ B (tach_cot_sanpham.tach)
   - mã cùng mẫu cha đã có → chép (dien_theo_cha.de_xuat)
CHẠY THỬ in số ô + ví dụ → docs/sanpham_chuan/suy_trong_ma.csv; --ghi để ghi (Sheet thử trước, chính sau).

  venv/bin/python tools/suy_trong_ma.py [--ghi] [--sheet ID]
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

import gspread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.dien_theo_cha import de_xuat as theo_cha  # noqa: E402
from tools.tach_cot_sanpham import _mo, tach  # noqa: E402
from tools.tu_dien_sanpham import OUT, SHEET_ID  # noqa: E402

THU = '1QwH7Y1A45Pb9S0JbfDSkrP-VeUmD_cA6FsKdI4Gmxcw'


def so(v):
    try:
        return float(str(v).replace(',', '.'))
    except ValueError:
        return 0.0


def suy(sp, h):
    """→ [(hàng, mã, cột, giá trị, luật, ví dụ nguồn)] cho ô trống, suy trong cùng mã."""
    g = lambda r, c: r[h.index(c)].strip() if h.index(c) < len(r) else ''  # noqa: E731
    ic = h.index('product_code')
    out, da = [], set()

    def them(i, ma, c, v, luat, nguon):
        if (ma, c) not in da:
            da.add((ma, c))
            out.append((i, ma, c, v, luat, nguon))
    for i, r in enumerate(sp[2:], start=3):
        ma = g(r, 'product_code').upper()
        if not ma:
            continue
        if not g(r, 'kieu_de') and so(g(r, 'cao_got_cm')) > 0 and g(r, 'gioi_tinh') == 'nam':
            them(i, ma, 'kieu_de', 'có gót', 'gót cm → có gót (nam)', f"cao_got_cm={g(r, 'cao_got_cm')}")
        if not g(r, 'be_mat') and 'da bò lộn' in g(r, 'chat_lieu'):
            them(i, ma, 'be_mat', 'da lộn', 'chat_lieu da bò lộn → be_mat', g(r, 'chat_lieu'))
        if not g(r, 'chat_lieu') and 'da lộn' in g(r, 'be_mat'):
            them(i, ma, 'chat_lieu', 'da bò lộn', 'be_mat da lộn → chat_lieu', g(r, 'be_mat'))
        for c, (v, nguon, tt) in tach(r, h).items():
            if tt == 'dien' and c in h and not g(r, c):
                them(i, ma, c, v, 'cột cũ của mã', ' ; '.join(nguon))
    hang = {sp[i][ic].strip().upper(): i + 1 for i in range(2, len(sp)) if sp[i][ic].strip()}
    for ma, c, v, tu, tt in theo_cha(sp, h):
        if tt == 'dien':
            them(hang[ma], ma, c, v, 'mẫu cha', ' '.join(tu))
    return out


def main():
    sid = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else SHEET_ID
    ghi = '--ghi' in sys.argv
    ws = _mo(sid, ghi=ghi)
    sp = ws.get_all_values()
    h = [x.strip() for x in sp[1]]
    ic = h.index('product_code')
    hang = {sp[i][ic].strip().upper(): i for i in range(2, len(sp)) if sp[i][ic].strip()}
    # 1) trả lại
    ds = json.load(open(os.path.join(OUT, f"tra_lai_2008_{'thu' if sid == THU else 'chinh'}.json"), encoding='utf-8'))
    xoa, giu = [], 0
    for _, ma, c, v in ds:
        k = hang.get(ma)
        if k is not None and sp[k][h.index(c)].strip() == v:
            xoa.append({'range': gspread.utils.rowcol_to_a1(k + 1, h.index(c) + 1), 'values': [['']]})
            sp[k][h.index(c)] = ''  # suy bước 2 trên trạng thái sau khi trả
        else:
            giu += 1
    print(f'Sheet {sid[:6]}…: 1) trả lại {len(xoa)} ô (giữ {giu} ô đã bị sửa khác) · theo cột {dict(Counter(c for _, _, c, _ in ds))}')
    # 2) suy trong mã
    sx = suy(sp, h)
    dl = Counter(x[4] for x in sx)
    print(f'  2) suy trong mã {len(sx)} ô: ' + ', '.join(f'{k} {n}' for k, n in dl.most_common()))
    vd = defaultdict(list)
    for x in sx:
        if len(vd[x[4]]) < 5:
            vd[x[4]].append(x)
    for k, xs in vd.items():
        for _, ma, c, v, _, ng in xs:
            print(f'     [{k}] {ma} {c} = {v}  ← {ng[:70]}')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'suy_trong_ma.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ma', 'cot', 'gia_tri', 'luat', 'nguon'])
        w.writerows([[ma, c, v, l, ng] for _, ma, c, v, l, ng in sx])
    if ghi:
        for k in range(0, len(xoa), 500):
            ws.batch_update(xoa[k:k + 500], value_input_option='RAW')
        up = [{'range': gspread.utils.rowcol_to_a1(i, h.index(c) + 1), 'values': [[v]]} for i, _, c, v, _, _ in sx]
        for k in range(0, len(up), 500):
            ws.batch_update(up[k:k + 500], value_input_option='RAW')
        print(f'✅ Đã trả {len(xoa)} ô, ghi {len(up)} ô')
    return 0


if __name__ == '__main__':
    sys.exit(main())
