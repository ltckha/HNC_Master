"""Đề xuất + ghi thông số còn trống trong SANPHAM (chất liệu quai / đế / lót / mặt lót / dáng mũi / phần dưới / phối đồ / sử dụng).

Nguồn theo thứ tự rẻ trước:
  (a) mẫu cùng mã cha đã có giá trị;
  (b) giá trị mặc định theo ngành hàng ở tab SUB;
  (c) AI (Gemini) nhìn ảnh — chỉ khi anh Kha duyệt số lượt (luật 5).
Chỉ ghi ô TRỐNG (đọc lại ngay trước khi ghi), không đè. SANPHAM: tên cột kỹ thuật ở hàng 2 (luật 4).

Lệnh:
  python tools/spec_fill.py plan [--scope instock|all]
      In tóm tắt (a)/(b) theo ngành; lưu CSV đề xuất vào HNC_Exported_Files.
  python tools/spec_fill.py ai --limit 20 [--scope instock|all]
      Gọi Gemini cho N mẫu có ảnh (ưu tiên bán chạy 60 ngày), lưu CSV đề xuất — KHÔNG ghi Sheet.
  python tools/spec_fill.py apply --csv <file> [--source a,b,c] [--categories "Ngành 1;Ngành 2"] [--codes "M1,M2"] [--dry-run]
      Ghi các dòng đề xuất đã duyệt vào ô trống SANPHAM, rồi báo web chép lại.
"""
import argparse
import base64
import csv
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import gspread
import requests
from google.oauth2.service_account import Credentials

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET_ID = "1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0"  # HNC_Control_Center
SANPHAM_HEADER_ROW = 2  # luật 4: SANPHAM để tên cột kỹ thuật ở hàng 2
MEDIA_DIR = "/Volumes/Media/HNC_Master"
sys.path.insert(0, ROOT)
from hnc_paths import find_system_dir  # noqa: E402  (đường dẫn Drive khai 1 chỗ)
EXPORT_DIR = os.path.join(find_system_dir(), "HNC_Exported_Files")
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]

# (cột SANPHAM hàng 2, cột mặc định ở SUB hàng 1) — so khớp sau khi bỏ khoảng trắng 2 đầu
SPEC_COLUMNS = [
    ("Chất liệu quai:", "Chất liệu quai:"),
    ("Chất liệu đế:", "Chất liệu đế:"),
    ("Lót trong:", "Lót trong:"),
    ("Mặt lót đế:", "Mặt lót đế:"),
    ("Dáng giày mũi:", "Mũi giày:"),
    ("Phần dưới giày:", "Gót giày:"),
    ("Kết hợp trang phục:", "Kết hợp trang phục"),
    ("Sử dụng:", "Sử dụng:"),
]
CSV_FIELDS = ["product_code", "nganh", "cot", "gia_tri_cu", "de_xuat", "nguon", "con_hang", "ban_60_ngay"]


def load_env():
    path = os.path.join(ROOT, ".env")
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def open_sheet(write=False):
    scope = "https://www.googleapis.com/auth/spreadsheets" + ("" if write else ".readonly")
    creds = Credentials.from_service_account_file(os.path.join(ROOT, "credentials.json"), scopes=[scope])
    return gspread.authorize(creds).open_by_key(SHEET_ID)


def col_index(header, name):
    names = [str(h).strip() for h in header]
    return names.index(name.strip()) if name.strip() in names else None


def load_data(ss):
    sp = ss.worksheet("SANPHAM").get_all_values()
    head = sp[SANPHAM_HEADER_ROW - 1]
    idx = {n: col_index(head, n) for n in ["product_code", "parent_product_code", "Tên Ngành Hàng", "CON_NAME", "image_01", "image_02", "image_03"]}
    for c, _ in SPEC_COLUMNS:
        idx[c] = col_index(head, c)
    missing = [n for n in ["product_code", "Tên Ngành Hàng"] + [c for c, _ in SPEC_COLUMNS] if idx[n] is None]
    if missing:
        sys.exit(f"DỪNG: SANPHAM thiếu cột {missing}")

    sub = ss.worksheet("SUB").get_all_values()
    sh = sub[0]
    cat_i = col_index(sh, "Tên Ngành Hàng")
    sub_defaults = {}
    for r in sub[1:]:
        cat = r[cat_i].strip().lower() if cat_i is not None else ""
        if not cat:
            continue
        d = {}
        for c, sc in SPEC_COLUMNS:
            i = col_index(sh, sc)
            if i is not None and i < len(r) and r[i].strip():
                d[c] = r[i].strip()
        sub_defaults[cat] = d

    stock = defaultdict(float)
    for t in ("KHO15E", "KHOY3C"):
        v = ss.worksheet(t).get_all_values()
        h = v[0]
        pc, q = col_index(h, "product_code"), col_index(h, "current_quantity")
        for r in v[1:]:
            try:
                stock[r[pc].strip().upper()] += float(r[q] or 0)
            except ValueError:
                pass

    ban = ss.worksheet("BAN").get_all_values()
    bh = ban[0]
    pc, q, di = col_index(bh, "product_code"), col_index(bh, "item_quantity"), col_index(bh, "Ngày")
    cut = datetime.now() - timedelta(days=60)
    sold, last = Counter(), None
    for r in ban[1:]:  # BAN chỉ ghi ngày ở dòng đầu mỗi ngày → mang ngày xuống các dòng sau
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", r[di].strip()) if di is not None else None
        if m:
            last = datetime(int(m[3]), int(m[2]), int(m[1]))
        if last and last >= cut:
            try:
                qty = float(r[q] or 0)
            except ValueError:
                qty = 0
            if qty > 0:
                sold[r[pc].strip().upper()] += qty
    return sp, idx, sub_defaults, stock, sold


def plan_rows(sp, idx, sub_defaults, stock, sold, scope):
    rows = sp[SANPHAM_HEADER_ROW:]
    parent_vals = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        code = r[idx["product_code"]].strip().upper()
        if not code:
            continue
        parent = (r[idx["parent_product_code"]].strip().upper() if idx["parent_product_code"] is not None else "") or code[:-1]
        for c, _ in SPEC_COLUMNS:
            v = r[idx[c]].strip()
            if v:
                parent_vals[parent][c][v] += 1
    out = []
    for r in rows:
        code = r[idx["product_code"]].strip().upper()
        if not code or (scope == "instock" and stock.get(code, 0) <= 0):
            continue
        parent = (r[idx["parent_product_code"]].strip().upper() if idx["parent_product_code"] is not None else "") or code[:-1]
        cat = r[idx["Tên Ngành Hàng"]].strip()
        for c, _ in SPEC_COLUMNS:
            if r[idx[c]].strip():
                continue
            vals = parent_vals[parent][c]
            if vals:
                val, src = vals.most_common(1)[0][0], "a"
            elif sub_defaults.get(cat.lower(), {}).get(c):
                val, src = sub_defaults[cat.lower()][c], "b"
            else:
                val, src = "", "c"
            out.append({"product_code": code, "nganh": cat, "cot": c, "gia_tri_cu": "", "de_xuat": val, "nguon": src,
                        "con_hang": int(stock.get(code, 0)), "ban_60_ngay": int(sold.get(code, 0))})
    out.sort(key=lambda x: (-x["ban_60_ngay"], -x["con_hang"], x["product_code"]))
    return out


def save_csv(rows, prefix):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


def cmd_plan(args):
    ss = open_sheet()
    sp, idx, sub_defaults, stock, sold = load_data(ss)
    rows = plan_rows(sp, idx, sub_defaults, stock, sold, args.scope)
    by_src = Counter(r["nguon"] for r in rows)
    print(f"Ô trống ({args.scope}): {len(rows)} | (a) mã cha: {by_src['a']} | (b) SUB: {by_src['b']} | (c) cần AI / tay: {by_src['c']}")
    groups = defaultdict(lambda: defaultdict(set))
    for r in rows:
        if r["nguon"] == "b":
            groups[r["nganh"]][(r["cot"], r["de_xuat"])].add(r["product_code"])
    print("\n(b) Mặc định SUB theo ngành:")
    for cat in sorted(groups, key=lambda c: -len(set().union(*groups[c].values()))):
        codes = set().union(*groups[cat].values())
        print(f"• {cat} — {len(codes)} mẫu:")
        for (c, v), cs in sorted(groups[cat].items()):
            print(f"    {c} {v}  ({len(cs)} ô)")
    a_rows = [r for r in rows if r["nguon"] == "a"]
    if a_rows:
        print("\n(a) Cùng mã cha (ví dụ):")
        for r in a_rows[:10]:
            print(f"    {r['product_code']} {r['cot']} {r['de_xuat']}")
    print("\nCSV:", save_csv([r for r in rows if r["nguon"] in ("a", "b")], "SPEC_FILL_PLAN"))


def images_for(code, r, idx, limit=3):
    """Ảnh của mẫu: thư mục NAS trước (ảnh gốc), không có thì link image_01..03. Trả về list (mime, bytes)."""
    out = []
    folder = os.path.join(MEDIA_DIR, code)
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and not name.startswith("."):
                with open(os.path.join(folder, name), "rb") as f:
                    out.append(f.read())
            if len(out) >= limit:
                break
    if not out:
        for n in ("image_01", "image_02", "image_03"):
            url = r[idx[n]].strip() if idx.get(n) is not None else ""
            if url.startswith("http"):
                try:
                    resp = requests.get(url, timeout=20)
                    if resp.ok and resp.content:
                        out.append(resp.content)
                except requests.RequestException:
                    pass
    from PIL import Image
    shrunk = []
    for data in out[:limit]:
        try:
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im.thumbnail((1024, 1024))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            shrunk.append(buf.getvalue())
        except Exception:
            continue
    return shrunk


def gemini_call(api_key, images, prompt):
    parts = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b).decode()}} for b in images]
    parts.append({"text": prompt})
    payload = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
    last_err = None
    global GEMINI_MODELS
    for model in list(GEMINI_MODELS):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(2):
            try:
                resp = requests.post(url, params={"key": api_key}, json=payload, timeout=60)
                if resp.status_code in (429, 503) and attempt == 0:
                    time.sleep(3)
                    continue
                if not resp.ok:
                    last_err = f"{model} HTTP {resp.status_code}"
                    break
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
                ans = json.loads(text)
                if isinstance(ans, list):  # có lúc mô hình bọc kết quả trong mảng
                    ans = next((x for x in ans if isinstance(x, dict)), {})
                if not isinstance(ans, dict):
                    ans = {}
                GEMINI_MODELS = [model] + [m for m in GEMINI_MODELS if m != model]  # lần sau gọi thẳng mô hình chạy được
                return model, ans
            except Exception as e:  # thử mô hình kế tiếp
                last_err = f"{model}: {e}"
                break
    raise RuntimeError(f"Gemini không trả lời ({last_err})")


def cmd_ai(args):
    env = load_env()
    api_key = env.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("DỪNG: thiếu GEMINI_API_KEY trong .env")
    ss = open_sheet()
    sp, idx, sub_defaults, stock, sold = load_data(ss)
    rows = plan_rows(sp, idx, sub_defaults, stock, sold, args.scope)
    need = defaultdict(list)
    for r in rows:
        if r["nguon"] == "c":
            need[r["product_code"]].append(r)
    by_code = {r[idx["product_code"]].strip().upper(): r for r in sp[SANPHAM_HEADER_ROW:] if r[idx["product_code"]].strip()}

    # Từ vựng đang dùng (để AI viết cùng kiểu chữ với dữ liệu sẵn có)
    vocab = {}
    for c, _ in SPEC_COLUMNS:
        cnt = Counter(r[idx[c]].strip() for r in sp[SANPHAM_HEADER_ROW:] if r[idx[c]].strip())
        vocab[c] = [v for v, _ in cnt.most_common(15)]

    order = sorted(need, key=lambda c: (-sold.get(c, 0), -stock.get(c, 0), c))
    # Lưu ngay sau mỗi mẫu vào file trong ngày; chạy lại thì bỏ qua mẫu đã gọi (không tốn lượt Gemini lần 2)
    out_path = os.path.join(EXPORT_DIR, f"SPEC_FILL_AI_{datetime.now().strftime('%Y%m%d')}.csv")
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8-sig") as f:
            done = {r["product_code"] for r in csv.DictReader(f)}
    new_file = not os.path.exists(out_path)
    out_f = open(out_path, "a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(out_f, fieldnames=CSV_FIELDS)
    if new_file:
        writer.writeheader()
    picked, results = [], []
    for code in order:
        if len(picked) >= args.limit:
            break
        if code in done:
            continue
        imgs = images_for(code, by_code[code], idx)
        if not imgs:
            continue
        picked.append(code)
        r = by_code[code]
        cols = [x["cot"] for x in need[code]]
        prompt = (
            "Bạn là nhân viên bán giày da của Hiệu giày Hải Nancy. Nhìn ảnh sản phẩm và điền thông số còn trống.\n"
            f"Mã: {code}. Tên: {r[idx['CON_NAME']] if idx.get('CON_NAME') is not None else ''}. Ngành: {r[idx['Tên Ngành Hàng']]}.\n"
            "Chỉ điền khi NHÌN THẤY rõ trong ảnh hoặc suy ra chắc chắn từ ngành / tên; không chắc thì để chuỗi rỗng \"\". "
            "Viết ngắn, chữ thường, cùng kiểu với các giá trị đang dùng dưới đây.\n"
            + "\n".join(f"- {c} ví dụ đang dùng: {', '.join(vocab[c][:10])}" for c in cols)
            + "\nTrả về JSON object, khoá đúng tên cột: " + json.dumps(cols, ensure_ascii=False)
        )
        try:
            model, ans = gemini_call(api_key, imgs, prompt)
        except RuntimeError as e:
            print(f"⚠️ {code}: {e}")
            continue
        n_ok = 0
        rows_out = []
        for item in need[code]:
            v = str(ans.get(item["cot"], ans.get(item["cot"].strip(), ans.get(item["cot"].rstrip(": "), ""))) or "").strip()
            rows_out.append(dict(item, de_xuat=v, nguon="c"))  # dòng rỗng = AI không chắc (giữ để đánh dấu đã gọi)
            if v:
                n_ok += 1
                results.append(dict(item, de_xuat=v, nguon="c"))
        writer.writerows(rows_out)
        out_f.flush()
        print(f"✓ {code} ({model}, {len(imgs)} ảnh): đề xuất {n_ok}/{len(need[code])} ô", flush=True)
    out_f.close()
    print(f"\nĐã gọi Gemini cho {len(picked)} mẫu mới (bỏ qua {len(done)} mẫu đã gọi hôm nay); đề xuất {len(results)} ô.")
    print("CSV:", out_path)


def cmd_apply(args):
    with open(args.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    sources = set(s.strip() for s in args.source.split(",")) if args.source else None
    cats = set(c.strip().lower() for c in args.categories.split(";")) if args.categories else None
    codes = set(c.strip().upper() for c in args.codes.split(",")) if args.codes else None
    rows = [r for r in rows if r["de_xuat"].strip()
            and (sources is None or r["nguon"] in sources)
            and (cats is None or r["nganh"].strip().lower() in cats)
            and (codes is None or r["product_code"].strip().upper() in codes)]
    if not rows:
        sys.exit("Không có dòng nào khớp bộ lọc.")

    ss = open_sheet(write=not args.dry_run)
    ws = ss.worksheet("SANPHAM")
    sp = ws.get_all_values()  # đọc lại ngay trước khi ghi
    head = sp[SANPHAM_HEADER_ROW - 1]
    pc = col_index(head, "product_code")
    row_of = {}
    for i, r in enumerate(sp[SANPHAM_HEADER_ROW:], start=SANPHAM_HEADER_ROW + 1):
        code = r[pc].strip().upper()
        if code and code not in row_of:
            row_of[code] = i
    updates, skipped = [], Counter()
    for r in rows:
        ci = col_index(head, r["cot"])
        ri = row_of.get(r["product_code"].strip().upper())
        if ci is None or ri is None:
            skipped["không tìm thấy mã / cột"] += 1
            continue
        cur = sp[ri - 1][ci].strip() if ci < len(sp[ri - 1]) else ""
        if cur:
            skipped["ô đã có giá trị (không đè)"] += 1
            continue
        updates.append({"range": gspread.utils.rowcol_to_a1(ri, ci + 1), "values": [[r["de_xuat"].strip()]]})
    print(f"Sẽ ghi {len(updates)} ô" + (f"; bỏ qua {dict(skipped)}" if skipped else ""))
    if args.dry_run or not updates:
        return
    for i in range(0, len(updates), 200):
        ws.batch_update(updates[i:i + 200])
        time.sleep(1)
    print(f"✅ Đã ghi {len(updates)} ô vào SANPHAM.")
    env = load_env()
    if env.get("SYNC_HINT_URL") and env.get("SYNC_HINT_KEY"):
        try:
            resp = requests.post(env["SYNC_HINT_URL"], params={"key": env["SYNC_HINT_KEY"]}, json={"tabs": ["SANPHAM"]}, timeout=15)
            print(f"🔄 Báo web chép lại SANPHAM: HTTP {resp.status_code}")
        except requests.RequestException as e:
            print(f"[!] Không báo được web: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--scope", choices=["instock", "all"], default="instock")
    p = sub.add_parser("ai")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--scope", choices=["instock", "all"], default="instock")
    p = sub.add_parser("apply")
    p.add_argument("--csv", required=True)
    p.add_argument("--source")
    p.add_argument("--categories")
    p.add_argument("--codes")
    p.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    {"plan": cmd_plan, "ai": cmd_ai, "apply": cmd_apply}[args.cmd](args)


if __name__ == "__main__":
    main()
