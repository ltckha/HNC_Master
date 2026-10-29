#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===================================================================
             🚀 HNC CONTROL CENTER - MAC MINI M4 ENGINE
===================================================================
Automated E-Commerce & Inventory Management System for HNC Master
Installed at: /Users/khan/Developer/HNC_Master
Thư mục Drive (mẫu, file xuất): xem hnc_paths.py — My Drive/HNC/He_thong, cũ: My Drive/Spark/HNC_Master
"""

import os
import csv
import functools
import sys
import re
import glob
import shutil
import time
import json
import base64
import urllib.request
import ssl
import shlex
from datetime import datetime
import pandas as pd
import openpyxl
import requests

# Rich Library CLI Formatting Setup
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
    from rich.prompt import Prompt
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None

# GSpread Google Sheets API Setup
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# Dotenv & Gemini Multimodal AI Setup
try:
    from dotenv import load_dotenv
    # override=True: khoá trong .env của HNC thắng biến môi trường chung (~/.zshrc có GEMINI_API_KEY dùng chung các repo) — mỗi repo 1 khoá riêng (anh Kha 16/10)
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)
except ImportError:
    pass

try:
    from google import genai
    from google.genai import types
    from PIL import Image
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# Paths Configuration
LOCAL_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Thư mục Drive khai 1 chỗ ở hnc_paths.py: My Drive/HNC/He_thong → My Drive/Spark/HNC_Master; không thấy thì dừng, không dùng local.
from hnc_paths import find_system_dir, in_csv_path
try:
    GDRIVE_DIR = find_system_dir()
except FileNotFoundError as _e:
    print(f"❌ {_e}")
    sys.exit(1)

CREDENTIALS_PATH = os.path.join(LOCAL_BASE_DIR, "credentials.json")
if not os.path.exists(CREDENTIALS_PATH) and os.path.exists(os.path.join(GDRIVE_DIR, "credentials.json")):
    CREDENTIALS_PATH = os.path.join(GDRIVE_DIR, "credentials.json")

TEMPLATES_DIR = os.path.join(GDRIVE_DIR, "HNC_Templates")
EXPORT_DIR = os.path.join(GDRIVE_DIR, "HNC_Exported_Files")

os.makedirs(EXPORT_DIR, exist_ok=True)
SPREADSHEET_NAME = "HNC_Control_Center"
# Mở theo ID (tên file Sheet đã đổi thành "HNC_Master" 17/10/2026 → mở theo tên bị lỗi SpreadsheetNotFound)
SPREADSHEET_ID_THAT = "1U0b6_aVJJ93i5-V1RV1jUsQ9dhLYCY9BcJMI7R6J2C0"
# P0 (20/10): HNC_SHEET_ID trỏ Sheet bản thử (vd HNC_Master_BAN_THU) để thử; không đặt = Sheet thật
SPREADSHEET_ID = os.getenv("HNC_SHEET_ID", "").strip() or SPREADSHEET_ID_THAT
# Chế độ Web (META che_do = web): P1 chỉ SỔ BÁN chuyển sang web (Bán hàng chốt 20/10) → menu Mac không ghi BAN.
# Kho / nhập / SANPHAM vẫn ghi như cũ (cùng phạm vi bot saleWebGate_). Mặc định master = như cũ.
WEB_MODE_LOCKED_TABS = {'BAN'}
# Tab web giayhainancy.vn chép về; ghi vào các tab này thì báo web chép lại (SYNC_HINT_URL / SYNC_HINT_KEY trong .env)
SYNC_WATCH_TABS = ['SANPHAM', 'KHO15E', 'KHOY3C', 'BAN', 'NHAP', 'XUAT', 'SUB', 'META', 'KYGUI']
GRID_EXTRA_ROWS = 100  # Số dòng dư thêm khi lưới Google Sheet không đủ chỗ ghi

# Media Ingestion & Asset Management Paths
MEDIA_DEST_DIR = "/Volumes/Media/HNC_Master"
SOURCE_PHOTOROOM = "/Volumes/home/Photos/MobileBackup/Xiaomi 15T Pro/Photoroom"
SOURCE_DOWNLOADS = os.path.expanduser("~/Downloads")

# Technical Variable Mappings for Dynamic Header Scanner
STATUS_COLUMNS = {
    1: ["web_upload"],
    2: ["shopee_upload"],
    3: ["tiktok_upload"],
    4: ["misa_upload"],
    5: ["web_stock"],
    6: ["shopee_upload", "web_stock"],
    7: ["tiktok_upload", "web_stock"],
    8: ["misa_stock", "misa_stock_y3c", "misa_stock_15e"],
    9: ["kho_sync"],
    10: ["web_label"],
    11: ["get_images"]
}


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# Mã "cần bổ sung" (anh Kha 16/10/2026; thường là mã tạo từ phiếu NCC): SANPHAM trống "Tên Ngành Hàng" hoặc giá bán.
# Xuất MISA / Shopee / TikTok / web cũ tự BỎ QUA các mã này (giữ trạng thái trống để xuất sau khi bổ sung). Giống bot HNC (needsInfo_).
PENDING_INFO_COLUMNS = ("Tên Ngành Hàng", "product_price")
# Tác vụ bỏ qua mã chưa bổ sung: 1 web đăng mới, 2 Shopee đăng mới, 3 TikTok đăng mới, 4 MISA danh mục, 5 web tồn, 8 MISA phiếu nhập
PENDING_INFO_SKIP_TASKS = {1, 2, 3, 4, 5, 8}
# MISA nhập kho: dòng chưa có số hoá đơn (so_hd) chờ 3 ngày rồi mới xuất "giá tạm" — giống bot (MISA_WAIT_DAYS, anh Kha 17/10)
MISA_WAIT_DAYS = 3


def clean_code(value):
    """Mã SP sạch: bỏ ký tự điều khiển ẩn (vd \\x08 khi dán) và khoảng trắng 2 đầu — tránh hỏng FSKU / tồn kho / feed web."""
    return _CONTROL_CHARS.sub('', str(value or '')).strip()


def pending_info_codes(df_sp, col_map_sp, data_start_row=2):
    """Tập mã SANPHAM (chữ hoa) "cần bổ sung": trống Tên Ngành Hàng hoặc giá bán (product_price ≤ 0)."""
    p_idx = col_map_sp.get('product_code')
    checks = [(n, col_map_sp.get(n)) for n in PENDING_INFO_COLUMNS if col_map_sp.get(n) is not None]
    if p_idx is None or not checks:
        return set()
    codes = set()
    for r in range(data_start_row, len(df_sp)):
        row = df_sp.iloc[r]
        code = clean_code(row[p_idx]).upper() if pd.notna(row[p_idx]) else ""
        if not code:
            continue
        for name, idx in checks:
            val = row[idx] if pd.notna(row[idx]) else ""
            empty = parse_number(val) <= 0 if name == 'product_price' else not str(val).strip()
            if empty:
                codes.add(code)
                break
    return codes


def drop_pending_info(records, row_indices, codes):
    """Bỏ các dòng thuộc mã chưa bổ sung (giữ nguyên thứ tự, không đánh dấu trạng thái) và in 1 dòng báo."""
    if not codes:
        return records, row_indices
    keep_rec, keep_idx, skipped = [], [], []
    for rec, idx in zip(records, row_indices):
        code = clean_code(rec.get('product_code', '')).upper()
        if code in codes:
            skipped.append(code)
            continue
        keep_rec.append(rec)
        keep_idx.append(idx)
    if skipped:
        uniq = sorted(set(skipped))
        print(f"⏭️ Bỏ qua {len(uniq)} mã chưa bổ sung (trống ngành / giá bán): {', '.join(uniq[:10])}{' …' if len(uniq) > 10 else ''}")
    return keep_rec, keep_idx


def safe_write_cell(ws, row, col, value):
    """Ghi dữ liệu an toàn vào ô openpyxl, bỏ qua nếu là MergedCell."""
    try:
        cell = ws.cell(row=row, column=col)
        if type(cell).__name__ != 'MergedCell':
            cell.value = value
    except Exception:
        pass


# Ảnh file đăng sàn (Shopee / TikTok) lấy từ web mới: <WEB_IMG_BASE>/img/<mã>/<n>.jpg (JPG ≤1600, công khai, đúng thứ tự ảnh trên web).
# Gốc ảnh: tên miền chính (đã chuyển sang web mới 17/10/2026); đổi được bằng WEB_IMG_BASE trong .env.
WEB_IMG_BASE = (os.getenv("WEB_IMG_BASE") or "https://giayhainancy.vn").rstrip("/")
SALE_MAX_IMAGES = 9  # Shopee / TikTok nhận tối đa 9 ảnh
_web_img_cache = {}
_web_img_state = {"down": False}


def web_image_urls(code, max_n=SALE_MAX_IMAGES):
    """Danh sách link ảnh của mã trên web mới (dò 1.jpg, 2.jpg… tới ảnh đầu tiên không có). None = không gọi được web."""
    code = clean_code(code).upper()
    if not code or _web_img_state["down"]:
        return None
    if code in _web_img_cache:
        return _web_img_cache[code]
    urls = []
    try:
        for n in range(1, max_n + 1):
            u = f"{WEB_IMG_BASE}/img/{requests.utils.quote(code)}/{n}.jpg"
            r = requests.head(u, timeout=10, allow_redirects=True)
            if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
                break
            urls.append(u)
    except requests.RequestException as e:
        _web_img_state["down"] = True
        print(f"⚠️ Không gọi được web mới để lấy ảnh ({e.__class__.__name__}) → dùng ảnh cũ trong Sheet cho cả lượt xuất này.")
        return None
    _web_img_cache[code] = urls
    return urls


def sale_images(code, sheet_pics):
    """9 link ảnh cho file sàn: ảnh web mới nếu có; web chưa có ảnh / không gọi được thì dùng image_01..09 cũ trong Sheet."""
    old = ["" if x is None or (isinstance(x, float) and x != x) else str(x).strip() for x in sheet_pics]  # bỏ ô trống / NaN
    urls = web_image_urls(code)
    if urls:
        picks = urls
    else:
        picks = old
        if urls is not None and any(old):
            print(f"⚠️ {code}: web mới chưa có ảnh → dùng ảnh web cũ trong Sheet")
    return (list(picks) + [""] * SALE_MAX_IMAGES)[:SALE_MAX_IMAGES]


# Tem mã hàng (V34): cùng cột / luật với cửa bot in_tem (zalo_bot/Code.gs LABEL_COLUMNS, labelRecord_) — luật 15
LABEL_COLUMNS = ['QR code', 'Tên', 'Màu', 'Size', 'Size Color', 'F6', 'Code128', 'Gía']


def label_record(rec, product_map):
    """1 dòng tem từ 1 dòng NHAP: QR = web_url, Tên = product_name, giá bán dạng "450.000 đ", F6 = số tem (= số lượng)."""
    pcode = str(rec.get('product_code', '')).strip()
    sz = str(rec.get('item_size', '')).strip()
    if sz.endswith('.0'):
        sz = sz[:-2]
    sp_info = product_map.get(pcode.upper(), product_map.get(pcode, {}))
    pname = sp_info.get('product_name') or rec.get('Tên', '')
    pcolor = str(rec.get('product_color') or sp_info.get('product_color') or rec.get('Màu', '')).strip()
    scolor = f"{pcolor} (Size {sz})" if sz and pcolor else (pcolor or f"Size {sz}")
    try:
        f6 = max(1, int(float(rec.get('item_quantity') or rec.get('Số lượng (*)') or rec.get('F6', 1))))
    except Exception:
        f6 = 1
    raw_price = sp_info.get('product_price') or rec.get('Giá', '')
    num_p = parse_number(raw_price)
    price_str = f"{int(num_p):,} đ".replace(",", ".") if num_p > 0 else str(raw_price)
    return {'QR code': sp_info.get('web_url') or rec.get('QR code', ''), 'Tên': pname, 'Màu': pcolor, 'Size': sz,
            'Size Color': scolor, 'F6': f6, 'Code128': f"{pcode}{sz}" if sz else pcode, 'Gía': price_str}


def fetch_web_images(url, product_code=""):
    """Cào tự động tối đa 10 ảnh sản phẩm chất lượng cao chuẩn theo product_code từ link web, loại bỏ hoàn toàn logo và ảnh rác."""
    if not url or not str(url).startswith('http'):
        return []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(str(url).strip(), headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        
        html = resp.text

        # 1. Tìm tất cả các khối <div class="carousel-item ..."> (Gallery chính của sản phẩm)
        carousel_items = re.findall(r'<div[^>]*class=[\"\'][^\"\']*carousel-item[^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*carousel-item|<div[^>]*class=[\"\']container|$)', html, re.DOTALL | re.IGNORECASE)
        if not carousel_items:
            carousel_items = re.findall(r'<div[^>]*class=[\"\'][^\"\']*carousel-item[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)

        carousel_imgs = []
        for item in carousel_items:
            src_m = re.search(r'src=[\"\'](https://static\.vnappmob\.com/(?:siso|soro)/giayhainancy/[^\s\"\'<>]+\.(?:jpg|jpeg|png|webp))[\"\']', item, re.IGNORECASE)
            if src_m:
                img_url = src_m.group(1)
                if img_url not in carousel_imgs and 'logo' not in img_url.lower() and 'banner' not in img_url.lower():
                    carousel_imgs.append(img_url)

        if carousel_imgs:
            return carousel_imgs[:10]

        # 2. Fallback an toàn: Quét các thẻ <img> có alt hoặc src chứa mã sản phẩm, loại trừ logo / nav-logo
        base_pcode = str(product_code).strip()
        base_pcode_short = base_pcode[:-1] if len(base_pcode) > 3 and base_pcode[-1].isupper() else base_pcode
        fallback_imgs = []
        for tag in re.findall(r'<img[^>]+>', html, re.IGNORECASE):
            if 'nav-logo' in tag or 'itemprop=\"logo\"' in tag or 'alt=\"logo\"' in tag.lower():
                continue
            src_m = re.search(r'src=[\"\'](https://static\.vnappmob\.com/(?:siso|soro)/giayhainancy/[^\s\"\'<>]+\.(?:jpg|jpeg|png|webp))[\"\']', tag, re.IGNORECASE)
            if src_m:
                src_url = src_m.group(1)
                tag_lower = tag.lower()
                if (base_pcode and base_pcode.lower() in tag_lower) or (base_pcode_short and base_pcode_short.lower() in tag_lower):
                    if src_url not in fallback_imgs:
                        fallback_imgs.append(src_url)

        return fallback_imgs[:10]
    except Exception as e:
        print(f"[!] Lỗi khi cào ảnh từ {url}: {e}")
        return []


class DynamicHeaderScanner:
    """Quét Header Động 2 Chiều: Nhận diện chỉ số cột an toàn từ tên biến kỹ thuật hoặc alias tiếng Việt"""

    @staticmethod
    def scan_data_headers(df):
        var_row_idx = 1
        col_map = {}
        
        for r_idx in range(min(4, len(df))):
            row_vals = df.iloc[r_idx]
            for col_idx, val in enumerate(row_vals):
                if pd.notna(val):
                    key = str(val).strip()
                    if key and key not in col_map:
                        col_map[key] = col_idx

        # Lấy hàng CUỐI cùng (trong 5 hàng đầu) có tên kỹ thuật: tab NHAP có "product_code" ở cả hàng 1 và hàng 2,
        # lấy hàng đầu sẽ coi hàng tiêu đề 2 là dữ liệu và ghi nhầm trạng thái vào đó.
        for idx in range(min(5, len(df))):
            vals = [str(v).strip() for v in df.iloc[idx].values if pd.notna(v)]
            if 'product_code' in vals or 'item_size' in vals or 'get_images' in vals:
                var_row_idx = idx

        # Tên ở hàng 1 trùng tên kỹ thuật cột khác (SANPHAM: nhãn Việt của cột mới, vd "Giới tính" — bộ chuẩn 29/10) → hàng kỹ thuật thắng
        if var_row_idx > 0 and len(df):
            hang1 = {str(v).strip(): i for i, v in enumerate(df.iloc[0].values) if pd.notna(v) and str(v).strip()}
            for col_idx, val in enumerate(df.iloc[var_row_idx].values):
                key = str(val).strip() if pd.notna(val) else ''
                if key and key in hang1 and hang1[key] != col_idx:
                    col_map[key] = col_idx

        return var_row_idx, col_map

    @staticmethod
    def get_col_idx(col_map, *field_names, default=None):
        """Tra cứu chỉ số cột theo danh sách tên alias kỹ thuật hoặc tiếng Việt an toàn."""
        for name in field_names:
            if name in col_map:
                return col_map[name]
        return default


class EngineDataLoader:
    """Tải và cập nhật dữ liệu trực tiếp Google Sheets API (Single Source of Truth)"""

    def __init__(self):
        self.gc = None
        self.spreadsheet = None
        self.is_google_api = False
        self._sync_tabs = set()  # tab đã ghi trong tác vụ hiện tại → báo web chép lại khi tác vụ xong
        self._init_connection()

    def che_do(self):
        """META che_do: 'web' | 'master' (mặc định master — như hôm nay). Đọc 1 lần mỗi lần mở menu. Cùng luật bot webModeOn_."""
        if getattr(self, '_che_do', None) is None:
            self._che_do = 'master'
            try:
                rows = self.spreadsheet.worksheet('META').get_all_values()
                head = [str(h).strip() for h in (rows[0] if rows else [])]
                if 'key' in head and 'value' in head:
                    ck, cv = head.index('key'), head.index('value')
                    for r in rows[1:]:
                        if len(r) > max(ck, cv) and r[ck].strip() == 'che_do':
                            self._che_do = 'web' if r[cv].strip().lower() == 'web' else 'master'
            except Exception:
                pass  # không đọc được META → giữ master
        return self._che_do

    def cho_chep(self):
        """META cho_chep = số dòng web còn chờ chép sang Sheet (web ghi). Đọc mới mỗi lần (giá trị đổi liên tục). Không có khoá → 0."""
        try:
            rows = self.spreadsheet.worksheet('META').get_all_values()
            head = [str(h).strip() for h in (rows[0] if rows else [])]
            if 'key' in head and 'value' in head:
                ck, cv = head.index('key'), head.index('value')
                for r in rows[1:]:
                    if len(r) > max(ck, cv) and r[ck].strip() == 'cho_chep':
                        return max(0, int(float(r[cv] or 0)))
        except Exception:
            pass
        return 0

    def meta_mode(self, key):
        """Khoá chế độ trong META ('web' | 'master'), mặc định master. Đọc 1 lần mỗi lần mở menu; đổi ở [7] thì xoá nhớ. Cùng luật bot metaMode_."""
        cache = self.__dict__.setdefault('_modes', {})
        if key not in cache:
            cache[key] = 'master'
            try:
                for r in self.spreadsheet.worksheet('META').get_all_values()[1:]:
                    if len(r) > 1 and r[0].strip() == key:
                        cache[key] = 'web' if r[1].strip().lower() == 'web' else 'master'
            except Exception:
                pass
        return cache[key]

    def che_do_kho(self):
        return self.meta_mode('che_do_kho')  # P2: phiếu kho ghi D1

    def che_do_ton(self):
        return self.meta_mode('che_do_ton')  # P3: tồn tính ở D1

    def che_do_hh(self):
        return self.meta_mode('che_do_hh')  # P4: hàng hoá + giá sửa trên admin

    def _write_ok(self, sheet_name, them_dong=False):
        # Sổ kho ở web (P2): menu Mac không THÊM dòng NHAP / XUAT (phiếu kho do web ghi); sửa ô trạng thái (in tem, MISA) vẫn được
        if them_dong and sheet_name == 'SANPHAM' and self.is_google_api and self.che_do_hh() == 'web':
            print("⛔ Hàng hoá đang sửa trên web: menu Mac không thêm mã vào SANPHAM. Tạo mã trên web (admin), hoặc đổi hàng hoá về Dự phòng khi web hỏng.")
            return False
        if them_dong and sheet_name in ('NHAP', 'XUAT') and self.is_google_api and self.che_do_kho() == 'web':
            print(f"⛔ Sổ kho đang ở Web: menu Mac không thêm dòng {sheet_name}. Nhập / xuất trên web / app, hoặc đổi sổ kho về Dự phòng khi web hỏng.")
            return False
        if sheet_name in WEB_MODE_LOCKED_TABS and self.is_google_api and self.che_do() == 'web':
            print(f"⛔ Đang chế độ Web (sổ gốc ở web): menu Mac không ghi tab {sheet_name}. Làm trên web / app, hoặc đổi META che_do = master khi web hỏng.")
            return False
        # Master mà web còn dòng đang chép → chưa ghi BAN / NHAP / XUAT (cùng luật bot choChepBlock_)
        if sheet_name in ('BAN', 'NHAP', 'XUAT') and self.is_google_api:
            n = self.cho_chep()
            if n > 0:
                print(f"⏳ Còn {n} dòng web đang chép sang Sheet — chờ về 0 rồi chạy lại (chưa ghi tab {sheet_name}).")
                return False
        return True

    def _mark_sync(self, sheet_name):
        if sheet_name in SYNC_WATCH_TABS:
            self._sync_tabs.add(sheet_name)

    def mark_platform_update(self, channel):
        """Ghi mốc "lần cập nhật tồn/giá gần nhất" của sàn vào tab META (key | value | updated_at),
        dòng key = <channel>_last_update — chỗ chung với web và bot Zalo. Tìm theo tên cột và theo key;
        chưa có dòng key thì thêm dòng; chưa có tab / cột thì chỉ in nhắc, không tự tạo."""
        if not self.is_google_api:
            return
        key = f"{channel}_last_update"
        try:
            try:
                ws = self.spreadsheet.worksheet('META')
            except Exception:
                print(f"[!] Chưa có tab META — chưa ghi mốc cập nhật {channel}.")
                return
            rows = ws.get_all_values()
            header = [str(h).strip() for h in (rows[0] if rows else [])]
            missing = [c for c in ('key', 'value', 'updated_at') if c not in header]
            if missing:
                print(f"[!] Tab META thiếu cột {missing} — chưa ghi mốc cập nhật {channel}.")
                return
            ck, cv, cu = header.index('key'), header.index('value'), header.index('updated_at')
            row = next((r + 1 for r in range(1, len(rows)) if len(rows[r]) > ck and rows[r][ck].strip() == key), None)
            now = datetime.now()
            stamp = now.strftime("%Y-%m-%d %H:%M")
            if row is None:
                row = len(rows) + 1
                ws.update(range_name=gspread.utils.rowcol_to_a1(row, ck + 1), values=[[key]])
            ws.update(range_name=gspread.utils.rowcol_to_a1(row, cv + 1), values=[[stamp]])
            ws.update(range_name=gspread.utils.rowcol_to_a1(row, cu + 1), values=[[now.strftime("%Y-%m-%d %H:%M:%S")]])
            self._mark_sync('META')
            print(f"🕒 Đã ghi mốc cập nhật {channel}: {stamp} (META dòng {row})")
        except Exception as e:
            print(f"[!] Không ghi được mốc cập nhật {channel}: {e}")

    def flush_sync_hint(self):
        """Báo web giayhainancy.vn chép lại các tab vừa ghi (Sheets API không chạy trigger Apps Script).
        POST SYNC_HINT_URL, header x-sync-key: SYNC_HINT_KEY (không để khoá trong URL — lọt log), body {"tabs":[...]}. Thiếu cấu hình hoặc lỗi → chỉ in cảnh báo."""
        tabs = set(self._sync_tabs)
        self._sync_tabs.clear()
        if not tabs:
            return
        url = os.getenv('SYNC_HINT_URL', '').strip()
        key = os.getenv('SYNC_HINT_KEY', '').strip()
        if not url or not key:
            return
        if tabs & {'BAN', 'NHAP', 'XUAT'}:
            tabs |= {'KHO15E', 'KHOY3C'}
        ordered = [t for t in SYNC_WATCH_TABS if t in tabs]
        try:
            r = requests.post(url, headers={'x-sync-key': key}, json={'tabs': ordered}, timeout=15)
            if r.status_code in (200, 202):
                print(f"🔄 Đã báo web chép lại Sheet: {', '.join(ordered)}")
            else:
                print(f"[!] Báo web chép Sheet lỗi HTTP {r.status_code} — web vẫn tự chép theo vòng dự phòng.")
        except Exception as e:
            print(f"[!] Không báo được web chép Sheet ({e}) — web vẫn tự chép theo vòng dự phòng.")

    def _init_connection(self):
        if not HAS_GSPREAD:
            print("[!] Thư viện 'gspread' chưa được cài đặt.")
            self.is_google_api = False
            return

        if not os.path.exists(CREDENTIALS_PATH):
            print(f"[!] Không tìm thấy file khóa dịch vụ Google tại: {CREDENTIALS_PATH}")
            self.is_google_api = False
            return

        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
            self.gc = gspread.authorize(creds)
            self.spreadsheet = self.gc.open_by_key(SPREADSHEET_ID)
            self.is_google_api = True
        except Exception as e:
            self.is_google_api = False
            print(f"\n❌ [LỖI KẾT NỐI GOOGLE SHEETS]: {e}")
            print("[!] Vui lòng kiểm tra lại kết nối mạng Internet hoặc quyền chia sẻ của Google Sheet!\n")

    def load_sheet(self, sheet_name):
        """Tải toàn bộ dữ liệu của sheet thành DataFrame từ Google Sheets."""
        if not self.is_google_api:
            self._init_connection()

        if self.is_google_api:
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
                data = ws.get_all_values()
                return pd.DataFrame(data), ws
            except Exception as e:
                raise ConnectionError(f"Không thể đọc sheet '{sheet_name}' từ Google Sheets: {e}")

        raise ConnectionError(f"Không có kết nối Google Sheets API để tải sheet '{sheet_name}'!")

    def _p5b_web(self, sheet_name, cells):
        """P5b (21/10): sổ ở Web + META p5b_web = 1 → gửi cờ lên web (co_nhap / co_sp) thay vì ghi Sheet — cùng luật bot
        nhapFlagsWeb_ / spFlagsWeb_ (tools/web_lenh.py). cells = {chỉ số dòng 0-based: {chỉ số cột: giá trị}}.
        Trả None = ghi Sheet như cũ (P5b tắt / web Dự phòng / cột ngoài hợp đồng), True = web đã ghi, False = web lỗi (không ghi)."""
        if not self.is_google_api or not cells or sheet_name not in ('NHAP', 'SANPHAM'):
            return None
        from tools import web_lenh
        m = web_lenh.meta(self.spreadsheet)
        if not web_lenh.p5b_on(m, 'che_do_kho' if sheet_name == 'NHAP' else 'che_do_hh'):
            return None
        v = self.spreadsheet.worksheet(sheet_name).get_all_values()
        hr = 1 if sheet_name == 'SANPHAM' else 0  # SANPHAM: tên cột kỹ thuật ở hàng 2 (luật 4)
        head = [str(h).strip() for h in v[hr]]
        if 'product_code' not in head:
            return None
        ic, im = head.index('product_code'), (head.index('ma_dong') if 'ma_dong' in head else None)
        cell = lambda r, c: (v[r][c] if r < len(v) and c is not None and c < len(v[r]) else '').strip()
        if sheet_name == 'NHAP':
            by_col = {}
            for r, cols in cells.items():
                for c, val in cols.items():
                    by_col.setdefault(head[c] if c < len(head) else '', []).append(
                        {'row': r + 1, 'code': cell(r, ic).upper(), 'ma_dong': cell(r, im), 'value': val})
            if any(f not in web_lenh.CO_NHAP_COLS for f in by_col):
                return None
            res = [web_lenh.co_nhap(f, d) for f, d in by_col.items()]
        else:
            res = [web_lenh.co_sp([{'code': cell(r, ic).upper(), 'doi': {head[c]: val for c, val in cols.items() if c < len(head)}} for r, cols in cells.items()])]
        if any(x is None for x in res):
            return None
        bad = [x for x in res if not x.get('ok')]
        if bad:
            print(f"❌ {bad[0].get('error')} — CHƯA ghi cờ {sheet_name} (web là gốc). File đã tạo: đừng nhập 2 lần; báo Thực thi.")
            return False
        print(f"🌐 Đã gửi cờ {sheet_name} lên web ({sum(len(c) for c in cells.values())} ô).")
        return True

    def update_status(self, sheet_name, row_indices, col_idx, status_text_or_list):
        """Cập nhật chữ 'Done - YYYY-MM-DD HH:mm' hoặc danh sách trạng thái riêng từng dòng lên Google Sheet."""
        if not self._write_ok(sheet_name):
            return False
        if not row_indices:
            return True

        if isinstance(status_text_or_list, list):
            status_list = status_text_or_list
        else:
            status_list = [status_text_or_list] * len(row_indices)

        w = self._p5b_web(sheet_name, {r: {col_idx: t} for r, t in zip(row_indices, status_list)})
        if w is not None:
            return w

        if self.is_google_api:
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
                g_col = col_idx + 1
                cell_updates = []
                for r_idx, st_text in zip(row_indices, status_list):
                    g_row = r_idx + 1
                    cell_updates.append({
                        'range': gspread.utils.rowcol_to_a1(g_row, g_col),
                        'values': [[st_text]]
                    })
                if cell_updates:
                    for i in range(0, len(cell_updates), 100):
                        chunk = cell_updates[i:i+100]
                        ws.batch_update(chunk)
                        self._mark_sync(sheet_name)
                        if i + 100 < len(cell_updates):
                            time.sleep(0.5)
                return True
            except Exception as e:
                print(f"[!] Lỗi khi ghi Google Sheet API ({sheet_name}): {e}")
        return False

    def update_batch_image_results(self, sheet_name, batch_records):
        """Batch update tất cả các dòng ảnh cào được vào Google Sheet (tránh vượt quota API)."""
        if not self._write_ok(sheet_name):
            return False
        if not batch_records:
            return True

        cells = {}
        for rec in batch_records:
            d = cells.setdefault(rec['row_idx'], {})
            for idx in range(10):
                d[rec['img_col_indices'][idx]] = rec['img_urls'][idx] if idx < len(rec['img_urls']) else ""
            d[rec['status_col_idx']] = rec['status_text']
        w = self._p5b_web(sheet_name, cells)
        if w is not None:
            return w

        if self.is_google_api:
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
                cell_updates = []
                for rec in batch_records:
                    g_row = rec['row_idx'] + 1
                    status_col_idx = rec['status_col_idx']
                    img_urls = rec['img_urls']
                    img_col_indices = rec['img_col_indices']
                    status_text = rec['status_text']

                    for idx in range(10):
                        c_idx = img_col_indices[idx]
                        val = img_urls[idx] if idx < len(img_urls) else ""
                        cell_updates.append({
                            'range': gspread.utils.rowcol_to_a1(g_row, c_idx + 1),
                            'values': [[val]]
                        })

                    cell_updates.append({
                        'range': gspread.utils.rowcol_to_a1(g_row, status_col_idx + 1),
                        'values': [[status_text]]
                    })

                for i in range(0, len(cell_updates), 100):
                    chunk = cell_updates[i:i+100]
                    ws.batch_update(chunk)
                    self._mark_sync(sheet_name)
                    time.sleep(0.5)
                return True
            except Exception as e:
                print(f"[!] Lỗi khi batch update Google Sheet API: {e}")
        return False

    def update_batch_media_results(self, sheet_name, batch_records):
        """Batch update các cột content_path, content_url, content_files vào Google Sheet siêu tốc."""
        if not self._write_ok(sheet_name):
            return False
        if not batch_records or not self.is_google_api:
            return False
        cells = {}
        for rec in batch_records:
            d = cells.setdefault(rec['row_idx'], {})
            for k, val in (('path_col_idx', 'path_val'), ('url_col_idx', 'url_val'), ('files_col_idx', 'files_val')):
                if rec.get(k) is not None:
                    d[rec[k]] = rec[val]
        w = self._p5b_web(sheet_name, cells)
        if w is not None:
            return w
        try:
            ws = self.spreadsheet.worksheet(sheet_name)
            p_idx = batch_records[0].get('path_col_idx')
            u_idx = batch_records[0].get('url_col_idx')
            f_idx = batch_records[0].get('files_col_idx')

            if p_idx is not None and u_idx is not None and f_idx is not None and (p_idx + 1 == u_idx and u_idx + 1 == f_idx):
                start_row = batch_records[0]['row_idx'] + 1
                end_row = batch_records[-1]['row_idx'] + 1
                matrix = []
                for rec in batch_records:
                    matrix.append([rec['path_val'], rec['url_val'], rec['files_val']])
                start_cell = gspread.utils.rowcol_to_a1(start_row, p_idx + 1)
                end_cell = gspread.utils.rowcol_to_a1(end_row, f_idx + 1)
                ws.update(range_name=f"{start_cell}:{end_cell}", values=matrix)
                self._mark_sync(sheet_name)
                return True

            cell_updates = []
            for rec in batch_records:
                g_row = rec['row_idx'] + 1
                if rec.get('path_col_idx') is not None:
                    cell_updates.append({
                        'range': gspread.utils.rowcol_to_a1(g_row, rec['path_col_idx'] + 1),
                        'values': [[rec['path_val']]]
                    })
                if rec.get('url_col_idx') is not None:
                    cell_updates.append({
                        'range': gspread.utils.rowcol_to_a1(g_row, rec['url_col_idx'] + 1),
                        'values': [[rec['url_val']]]
                    })
                if rec.get('files_col_idx') is not None:
                    cell_updates.append({
                        'range': gspread.utils.rowcol_to_a1(g_row, rec['files_col_idx'] + 1),
                        'values': [[rec['files_val']]]
                    })

            for i in range(0, len(cell_updates), 300):
                chunk = cell_updates[i:i+300]
                ws.batch_update(chunk)
                self._mark_sync(sheet_name)
                time.sleep(0.5)
            return True
        except Exception as e:
            print(f"[!] Lỗi khi batch update media results: {e}")
            return False

    def append_rows_to_sheet(self, sheet_name, new_rows):
        """Append các dòng mới vào cuối bảng Google Sheet (với công thức USER_ENTERED)."""
        if not self._write_ok(sheet_name, them_dong=True):
            return False
        if not new_rows:
            return True

        if self.is_google_api:
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
                ws.append_rows(new_rows, value_input_option='USER_ENTERED')
                self._mark_sync(sheet_name)
                return True
            except Exception as e:
                print(f"[!] Lỗi khi append Google Sheet API ({sheet_name}): {e}")
        return False

    def insert_rows_with_exact_range(self, sheet_name, new_rows, start_row):
        """Ghi các dòng mới vào đúng tọa độ A{start_row}:{last_col}{end_row} (tránh 100% lỗi lệch cột của append_rows)."""
        if not self._write_ok(sheet_name, them_dong=True):
            return False
        if not new_rows or not self.is_google_api:
            return False
        try:
            ws = self.spreadsheet.worksheet(sheet_name)
            num_cols = max(len(r) for r in new_rows)
            end_row = start_row + len(new_rows) - 1
            # Tự mở rộng lưới khi vượt số dòng hiện có (thêm dư GRID_EXTRA_ROWS dòng)
            if end_row > ws.row_count:
                ws.add_rows(end_row - ws.row_count + GRID_EXTRA_ROWS)
            last_col_letter = gspread.utils.rowcol_to_a1(1, num_cols).rstrip('0123456789')
            range_name = f"A{start_row}:{last_col_letter}{end_row}"
            ws.update(range_name=range_name, values=new_rows, value_input_option='USER_ENTERED')
            self._mark_sync(sheet_name)
            return True
        except Exception as e:
            print(f"[!] Lỗi khi ghi Google Sheet API ({sheet_name}) tại {start_row}: {e}")
            return False


def sync_hint_after(fn):
    """Hết tác vụ (kể cả khi lỗi) thì báo web chép lại các tab tác vụ đã ghi."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            for a in list(args) + list(kwargs.values()):
                if isinstance(a, EngineDataLoader):
                    a.flush_sync_hint()
                    break
    return wrapper


def get_stock_maps(loader):
    """Tính toán bảng Tồn kho Realtime từ KHO15E và KHOY3C."""
    stock_15e_dict = {}
    stock_y3c_dict = {}
    stock_total_dict = {}

    df_15e, _ = loader.load_sheet('KHO15E')
    var_idx_15, map_15 = DynamicHeaderScanner.scan_data_headers(df_15e)
    p_col = DynamicHeaderScanner.get_col_idx(map_15, 'product_code', 'Mã sản phẩm', 'Mã SP', default=1)
    s_col = DynamicHeaderScanner.get_col_idx(map_15, 'item_size', 'Size', 'Kích cỡ', default=3)
    q_col = DynamicHeaderScanner.get_col_idx(map_15, 'current_quantity', 'Tồn hiện tại', 'Tồn kho', default=5)

    start_r = (var_idx_15 + 1) if var_idx_15 is not None else 1
    for i in range(start_r, len(df_15e)):
        row = df_15e.iloc[i]
        pcode = str(row[p_col]).strip() if pd.notna(row[p_col]) else ""
        size_val = str(row[s_col]).strip() if pd.notna(row[s_col]) else ""
        if size_val.endswith('.0'): size_val = size_val[:-2]
        try:
            qty = float(row[q_col]) if pd.notna(row[q_col]) else 0.0
        except (ValueError, TypeError):
            qty = 0.0

        if pcode:
            sku = f"{pcode}{size_val}"
            stock_15e_dict[sku] = stock_15e_dict.get(sku, 0.0) + qty

    df_y3c, _ = loader.load_sheet('KHOY3C')
    var_idx_y3, map_y3 = DynamicHeaderScanner.scan_data_headers(df_y3c)
    p_col = DynamicHeaderScanner.get_col_idx(map_y3, 'product_code', 'Mã sản phẩm', 'Mã SP', default=1)
    s_col = DynamicHeaderScanner.get_col_idx(map_y3, 'item_size', 'Size', 'Kích cỡ', default=3)
    q_col = DynamicHeaderScanner.get_col_idx(map_y3, 'current_quantity', 'Tồn hiện tại', 'Tồn kho', default=5)

    start_r = (var_idx_y3 + 1) if var_idx_y3 is not None else 1
    for i in range(start_r, len(df_y3c)):
        row = df_y3c.iloc[i]
        pcode = str(row[p_col]).strip() if pd.notna(row[p_col]) else ""
        size_val = str(row[s_col]).strip() if pd.notna(row[s_col]) else ""
        if size_val.endswith('.0'): size_val = size_val[:-2]
        try:
            qty = float(row[q_col]) if pd.notna(row[q_col]) else 0.0
        except (ValueError, TypeError):
            qty = 0.0

        if pcode:
            sku = f"{pcode}{size_val}"
            stock_y3c_dict[sku] = stock_y3c_dict.get(sku, 0.0) + qty

    all_skus = set(stock_15e_dict.keys()).union(set(stock_y3c_dict.keys()))
    for sku in all_skus:
        stock_total_dict[sku] = stock_15e_dict.get(sku, 0.0) + stock_y3c_dict.get(sku, 0.0)

    return stock_15e_dict, stock_y3c_dict, stock_total_dict


CHANNEL_LINKS_FILE = "channel_links.csv"
CHANNEL_LINKS_COLUMNS = ["product_code", "channel", "item_id", "shopid", "url"]


def build_channel_links(channel, ws, sp_codes):
    """Đọc ID sản phẩm trên sàn từ sheet mẫu cập nhật (theo tên cột hàng 1) → ({product_code: item_id}, shopid, số SKU không khớp).
    Shopee: et_title_product_id + et_title_variation_sku (mã+size), dữ liệu từ hàng 7, shopid ở hàng 2.
    TikTok: product_id + seller_sku (mã), dữ liệu từ hàng 6. Thiếu cột → None."""
    header = {}
    for c in range(1, ws.max_column + 1):
        k = str(ws.cell(row=1, column=c).value or '').strip()
        if k and k not in header:
            header[k] = c
    if channel == 'shopee':
        id_col, sku_col = header.get('et_title_product_id'), header.get('et_title_variation_sku')
        name_col, status_col, first_row = header.get('et_title_variation_name'), None, 7
    else:
        id_col, sku_col = header.get('product_id'), header.get('seller_sku')
        name_col, status_col, first_row = header.get('variation_value'), header.get('product_status'), 6
    if id_col is None or sku_col is None:
        return None

    shopid = ''
    if channel == 'shopee':
        for c in range(1, ws.max_column + 1):
            v = str(ws.cell(row=2, column=c).value or '').strip()
            if re.fullmatch(r'\d{5,}', v):
                shopid = v
                break

    codes_by_len = sorted(sp_codes, key=len, reverse=True)

    def to_code(sku, var_name):
        sku = sku.strip().upper()
        if not sku:
            return None
        if sku in sp_codes:
            return sku
        tail = var_name.split(',')[-1].strip().upper() if ',' in var_name else ''
        if tail and sku.endswith(tail) and sku[:-len(tail)] in sp_codes:
            return sku[:-len(tail)]
        for code in codes_by_len:
            if sku.startswith(code) and sku[len(code):].isdigit():
                return code
        return None

    stats = {}  # code → {item_id: [số biến thể, đang bán]}
    unmatched = 0
    for r in range(first_row, ws.max_row + 1):
        item_id = str(ws.cell(row=r, column=id_col).value or '').strip()
        sku = str(ws.cell(row=r, column=sku_col).value or '').strip()
        if not item_id or not sku:
            continue
        var_name = str(ws.cell(row=r, column=name_col).value or '') if name_col else ''
        code = to_code(sku, var_name)
        if not code:
            unmatched += 1
            continue
        info = stats.setdefault(code, {}).setdefault(item_id, [0, False])
        info[0] += 1
        if status_col and 'Trên kệ' in str(ws.cell(row=r, column=status_col).value or ''):
            info[1] = True

    # Một mã gắn nhiều item_id → giữ tin đang bán, nhiều biến thể hơn, rồi ID lớn hơn (mới hơn)
    links = {}
    for code, items in stats.items():
        best = max(items.items(), key=lambda kv: (kv[1][1], kv[1][0], int(kv[0]) if kv[0].isdigit() else 0))
        links[code] = best[0]
    return links, shopid, unmatched


def export_channel_links(channel, ws, sp_codes):
    """Ghi đè EXPORT_DIR/channel_links.csv: thay các dòng của kênh này, giữ nguyên dòng của kênh kia.
    Cột: product_code, channel, item_id (Shopee item_id / TikTok product_id), shopid, url. Trả về (số mã, số SKU không khớp)."""
    built = build_channel_links(channel, ws, sp_codes)
    if built is None:
        print(f"[!] Không ghi {CHANNEL_LINKS_FILE}: file mẫu {channel} thiếu cột ID sản phẩm / SKU.")
        return None
    links, shopid, unmatched = built
    path = os.path.join(EXPORT_DIR, CHANNEL_LINKS_FILE)

    rows = []
    if os.path.exists(path):
        with open(path, newline='', encoding='utf-8') as f:
            rows = [r for r in csv.DictReader(f) if r.get('channel') != channel]
    for code in sorted(links):
        item_id = links[code]
        if channel == 'shopee':
            url = f"https://shopee.vn/product/{shopid}/{item_id}" if shopid else ''
        else:
            url = f"https://shop.tiktok.com/vn/pdp/{item_id}"
        rows.append({'product_code': code, 'channel': channel, 'item_id': item_id, 'shopid': shopid, 'url': url})
    rows.sort(key=lambda r: (r.get('channel', ''), r.get('product_code', '')))

    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CHANNEL_LINKS_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, path)
    return len(links), unmatched


def sanpham_codes(df_sp, col_map_sp):
    """Tập product_code (viết hoa) trong SANPHAM."""
    idx = col_map_sp.get('product_code')
    if idx is None:
        return set()
    return {str(df_sp.iloc[r][idx] or '').strip().upper() for r in range(2, len(df_sp)) if str(df_sp.iloc[r][idx] or '').strip()}


def get_sub_info(loader):
    """Loads SUB category attribute mapping dynamically."""
    sub_dict = {}
    try:
        df_sub, _ = loader.load_sheet('SUB')
        _, col_map = DynamicHeaderScanner.scan_data_headers(df_sub)
        header_row = df_sub.iloc[0].values
        col_names = [str(c).strip() for c in header_row]

        for i in range(1, len(df_sub)):
            row_dict = {}
            for col_idx, cname in enumerate(col_names):
                val = df_sub.iloc[i, col_idx]
                row_dict[cname] = val if pd.notna(val) else ""

            for k, v in col_map.items():
                val = df_sub.iloc[i, v] if pd.notna(df_sub.iloc[i, v]) else ""
                row_dict[k] = val

            cat_name = str(df_sub.iloc[i, col_map.get('Tên Ngành Hàng', 0)]).strip()
            if cat_name:
                sub_dict[cat_name.lower()] = row_dict
                sub_dict[cat_name] = row_dict
    except Exception as e:
        print(f"[!] Lỗi khi load SUB: {e}")
    return sub_dict


def parse_number(val):
    """Chuyển đổi các định dạng số/tiền tệ Việt Nam ('500.000 đ', '1,200,000', 500000) thành float chuẩn"""
    if val is None or pd.isna(val) or str(val).strip() == "":
        return 0.0
    s = str(val).strip().replace('đ', '').replace('Đ', '').replace('VND', '').replace('vnd', '').replace(' ', '')
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif '.' in s and s.count('.') > 1:
        s = s.replace('.', '')
    elif '.' in s and len(s.split('.')[-1]) == 3:
        s = s.replace('.', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_percent_rate(val_str):
    """Chuyển chuỗi '8%', '0,60%', '0.05', '0' thành số float (ví dụ 0.08, 0.006)"""
    if val_str is None or pd.isna(val_str) or str(val_str).strip() == "":
        return 0.0
    s = str(val_str).strip().replace('%', '').replace(',', '.')
    try:
        f = float(s)
        return (f / 100.0) if (f > 1.0 or '%' in str(val_str)) else f
    except ValueError:
        return 0.0


def parse_price_multiplier(val, default=1.0):
    """Chuyển đổi tỷ lệ % giá TMĐT ('140%', 1.4, '100%') thành hệ số nhân float chuẩn (ví dụ 1.40)"""
    if val is None or pd.isna(val) or str(val).strip() == "":
        return default
    s = str(val).strip().replace('%', '').replace(' ', '').replace(',', '.')
    try:
        f = float(s)
        if f <= 0:
            return default
        if f > 3.0:  # Ví dụ 140, 150, 100
            return f / 100.0
        return f      # Ví dụ 1.4, 1.15, 1.0
    except Exception:
        return default


def map_tiktok_attributes(sub_info, sp=None):
    """Ánh xạ thuộc tính bổ sung TikTok Shop. Chất liệu / dịp / mũi / gót / kiểu buộc đọc thẳng dòng SANPHAM của mã (sp, theo tên cột
    hàng 2 — luật 4); các cột cùng tên ở SUB chỉ là danh sách thả, không gắn ngành (Phân tích · Bán hàng rà 29/10). Khớp san.js web (luật 15).
    Tổ chức chịu trách nhiệm vẫn lấy ở SUB."""
    sp = {str(k).strip(): v for k, v in (sp or {}).items()}

    def _sp(name):
        v = sp.get(name, '')
        return '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)

    def _moi(*ten, cu=''):
        """Bộ chuẩn 29/10: cột mới (BA–BO) trước, trống thì cột cũ — cùng thứ tự san.js web (luật 15)."""
        return ' '.join(x for x in (_sp(t).strip() for t in ten) if x) or _sp(cu)

    origin = "Việt Nam"

    # Chất liệu
    mat_raw = _moi('chat_lieu', cu='Chất liệu').split(',')[0].lower()  # chọn nhiều → ô sàn 1 giá trị lấy giá trị đầu (29/10)
    if 'bò' in mat_raw or 'da' in mat_raw:
        material = 'Da'
    elif 'vải' in mat_raw or 'lưới' in mat_raw or 'bố' in mat_raw:
        material = 'Vải'
    else:
        material = 'Da'

    # Dịp
    use_raw = _moi('dip', cu='Sử dụng:').lower()
    if 'tiệc' in use_raw or 'cưới' in use_raw:
        occasion = 'Lễ cưới'
    elif 'công sở' in use_raw or 'kinh doanh' in use_raw:
        occasion = 'Kinh doanh'
    else:
        occasion = 'Thông thường'

    season = "Bốn mùa"

    # Hình dáng ngón chân
    toe_raw = _moi('dang_mui', cu='Dáng giày mũi:').lower()
    if 'nhọn' in toe_raw:
        toe_shape = 'Mũi nhọn'
    elif 'vuông' in toe_raw:
        toe_shape = 'Mũi vuông'
    elif 'hở' in toe_raw or 'xỏ ngón' in toe_raw:
        toe_shape = 'Mũi hở'
    else:
        toe_shape = 'Mũi tròn'

    # Chiều cao gót
    heel_raw = _moi('kieu_de', 'cao_got_cm', cu='Phần dưới giày:').lower()
    # Theo số cm (khớp san.js web 29/10): luật cũ dò ký tự '5' / '2' nên "gót 4cm" ra phẳng, "gót 2,5cm" ra vừa
    so_cm = re.search(r'(\d+(?:[.,]\d+)?)', heel_raw)
    cm = float(so_cm.group(1).replace(',', '.')) if so_cm else None
    if (cm is not None and cm > 3) or (cm is None and 'cao' in heel_raw):
        heel_height = 'Gót vừa (3-5 cm)'
    elif (cm is not None and cm > 1) or (cm is None and 'thấp' in heel_raw):
        heel_height = 'Gót thấp (1-3 cm)'
    else:
        heel_height = 'Gót phẳng (1 cm trở xuống)'

    # Loại buộc
    feat_raw = _moi('kieu_dong', cu='Đặc điểm').split(',')[0].lower()  # chọn nhiều → giá trị đầu (khớp web 29/10)
    if 'cột' in feat_raw or 'dây' in feat_raw:
        closure = 'Dây buộc'
    elif 'xé' in feat_raw or 'dán' in feat_raw:
        closure = 'Khóa dán'
    elif 'kéo' in feat_raw:
        closure = 'Khóa kéo'
    else:
        closure = 'Khóa trượt'

    heel_type = "Giày đế bằng"

    org_name = str(sub_info.get('Tên tổ chức chịu trách nhiệm hàng hóa') or sub_info.get('Tên đối tượng', 'HỘ KINH DOANH LƯU THÁI CHÍ KHA (HIỆU GIÀY HẢI NANCY 2)')).strip()
    org_addr = str(sub_info.get('Địa chỉ tổ chức chịu trách nhiệm hàng hóa', '15E Tăng Bạt Hổ, Phường Xuân Hương - Đà Lạt, Lâm Đồng, Việt Nam.')).strip()

    return {
        'origin': origin,
        'material': material,
        'occasion': occasion,
        'season': season,
        'toe_shape': toe_shape,
        'heel_height': heel_height,
        'closure': closure,
        'heel_type': heel_type,
        'org_name': org_name,
        'org_addr': org_addr
    }


def get_supplier_map(loader):
    """Load thông tin Nhà cung cấp từ tab SUB (Mã đối tượng, Tên đối tượng, % chiết khấu, Thuế suất)."""
    supplier_map = {}
    try:
        df_sub, _ = loader.load_sheet('SUB')
        _, map_sub = DynamicHeaderScanner.scan_data_headers(df_sub)
        
        sup_col = DynamicHeaderScanner.get_col_idx(map_sub, 'supplier', 'Nhà cung cấp', 'NCC')
        ma_col = DynamicHeaderScanner.get_col_idx(map_sub, 'Mã đối tượng', 'ma_dt')
        ten_col = DynamicHeaderScanner.get_col_idx(map_sub, 'Tên đối tượng', 'ten_dt')
        ck_col = DynamicHeaderScanner.get_col_idx(map_sub, '% chiết khấu', 'ChietKhau')
        vat_col = DynamicHeaderScanner.get_col_idx(map_sub, 'Thuế suất', 'VAT')

        if sup_col is not None:
            for i in range(1, len(df_sub)):
                row = df_sub.iloc[i]
                sup_name = str(row[sup_col]).strip() if pd.notna(row[sup_col]) else ""
                if sup_name:
                    supplier_map[sup_name.lower()] = {
                        'ma_dt': str(row[ma_col]).strip() if (ma_col is not None and pd.notna(row[ma_col])) else "",
                        'ten_dt': str(row[ten_col]).strip() if (ten_col is not None and pd.notna(row[ten_col])) else "",
                        'discount_str': str(row[ck_col]).strip() if (ck_col is not None and pd.notna(row[ck_col])) else "0",
                        'vat_str': str(row[vat_col]).strip() if (vat_col is not None and pd.notna(row[vat_col])) else "0"
                    }
    except Exception as e:
        print(f"[!] Lỗi tải thông tin supplier từ SUB: {e}")
    return supplier_map


def get_product_info_map(loader):
    """Load thông tin chi tiết sản phẩm từ tab SANPHAM (Tên, Giá, Link Web, Màu, Supplier, ĐVT, Đơn giá HĐ)."""
    product_map = {}
    try:
        df_sp, _ = loader.load_sheet('SANPHAM')
        _, map_sp = DynamicHeaderScanner.scan_data_headers(df_sp)

        pcode_col = DynamicHeaderScanner.get_col_idx(map_sp, 'product_code', 'Mã sản phẩm', 'Mã SP')
        pname_col = DynamicHeaderScanner.get_col_idx(map_sp, 'product_name', 'Tên sản phẩm', 'Tên')
        pprice_col = DynamicHeaderScanner.get_col_idx(map_sp, 'product_price', 'Giá bán', 'Giá')
        pcolor_col = DynamicHeaderScanner.get_col_idx(map_sp, 'product_color', 'Màu sắc', 'Màu')
        web_url_col = DynamicHeaderScanner.get_col_idx(map_sp, 'web_url', 'Link sản phẩm', 'Link web')
        inv_col = DynamicHeaderScanner.get_col_idx(map_sp, 'invoice_price', 'Đơn giá', 'Giá hóa đơn')
        pur_col = DynamicHeaderScanner.get_col_idx(map_sp, 'purchase_price', 'Giá mua')
        sup_col = DynamicHeaderScanner.get_col_idx(map_sp, 'supplier', 'Nhà cung cấp', 'NCC')
        unit_col = DynamicHeaderScanner.get_col_idx(map_sp, 'product_unit', 'ĐVT', 'Đơn vị tính')

        if pcode_col is not None:
            for i in range(2, len(df_sp)):
                row = df_sp.iloc[i]
                pcode = str(row[pcode_col]).strip() if pd.notna(row[pcode_col]) else ""
                if pcode:
                    pname = str(row[pname_col]).strip() if (pname_col is not None and pd.notna(row[pname_col])) else ""
                    pprice = str(row[pprice_col]).strip() if (pprice_col is not None and pd.notna(row[pprice_col])) else ""
                    pcolor = str(row[pcolor_col]).strip() if (pcolor_col is not None and pd.notna(row[pcolor_col])) else ""
                    web_url = str(row[web_url_col]).strip() if (web_url_col is not None and pd.notna(row[web_url_col])) else ""

                    raw_inv = row[inv_col] if (inv_col is not None and pd.notna(row[inv_col])) else ""
                    inv_price = str(raw_inv).strip()

                    pur_price = row[pur_col] if (pur_col is not None and pd.notna(row[pur_col])) else 0
                    sup = str(row[sup_col]).strip() if (sup_col is not None and pd.notna(row[sup_col])) else ""
                    unit = str(row[unit_col]).strip() if (unit_col is not None and pd.notna(row[unit_col])) else ""

                    pcode_upper = pcode.upper()
                    product_map[pcode_upper] = {
                        'product_name': pname,
                        'product_price': pprice,
                        'product_color': pcolor,
                        'web_url': web_url,
                        'invoice_price': inv_price,
                        'purchase_price': pur_price,
                        'supplier': sup,
                        'unit': unit
                    }
    except Exception as e:
        print(f"[!] Lỗi tải thông tin sản phẩm từ SANPHAM: {e}")
    return product_map


def unroll_sizes(sizes_str):
    """Bóc dải Size '38,39,40' thành danh sách [38, 39, 40]"""
    if not sizes_str or pd.isna(sizes_str):
        return [""]
    s = str(sizes_str).strip()
    parts = [p.strip() for p in re.split(r'[,;\s]+', s) if p.strip()]
    return parts if parts else [s]


@sync_hint_after
def process_export_task(choice, loader):
    """Engine chính xử lý 11 tác vụ xuất file & cào ảnh"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ==================== TASK 11: CÀO ẢNH SẢN PHẨM TỪ LINK WEB ====================
    if choice == 11:
        df_raw, _ = loader.load_sheet('SANPHAM')
        var_row_idx, col_map = DynamicHeaderScanner.scan_data_headers(df_raw)

        link_col_idx = col_map.get('Link web')
        status_col_idx = col_map.get('get_images')
        pcode_col_idx = col_map.get('product_code')

        if link_col_idx is None or status_col_idx is None:
            msg = "❌ Không tìm thấy cột 'Link web' hoặc 'get_images' trong tab SANPHAM!"
            if HAS_RICH: console.print(f"[bold red]{msg}[/bold red]")
            else: print(msg)
            return

        img_col_names = [f"image_{i:02d}" for i in range(1, 11)]
        img_col_indices = [col_map[name] for name in img_col_names if name in col_map]

        if len(img_col_indices) < 10:
            alt_names = [f"Pic {i}" for i in range(1, 11)]
            img_col_indices = [col_map[name] for name in alt_names if name in col_map]

        data_start_row = (var_row_idx + 1) if var_row_idx is not None else 2
        batch_records = []

        for rel_idx in range(data_start_row, len(df_raw)):
            row = df_raw.iloc[rel_idx]
            link_val = str(row[link_col_idx]).strip() if pd.notna(row[link_col_idx]) else ""
            status_val = str(row[status_col_idx]).strip() if pd.notna(row[status_col_idx]) else ""
            pcode_val = str(row[pcode_col_idx]).strip() if (pcode_col_idx is not None and pd.notna(row[pcode_col_idx])) else ""

            if not status_val and pcode_val:
                imgs = []
                status_text = ""

                # 1. Thử cào ảnh từ Link web nếu có
                if link_val and str(link_val).startswith("http"):
                    if HAS_RICH:
                        console.print(f"🔎 Đang cào ảnh chuẩn cho dòng {rel_idx + 1} (Mã: {pcode_val}): {link_val}...")
                    else:
                        print(f"🔎 Đang cào ảnh chuẩn cho dòng {rel_idx + 1} (Mã: {pcode_val}): {link_val}...")
                    imgs = fetch_web_images(link_val, pcode_val)
                    if imgs:
                        status_text = f"Done - {now_str}"

                # 2. Nếu không có link web hoặc web chưa có ảnh -> Đối chiếu thư mục Media NAS (chỉ lấy đường dẫn thư mục)
                if not imgs:
                    local_folder = os.path.join(MEDIA_DEST_DIR, pcode_val)
                    if os.path.exists(local_folder):
                        try:
                            f_list = [
                                f for f in os.listdir(local_folder)
                                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.heic')) and not f.startswith('.')
                            ]
                            if f_list:
                                status_text = local_folder
                                if HAS_RICH:
                                    console.print(f"  📁 [bold green]Tìm thấy {len(f_list)} ảnh trong Media NAS:[/bold green] [cyan]{local_folder}[/cyan]")
                                else:
                                    print(f"  📁 Tìm thấy {len(f_list)} ảnh trong Media NAS: {local_folder}")
                        except Exception:
                            pass

                # 3. Ghi nhận kết quả cập nhật
                if imgs:
                    # Đã có ảnh từ web: Ghi link ảnh web vào image_01-10 và đánh dấu Done
                    batch_records.append({
                        'row_idx': rel_idx,
                        'img_col_indices': img_col_indices,
                        'img_urls': imgs,
                        'status_col_idx': status_col_idx,
                        'status_text': status_text
                    })
                elif status_text:
                    # Có ảnh trong Media NAS nhưng chưa up web: Chỉ cập nhật đường dẫn thư mục vào get_images, KHÔNG điền vào image_01-10
                    batch_records.append({
                        'row_idx': rel_idx,
                        'img_col_indices': img_col_indices,
                        'img_urls': [],
                        'status_col_idx': status_col_idx,
                        'status_text': status_text
                    })
                else:
                    if link_val and str(link_val).startswith("http"):
                        status_text = f"No Image - {now_str}"
                        batch_records.append({
                            'row_idx': rel_idx,
                            'img_col_indices': img_col_indices,
                            'img_urls': [],
                            'status_col_idx': status_col_idx,
                            'status_text': status_text
                        })

        if batch_records:
            loader.update_batch_image_results('SANPHAM', batch_records)

        msg = f"\n✅ Đã quét và cập nhật ảnh chuẩn hoàn tất cho {len(batch_records)} sản phẩm!\n"
        if HAS_RICH: console.print(Panel(msg, title="[bold green]CÀO ẢNH HOÀN TẤT[/bold green]", border_style="green"))
        else: print(msg)
        return

    # ==================== TASK 5: WEBSITE STOCK IMPORT ====================
    if choice == 5:
        opt_text = """-------------------------------------------------------------------
         🌐 CHỌN CHẾ ĐỘ XUẤT WEBSITE STOCK IMPORT
-------------------------------------------------------------------
  [1] 📥 Xuất theo Phiếu Nhập Mới (Chỉ các dòng chưa xuất ở tab NHAP)
  [2] 📦 Xuất FULL Toàn Bộ Tồn Kho Hiện Tại (Từ KHO15E & KHOY3C, Tồn Realtime)
  -----------------------------------------------------------------
  [0] ↩️ Quay lại
-------------------------------------------------------------------"""
        if HAS_RICH:
            console.print(Panel(opt_text, border_style="cyan"))
            web_mode = Prompt.ask("[bold cyan]Mời chọn chế độ xuất tồn kho Web [1/2][/bold cyan]", choices=["0", "1", "2"], default="1")
        else:
            print(opt_text)
            web_mode = input("Mời chọn chế độ xuất tồn kho Web [1/2]: ").strip()

        if web_mode not in ["1", "2"]:
            print("Đã hủy tác vụ xuất tồn kho Website.")
            return

        df_sp, _ = loader.load_sheet('SANPHAM')
        _, col_map_sp = DynamicHeaderScanner.scan_data_headers(df_sp)
        skip_codes = pending_info_codes(df_sp, col_map_sp)

        price_map = {}
        for r in range(2, len(df_sp)):
            row = df_sp.iloc[r]
            pcode = str(row[col_map_sp.get('product_code', 0)] or '').strip()
            raw_price = row[col_map_sp.get('product_price', 0)]
            pprice = parse_number(raw_price)
            sizes = unroll_sizes(row[col_map_sp.get('Size', 0)])
            if sizes:
                for sz in sizes:
                    price_map[f"{pcode}{sz}"] = pprice
            price_map[pcode] = pprice

        # CHẾ ĐỘ 2: XUẤT FULL TOÀN BỘ TỒN KHO TỪ KHO15E & KHOY3C
        if web_mode == "2":
            exported_files = []
            kho_configs = [
                ('15E', 'KHO15E'),
                ('Y3C', 'KHOY3C')
            ]

            total_exported_sku = 0
            skipped_full = set()
            for kho_code, sheet_k in kho_configs:
                df_k, _ = loader.load_sheet(sheet_k)
                _, col_map_k = DynamicHeaderScanner.scan_data_headers(df_k)

                p_col = col_map_k.get('product_code', 1)
                s_col = col_map_k.get('item_size', 3)
                q_col = col_map_k.get('current_quantity', 5)

                out_rows = []
                for i in range(1, len(df_k)):
                    row = df_k.iloc[i]
                    pcode = str(row[p_col] or '').strip()
                    sz = str(row[s_col] or '').strip()
                    if sz.endswith('.0'): sz = sz[:-2]

                    if not pcode:
                        continue
                    if pcode.upper() in skip_codes:
                        skipped_full.add(pcode.upper())
                        continue

                    try:
                        qty_val = float(row[q_col] or 0)
                        qty = max(0, int(round(qty_val)))
                    except Exception:
                        qty = 0

                    barcode = f"{pcode}{sz}" if sz else pcode
                    price = price_map.get(barcode, price_map.get(pcode, ''))

                    out_rows.append({
                        'product_code': pcode,
                        'item_size': sz,
                        'item_quantity': qty,
                        'item_price': price,
                        'item_barcode': barcode
                    })

                out_df = pd.DataFrame(out_rows)
                out_file = os.path.join(EXPORT_DIR, f"WEB_STOCK_{kho_code}_FULL_{timestamp_file}.csv")
                out_df.to_csv(out_file, sep='\t', index=False)
                exported_files.append(out_file)
                total_exported_sku += len(out_rows)

            if skipped_full:
                print(f"⏭️ Bỏ qua {len(skipped_full)} mã chưa bổ sung (trống ngành / giá bán): {', '.join(sorted(skipped_full)[:10])}{' …' if len(skipped_full) > 10 else ''}")
            exported_filepath = "\n📁 ".join(exported_files)
            success_msg = f"\n✅ Đã xuất FULL toàn bộ {total_exported_sku} SKU tồn kho Website thành công!\n📁 {exported_filepath}\n"
            if HAS_RICH:
                console.print(Panel(success_msg, title="[bold green]XUẤT FULL TỒN KHO WEBSITE THÀNH CÔNG[/bold green]", border_style="green"))
            else:
                print(success_msg)
            return

        # CHẾ ĐỘ 1: XUẤT THEO PHIẾU NHẬP MỚI TỪ TAB NHAP
        df_nhap, _ = loader.load_sheet('NHAP')
        _, col_map_nhap = DynamicHeaderScanner.scan_data_headers(df_nhap)

        status_col_idx = col_map_nhap.get('web_stock', None)
        pcode_col_idx = col_map_nhap.get('product_code', None)
        pending_row_indices = []
        pending_records = []

        for r in range(2, len(df_nhap)):
            row_data = df_nhap.iloc[r]
            pcode_val = str(row_data[pcode_col_idx]).strip() if (pcode_col_idx is not None and pd.notna(row_data[pcode_col_idx])) else ""
            if not pcode_val:
                continue

            st_val = str(row_data[status_col_idx]).strip() if (status_col_idx is not None and pd.notna(row_data[status_col_idx])) else ""
            if not st_val:
                pending_row_indices.append(r)
                rec = {}
                for k, idx in col_map_nhap.items():
                    rec[k] = row_data[idx] if idx < len(row_data) else ""
                pending_records.append(rec)

        pending_records, pending_row_indices = drop_pending_info(pending_records, pending_row_indices, skip_codes)
        if not pending_records:
            msg = "ℹ️ Không có dòng nào mới cần xuất Website Stock (Tất cả đã 'Done')."
            if HAS_RICH: console.print(Panel(msg, border_style="yellow"))
            else: print(msg)
            return

        records_by_kho = {}
        for rec in pending_records:
            kho_raw = str(rec.get('KHO', '')).strip().upper()
            if kho_raw in ['15E', '15ETBH']:
                kho_key = '15E'
            elif kho_raw in ['Y3C', '3C', '3CTBH']:
                kho_key = 'Y3C'
            else:
                kho_key = kho_raw if kho_raw else 'KHAC'

            if kho_key not in records_by_kho:
                records_by_kho[kho_key] = []
            records_by_kho[kho_key].append(rec)

        exported_files = []
        for kho_name, k_records in records_by_kho.items():
            out_rows = []
            for rec in k_records:
                pcode = str(rec.get('product_code', '')).strip()
                sz = str(rec.get('item_size', '')).strip()
                if sz.endswith('.0'): sz = sz[:-2]
                barcode = f"{pcode}{sz}" if sz else pcode
                qty = rec.get('item_quantity', 0)
                price = price_map.get(barcode, price_map.get(pcode, rec.get('Giá', '')))

                out_rows.append({
                    'product_code': pcode,
                    'item_size': sz,
                    'item_quantity': qty,
                    'item_price': price,
                    'item_barcode': barcode
                })

            out_df = pd.DataFrame(out_rows)
            out_file = os.path.join(EXPORT_DIR, f"WEB_STOCK_{kho_name}_{timestamp_file}.csv")
            out_df.to_csv(out_file, sep='\t', index=False)
            exported_files.append(out_file)

        status_text = f"Done - {now_str}"
        loader.update_status('NHAP', pending_row_indices, status_col_idx, status_text)

        exported_filepath = "\n📁 ".join(exported_files)
        success_msg = f"\n✅ Đã xuất thành công {len(pending_records)} dòng nhập kho Website vào các file:\n📁 {exported_filepath}\n📝 Đã cập nhật trạng thái '{status_text}' vào cột 'web_stock' trên tab NHAP!\n"
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]XUẤT NHẬP KHO WEBSITE THÀNH CÔNG[/bold green]", border_style="green"))
        else:
            print(success_msg)
        return

    # ==================== TASK 6: SHOPEE UPDATE PRICE/STOCK ====================
    if choice == 6:
        opt_text = """-------------------------------------------------------------------
         🛒 CHỌN CHẾ ĐỘ XUẤT FILE SHOPEE CẬP NHẬT
-------------------------------------------------------------------
  [1] 📦 Chỉ Cập Nhật Số Lượng Tồn Kho (Kho 15E + Kho Y3C, Tồn >= 0)
  [2] 🏷️ Chỉ Cập Nhật Giá Bán (product_price * Shopee Price %)
  [3] ⚡ Cập Nhật Cả Hai (Giá Bán & Tồn Kho Realtime)
  -----------------------------------------------------------------
  [0] ↩️ Quay lại
-------------------------------------------------------------------"""
        if HAS_RICH:
            console.print(Panel(opt_text, border_style="yellow"))
            update_mode = Prompt.ask("[bold yellow]Mời chọn chế độ cập nhật Shopee [1-3][/bold yellow]", default="3")
        else:
            print(opt_text)
            update_mode = input("Mời chọn chế độ cập nhật Shopee [1-3]: ").strip()

        if update_mode not in ["1", "2", "3"]:
            print("Đã hủy tác vụ cập nhật Shopee.")
            return

        tpl_file = os.path.join(TEMPLATES_DIR, "tpl_shopee_update.xlsx")
        if not os.path.exists(tpl_file):
            msg = f"❌ Không tìm thấy file template Shopee Update tại: {tpl_file}"
            if HAS_RICH: console.print(f"[bold red]{msg}[/bold red]")
            else: print(msg)
            return

        wb = openpyxl.load_workbook(tpl_file)
        ws_tpl = wb['Sheet1']

        # 1. Tải bản đồ Tồn kho Realtime (Kho 15E + Kho Y3C)
        stock_15e, stock_y3c, stock_total = get_stock_maps(loader)

        # 2. Tải bản đồ Giá bán Shopee từ SANPHAM & SUB
        sub_dict = get_sub_info(loader)
        df_sp, _ = loader.load_sheet('SANPHAM')
        _, col_map_sp = DynamicHeaderScanner.scan_data_headers(df_sp)

        price_map = {}
        for r in range(2, len(df_sp)):
            row = df_sp.iloc[r]
            pcode = str(row[col_map_sp.get('product_code', 0)] or '').strip()
            raw_price = row[col_map_sp.get('product_price', 0)]
            pprice = parse_number(raw_price)
            cat_b = str(row[col_map_sp.get('Tên nhóm hàng hóa')] if col_map_sp.get('Tên nhóm hàng hóa') is not None else row[col_map_sp.get('Tên Ngành Hàng', 1)]).strip()
            sub_info = sub_dict.get(cat_b.lower()) or sub_dict.get(cat_b, {})
            shopee_rate = sub_info.get('Shopee Price %', '100%')
            mult = parse_price_multiplier(shopee_rate)
            shopee_price = int(round(pprice * mult))

            sizes = unroll_sizes(row[col_map_sp.get('Size', 0)])
            if sizes:
                for sz in sizes:
                    sku = f"{pcode}{sz}"
                    price_map[sku] = shopee_price
            price_map[pcode] = shopee_price

        updated_rows_count = 0
        updated_stock_count = 0
        updated_price_count = 0

        for r in range(7, ws_tpl.max_row + 1):
            sku = str(ws_tpl.cell(row=r, column=6).value or '').strip()
            parent_sku = str(ws_tpl.cell(row=r, column=5).value or '').strip()

            if not sku and not parent_sku:
                continue

            # Cập nhật Số lượng (Tồn kho >= 0)
            if update_mode in ["1", "3"]:
                raw_stk = stock_total.get(sku, stock_total.get(parent_sku, 0))
                stk = max(0, int(raw_stk))
                safe_write_cell(ws_tpl, r, 9, stk)
                updated_stock_count += 1

            # Cập nhật Giá
            if update_mode in ["2", "3"]:
                new_price = price_map.get(sku) or price_map.get(parent_sku)
                if new_price and new_price > 0:
                    safe_write_cell(ws_tpl, r, 7, new_price)
                    updated_price_count += 1

            updated_rows_count += 1

        mode_name_map = {
            "1": "STOCK_ONLY",
            "2": "PRICE_ONLY",
            "3": "FULL"
        }
        mode_label = mode_name_map.get(update_mode, "UPDATE")
        try:
            link_result = export_channel_links('shopee', ws_tpl, sanpham_codes(df_sp, col_map_sp))
            if link_result:
                print(f"🔗 {CHANNEL_LINKS_FILE}: {link_result[0]} mã Shopee (bỏ qua {link_result[1]} SKU không khớp mã SANPHAM)")
        except Exception as e:
            print(f"[!] Lỗi khi ghi {CHANNEL_LINKS_FILE} (file Shopee vẫn xuất bình thường): {e}")
        exported_filepath = os.path.join(EXPORT_DIR, f"SHOPEE_UPDATE_{mode_label}_{timestamp_file}.xlsx")
        wb.save(exported_filepath)
        if updated_stock_count > 0:
            loader.mark_platform_update('shopee')
        else:
            print("ℹ️ Không ghi mốc shopee_last_update: file này không cập nhật tồn kho (chế độ chỉ giá).")
        wb.close()

        mode_desc = {
            "1": f"📦 Chỉ Cập Nhật Tồn Kho (Đã đồng bộ {updated_stock_count} SKU, Tồn >= 0)",
            "2": f"🏷️ Chỉ Cập Nhật Giá Bán (Đã đồng bộ {updated_price_count} SKU)",
            "3": f"⚡ Cập Nhật Toàn Diện (Tồn kho: {updated_stock_count} SKU, Giá bán: {updated_price_count} SKU)"
        }

        success_msg = f"\n✅ Đã đồng bộ hoàn tất {updated_rows_count} dòng sản phẩm trên Shopee!\n🎯 Chế độ: {mode_desc.get(update_mode)}\n📁 {exported_filepath}\n"
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]XUẤT FILE SHOPEE UPDATE THÀNH CÔNG[/bold green]", border_style="green"))
        else:
            print(success_msg)
        return

    # ==================== TASK 7: TIKTOK UPDATE PRICE/STOCK ====================
    if choice == 7:
        opt_text = """-------------------------------------------------------------------
         🎵 CHỌN CHẾ ĐỘ XUẤT FILE TIKTOK CẬP NHẬT
-------------------------------------------------------------------
  [1] 📦 Chỉ Cập Nhật Số Lượng Tồn Kho (Kho 15E + Y3C, Tồn >= 0)
  [2] 🏷️ Chỉ Cập Nhật Giá Bán (product_price * Tiktok Price %)
  [3] ⚡ Cập Nhật TẤT CẢ Dữ Liệu (Tên, Mô Tả, Giá, Ảnh, Size Chart, Thuộc Tính, Tồn Kho)
  -----------------------------------------------------------------
  [0] ↩️ Quay lại
-------------------------------------------------------------------"""
        if HAS_RICH:
            console.print(Panel(opt_text, border_style="cyan"))
            update_mode = Prompt.ask("[bold cyan]Mời chọn chế độ cập nhật TikTok [1/2/3][/bold cyan]", choices=["0", "1", "2", "3"], default="3")
        else:
            print(opt_text)
            update_mode = input("Mời chọn chế độ cập nhật TikTok [1/2/3]: ").strip()

        if update_mode not in ["1", "2", "3"]:
            print("Đã hủy tác vụ cập nhật TikTok.")
            return

        tpl_file = os.path.join(TEMPLATES_DIR, "tpl_tiktok_update.xlsx")
        if not os.path.exists(tpl_file):
            msg = f"❌ Không tìm thấy file template TikTok Update tại: {tpl_file}"
            if HAS_RICH: console.print(f"[bold red]{msg}[/bold red]")
            else: print(msg)
            return

        wb = openpyxl.load_workbook(tpl_file)
        ws_tpl = wb['Template'] if 'Template' in wb.sheetnames else wb.active

        # 1. Tải bản đồ Tồn kho Realtime
        stock_15e, stock_y3c, stock_total = get_stock_maps(loader)

        # 2. Tải toàn bộ bản đồ Sản phẩm & Danh mục từ SANPHAM & SUB
        sub_dict = get_sub_info(loader)
        df_sp, _ = loader.load_sheet('SANPHAM')
        _, col_map_sp = DynamicHeaderScanner.scan_data_headers(df_sp)

        prod_full_map = {}
        for r in range(2, len(df_sp)):
            row = df_sp.iloc[r]
            pcode = str(row[col_map_sp.get('product_code', 0)] or '').strip()
            pname = str(row[col_map_sp.get('CON_NAME')] if col_map_sp.get('CON_NAME') is not None else row[col_map_sp.get('product_name', 0)] or '').strip()
            pdesc = str(row[col_map_sp.get('CON_DES')] if col_map_sp.get('CON_DES') is not None else row[col_map_sp.get('product_description', 0)] or '').strip()
            raw_price = row[col_map_sp.get('product_price', 0)]
            pprice = parse_number(raw_price)
            pcolor = str(row[col_map_sp.get('product_color', 0)] or '').strip()
            cat_b = str(row[col_map_sp.get('Tên nhóm hàng hóa')] if col_map_sp.get('Tên nhóm hàng hóa') is not None else row[col_map_sp.get('Tên Ngành Hàng', 1)]).strip()
            sub_info = sub_dict.get(cat_b.lower()) or sub_dict.get(cat_b, {})
            tiktok_cat = str(sub_info.get('Tiktok', '')).strip()
            tiktok_size_url = str(sub_info.get('Tiktok Size', '')).strip()
            tiktok_rate = sub_info.get('Tiktok Price %', '100%')
            mult = parse_price_multiplier(tiktok_rate)
            tiktok_price = int(round(pprice * mult))
            weight = sub_info.get('Cân nặng', 1500)
            length = sub_info.get('Chiều dài', 32)
            width = sub_info.get('Chiều rộng', 20)
            height = sub_info.get('Chiều cao', 12)
            attrs = map_tiktok_attributes(sub_info, {k: row[i] for k, i in col_map_sp.items()})

            sheet_pics = [row[col_map_sp['image_0' + str(n)]] if col_map_sp.get('image_0' + str(n)) is not None else '' for n in range(1, 10)]
            if col_map_sp.get('image_01') is None and col_map_sp.get('Pic 1') is not None:
                sheet_pics[0] = row[col_map_sp['Pic 1']]
            # Ảnh lấy lúc ghi (chỉ mã có trong file mẫu, chế độ 3) — không dò web cho mọi dòng SANPHAM
            data_obj = {
                'pcode': pcode,
                'pname': pname,
                'pdesc': pdesc,
                'pprice': tiktok_price,
                'pcolor': pcolor,
                'tiktok_cat': tiktok_cat,
                'tiktok_size_url': tiktok_size_url,
                'weight': weight,
                'length': length,
                'width': width,
                'height': height,
                'sheet_pics': sheet_pics,
                'attrs': attrs
            }
            prod_full_map[pcode.lower()] = data_obj
            sizes = unroll_sizes(row[col_map_sp.get('Size', 0)])
            if sizes:
                for sz in sizes:
                    prod_full_map[f"{pcode}{sz}".lower()] = data_obj

        # Quét động các cột trong tpl_tiktok_update.xlsx từ Dòng 1
        key_col_map = {}
        for c in range(1, ws_tpl.max_column + 1):
            k = str(ws_tpl.cell(row=1, column=c).value or '').strip()
            if k:
                key_col_map[k] = c

        cat_col = key_col_map.get('category')
        name_col = key_col_map.get('product_name')
        desc_col = key_col_map.get('product_description')
        brand_col = key_col_map.get('brand')
        price_col = key_col_map.get('price')
        qty_col = key_col_map.get('quantity') or key_col_map.get('stock')
        if not qty_col:
            # Mẫu Kho hàng (Inventory) của TikTok có thể đặt tên cột tồn khác (vd quantity/<kho>, warehouse_quantity…)
            qty_col = next((c for k, c in key_col_map.items()
                            if k.lower().startswith(('quantity', 'stock', 'warehouse_quantity'))), None)
        sku_col = key_col_map.get('seller_sku', 10 if ws_tpl.max_column >= 10 else 7)
        var_col = key_col_map.get('variation_value', 6 if ws_tpl.max_column >= 9 else 5)
        weight_col = key_col_map.get('parcel_weight')
        len_col = key_col_map.get('parcel_length')
        wid_col = key_col_map.get('parcel_width')
        hei_col = key_col_map.get('parcel_height')
        cod_col = key_col_map.get('cod')
        pic1_col = key_col_map.get('main_image')
        pic2_col = key_col_map.get('image_2')
        pic3_col = key_col_map.get('image_3')
        pic4_col = key_col_map.get('image_4')
        pic5_col = key_col_map.get('image_5')
        pic6_col = key_col_map.get('image_6')
        pic7_col = key_col_map.get('image_7')
        pic8_col = key_col_map.get('image_8')
        pic9_col = key_col_map.get('image_9')
        size_chart_col = key_col_map.get('size_chart')

        org_name_col = key_col_map.get('product_property/101489')
        org_addr_col = key_col_map.get('product_property/101490')
        origin_col = key_col_map.get('product_property/100149')
        mat_col = key_col_map.get('product_property/100157')
        occ_col = key_col_map.get('product_property/100392')
        season_col = key_col_map.get('product_property/100397')
        toe_col = key_col_map.get('product_property/100419')
        heel_col = key_col_map.get('product_property/100421')
        closure_col = key_col_map.get('product_property/100422')
        heel_type_col = key_col_map.get('product_property/100423')

        # Cảnh báo thông minh nếu chọn chế độ nhưng template thiếu cột tương ứng
        if update_mode == "1" and not qty_col:
            warn_t = "⚠️ Mẫu TikTok hiện tại KHÔNG có cột tồn kho ('quantity') → file này KHÔNG cập nhật tồn, và KHÔNG ghi mốc tiktok_last_update. Hãy thay HNC_Templates/tpl_tiktok_update.xlsx bằng mẫu có cột Tồn kho."
            if HAS_RICH: console.print(f"[bold yellow]{warn_t}[/bold yellow]")
            else: print(warn_t)

        if update_mode == "2" and not price_col:
            warn_t = "⚠️ Template hiện tại không có cột giá bán ('price')."
            if HAS_RICH: console.print(f"[bold yellow]{warn_t}[/bold yellow]")
            else: print(warn_t)

        updated_rows_count = 0
        updated_price_count = 0
        updated_stock_count = 0

        for r in range(6, ws_tpl.max_row + 1):
            seller_sku = str(ws_tpl.cell(row=r, column=sku_col).value or '').strip()
            var_val = str(ws_tpl.cell(row=r, column=var_col).value or '').strip()

            if not seller_sku and not var_val:
                continue

            sz = var_val.split(',')[-1].strip() if ',' in var_val else var_val
            full_sku = f"{seller_sku}{sz}"

            pdata = prod_full_map.get(full_sku.lower()) or prod_full_map.get(seller_sku.lower())
            attrs = pdata['attrs'] if pdata else map_tiktok_attributes(list(sub_dict.values())[0] if sub_dict else {})

            # [1] Cập nhật Tồn kho (Tồn >= 0)
            if update_mode in ["1", "3"] and qty_col:
                raw_stk = stock_total.get(full_sku, stock_total.get(seller_sku, 0))
                stk = max(0, int(raw_stk))
                safe_write_cell(ws_tpl, r, qty_col, stk)
                updated_stock_count += 1

            # [2] Cập nhật Giá mới
            if update_mode in ["2", "3"] and price_col:
                new_price = pdata['pprice'] if pdata else None
                if new_price and new_price > 0:
                    safe_write_cell(ws_tpl, r, price_col, new_price)
                    updated_price_count += 1

            # [3] Cập nhật TẤT CẢ Dữ Liệu Sản Phẩm
            if update_mode == "3" and pdata:
                if cat_col and pdata['tiktok_cat']: safe_write_cell(ws_tpl, r, cat_col, pdata['tiktok_cat'])
                if name_col and pdata['pname']: safe_write_cell(ws_tpl, r, name_col, pdata['pname'])
                if desc_col and pdata['pdesc']: safe_write_cell(ws_tpl, r, desc_col, pdata['pdesc'])
                if brand_col: safe_write_cell(ws_tpl, r, brand_col, "Hải Nancy (7208750233873008390)")
                if weight_col: safe_write_cell(ws_tpl, r, weight_col, pdata['weight'])
                if len_col: safe_write_cell(ws_tpl, r, len_col, pdata['length'])
                if wid_col: safe_write_cell(ws_tpl, r, wid_col, pdata['width'])
                if hei_col: safe_write_cell(ws_tpl, r, hei_col, pdata['height'])
                if cod_col: safe_write_cell(ws_tpl, r, cod_col, "Y")
                if 'pics' not in pdata:
                    pdata['pics'] = sale_images(pdata['pcode'], pdata['sheet_pics'])  # ảnh web mới, thiếu thì ảnh cũ trong Sheet
                for p_col, p_url in zip([pic1_col, pic2_col, pic3_col, pic4_col, pic5_col, pic6_col, pic7_col, pic8_col, pic9_col], pdata['pics']):
                    if p_col and p_url: safe_write_cell(ws_tpl, r, p_col, p_url)
                if size_chart_col and pdata['tiktok_size_url']: safe_write_cell(ws_tpl, r, size_chart_col, pdata['tiktok_size_url'])

            # Điền đầy đủ thuộc tính cho chế độ 2 & 3
            if update_mode in ["2", "3"]:
                if org_name_col: safe_write_cell(ws_tpl, r, org_name_col, attrs['org_name'])
                if org_addr_col: safe_write_cell(ws_tpl, r, org_addr_col, attrs['org_addr'])
                if origin_col: safe_write_cell(ws_tpl, r, origin_col, attrs['origin'])
                if mat_col: safe_write_cell(ws_tpl, r, mat_col, attrs['material'])
                if occ_col: safe_write_cell(ws_tpl, r, occ_col, attrs['occasion'])
                if season_col: safe_write_cell(ws_tpl, r, season_col, attrs['season'])
                if toe_col: safe_write_cell(ws_tpl, r, toe_col, attrs['toe_shape'])
                if heel_col: safe_write_cell(ws_tpl, r, heel_col, attrs['heel_height'])
                if closure_col: safe_write_cell(ws_tpl, r, closure_col, attrs['closure'])
                if heel_type_col: safe_write_cell(ws_tpl, r, heel_type_col, attrs['heel_type'])

            updated_rows_count += 1

        mode_name_map = {
            "1": "STOCK_ONLY",
            "2": "PRICE_ONLY",
            "3": "FULL_ALL_INFO"
        }
        mode_label = mode_name_map.get(update_mode, "UPDATE")
        try:
            link_result = export_channel_links('tiktok', ws_tpl, sanpham_codes(df_sp, col_map_sp))
            if link_result:
                print(f"🔗 {CHANNEL_LINKS_FILE}: {link_result[0]} mã TikTok (bỏ qua {link_result[1]} SKU không khớp mã SANPHAM)")
        except Exception as e:
            print(f"[!] Lỗi khi ghi {CHANNEL_LINKS_FILE} (file TikTok vẫn xuất bình thường): {e}")
        exported_filepath = os.path.join(EXPORT_DIR, f"TIKTOK_UPDATE_{mode_label}_{timestamp_file}.xlsx")
        wb.save(exported_filepath)
        if updated_stock_count > 0:
            loader.mark_platform_update('tiktok')
        else:
            print("ℹ️ Không ghi mốc tiktok_last_update: file này không cập nhật tồn kho (mẫu không có cột tồn hoặc chế độ chỉ giá).")
        wb.close()

        mode_desc = {
            "1": f"📦 Chỉ Cập Nhật Tồn Kho (Đã đồng bộ {updated_stock_count} SKU, Tồn >= 0)",
            "2": f"🏷️ Chỉ Cập Nhật Giá Bán (Đã đồng bộ {updated_price_count} SKU)",
            "3": f"⚡ Cập Nhật TẤT CẢ Dữ Liệu Sản Phẩm (Tên, Mô tả, Giá 140%, Ảnh 1-9, Size chart, Thuộc tính, Tồn kho: {updated_rows_count} SKU)"
        }

        success_msg = f"\n✅ Đã đồng bộ hoàn tất {updated_rows_count} dòng sản phẩm trên TikTok Shop!\n🎯 Chế độ: {mode_desc.get(update_mode)}\n📁 {exported_filepath}\n"
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]XUẤT FILE TIKTOK UPDATE THÀNH CÔNG[/bold green]", border_style="green"))
        else:
            print(success_msg)
        return

    # Tasks standard processing
    possible_status_cols = STATUS_COLUMNS.get(choice, [])
    sheet_name = 'SANPHAM' if choice in [1, 2, 3, 4] else 'NHAP'

    df_raw, _ = loader.load_sheet(sheet_name)
    var_row_idx, col_map = DynamicHeaderScanner.scan_data_headers(df_raw)

    status_col_name = None
    status_col_idx = None

    for candidate in possible_status_cols:
        if candidate in col_map:
            status_col_name = candidate
            status_col_idx = col_map[candidate]
            break

    if status_col_idx is None:
        msg = f"❌ Không tìm thấy cột trạng thái {possible_status_cols} trong tab {sheet_name}!"
        if HAS_RICH: console.print(f"[bold red]{msg}[/bold red]")
        else: print(msg)
        return

    data_start_row = (var_row_idx + 1) if var_row_idx is not None else 2

    pending_row_indices = []
    pending_records = []

    pcode_idx = col_map.get('product_code')
    fsku_idx = col_map.get('FSKU')
    kho_idx = col_map.get('KHO')

    for rel_idx in range(data_start_row, len(df_raw)):
        row = df_raw.iloc[rel_idx]

        pcode_val = str(row[pcode_idx]).strip() if (pcode_idx is not None and pd.notna(row[pcode_idx])) else ""
        fsku_val = str(row[fsku_idx]).strip() if (fsku_idx is not None and pd.notna(row[fsku_idx])) else ""

        if not pcode_val and not fsku_val:
            continue

        status_val = str(row[status_col_idx]).strip() if pd.notna(row[status_col_idx]) else ""
        if not status_val:
            pending_row_indices.append(rel_idx)
            rec = {}
            for var_name, c_idx in col_map.items():
                rec[var_name] = row[c_idx] if pd.notna(row[c_idx]) else ""
            pending_records.append(rec)

    if choice in PENDING_INFO_SKIP_TASKS:
        if sheet_name == 'SANPHAM':
            skip_codes = pending_info_codes(df_raw, col_map, data_start_row)
        else:
            df_sp_chk, _ = loader.load_sheet('SANPHAM')
            sp_hdr_idx, col_map_sp_chk = DynamicHeaderScanner.scan_data_headers(df_sp_chk)
            skip_codes = pending_info_codes(df_sp_chk, col_map_sp_chk, (sp_hdr_idx + 1) if sp_hdr_idx is not None else 2)
        pending_records, pending_row_indices = drop_pending_info(pending_records, pending_row_indices, skip_codes)

    if not pending_records and choice != 10:  # in tem: vẫn cho in lại theo phiếu / ngày
        msg = f"✨ Tất cả các bản ghi trong tab {sheet_name} đều đã hoàn thành (Done) cho tác vụ [{choice}]!"
        if HAS_RICH: console.print(f"[bold yellow]{msg}[/bold yellow]")
        else: print(msg)
        return

    stock_15e, stock_y3c, stock_total = get_stock_maps(loader)
    sub_dict = get_sub_info(loader)
    exported_filepath = ""

    # ==================== TASK 1: WEBSITE PRODUCT IMPORT ====================
    if choice == 1:
        out_rows = []
        for rec in pending_records:
            pcode = str(rec.get('product_code', '')).strip()
            pname = str(rec.get('product_name') or rec.get('CON_NAME') or '').strip()
            raw_price = rec.get('product_price', 0)
            pprice = int(round(parse_number(raw_price)))
            punit = str(rec.get('product_unit') or 'Đôi').strip()
            porigin = str(rec.get('product_origin') or 'Việt Nam').strip()
            pcolor = str(rec.get('product_color') or '').strip()
            pcat = str(rec.get('product_category_id') or '').strip()
            pdesc = str(rec.get('product_description') or rec.get('CON_DES') or '').strip()
            pbonus = str(rec.get('Bonus:') or rec.get('product_feature') or '').strip()

            out_rows.append({
                'product_code': pcode,
                'product_name': pname,
                'product_price': pprice,
                'product_unit': punit,
                'product_origin': porigin,
                'product_color': pcolor,
                'product_category_id': pcat,
                'product_description': pdesc,
                'product_feature': pbonus
            })

        out_df = pd.DataFrame(out_rows)
        exported_filepath = os.path.join(EXPORT_DIR, f"WEB_PRODUCTS_{timestamp_file}.csv")
        out_df.to_csv(exported_filepath, sep='\t', index=False)

    # ==================== TASK 2: SHOPEE UPLOAD MỚI ====================
    elif choice == 2:
        tpl_file = os.path.join(TEMPLATES_DIR, "tpl_shopee_upload.xlsx")
        wb = openpyxl.load_workbook(tpl_file)
        ws_tpl = wb['Bản đăng tải']

        # Xóa các dòng dữ liệu cũ từ dòng 7 (nếu có)
        if ws_tpl.max_row >= 7:
            ws_tpl.delete_rows(7, ws_tpl.max_row - 6)

        row_status_list = []
        warning_rows = []
        valid_records = []

        for rel_idx, rec in zip(pending_row_indices, pending_records):
            parent_code = str(rec.get('Mã hàng hóa cha') or rec.get('parent_product_code', '')).strip()
            pcode = str(rec.get('product_code', '')).strip()
            pname = str(rec.get('CON_NAME') or rec.get('product_name', '')).strip()
            pdesc = str(rec.get('CON_DES') or rec.get('product_description', '')).strip()
            raw_price = rec.get('product_price', 0)
            pprice = parse_number(raw_price)
            pcolor = str(rec.get('product_color', '')).strip()
            cat_b = str(rec.get('Tên nhóm hàng hóa') or rec.get('Tên Ngành Hàng') or rec.get('Loại sản phẩm', '')).strip()

            sub_info = sub_dict.get(cat_b.lower()) or sub_dict.get(cat_b, {})
            shopee_cat = str(sub_info.get('Shopee', '')).strip()
            shopee_size_tpl = str(sub_info.get('Shopee Size', '')).strip()
            shopee_multiplier = parse_price_multiplier(sub_info.get('Shopee Price %', '100%'))
            shopee_price = int(round(pprice * shopee_multiplier))

            weight = sub_info.get('Cân nặng', 1500)
            length = sub_info.get('Chiều dài', 32)
            width = sub_info.get('Chiều rộng', 20)
            height = sub_info.get('Chiều cao', 12)

            pic1, pic2, pic3, pic4, pic5, pic6, pic7, pic8, pic9 = sale_images(pcode, [rec.get('image_01') or rec.get('Pic 1', '')] +
                [rec.get(f'image_0{n}', '') for n in range(2, 10)])  # ảnh web mới, thiếu thì ảnh cũ trong Sheet

            # Lấy dải Size chuẩn từ cột Size (đã bao gồm đầy đủ dải size và size plus)
            all_sizes = unroll_sizes(rec.get('Size', ''))

            # KIỂM TRA TÍNH TOÀN VẸN DỮ LIỆU (STRICT QA GATE)
            missing_reasons = []
            if not parent_code:
                missing_reasons.append("Thiếu mã cha")
            if not pcode:
                missing_reasons.append("Thiếu mã SP")
            if not pname:
                missing_reasons.append("Thiếu tên")
            if pprice <= 0:
                missing_reasons.append("Thiếu giá")
            if not shopee_cat:
                missing_reasons.append("Thiếu ngành hàng Shopee")
            if not pic1:
                missing_reasons.append("Thiếu ảnh")

            if missing_reasons:
                reason_str = ", ".join(missing_reasons)
                row_status_list.append(reason_str)
                warning_rows.append(f"⚠️ Dòng {rel_idx + 1}: Mã '{pcode}' [bold red]{reason_str.upper()}[/bold red]! Đã bỏ qua.")
                continue

            row_status_list.append(f"Done - {now_str}")
            valid_records.append({
                'parent_code': parent_code,
                'pcode': pcode,
                'pname': pname,
                'pdesc': pdesc,
                'pprice': shopee_price,
                'pcolor': pcolor,
                'shopee_cat': shopee_cat,
                'shopee_size_tpl': shopee_size_tpl,
                'weight': weight,
                'length': length,
                'width': width,
                'height': height,
                'pic1': pic1,
                'pic2': pic2,
                'pic3': pic3,
                'pic4': pic4,
                'pic5': pic5,
                'pic6': pic6,
                'pic7': pic7,
                'pic8': pic8,
                'pic9': pic9,
                'all_sizes': all_sizes
            })

        if warning_rows:
            warn_msg = "\n".join(warning_rows)
            if HAS_RICH:
                console.print(Panel(warn_msg, title="[bold yellow]CẢNH BÁO DỮ LIỆU SHOPEE UPLOAD[/bold yellow]", border_style="yellow"))
            else:
                print(f"\n--- CẢNH BÁO ---\n{warn_msg}\n")

        row_num = 7
        for vrec in valid_records:
            if vrec['all_sizes']:
                for sz in vrec['all_sizes']:
                    sku = f"{vrec['pcode']}{sz}"
                    stk = int(stock_total.get(sku, 0))

                    safe_write_cell(ws_tpl, row_num, 1, vrec['shopee_cat'])       # Col A (1): Ngành hàng
                    safe_write_cell(ws_tpl, row_num, 2, vrec['pname'])            # Col B (2): Tên sản phẩm
                    safe_write_cell(ws_tpl, row_num, 3, vrec['pdesc'])            # Col C (3): Mô tả sản phẩm
                    safe_write_cell(ws_tpl, row_num, 4, vrec['parent_code'])      # Col D (4): SKU sản phẩm (Mã cha)
                    safe_write_cell(ws_tpl, row_num, 5, vrec['pcode'])            # Col E (5): Mã sản phẩm (Mã biến thể màu)
                    safe_write_cell(ws_tpl, row_num, 6, "Màu sắc")                # Col F (6): Tên nhóm phân loại 1
                    safe_write_cell(ws_tpl, row_num, 7, vrec['pcolor'])           # Col G (7): Tên phân loại 1 (Màu)
                    safe_write_cell(ws_tpl, row_num, 8, vrec['pic1'])             # Col H (8): Hình ảnh mỗi phân loại
                    safe_write_cell(ws_tpl, row_num, 9, "Kích thước")             # Col I (9): Tên nhóm phân loại 2
                    safe_write_cell(ws_tpl, row_num, 10, sz)                      # Col J (10): Tên phân loại 2 (Size)
                    safe_write_cell(ws_tpl, row_num, 11, vrec['pprice'])          # Col K (11): Giá đã nhân % Shopee
                    safe_write_cell(ws_tpl, row_num, 12, stk)                     # Col L (12): Kho hàng
                    safe_write_cell(ws_tpl, row_num, 13, sku)                     # Col M (13): SKU phân loại
                    safe_write_cell(ws_tpl, row_num, 14, vrec['shopee_size_tpl']) # Col N (14): Size Chart Template
                    safe_write_cell(ws_tpl, row_num, 17, vrec['pic1'])            # Col Q (17): Ảnh bìa
                    safe_write_cell(ws_tpl, row_num, 18, vrec['pic2'])            # Col R (18): Ảnh 1
                    safe_write_cell(ws_tpl, row_num, 19, vrec['pic3'])            # Col S (19): Ảnh 2
                    safe_write_cell(ws_tpl, row_num, 20, vrec['pic4'])            # Col T (20): Ảnh 3
                    safe_write_cell(ws_tpl, row_num, 21, vrec['pic5'])            # Col U (21): Ảnh 4
                    safe_write_cell(ws_tpl, row_num, 22, vrec['pic6'])            # Col V (22): Ảnh 5
                    safe_write_cell(ws_tpl, row_num, 23, vrec['pic7'])            # Col W (23): Ảnh 6
                    safe_write_cell(ws_tpl, row_num, 24, vrec['pic8'])            # Col X (24): Ảnh 7
                    safe_write_cell(ws_tpl, row_num, 25, vrec['pic9'])            # Col Y (25): Ảnh 8
                    safe_write_cell(ws_tpl, row_num, 26, vrec['weight'])          # Col Z (26): Cân nặng (gram)
                    safe_write_cell(ws_tpl, row_num, 27, vrec['length'])          # Col AA (27): Chiều dài
                    safe_write_cell(ws_tpl, row_num, 28, vrec['width'])           # Col AB (28): Chiều rộng
                    safe_write_cell(ws_tpl, row_num, 29, vrec['height'])          # Col AC (29): Chiều cao
                    safe_write_cell(ws_tpl, row_num, 30, "Tắt")                   # Col AD (30): Hỏa Tốc
                    safe_write_cell(ws_tpl, row_num, 31, "Bật")                   # Col AE (31): Nhanh
                    safe_write_cell(ws_tpl, row_num, 32, "Tắt")                   # Col AF (32): Hàng Cồng Kềnh
                    row_num += 1
            else:
                # Không có size -> ghi 1 dòng phân loại màu
                sku = vrec['pcode']
                stk = int(stock_total.get(sku, 0))

                safe_write_cell(ws_tpl, row_num, 1, vrec['shopee_cat'])
                safe_write_cell(ws_tpl, row_num, 2, vrec['pname'])
                safe_write_cell(ws_tpl, row_num, 3, vrec['pdesc'])
                safe_write_cell(ws_tpl, row_num, 4, vrec['parent_code'])
                safe_write_cell(ws_tpl, row_num, 5, vrec['pcode'])
                safe_write_cell(ws_tpl, row_num, 6, "Màu sắc")
                safe_write_cell(ws_tpl, row_num, 7, vrec['pcolor'])
                safe_write_cell(ws_tpl, row_num, 8, vrec['pic1'])
                safe_write_cell(ws_tpl, row_num, 9, "")
                safe_write_cell(ws_tpl, row_num, 10, "")
                safe_write_cell(ws_tpl, row_num, 11, vrec['pprice'])
                safe_write_cell(ws_tpl, row_num, 12, stk)
                safe_write_cell(ws_tpl, row_num, 13, sku)
                safe_write_cell(ws_tpl, row_num, 14, vrec['shopee_size_tpl'])
                safe_write_cell(ws_tpl, row_num, 17, vrec['pic1'])
                safe_write_cell(ws_tpl, row_num, 18, vrec['pic2'])
                safe_write_cell(ws_tpl, row_num, 19, vrec['pic3'])
                safe_write_cell(ws_tpl, row_num, 20, vrec['pic4'])
                safe_write_cell(ws_tpl, row_num, 21, vrec['pic5'])
                safe_write_cell(ws_tpl, row_num, 22, vrec['pic6'])
                safe_write_cell(ws_tpl, row_num, 23, vrec['pic7'])
                safe_write_cell(ws_tpl, row_num, 24, vrec['pic8'])
                safe_write_cell(ws_tpl, row_num, 25, vrec['pic9'])
                safe_write_cell(ws_tpl, row_num, 26, vrec['weight'])
                safe_write_cell(ws_tpl, row_num, 27, vrec['length'])
                safe_write_cell(ws_tpl, row_num, 28, vrec['width'])
                safe_write_cell(ws_tpl, row_num, 29, vrec['height'])
                safe_write_cell(ws_tpl, row_num, 30, "Tắt")
                safe_write_cell(ws_tpl, row_num, 31, "Bật")
                safe_write_cell(ws_tpl, row_num, 32, "Tắt")
                row_num += 1

        exported_filepath = os.path.join(EXPORT_DIR, f"SHOPEE_UPLOAD_{timestamp_file}.xlsx")
        wb.save(exported_filepath)
        wb.close()

        # Cập nhật trạng thái từng dòng vào cột shopee_upload trên tab SANPHAM
        loader.update_status(sheet_name, pending_row_indices, status_col_idx, row_status_list)

        success_msg = f"\n✅ Đã xử lý xong {len(pending_records)} sản phẩm (Hợp lệ xuất file: {len(valid_records)}, Bị gắn cờ cảnh báo: {len(warning_rows)})\n📁 {exported_filepath}\n📝 Đã cập nhật trạng thái chi tiết ('Done' hoặc cờ lỗi) vào cột 'shopee_upload' trên Google Sheet / Excel!\n"
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]KẾT QUẢ XUẤT SHOPEE UPLOAD MỚI[/bold green]", border_style="green"))
        else:
            print(success_msg)
        return

    # ==================== TASK 3: TIKTOK UPLOAD MỚI ====================
    elif choice == 3:
        tpl_file = os.path.join(TEMPLATES_DIR, "tpl_tiktok_upload.xlsx")
        wb = openpyxl.load_workbook(tpl_file)
        ws_tpl = wb['Template']

        # Xóa các dòng mẫu minh họa từ dòng 6
        if ws_tpl.max_row >= 6:
            ws_tpl.delete_rows(6, ws_tpl.max_row - 5)

        row_status_list = []
        warning_rows = []
        valid_records = []

        for rel_idx, rec in zip(pending_row_indices, pending_records):
            parent_code = str(rec.get('Mã hàng hóa cha') or rec.get('parent_product_code', '')).strip()
            pcode = str(rec.get('product_code', '')).strip()
            pname = str(rec.get('CON_NAME') or rec.get('product_name', '')).strip()
            pdesc = str(rec.get('CON_DES') or rec.get('product_description', '')).strip()
            raw_price = rec.get('product_price', 0)
            pprice = parse_number(raw_price)
            pcolor = str(rec.get('product_color', '')).strip()
            cat_b = str(rec.get('Tên nhóm hàng hóa') or rec.get('Tên Ngành Hàng') or rec.get('Loại sản phẩm', '')).strip()

            sub_info = sub_dict.get(cat_b.lower()) or sub_dict.get(cat_b, {})
            tiktok_cat = str(sub_info.get('Tiktok', '')).strip()
            tiktok_size_url = str(sub_info.get('Tiktok Size', '')).strip()
            tiktok_rate = sub_info.get('Tiktok Price %', '100%')
            tiktok_mult = parse_price_multiplier(tiktok_rate)
            tiktok_price = int(round(pprice * tiktok_mult))

            weight = sub_info.get('Cân nặng', 1500)
            length = sub_info.get('Chiều dài', 32)
            width = sub_info.get('Chiều rộng', 20)
            height = sub_info.get('Chiều cao', 12)

            pic1, pic2, pic3, pic4, pic5, pic6, pic7, pic8, pic9 = sale_images(pcode, [rec.get('image_01') or rec.get('Pic 1', '')] +
                [rec.get(f'image_0{n}', '') for n in range(2, 10)])  # ảnh web mới, thiếu thì ảnh cũ trong Sheet

            # Lấy dải Size chuẩn từ cột Size
            all_sizes = unroll_sizes(rec.get('Size', ''))

            # Ánh xạ thuộc tính bổ sung TikTok
            attr_dict = map_tiktok_attributes(sub_info, rec)

            # KIỂM TRA TÍNH TOÀN VẸN DỮ LIỆU (STRICT QA GATE)
            missing_reasons = []
            if not pcode:
                missing_reasons.append("Thiếu mã SP")
            if not pname:
                missing_reasons.append("Thiếu tên")
            if pprice <= 0:
                missing_reasons.append("Thiếu giá")
            if not tiktok_cat:
                missing_reasons.append("Thiếu ngành hàng TikTok")
            if not pic1:
                missing_reasons.append("Thiếu ảnh")

            if missing_reasons:
                reason_str = ", ".join(missing_reasons)
                row_status_list.append(reason_str)
                warning_rows.append(f"⚠️ Dòng {rel_idx + 1}: Mã '{pcode}' [bold red]{reason_str.upper()}[/bold red]! Đã bỏ qua.")
                continue

            row_status_list.append(f"Done - {now_str}")
            valid_records.append({
                'pcode': pcode,
                'pname': pname,
                'pdesc': pdesc,
                'pprice': tiktok_price,
                'pcolor': pcolor,
                'tiktok_cat': tiktok_cat,
                'tiktok_size_url': tiktok_size_url,
                'weight': weight,
                'length': length,
                'width': width,
                'height': height,
                'pic1': pic1,
                'pic2': pic2,
                'pic3': pic3,
                'pic4': pic4,
                'pic5': pic5,
                'pic6': pic6,
                'pic7': pic7,
                'pic8': pic8,
                'pic9': pic9,
                'all_sizes': all_sizes,
                'attr': attr_dict
            })

        if warning_rows:
            warn_msg = "\n".join(warning_rows)
            if HAS_RICH:
                console.print(Panel(warn_msg, title="[bold yellow]CẢNH BÁO DỮ LIỆU TIKTOK UPLOAD[/bold yellow]", border_style="yellow"))
            else:
                print(f"\n--- CẢNH BÁO ---\n{warn_msg}\n")

        row_num = 6
        for vrec in valid_records:
            attr = vrec['attr']
            if vrec['all_sizes']:
                for sz in vrec['all_sizes']:
                    sku = f"{vrec['pcode']}{sz}" if sz else vrec['pcode']
                    stk = max(0, int(stock_total.get(sku, 0)))

                    safe_write_cell(ws_tpl, row_num, 1, vrec['tiktok_cat'])       # Col A (1): Hạng mục
                    safe_write_cell(ws_tpl, row_num, 2, "Hải Nancy (7208750233873008390)") # Col B (2): Thương hiệu
                    safe_write_cell(ws_tpl, row_num, 3, vrec['pname'])            # Col C (3): Tên sản phẩm
                    safe_write_cell(ws_tpl, row_num, 4, vrec['pdesc'])            # Col D (4): Mô tả sản phẩm
                    safe_write_cell(ws_tpl, row_num, 5, vrec['pic1'])             # Col E (5): Ảnh chính
                    safe_write_cell(ws_tpl, row_num, 6, vrec['pic2'])             # Col F (6): Ảnh 2
                    safe_write_cell(ws_tpl, row_num, 7, vrec['pic3'])             # Col G (7): Ảnh 3
                    safe_write_cell(ws_tpl, row_num, 8, vrec['pic4'])             # Col H (8): Ảnh 4
                    safe_write_cell(ws_tpl, row_num, 9, vrec['pic5'])             # Col I (9): Ảnh 5
                    safe_write_cell(ws_tpl, row_num, 10, vrec['pic6'])            # Col J (10): Ảnh 6
                    safe_write_cell(ws_tpl, row_num, 11, vrec['pic7'])            # Col K (11): Ảnh 7
                    safe_write_cell(ws_tpl, row_num, 12, vrec['pic8'])            # Col L (12): Ảnh 8
                    safe_write_cell(ws_tpl, row_num, 13, vrec['pic9'])            # Col M (13): Ảnh 9
                    safe_write_cell(ws_tpl, row_num, 14, "Màu sắc")               # Col N (14): Tên biến thể 1
                    safe_write_cell(ws_tpl, row_num, 15, vrec['pcolor'])          # Col O (15): Giá trị biến thể 1
                    safe_write_cell(ws_tpl, row_num, 16, vrec['pic1'])            # Col P (16): Ảnh biến thể 1
                    safe_write_cell(ws_tpl, row_num, 17, "Kích cỡ")               # Col Q (17): Tên biến thể 2
                    safe_write_cell(ws_tpl, row_num, 18, sz)                      # Col R (18): Giá trị biến thể 2 (Size)
                    safe_write_cell(ws_tpl, row_num, 19, vrec['weight'])          # Col S (19): Trọng lượng kiện hàng (g)
                    safe_write_cell(ws_tpl, row_num, 20, vrec['length'])          # Col T (20): Dài (cm)
                    safe_write_cell(ws_tpl, row_num, 21, vrec['width'])           # Col U (21): Rộng (cm)
                    safe_write_cell(ws_tpl, row_num, 22, vrec['height'])          # Col V (22): Cao (cm)
                    safe_write_cell(ws_tpl, row_num, 23, "Cách giao sản phẩm này giống với các cách giao hàng cho cửa hàng. ") # Col W (23)
                    safe_write_cell(ws_tpl, row_num, 24, vrec['pprice'])          # Col X (24): Giá TikTok (đã nhân 140%)
                    safe_write_cell(ws_tpl, row_num, 25, stk)                     # Col Y (25): Số lượng tồn kho
                    safe_write_cell(ws_tpl, row_num, 26, sku)                     # Col Z (26): SKU người bán
                    safe_write_cell(ws_tpl, row_num, 27, vrec['tiktok_size_url']) # Col AA (27): Link Bảng quy đổi kích cỡ
                    safe_write_cell(ws_tpl, row_num, 28, "Có")                    # Col AB (28): COD
                    safe_write_cell(ws_tpl, row_num, 29, attr['origin'])          # Col AC (29): Quốc gia xuất xứ
                    safe_write_cell(ws_tpl, row_num, 30, attr['material'])        # Col AD (30): Chất liệu
                    safe_write_cell(ws_tpl, row_num, 31, attr['occasion'])        # Col AE (31): Dịp
                    safe_write_cell(ws_tpl, row_num, 32, attr['season'])          # Col AF (32): Mùa
                    safe_write_cell(ws_tpl, row_num, 33, attr['toe_shape'])       # Col AG (33): Hình dáng ngón chân
                    safe_write_cell(ws_tpl, row_num, 34, attr['heel_height'])     # Col AH (34): Chiều cao gót
                    safe_write_cell(ws_tpl, row_num, 35, attr['closure'])         # Col AI (35): Loại buộc
                    safe_write_cell(ws_tpl, row_num, 36, attr['heel_type'])       # Col AJ (36): Loại giày cao gót
                    safe_write_cell(ws_tpl, row_num, 37, attr['org_name'])       # Col AK (37): Tên tổ chức chịu trách nhiệm
                    safe_write_cell(ws_tpl, row_num, 38, attr['org_addr'])       # Col AL (38): Địa chỉ tổ chức chịu trách nhiệm
                    row_num += 1
            else:
                sku = vrec['pcode']
                stk = max(0, int(stock_total.get(sku, 0)))
                safe_write_cell(ws_tpl, row_num, 1, vrec['tiktok_cat'])
                safe_write_cell(ws_tpl, row_num, 2, "Hải Nancy (7208750233873008390)")
                safe_write_cell(ws_tpl, row_num, 3, vrec['pname'])
                safe_write_cell(ws_tpl, row_num, 4, vrec['pdesc'])
                safe_write_cell(ws_tpl, row_num, 5, vrec['pic1'])
                safe_write_cell(ws_tpl, row_num, 14, "Màu sắc")
                safe_write_cell(ws_tpl, row_num, 15, vrec['pcolor'])
                safe_write_cell(ws_tpl, row_num, 16, vrec['pic1'])
                safe_write_cell(ws_tpl, row_num, 19, vrec['weight'])
                safe_write_cell(ws_tpl, row_num, 20, vrec['length'])
                safe_write_cell(ws_tpl, row_num, 21, vrec['width'])
                safe_write_cell(ws_tpl, row_num, 22, vrec['height'])
                safe_write_cell(ws_tpl, row_num, 23, "Cách giao sản phẩm này giống với các cách giao hàng cho cửa hàng. ")
                safe_write_cell(ws_tpl, row_num, 24, vrec['pprice'])
                safe_write_cell(ws_tpl, row_num, 25, stk)
                safe_write_cell(ws_tpl, row_num, 26, sku)
                safe_write_cell(ws_tpl, row_num, 27, vrec['tiktok_size_url'])
                safe_write_cell(ws_tpl, row_num, 28, "Có")
                safe_write_cell(ws_tpl, row_num, 29, attr['origin'])
                safe_write_cell(ws_tpl, row_num, 30, attr['material'])
                safe_write_cell(ws_tpl, row_num, 31, attr['occasion'])
                safe_write_cell(ws_tpl, row_num, 32, attr['season'])
                safe_write_cell(ws_tpl, row_num, 33, attr['toe_shape'])
                safe_write_cell(ws_tpl, row_num, 34, attr['heel_height'])
                safe_write_cell(ws_tpl, row_num, 35, attr['closure'])
                safe_write_cell(ws_tpl, row_num, 36, attr['heel_type'])
                safe_write_cell(ws_tpl, row_num, 37, attr['org_name'])
                safe_write_cell(ws_tpl, row_num, 38, attr['org_addr'])
                row_num += 1

        exported_filepath = os.path.join(EXPORT_DIR, f"TIKTOK_UPLOAD_{timestamp_file}.xlsx")
        wb.save(exported_filepath)
        wb.close()

        # Cập nhật trạng thái từng dòng vào cột tiktok_upload trên tab SANPHAM
        loader.update_status(sheet_name, pending_row_indices, status_col_idx, row_status_list)

        success_msg = f"\n✅ Đã xử lý xong {len(pending_records)} sản phẩm (Hợp lệ xuất file: {len(valid_records)}, Bị gắn cờ cảnh báo: {len(warning_rows)})\n📁 {exported_filepath}\n📝 Đã cập nhật trạng thái chi tiết ('Done' hoặc cờ lỗi) vào cột 'tiktok_upload' trên Google Sheet / Excel!\n"
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]KẾT QUẢ XUẤT TIKTOK UPLOAD MỚI[/bold green]", border_style="green"))
        else:
            print(success_msg)
        return

    # ==================== TASK 4: MISA DANH MỤC HÀNG HÓA ====================
    elif choice == 4:
        tpl_file = os.path.join(TEMPLATES_DIR, "tpl_misa_upload.xlsx")
        wb = openpyxl.load_workbook(tpl_file)
        ws_tpl = wb['Tep nhap khau']

        # Xóa các dòng mẫu minh họa từ dòng 6
        if ws_tpl.max_row >= 6:
            ws_tpl.delete_rows(6, ws_tpl.max_row - 5)

        row_status_list = []
        warning_rows = []
        valid_records = []

        for rel_idx, rec in zip(pending_row_indices, pending_records):
            parent_code = str(rec.get('Mã hàng hóa cha') or rec.get('parent_product_code', '')).strip()
            pcode = str(rec.get('product_code', '')).strip()
            pname = str(rec.get('product_name', '')).strip()
            raw_price = rec.get('product_price', 0)
            pprice = parse_number(raw_price)
            punit = str(rec.get('product_unit') or rec.get('ĐVT', '')).strip()
            pcolor = str(rec.get('product_color', '')).strip()
            brand = str(rec.get('Thương hiệu', 'Hải Nancy')).strip()
            cat_b = str(rec.get('Tên nhóm hàng hóa') or rec.get('Tên Ngành Hàng') or rec.get('Loại sản phẩm', '')).strip()

            sub_info = sub_dict.get(cat_b.lower()) or sub_dict.get(cat_b, {})
            hnc_cat = str(sub_info.get('Mã nhóm hàng hóa') or sub_info.get('HNC', '')).strip()
            weight = sub_info.get('Cân nặng', 1500)
            desc = str(rec.get('CON_DES') or rec.get('product_description', '')).strip()  # mô tả đã duyệt (web ghi CON_DES) trước, như Shopee / TikTok / web
            pic1 = str(rec.get('image_01') or rec.get('Pic 1', '')).strip()

            # Lấy dải Size chuẩn từ cột Size (đã bao gồm đầy đủ dải size và size plus)
            all_sizes = unroll_sizes(rec.get('Size', ''))

            # KIỂM TRA TÍNH TOÀN VẸN DỮ LIỆU (STRICT QA GATE)
            missing_reasons = []
            if not parent_code:
                missing_reasons.append("Thiếu mã cha")
            if not pcode:
                missing_reasons.append("Thiếu mã SP")
            if not pname:
                missing_reasons.append("Thiếu tên")
            if pprice <= 0:
                missing_reasons.append("Thiếu giá")
            if not punit:
                missing_reasons.append("Thiếu ĐVT")
            if not hnc_cat:
                missing_reasons.append("Thiếu nhóm hàng")

            if missing_reasons:
                reason_str = ", ".join(missing_reasons)
                row_status_list.append(reason_str)
                warning_rows.append(f"⚠️ Dòng {rel_idx + 1}: Mã '{pcode}' [bold red]{reason_str.upper()}[/bold red]! Đã bỏ qua.")
                continue

            row_status_list.append(f"Done - {now_str}")
            valid_records.append({
                'parent_code': parent_code,
                'pcode': pcode,
                'pname': pname,
                'pprice': pprice,
                'punit': punit,
                'pcolor': pcolor,
                'brand': brand,
                'hnc_cat': hnc_cat,
                'weight': weight,
                'desc': desc,
                'pic1': pic1,
                'all_sizes': all_sizes
            })

        if warning_rows:
            warn_msg = "\n".join(warning_rows)
            if HAS_RICH:
                console.print(Panel(warn_msg, title="[bold yellow]CẢNH BÁO DỮ LIỆU MISA DANH MỤC[/bold yellow]", border_style="yellow"))
            else:
                print(f"\n--- CẢNH BÁO ---\n{warn_msg}\n")

        # Quét lịch sử SANPHAM để phát hiện các mã cha đã từng được xuất lên MISA trước đó
        misa_uploaded_parents = set()
        status_col_name = STATUS_COLUMNS[4][0]
        status_idx_in_df = col_map.get(status_col_name)
        parent_idx_in_df = col_map.get('parent_product_code') if col_map.get('parent_product_code') is not None else col_map.get('Mã hàng hóa cha')
        if status_idx_in_df is not None and parent_idx_in_df is not None:
            for r in range(var_row_idx + 1, len(df_raw)):
                p_code_val = str(df_raw.iloc[r, parent_idx_in_df]).strip()
                st_val = str(df_raw.iloc[r, status_idx_in_df]).strip().lower()
                if p_code_val and "done" in st_val:
                    misa_uploaded_parents.add(p_code_val)

        # Phân loại: Mã mới tinh (NEW) vs Thêm màu mới trên mã cha đã có (UPDATE)
        new_records = []
        update_records = []
        for vrec in valid_records:
            if vrec['parent_code'] in misa_uploaded_parents:
                update_records.append(vrec)
            else:
                new_records.append(vrec)

        exported_files = []

        # 1. XỬ LÝ XUẤT FILE MISA IMPORT MỚI (tpl_misa_upload.xlsx)
        if new_records:
            tpl_file_new = os.path.join(TEMPLATES_DIR, "tpl_misa_upload.xlsx")
            wb_new = openpyxl.load_workbook(tpl_file_new)
            ws_new = wb_new['Tep nhap khau']
            if ws_new.max_row >= 6:
                ws_new.delete_rows(6, ws_new.max_row - 5)

            # Gom nhóm tất cả các biến thể màu theo từng mã cha
            grouped_new = {}
            for vrec in new_records:
                p_code = vrec['parent_code']
                if p_code not in grouped_new:
                    grouped_new[p_code] = []
                grouped_new[p_code].append(vrec)

            row_num = 6
            seen_child_skus = set()

            for p_code, var_list in grouped_new.items():
                first_rec = var_list[0]
                # Ghi đúng 1 DÒNG DUY NHẤT cho Hàng Hóa Cha
                safe_write_cell(ws_new, row_num, 3, "Hàng hóa cha ")
                safe_write_cell(ws_new, row_num, 4, p_code)
                safe_write_cell(ws_new, row_num, 7, first_rec['pname'])
                safe_write_cell(ws_new, row_num, 8, first_rec['pprice'])
                safe_write_cell(ws_new, row_num, 9, first_rec['punit'])
                safe_write_cell(ws_new, row_num, 11, "Không")
                safe_write_cell(ws_new, row_num, 12, first_rec['brand'])
                safe_write_cell(ws_new, row_num, 13, first_rec['hnc_cat'])
                safe_write_cell(ws_new, row_num, 15, first_rec['weight'])
                safe_write_cell(ws_new, row_num, 19, 1)
                safe_write_cell(ws_new, row_num, 20, 0.5)
                safe_write_cell(ws_new, row_num, 22, '101-Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);')
                safe_write_cell(ws_new, row_num, 45, first_rec['desc'])
                row_num += 1

                # Ghi các dòng Hàng Hóa Con cho TẤT CẢ các màu của mã cha này
                for vrec in var_list:
                    valid_sizes = [str(s).strip() for s in vrec['all_sizes'] if s and str(s).strip()]
                    if valid_sizes:
                        for sz in valid_sizes:
                            sku = f"{vrec['pcode']}{sz}"
                            if sku in seen_child_skus:
                                continue
                            seen_child_skus.add(sku)

                            safe_write_cell(ws_new, row_num, 3, "Hàng hóa con theo thuộc tính")
                            safe_write_cell(ws_new, row_num, 4, sku)
                            safe_write_cell(ws_new, row_num, 5, sku)
                            safe_write_cell(ws_new, row_num, 6, p_code)
                            safe_write_cell(ws_new, row_num, 7, vrec['pname'])
                            safe_write_cell(ws_new, row_num, 8, vrec['pprice'])
                            safe_write_cell(ws_new, row_num, 9, vrec['punit'])

                            if vrec['pcolor']:
                                safe_write_cell(ws_new, row_num, 32, "Màu sắc")
                                safe_write_cell(ws_new, row_num, 33, vrec['pcolor'])
                                safe_write_cell(ws_new, row_num, 34, "Size")
                                safe_write_cell(ws_new, row_num, 35, sz)
                            else:
                                safe_write_cell(ws_new, row_num, 32, "Size")
                                safe_write_cell(ws_new, row_num, 33, sz)
                                safe_write_cell(ws_new, row_num, 34, "")
                                safe_write_cell(ws_new, row_num, 35, "")
                            row_num += 1
                    else:
                        sku = vrec['pcode']
                        if sku in seen_child_skus:
                            continue
                        seen_child_skus.add(sku)

                        safe_write_cell(ws_new, row_num, 3, "Hàng hóa con theo thuộc tính")
                        safe_write_cell(ws_new, row_num, 4, sku)
                        safe_write_cell(ws_new, row_num, 5, sku)
                        safe_write_cell(ws_new, row_num, 6, p_code)
                        safe_write_cell(ws_new, row_num, 7, vrec['pname'])
                        safe_write_cell(ws_new, row_num, 8, vrec['pprice'])
                        safe_write_cell(ws_new, row_num, 9, vrec['punit'])

                        if vrec['pcolor']:
                            safe_write_cell(ws_new, row_num, 32, "Màu sắc")
                            safe_write_cell(ws_new, row_num, 33, vrec['pcolor'])
                            safe_write_cell(ws_new, row_num, 34, "")
                            safe_write_cell(ws_new, row_num, 35, "")
                        else:
                            safe_write_cell(ws_new, row_num, 32, "")
                            safe_write_cell(ws_new, row_num, 33, "")
                            safe_write_cell(ws_new, row_num, 34, "")
                            safe_write_cell(ws_new, row_num, 35, "")
                        row_num += 1

            new_filename = f"MISA_PRODUCTS_NEW_{timestamp_file}.xlsx" if update_records else f"MISA_PRODUCTS_{timestamp_file}.xlsx"
            filepath_new = os.path.join(EXPORT_DIR, new_filename)
            wb_new.save(filepath_new)
            wb_new.close()
            exported_files.append(f"📦 [MỚI 100% ({len(new_records)} SP)]: {filepath_new}")

        # 2. XỬ LÝ XUẤT FILE MISA CẬP NHẬT (tpl_misa_update.xlsx - THÊM MÀU MỚI)
        if update_records:
            tpl_file_up = os.path.join(TEMPLATES_DIR, "tpl_misa_update.xlsx")
            wb_up = openpyxl.load_workbook(tpl_file_up)
            ws_up = wb_up['Nhap_khau_cap_nhat_thong_tin']
            if ws_up.max_row >= 3:
                ws_up.delete_rows(3, ws_up.max_row - 2)

            # Gom nhóm tất cả các biến thể màu theo từng mã cha
            grouped_up = {}
            for vrec in update_records:
                p_code = vrec['parent_code']
                if p_code not in grouped_up:
                    grouped_up[p_code] = []
                grouped_up[p_code].append(vrec)

            row_up = 3
            seen_child_skus_up = set()

            for p_code, var_list in grouped_up.items():
                first_rec = var_list[0]
                # Ghi đúng 1 DÒNG DUY NHẤT cho Hàng Hóa Cha
                safe_write_cell(ws_up, row_up, 1, p_code)
                safe_write_cell(ws_up, row_up, 2, "")
                safe_write_cell(ws_up, row_up, 3, "")
                safe_write_cell(ws_up, row_up, 7, first_rec['pname'])
                safe_write_cell(ws_up, row_up, 8, first_rec['hnc_cat'])
                safe_write_cell(ws_up, row_up, 9, first_rec['punit'])
                safe_write_cell(ws_up, row_up, 10, first_rec['pprice'])
                safe_write_cell(ws_up, row_up, 11, 1)
                safe_write_cell(ws_up, row_up, 12, first_rec['brand'] if first_rec['brand'] else 'Hải nancy')
                safe_write_cell(ws_up, row_up, 13, first_rec['weight'])
                safe_write_cell(ws_up, row_up, 16, 1)
                safe_write_cell(ws_up, row_up, 17, 0.5)
                safe_write_cell(ws_up, row_up, 18, '101 - Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);')
                row_up += 1

                # Ghi các dòng Hàng Hóa Con thêm màu mới
                for vrec in var_list:
                    valid_sizes = [str(s).strip() for s in vrec['all_sizes'] if s and str(s).strip()]
                    if valid_sizes:
                        for sz in valid_sizes:
                            sku = f"{vrec['pcode']}{sz}"
                            if sku in seen_child_skus_up:
                                continue
                            seen_child_skus_up.add(sku)

                            child_name = f"{vrec['pname']} ({vrec['pcolor']}/{sz})" if vrec['pcolor'] else f"{vrec['pname']} (Size {sz})"
                            safe_write_cell(ws_up, row_up, 1, sku)
                            safe_write_cell(ws_up, row_up, 2, p_code)
                            safe_write_cell(ws_up, row_up, 3, sku)
                            safe_write_cell(ws_up, row_up, 7, child_name)
                            safe_write_cell(ws_up, row_up, 9, vrec['punit'])
                            safe_write_cell(ws_up, row_up, 10, vrec['pprice'])
                            safe_write_cell(ws_up, row_up, 11, 1)
                            safe_write_cell(ws_up, row_up, 16, 1)
                            safe_write_cell(ws_up, row_up, 17, 0.5)
                            safe_write_cell(ws_up, row_up, 18, '101 - Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);')

                            if vrec['pcolor']:
                                safe_write_cell(ws_up, row_up, 24, "Màu sắc")
                                safe_write_cell(ws_up, row_up, 25, vrec['pcolor'])
                                safe_write_cell(ws_up, row_up, 26, "Size")
                                safe_write_cell(ws_up, row_up, 27, sz)
                            else:
                                safe_write_cell(ws_up, row_up, 24, "Size")
                                safe_write_cell(ws_up, row_up, 25, sz)
                                safe_write_cell(ws_up, row_up, 26, "")
                                safe_write_cell(ws_up, row_up, 27, "")
                            row_up += 1
                    else:
                        sku = vrec['pcode']
                        if sku in seen_child_skus_up:
                            continue
                        seen_child_skus_up.add(sku)

                        child_name = f"{vrec['pname']} ({vrec['pcolor']})" if vrec['pcolor'] else vrec['pname']
                        safe_write_cell(ws_up, row_up, 1, sku)
                        safe_write_cell(ws_up, row_up, 2, p_code)
                        safe_write_cell(ws_up, row_up, 3, sku)
                        safe_write_cell(ws_up, row_up, 7, child_name)
                        safe_write_cell(ws_up, row_up, 9, vrec['punit'])
                        safe_write_cell(ws_up, row_up, 10, vrec['pprice'])
                        safe_write_cell(ws_up, row_up, 11, 1)
                        safe_write_cell(ws_up, row_up, 16, 1)
                        safe_write_cell(ws_up, row_up, 17, 0.5)
                        safe_write_cell(ws_up, row_up, 18, '101 - Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);')

                        if vrec['pcolor']:
                            safe_write_cell(ws_up, row_up, 24, "Màu sắc")
                            safe_write_cell(ws_up, row_up, 25, vrec['pcolor'])
                            safe_write_cell(ws_up, row_up, 26, "")
                            safe_write_cell(ws_up, row_up, 27, "")
                        else:
                            safe_write_cell(ws_up, row_up, 24, "")
                            safe_write_cell(ws_up, row_up, 25, "")
                            safe_write_cell(ws_up, row_up, 26, "")
                            safe_write_cell(ws_up, row_up, 27, "")
                        row_up += 1

            update_filename = f"MISA_PRODUCTS_UPDATE_{timestamp_file}.xlsx"
            filepath_up = os.path.join(EXPORT_DIR, update_filename)
            wb_up.save(filepath_up)
            wb_up.close()
            exported_files.append(f"⚡ [THÊM MÀU MỚI ({len(update_records)} SP)]: {filepath_up}")

        # Cập nhật trạng thái từng dòng vào cột misa_upload trên tab SANPHAM
        loader.update_status(sheet_name, pending_row_indices, status_col_idx, row_status_list)

        files_str = "\n📁 ".join(exported_files)
        success_msg = f"\n✅ Đã xử lý xong {len(pending_records)} sản phẩm (Hợp lệ: {len(valid_records)}, Cảnh báo: {len(warning_rows)})\n📁 {files_str}\n📝 Đã cập nhật trạng thái chi tiết ('Done' hoặc cờ lỗi) vào cột 'misa_upload' trên Google Sheet!\n"
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]KẾT QUẢ XUẤT MISA DANH MỤC TỰ ĐỘNG PHÂN LOẠI[/bold green]", border_style="green"))
        else:
            print(success_msg)
        return
    # ==================== TASK 8: MISA NHẬP KHO (TỰ ĐỘNG TÁCH 15E / 3C - KIỂM TRA CHẶT CHẼ) ====================
    elif choice == 8:
        supplier_map = get_supplier_map(loader)
        product_map = get_product_info_map(loader)

        records_by_kho = {'15E': [], '3C': []}
        waiting_hd = set()
        row_status_list = []
        warning_rows = []
        valid_count = 0

        for rel_idx, rec in zip(pending_row_indices, pending_records):
            pcode = str(rec.get('product_code', '')).strip()
            sz = str(rec.get('item_size', '')).strip()
            if sz.endswith('.0'): sz = sz[:-2]
            sku = f"{pcode}{sz}" if sz else pcode

            sp_info = product_map.get(pcode, {})
            sup_name = sp_info.get('supplier', '')
            sup_info = supplier_map.get(sup_name.lower(), {}) if sup_name else {}

            doc_date = str(rec.get('Ngày chứng từ (*)') or rec.get('Ngày') or '').strip()
            doc_no = str(rec.get('Số chứng từ (*)') or '').strip()

            unit = sp_info.get('unit', '')
            # Giá theo lô (anh Kha 17/10, giống bot): don_gia_hd → don_gia_phieu → giá theo mã (invoice_price, rồi purchase_price) = "giá cũ"
            so_hd = str(rec.get('so_hd', '') or '').strip()
            lot_price = parse_number(rec.get('don_gia_hd')) or parse_number(rec.get('don_gia_phieu'))
            raw_inv = sp_info.get('invoice_price', '')
            inv_num = parse_number(raw_inv)
            if inv_num <= 0 and parse_number(sp_info.get('purchase_price')) > 0:
                # invoice_price trống → lấy giá nhập (purchase_price, vd mã tạo từ phiếu NCC) — anh Kha chốt 17/10
                inv_num = parse_number(sp_info.get('purchase_price'))
                raw_inv = str(inv_num)
            if lot_price > 0:
                inv_num = lot_price
                raw_inv = str(lot_price)
            qty = parse_number(rec.get('Số lượng (*)') or rec.get('item_quantity', 0))

            kho_raw = str(rec.get('KHO', '')).strip().upper()

            # Dòng trả hàng / huỷ đơn (Số chứng từ TRA-…): anh nhập trả trong app MISA → không xuất phiếu nhập
            if doc_no.upper().startswith('DOI-'):  # đổi / gộp mã (web, H8): chưa chốt cách nhập MISA → không xuất, không đánh dấu
                row_status_list.append("")
                continue
            if doc_no.upper().startswith(('TRA-', 'KK-')):  # khách trả / kiểm kho (web ghi KK-ddMMyy): không xuất phiếu nhập
                row_status_list.append("Bỏ qua - trả hàng")
                continue

            # Chờ hoá đơn: chưa có số HĐ thì đợi MISA_WAIT_DAYS ngày, quá hạn mới xuất "giá tạm" (giống bot)
            age_days = 99
            try:
                age_days = (datetime.now().date() - datetime.strptime(doc_date[:10], '%d/%m/%Y').date()).days
            except ValueError:
                pass
            if not so_hd and age_days <= MISA_WAIT_DAYS:
                row_status_list.append("")
                waiting_hd.add(f"{doc_no} {doc_date}")
                continue
            price_tags = [t for t in ('' if so_hd else 'giá tạm', '' if lot_price > 0 else 'giá cũ theo mã') if t]

            # DANH SÁCH KIỂM TRA LỖI THIẾU DỮ LIỆU
            missing_reasons = []

            # 1. Kiểm tra Số chứng từ (*)
            if not doc_no:
                missing_reasons.append("Thiếu số chứng từ")

            # 2. Kiểm tra ĐVT
            if not unit:
                missing_reasons.append("Thiếu ĐVT")

            # 3. Kiểm tra Ngày chứng từ (*)
            if not doc_date:
                missing_reasons.append("Thiếu ngày")

            # 4. Kiểm tra Số lượng (*)
            if qty <= 0:
                missing_reasons.append("Thiếu số lượng")

            # 5. Kiểm tra Đơn giá hóa đơn
            if not raw_inv or inv_num <= 0:
                missing_reasons.append("Thiếu đơn giá")

            # 6. Kiểm tra Nhà cung cấp
            if not sup_name or not sup_info:
                missing_reasons.append("Thiếu NCC")

            # 7. Kiểm tra Mã kho (*)
            kho_key = None
            if kho_raw in ['15E', '15ETBH']:
                kho_key = '15E'
            elif kho_raw in ['Y3C', '3C', '3CTBH']:
                kho_key = '3C'
            else:
                missing_reasons.append("Thiếu kho")

            # NẾU CÓ BẤT KỲ LỖI THIẾU NÀO -> LOẠI BỎ KHỎI FILE VÀ GẮN CỜ
            if missing_reasons:
                reason_str = ", ".join(missing_reasons)
                row_status_list.append(reason_str)
                warning_rows.append(f"⚠️ Dòng {rel_idx + 1}: Mã '{pcode}' (SKU: {sku}) [bold red]{reason_str.upper()}[/bold red]! Đã bỏ qua.")
                continue

            # DÒNG ĐẦY ĐỦ THÔNG TIN HỢP LỆ 100%
            row_status_list.append(f"Done - {now_str}" + (" · " + " · ".join(price_tags) if price_tags else ""))
            valid_count += 1

            if kho_key not in records_by_kho:
                records_by_kho[kho_key] = []

            # Lưu thông tin hợp lệ để xuất file
            rec_valid = dict(rec)
            rec_valid['_sp_info'] = sp_info
            rec_valid['_sup_info'] = sup_info
            rec_valid['_price'] = inv_num
            rec_valid['_qty'] = qty
            rec_valid['_sku'] = sku
            rec_valid['_doc_no'] = doc_no
            rec_valid['_doc_date'] = doc_date
            rec_valid['_unit'] = unit
            rec_valid['_note'] = ((f" · HĐ {so_hd}" + (f" ngày {rec.get('ngay_hd')}" if str(rec.get('ngay_hd', '') or '').strip() else "")) if so_hd else "") + \
                (f" ({', '.join(price_tags)})" if price_tags else "")
            records_by_kho[kho_key].append(rec_valid)

        if waiting_hd:
            print(f"⏳ Chờ hoá đơn (≤ {MISA_WAIT_DAYS} ngày, chưa xuất): {', '.join(sorted(waiting_hd))}")
        if warning_rows:
            warn_msg = "\n".join(warning_rows)
            if HAS_RICH:
                console.print(Panel(warn_msg, title="[bold yellow]CẢNH BÁO DỮ LIỆU CHƯA ĐẦY ĐỦ[/bold yellow]", border_style="yellow"))
            else:
                print(f"\n--- CẢNH BÁO ---\n{warn_msg}\n")

        exported_files = []

        # Xử lý xuất file cho từng kho (Chỉ xuất các dòng hợp lệ)
        kho_configs = [
            ('15E', 'tpl_misa_stock_15e.xlsx', '15ETBH', f"MISA_STOCK_15E_{timestamp_file}.xlsx"),
            ('3C', 'tpl_misa_stock_y3c.xlsx', '3CTBH', f"MISA_STOCK_3C_{timestamp_file}.xlsx")
        ]

        for kho_code, tpl_filename, misa_kho_code, out_filename in kho_configs:
            valid_kho_records = records_by_kho.get(kho_code, [])
            if not valid_kho_records:
                continue

            tpl_file = os.path.join(TEMPLATES_DIR, tpl_filename)
            wb = openpyxl.load_workbook(tpl_file)
            ws_tpl = wb['Nhap kho']

            # Xóa các dòng mẫu minh họa từ dòng 9
            if ws_tpl.max_row >= 9:
                ws_tpl.delete_rows(9, ws_tpl.max_row - 8)

            row_num = 9
            for rec in valid_kho_records:
                sku = rec['_sku']
                doc_date = rec['_doc_date']
                doc_no = rec['_doc_no']
                unit = rec['_unit']
                price = rec['_price']
                qty = rec['_qty']

                sp_info = rec['_sp_info']
                sup_info = rec['_sup_info']

                ma_dt = sup_info.get('ma_dt', '')
                ten_dt = sup_info.get('ten_dt', '')
                discount_str = sup_info.get('discount_str', '0')
                vat_str = sup_info.get('vat_str', '0')

                thanh_tien = qty * price
                discount_rate = parse_percent_rate(discount_str)
                tien_chiet_khau = round(thanh_tien * discount_rate, 2)

                vat_rate = parse_percent_rate(vat_str)
                tien_thue = round((thanh_tien - tien_chiet_khau) * vat_rate, 2)
                tien_thanh_toan = thanh_tien - tien_chiet_khau + tien_thue

                # Điền đầy đủ 22 cột chuẩn của MISA eShop
                safe_write_cell(ws_tpl, row_num, 1, "Nhập kho mua hàng")       # Cột A (1): Loại nhập kho
                safe_write_cell(ws_tpl, row_num, 2, doc_date)                  # Cột B (2): Ngày chứng từ (*)
                safe_write_cell(ws_tpl, row_num, 3, doc_no)                    # Cột C (3): Số chứng từ (*)
                safe_write_cell(ws_tpl, row_num, 4, ma_dt)                    # Cột D (4): Mã đối tượng
                safe_write_cell(ws_tpl, row_num, 5, ten_dt)                   # Cột E (5): Tên đối tượng
                safe_write_cell(ws_tpl, row_num, 6, (f"Nhập kho mua hàng từ {ten_dt}" if ten_dt else "Nhập kho mua hàng") + rec.get('_note', ''))  # Cột F (6): Diễn giải (+ số HĐ / giá tạm; mẫu MISA không có cột Số HĐ)
                safe_write_cell(ws_tpl, row_num, 7, "Chưa thanh toán")         # Cột G (7): Hình thức thanh toán
                safe_write_cell(ws_tpl, row_num, 8, sku)                       # Cột H (8): Mã hàng (*)
                safe_write_cell(ws_tpl, row_num, 9, "")                        # Cột I (9): Tên hàng (bỏ trống)
                safe_write_cell(ws_tpl, row_num, 10, "")                       # Cột J (10): Số lô
                safe_write_cell(ws_tpl, row_num, 11, "")                       # Cột K (11): Hạn sử dụng
                safe_write_cell(ws_tpl, row_num, 12, misa_kho_code)            # Cột L (12): Mã kho (*)
                safe_write_cell(ws_tpl, row_num, 13, "")                       # Cột M (13): Mã vị trí lưu kho
                safe_write_cell(ws_tpl, row_num, 14, unit)                     # Cột N (14): ĐVT
                safe_write_cell(ws_tpl, row_num, 15, qty)                      # Cột O (15): Số lượng (*)
                safe_write_cell(ws_tpl, row_num, 16, price)                    # Cột P (16): Đơn giá
                safe_write_cell(ws_tpl, row_num, 17, thanh_tien)               # Cột Q (17): Thành tiền
                safe_write_cell(ws_tpl, row_num, 18, discount_rate)            # Cột R (18): % chiết khấu
                safe_write_cell(ws_tpl, row_num, 19, tien_chiet_khau)          # Cột S (19): Tiền chiết khấu
                safe_write_cell(ws_tpl, row_num, 20, vat_rate)                 # Cột T (20): Thuế suất
                safe_write_cell(ws_tpl, row_num, 21, tien_thue)                # Cột U (21): Tiền thuế
                safe_write_cell(ws_tpl, row_num, 22, tien_thanh_toan)          # Cột V (22): Tiền thanh toán
                row_num += 1

            out_filepath = os.path.join(EXPORT_DIR, out_filename)
            wb.save(out_filepath)
            wb.close()
            exported_files.append(out_filepath)

        exported_filepath = "\n📁 ".join(exported_files) if exported_files else "(Không có file nào do toàn bộ dữ liệu bị thiếu trường bắt buộc)"

        # Cập nhật từng trạng thái riêng biệt cho từng dòng lên Google Sheet / Excel
        loader.update_status(sheet_name, pending_row_indices, status_col_idx, row_status_list)

        success_msg = f"\n✅ Đã xử lý xong {len(pending_records)} bản ghi (Hợp lệ xuất file: {valid_count}, Bị gắn cờ cảnh báo: {len(warning_rows)})\n📁 {exported_filepath}\n📝 Đã cập nhật trạng thái chi tiết ('Done' hoặc các cờ thiếu) vào cột tương ứng trên Google Sheet / Excel!\n"
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]KẾT QUẢ XỬ LÝ MISA[/bold green]", border_style="green"))
        else:
            print(success_msg)
        return

    # ==================== TASK 10: IN TEM BARCODE & QR CODE ====================
    elif choice == 10:
        # V34 (anh Kha 18/10): in tem theo kho / số chứng từ / ngày — cùng cột và luật với cửa bot in_tem (LABEL_COLUMNS).
        # Tạo file KHÔNG tính là đã in: chỉ ghi web_label = Done khi trả lời "Đã in xong".
        product_map = get_product_info_map(loader)
        if input("[1] Theo phiếu / ngày (mặc định)  [2] In bù theo mã hàng: ").strip() == '2':
            # In bù (cùng luật cửa bot in_bu): mã + size → tem mẫu A, không đụng web_label NHAP
            kho_want = {'1': '15E', '2': 'Y3C'}.get(input("Kho [1] 15E  [2] Y3C: ").strip(), '')
            if not kho_want:
                print("ℹ️ Cần chọn 1 kho.")
                return
            raw = input("Mã hàng + size, mỗi mã cách nhau dấu phẩy, thêm xN nếu in N tem (vd HT1121D40x2, HT1121D41): ").strip().upper()
            keys = {k.upper() for k in product_map}
            recs, bad = [], []
            for part in [p.strip().replace(' ', '') for p in raw.split(',') if p.strip()]:
                m = re.match(r'^(.+?)(?:X(\d+))?$', part)
                ma, n = m.group(1), int(m.group(2) or 1)
                # Mã dính size có dấu nối (tem quét "AP048N-40", "AP048N_40", "ap048n/40") — cùng luật bot parseMessage_ (19/10)
                code = next((ma[:k] for k in range(len(ma), 0, -1) if ma[:k] in keys and re.match(r'^[-_/.]?\d{0,2}(\.5)?$', ma[k:])), '')
                if not code:
                    bad.append(ma)
                    continue
                recs.append(label_record({'product_code': code, 'item_size': ma[len(code):].lstrip('-_/.'), 'item_quantity': n}, product_map))
            if bad:
                print(f"❌ Mã không có trong SANPHAM: {', '.join(bad)} — không in.")
                return
            if not recs:
                return
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
            import label_print
            out_df = pd.DataFrame(recs, columns=LABEL_COLUMNS)
            print(f"🏷️ In bù {len(recs)} mã · {int(out_df['F6'].sum())} tem kho {kho_want}")
            res = label_print.print_records(out_df.astype(str).to_dict('records'), kho_want)
            print("✅ Đã in." if res['ok'] else f"❌ Chưa in được: {res['loi']}")
            return
        kho_pick = input("Kho in tem [1] 15E  [2] Y3C  [Enter] cả 2: ").strip()
        kho_want = {'1': '15E', '2': 'Y3C'}.get(kho_pick, '')
        filt = input("Số chứng từ (vd NK000045) hoặc ngày dd/mm/yyyy (lấy cả dòng nhập Zalo không số) — Enter = mọi dòng chưa in: ").strip().upper()
        pcode_idx, kho_idx2 = col_map.get('product_code'), col_map.get('KHO')
        doc_idx, date_idx = col_map.get('Số chứng từ (*)'), col_map.get('Ngày chứng từ (*)')

        def kho_norm(v):
            v = str(v or '').strip().upper()
            return '15E' if v in ('15E', '15ETBH', 'TBH') else ('Y3C' if v in ('Y3C', '3C', '3CTBH', 'YEN') else '')

        sel_idx, sel_recs = [], []
        if filt:
            for rel_idx in range(data_start_row, len(df_raw)):
                row = df_raw.iloc[rel_idx]
                code = str(row[pcode_idx]).strip() if pd.notna(row[pcode_idx]) else ""
                if not code or code == 'product_code':
                    continue
                doc = str(row[doc_idx]).strip().upper() if (doc_idx is not None and pd.notna(row[doc_idx])) else ""
                if doc.startswith(('TRA-', 'KK-', 'DOI-')):
                    continue
                if kho_want and kho_norm(row[kho_idx2]) != kho_want:
                    continue
                day = str(row[date_idx]).strip()[:10] if (date_idx is not None and pd.notna(row[date_idx])) else ""
                if (re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', filt) and day != filt) or (not re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', filt) and doc != filt):
                    continue
                sel_idx.append(rel_idx)
                sel_recs.append({k: (row[i] if pd.notna(row[i]) else "") for k, i in col_map.items() if i < len(row)})
        else:
            for rel_idx, rec in zip(pending_row_indices, pending_records):
                if str(rec.get('Số chứng từ (*)', '')).strip().upper().startswith(('TRA-', 'KK-', 'DOI-')):
                    continue
                if kho_want and kho_norm(rec.get('KHO')) != kho_want:
                    continue
                sel_idx.append(rel_idx)
                sel_recs.append(rec)
        if not sel_recs:
            print("ℹ️ Không có dòng nào để in tem với lựa chọn này.")
            return

        out_df = pd.DataFrame([label_record(rec, product_map) for rec in sel_recs], columns=LABEL_COLUMNS)
        exported_filepath = os.path.join(EXPORT_DIR, f"WEB_LABEL_{timestamp_file}.csv")
        out_df.to_csv(exported_filepath, index=False)
        in_fixed_path = in_csv_path()
        try:
            os.makedirs(os.path.dirname(in_fixed_path), exist_ok=True)
            out_df.to_csv(in_fixed_path, index=False)  # mẫu .lbx cũ đọc IN.csv
            if kho_want:
                out_df.to_csv(os.path.join(os.path.dirname(in_fixed_path), f"IN_{kho_want}.csv"), index=False)
            exported_filepath += f"\n📁 (Đã ghi đè) {in_fixed_path}" + (f" + IN_{kho_want}.csv" if kho_want else "")
        except Exception as e:
            print(f"[!] Không thể ghi đè file IN.csv: {e}")
        print(f"\n🏷️ {len(sel_recs)} dòng · {int(out_df['F6'].sum())} tem\n📁 {exported_filepath}")
        # V34 mục 6: in thẳng trên QL-700 bằng cùng hàm dựng tem với dịch vụ in tự động (tools/label_print.py) — mỗi kho 1 đợt
        if kho_want and input(f"In thẳng {int(out_df['F6'].sum())} tem kho {kho_want} trên máy QL-700 ngay? (y/Enter = không): ").strip().lower() == 'y':
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
            import label_print
            res = label_print.print_records(out_df.astype(str).to_dict('records'), kho_want)
            if res['ok']:
                loader.update_status(sheet_name, sel_idx, status_col_idx, f"Done - {now_str}")
                print(f"✅ Đã in {res['so_tem']} tem và đánh dấu đã in (web_label).")
                return
            print(f"❌ Chưa in được: {res['loi']}")
        elif not kho_want:
            print("ℹ️ In thẳng trên QL-700 cần chọn 1 kho (tem 2 kho in riêng).")
        if input("Mở P-touch in xong chưa? Đã in xong thì gõ y để đánh dấu (Enter = chưa): ").strip().lower() == 'y':
            loader.update_status(sheet_name, sel_idx, status_col_idx, f"Done - {now_str}")
            print("✅ Đã đánh dấu đã in (web_label).")
        else:
            print("ℹ️ Chưa đánh dấu — lần sau vẫn ra các dòng này (hoặc bấm \"Đã in xong\" trên app).")
        return

    # ==================== TASK 9: ĐỒNG BỘ SKU TAB NHAP VÀO 2 KHO ====================
    elif choice == 9:
        df_15e, _ = loader.load_sheet('KHO15E')
        df_y3c, _ = loader.load_sheet('KHOY3C')

        _, col_map_15 = DynamicHeaderScanner.scan_data_headers(df_15e)
        _, col_map_y3 = DynamicHeaderScanner.scan_data_headers(df_y3c)

        existing_15e = set()
        for r in range(1, len(df_15e)):
            p = str(df_15e.iloc[r, col_map_15.get('product_code', 1)] or '').strip()
            s = str(df_15e.iloc[r, col_map_15.get('item_size', 3)] or '').strip()
            if s.endswith('.0'): s = s[:-2]
            if p: existing_15e.add(f"{p}{s}")

        existing_y3c = set()
        for r in range(1, len(df_y3c)):
            p = str(df_y3c.iloc[r, col_map_y3.get('product_code', 1)] or '').strip()
            s = str(df_y3c.iloc[r, col_map_y3.get('item_size', 3)] or '').strip()
            if s.endswith('.0'): s = s[:-2]
            if p: existing_y3c.add(f"{p}{s}")

        new_rows_15e = []
        new_rows_y3c = []
        cur_row_15e = len(df_15e) + 1
        cur_row_y3c = len(df_y3c) + 1

        for rec in pending_records:
            pcode = clean_code(rec.get('product_code', ''))  # bỏ ký tự ẩn trước khi thêm SKU vào KHO
            color = str(rec.get('product_color', '')).strip()
            sz = str(rec.get('item_size', '')).strip()
            if sz.endswith('.0'): sz = sz[:-2]
            sku = f"{pcode}{sz}" if sz else pcode
            kho = str(rec.get('KHO', '')).strip().upper()

            if not pcode:
                continue

            loc_15e = loc_y3c = ''  # vị trí để trống, không lấy mặc định từ SUB (anh Kha 18/10, khớp bot appendKhoRow_)

            # Nếu dòng này thuộc Kho 15E ➔ Chỉ kiểm tra và thêm vào KHO15E
            if '15E' in kho:
                if sku not in existing_15e:
                    fsku_formula = f"=CONCATENATE($A$1;B{cur_row_15e};D{cur_row_15e})"
                    calc_formula = f"=E{cur_row_15e} + SUMIF(NHAP!H:H; A{cur_row_15e}; NHAP!G:G) - SUMIF(XUAT!G:G; A{cur_row_15e}; XUAT!F:F) - SUMIF(BAN!H:H; A{cur_row_15e}; BAN!F:F)"
                    new_rows_15e.append([fsku_formula, pcode, color, sz, 0, calc_formula, loc_15e])
                    existing_15e.add(sku)
                    cur_row_15e += 1

            # Nếu dòng này thuộc Kho Y3C (hoặc 3C) ➔ Chỉ kiểm tra và thêm vào KHOY3C
            elif '3C' in kho or 'Y3C' in kho:
                if sku not in existing_y3c:
                    fsku_formula = f"=CONCATENATE($A$1;B{cur_row_y3c};D{cur_row_y3c})"
                    calc_formula = f"=E{cur_row_y3c} + SUMIF(NHAP!H:H; A{cur_row_y3c}; NHAP!G:G) - SUMIF(XUAT!G:G; A{cur_row_y3c}; XUAT!F:F) - SUMIF(BAN!H:H; A{cur_row_y3c}; BAN!F:F)"
                    new_rows_y3c.append([fsku_formula, pcode, color, sz, 0, calc_formula, loc_y3c])
                    existing_y3c.add(sku)
                    cur_row_y3c += 1

        if new_rows_15e:
            loader.append_rows_to_sheet('KHO15E', new_rows_15e)
        if new_rows_y3c:
            loader.append_rows_to_sheet('KHOY3C', new_rows_y3c)

        status_text = f"Done - {now_str}"
        loader.update_status(sheet_name, pending_row_indices, status_col_idx, status_text)

        msg = f"\n✅ Đã đồng bộ hoàn tất {len(pending_records)} dòng từ tab NHAP!\n➕ Thêm mới vào KHO15E: {len(new_rows_15e)} SKU\n➕ Thêm mới vào KHOY3C: {len(new_rows_y3c)} SKU\n📝 Đã cập nhật trạng thái '{status_text}' vào cột 'kho_sync' trên tab NHAP!\n"
        if HAS_RICH:
            console.print(Panel(msg, title="[bold green]ĐỒNG BỘ KHO THÀNH CÔNG[/bold green]", border_style="green"))
        else:
            print(msg)
        return



    status_text = f"Done - {now_str}"
    loader.update_status(sheet_name, pending_row_indices, status_col_idx, status_text)

    success_msg = f"\n✅ Xuất thành công {len(pending_records)} bản ghi vào file:\n📁 {exported_filepath}\n📝 Đã cập nhật trạng thái '{status_text}' vào ô tương ứng trên Google Sheet / Excel!\n"
    if HAS_RICH:
        console.print(Panel(success_msg, title="[bold green]THÀNH CÔNG[/bold green]", border_style="green"))
    else:
        print(success_msg)


@sync_hint_after
def process_media_management(loader, auto_ingest=True):
    """Gom file tư liệu từ Photoroom & Downloads và cập nhật 3 cột content_path, content_url, content_files lên Google Sheet SANPHAM."""
    if not os.path.exists(MEDIA_DEST_DIR):
        msg = f"❌ Không tìm thấy thư mục đích tại: {MEDIA_DEST_DIR}\nVui lòng kiểm tra lại ổ đĩa / kết nối ổ cứng / Volumes!"
        if HAS_RICH: console.print(Panel(msg, title="[bold red]LỖI THƯ MỤC MEDIA[/bold red]", border_style="red"))
        else: print(msg)
        return

    if HAS_RICH:
        console.print(Panel(f"🔍 Đang tải dữ liệu SANPHAM và quét thư mục Media...", border_style="cyan"))
    else:
        print("🔍 Đang tải dữ liệu SANPHAM và quét thư mục Media...")

    df_sp, _ = loader.load_sheet('SANPHAM')
    var_row_idx, col_map = DynamicHeaderScanner.scan_data_headers(df_sp)
    p_idx = col_map.get('product_code', 22)
    path_col_idx = col_map.get('content_path')
    url_col_idx = col_map.get('content_url')
    files_col_idx = col_map.get('content_files')

    if path_col_idx is None or url_col_idx is None or files_col_idx is None:
        msg = "❌ Không tìm thấy đủ 3 cột 'content_path', 'content_url', 'content_files' ở Dòng 2 trên tab SANPHAM!"
        if HAS_RICH: console.print(Panel(msg, title="[bold red]THIẾU CỘT TRÊN SHEET[/bold red]", border_style="red"))
        else: print(msg)
        return

    # Thu thập tất cả mã sản phẩm từ SANPHAM và NHAP
    all_pcodes = {}
    data_start_row = (var_row_idx + 1) if var_row_idx is not None else 2
    for r in range(data_start_row, len(df_sp)):
        val = str(df_sp.iloc[r, p_idx]).strip() if pd.notna(df_sp.iloc[r, p_idx]) else ''
        if val:
            all_pcodes[val.upper()] = val

    try:
        df_nhap, _ = loader.load_sheet('NHAP')
        _, map_nhap = DynamicHeaderScanner.scan_data_headers(df_nhap)
        p_nhap_idx = map_nhap.get('product_code')
        if p_nhap_idx is not None:
            for r in range(2, len(df_nhap)):
                val_n = str(df_nhap.iloc[r, p_nhap_idx]).strip() if pd.notna(df_nhap.iloc[r, p_nhap_idx]) else ''
                if val_n and val_n.upper() not in all_pcodes:
                    all_pcodes[val_n.upper()] = val_n
    except Exception:
        pass

    sorted_pcodes = sorted(all_pcodes.keys(), key=lambda x: len(x), reverse=True)

    def find_matching_code(filename):
        base = os.path.splitext(filename)[0]
        base_clean = re.sub(r'^(Lookbook_|Look_Book_|lookbook_)', '', base, flags=re.IGNORECASE).strip()
        base_clean_upper = base_clean.upper()

        # 1. Khớp với danh bạ mã có sẵn trên Google Sheet
        for pcode_up in sorted_pcodes:
            if base_clean_upper == pcode_up or base_clean_upper.startswith(pcode_up + '_') or base_clean_upper.startswith(pcode_up + '-') or base_clean_upper.startswith(pcode_up + ' '):
                return all_pcodes[pcode_up]
            if base_clean_upper.startswith(pcode_up):
                rem = base_clean_upper[len(pcode_up):]
                if rem.startswith(('_', '-', ' ', 'G', 'P', 'V')):
                    return all_pcodes[pcode_up]

        # 2. Bộ lọc Regex thông minh nhận diện mã sản phẩm mới (chưa có trên Sheet)
        m = re.match(r'^([A-Za-z0-9]{3,12})(?:[_\-\s].*|$)', base_clean)
        if m:
            cand = m.group(1).upper()
            has_digit = any(c.isdigit() for c in cand)
            has_alpha = any(c.isalpha() for c in cand)
            if has_digit and has_alpha:
                excluded_prefixes = ('GEMINI', 'SCREENSHOT', 'IMAGE', 'IMG', 'DSC', 'PHOTO', 'LOOKBOOK', 'FREEBIE', 'DESIGN', 'HONDA', 'SNOWFLAKE', 'BOOTS', 'BEHIND', 'GNOME')
                if not cand.startswith(excluded_prefixes):
                    return cand

        return None

    ingested_count = 0
    if auto_ingest:
        sources = [
            ("Photoroom", SOURCE_PHOTOROOM, ('.jpg', '.jpeg', '.png', '.webp', '.heic', '.mp4', '.mov')),
            ("Downloads", SOURCE_DOWNLOADS, ('.mp4', '.mov', '.jpg', '.jpeg', '.png', '.webp', '.heic'))
        ]
        for src_name, src_path, valid_exts in sources:
            if not os.path.exists(src_path):
                continue
            if HAS_RICH:
                console.print(f"🔎 Đang quét nguồn [{src_name}]: {src_path}...")
            else:
                print(f"🔎 Đang quét nguồn [{src_name}]: {src_path}...")

            for root, dirs, files in os.walk(src_path):
                for f in files:
                    if f.startswith('.') or not f.lower().endswith(valid_exts):
                        continue
                    matched_code = find_matching_code(f)
                    if matched_code:
                        dst_folder = os.path.join(MEDIA_DEST_DIR, matched_code)
                        os.makedirs(dst_folder, exist_ok=True)
                        src_file_path = os.path.join(root, f)
                        dst_file_path = os.path.join(dst_folder, f)
                        if src_file_path != dst_file_path:
                            try:
                                shutil.move(src_file_path, dst_file_path)
                                ingested_count += 1
                                if HAS_RICH:
                                    console.print(f"  📦 [bold green]Đã gom:[/bold green] [cyan]{f}[/cyan] ➔ Thư mục [bold yellow]{matched_code}[/bold yellow]")
                                else:
                                    print(f"  📦 Đã gom: {f} -> Thư mục {matched_code}")
                            except Exception as e:
                                if HAS_RICH:
                                    console.print(f"  ⚠️ [bold red]Lỗi gom file {f}:[/bold red] {e}")
                                else:
                                    print(f"  ⚠️ Lỗi gom file {f}: {e}")

    # Quét toàn bộ thư mục Media và chuẩn bị batch update lên SANPHAM
    batch_records = []
    stats = {'video_img': 0, 'video': 0, 'img': 0, 'empty': 0}

    for r in range(data_start_row, len(df_sp)):
        pcode = str(df_sp.iloc[r, p_idx]).strip() if pd.notna(df_sp.iloc[r, p_idx]) else ''
        if not pcode:
            continue

        folder_path = os.path.join(MEDIA_DEST_DIR, pcode)
        if os.path.exists(folder_path):
            try:
                files = os.listdir(folder_path)
                v = [x for x in files if x.lower().endswith(('.mp4', '.mov', '.m4v', '.avi', '.mkv')) and not x.startswith('.')]
                i = [x for x in files if x.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.heic')) and not x.startswith('.')]

                if v and i:
                    tag = "VIDEO, IMG"
                    stats['video_img'] += 1
                elif v:
                    tag = "VIDEO"
                    stats['video'] += 1
                elif i:
                    tag = "IMG"
                    stats['img'] += 1
                else:
                    tag = ""
                    stats['empty'] += 1

                c_path = folder_path
                c_url = ""
            except Exception:
                tag = ""
                c_path = folder_path
                c_url = ""
                stats['empty'] += 1
        else:
            tag = ""
            c_path = ""
            c_url = ""
            stats['empty'] += 1

        batch_records.append({
            'row_idx': r,
            'path_col_idx': path_col_idx,
            'path_val': c_path,
            'url_col_idx': url_col_idx,
            'url_val': c_url,
            'files_col_idx': files_col_idx,
            'files_val': tag
        })

    if batch_records:
        if HAS_RICH:
            console.print(f"📝 Đang cập nhật trạng thái Media lên Google Sheet tab SANPHAM ({len(batch_records)} dòng)...")
        else:
            print(f"📝 Đang cập nhật trạng thái Media lên Google Sheet tab SANPHAM ({len(batch_records)} dòng)...")
        loader.update_batch_media_results('SANPHAM', batch_records)

    report_text = f"""✅ ĐỒNG BỘ MEDIA HOÀN TẤT!
➕ File đã tự động gom về thư mục: {ingested_count} file
📊 Thống kê Media tab SANPHAM:
   • Có cả Video & Ảnh (VIDEO, IMG): {stats['video_img']} sản phẩm
   • Chỉ có Video (VIDEO): {stats['video']} sản phẩm
   • Chỉ có Ảnh (IMG): {stats['img']} sản phẩm
   • Chưa có file tư liệu (Để trống): {stats['empty']} sản phẩm
📝 Đã đồng bộ đầy đủ 3 cột: 'content_path', 'content_url', 'content_files' trên Google Sheet!"""

    if HAS_RICH:
        console.print(Panel(report_text, title="[bold green]KẾT QUẢ QUẢN LÝ MEDIA[/bold green]", border_style="green"))
    else:
        print(f"\n{report_text}\n")


def load_sub_dictionary(loader):
    """Trích xuất danh mục chuẩn từ sheet SUB để khóa chặt Schema cho Gemini AI. Đọc theo tên cột hàng 1 (luật 4)."""
    df_sub, _ = loader.load_sheet('SUB')
    head = [str(h).strip() for h in df_sub.iloc[0].values]

    def cell(r, name):
        if name not in head:
            return ''
        v = df_sub.iloc[r, head.index(name)]
        v = str(v).strip() if pd.notna(v) else ''
        return '' if v == 'nan' else v

    def get_col_values(name):
        res = []
        for r in range(1, len(df_sub)):
            val = cell(r, name)
            if val and val not in res:
                res.append(val)
        return res

    # Ngành của tiệm: có Mã nhóm hàng hóa, bỏ dòng ngành Shopee lẻ (loai_dong = shopee, anh Kha 19/10 — khớp bot productCategories_)
    valid_categories = []
    category_map = {}
    for r in range(1, len(df_sub)):
        cname, cid = cell(r, 'Tên Ngành Hàng'), cell(r, 'Mã nhóm hàng hóa')
        if cell(r, 'loai_dong').lower() == 'shopee':
            continue
        if cname and cid and cname not in valid_categories:
            valid_categories.append(cname)
            category_map[cname] = cid

    return {
        'categories': valid_categories,
        'category_map': category_map,
        'features': get_col_values('Đặc điểm'),
        'brands': get_col_values('Thương hiệu'),
        'materials': get_col_values('Chất liệu'),
        'highlights': get_col_values('Nhấn mạnh'),
        'strap_materials': get_col_values('Chất liệu quai:'),
        'sole_materials': get_col_values('Chất liệu đế:'),
        'inner_linings': get_col_values('Lót trong:'),
        'insole_surfaces': get_col_values('Mặt lót đế:'),
        'toe_shapes': get_col_values('Mũi giày:'),
        'bottom_parts': get_col_values('Gót giày:'),
        'outfit_matches': get_col_values('Kết hợp trang phục:'),
        'usages': get_col_values('Sử dụng:'),
        'suppliers': get_col_values('supplier')
    }


def get_image_mime_type(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".webp":
        return "image/webp"
    elif ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    return "image/jpeg"


def parse_image_paths(input_str):
    """Bóc tách 1 hoặc nhiều đường dẫn file ảnh từ chuỗi kéo thả Terminal."""
    if not input_str or not input_str.strip():
        return []
    raw = input_str.strip()
    paths = []
    try:
        tokens = shlex.split(raw)
    except Exception:
        tokens = [p.strip('\'"') for p in raw.split(' ') if p.strip()]

    for tok in tokens:
        cleaned = tok.strip('\'"').replace('\\ ', ' ')
        if os.path.exists(cleaned) and not os.path.isdir(cleaned):
            paths.append(cleaned)
        elif os.path.exists(tok.strip('\'"')) and not os.path.isdir(tok.strip('\'"')):
            paths.append(tok.strip('\'"'))
    return paths


def parse_vietnamese_shoe_sizes(size_input, gender='male'):
    """Giải mã thông minh mọi cú pháp size chat xưởng tiếng Việt (889901123, 55677890, 39/2đ, 38-42, 38,39...)."""
    if not size_input:
        return ['38', '39', '40', '41', '42', '43'] if gender == 'male' else ['35', '36', '37', '38', '39']

    # Nếu đã là list
    if isinstance(size_input, list):
        expanded = []
        for item in size_input:
            expanded.extend(parse_vietnamese_shoe_sizes(str(item), gender))
        return expanded if expanded else ['38', '39', '40', '41', '42', '43']

    s = str(size_input).strip()

    # 1. Dạng chuỗi số viết tắt xưởng: '889901123' hoặc '55677890'
    clean_digits = re.sub(r'[^0-9]', '', s)
    if len(clean_digits) >= 4 and s == clean_digits:
        is_female = ('5' in clean_digits or '6' in clean_digits or '7' in clean_digits) and ('1' not in clean_digits and '2' not in clean_digits and '3' not in clean_digits) or (gender == 'female')
        if is_female:
            digit_map = {'5': '35', '6': '36', '7': '37', '8': '38', '9': '39', '0': '40', '1': '41'}
        else:
            digit_map = {'7': '37', '8': '38', '9': '39', '0': '40', '1': '41', '2': '42', '3': '43', '4': '44', '5': '45'}
        res = [digit_map[d] for d in clean_digits if d in digit_map]
        if res:
            return res

    # 2. Dạng phân số / nhân số lượng: '39/2đ 40/2đ', '39:2, 40:2', '39x2 40x2'
    slash_matches = re.findall(r'(\d{2})\s*[/x:đ\-]\s*(\d+)(?:\s*(?:đ|đôi|c|cái))?', s, re.IGNORECASE)
    if slash_matches:
        res = []
        for sz, qty in slash_matches:
            try:
                q = int(qty)
                res.extend([sz] * q)
            except ValueError:
                res.append(sz)
        if res:
            return res

    # 3. Dạng dải khoảng: '38-42', 'sz từ 38 đến 42'
    range_match = re.search(r'(\d{2})\s*(?:-|➔|đến|to)\s*(\d{2})', s, re.IGNORECASE)
    if range_match:
        try:
            start_sz = int(range_match.group(1))
            end_sz = int(range_match.group(2))
            if 30 <= start_sz <= 50 and 30 <= end_sz <= 50 and start_sz <= end_sz:
                return [str(i) for i in range(start_sz, end_sz + 1)]
        except Exception:
            pass

    # 4. Dạng phân tách thông thường (dấu phẩy, chấm phẩy, khoảng trắng)
    tokens = [t.strip() for t in re.split(r'[,;\s]+', s) if t.strip()]
    res = []
    for tok in tokens:
        m = re.match(r'^(\d{2})(?:[x/:](\d+))?$', tok, re.IGNORECASE)
        if m:
            sz = m.group(1)
            q = int(m.group(2)) if m.group(2) else 1
            res.extend([sz] * q)
        elif tok.isdigit() and len(tok) == 2:
            res.append(tok)
        elif tok.lower() in ['freesize', 'free', 'f']:
            res.append('FreeSize')

    return res if res else [s]


def format_size_display(sizes_list):
    """Hiển thị dải size có gom nhóm số lượng rõ ràng, ví dụ: 39 (x2), 40 (x2), 41 (x2) ➔ Tổng: 8 đôi."""
    if not sizes_list:
        return "Chưa có size"
    from collections import Counter
    counts = Counter([str(s).strip() for s in sizes_list if str(s).strip()])
    def sort_key(k):
        try: return (0, int(k))
        except ValueError: return (1, k)
    sorted_sizes = sorted(counts.keys(), key=sort_key)
    parts = []
    total_qty = 0
    for sz in sorted_sizes:
        qty = counts[sz]
        total_qty += qty
        if qty > 1:
            parts.append(f"{sz} (x{qty})")
        else:
            parts.append(f"{sz}")
    return f"{', '.join(parts)}  ➔  Tổng: {total_qty} đôi"


def analyze_product_with_gemini(image_paths, user_notes, sub_dict):
    """Gọi Gemini REST API phân tích (ưu tiên đoạn chat/ghi chú làm chủ đạo, ảnh bổ trợ)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Không tìm thấy GEMINI_API_KEY trong file .env hoặc biến môi trường!")

    if not image_paths:
        image_paths = []
    elif isinstance(image_paths, str):
        image_paths = [image_paths]

    parts = []
    valid_count = 0
    for img_path in image_paths:
        if os.path.exists(img_path) and not os.path.isdir(img_path):
            with open(img_path, "rb") as img_file:
                img_b64 = base64.b64encode(img_file.read()).decode("utf-8")
            mime_type = get_image_mime_type(img_path)
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": img_b64
                }
            })
            valid_count += 1

    if valid_count == 0 and not user_notes:
        raise ValueError("Bạn cần nhập ít nhất Tin nhắn đặt hàng/Ghi chú HOẶC File ảnh sản phẩm!")

    cat_list = ", ".join([f"'{c}'" for c in sub_dict['categories']])
    feat_list = ", ".join([f"'{c}'" for c in sub_dict['features']])
    mat_list = ", ".join([f"'{c}'" for c in sub_dict['materials']])
    hl_list = ", ".join([f"'{c}'" for c in sub_dict['highlights']])
    strap_list = ", ".join([f"'{c}'" for c in sub_dict['strap_materials']])
    sole_list = ", ".join([f"'{c}'" for c in sub_dict['sole_materials']])
    lining_list = ", ".join([f"'{c}'" for c in sub_dict['inner_linings']])
    insole_list = ", ".join([f"'{c}'" for c in sub_dict['insole_surfaces']])
    toe_list = ", ".join([f"'{c}'" for c in sub_dict['toe_shapes']])
    bottom_list = ", ".join([f"'{c}'" for c in sub_dict['bottom_parts']])
    outfit_list = ", ".join([f"'{c}'" for c in sub_dict['outfit_matches']])
    usage_list = ", ".join([f"'{c}'" for c in sub_dict['usages']])
    sup_list = ", ".join([f"'{c}'" for c in sub_dict['suppliers']])

    prompt = f"""Bạn là chuyên gia phân tích và chuẩn hóa dữ liệu sản phẩm giày da và phụ kiện của Hiệu giày Hải Nancy.
Hãy quan sát kỹ các hình ảnh sản phẩm được cung cấp (ảnh sản phẩm, tem hộp, nhãn mác, đế...) và kết hợp với ghi chú / đoạn chat của người dùng để trả về JSON chuẩn xác:

QUY TẮC BẮT BUỘC VỀ GHI CHÚ CỦA NGƯỜI DÙNG (ƯU TIÊN SỐ 1 TUYỆT ĐỐI):
1. Nhận diện Mã sản phẩm gốc / Mã xưởng:
   - Nếu trong ghi chú có mã (ví dụ: 'JHA165' hoặc '8918'): BẮT BUỘC DÙNG ĐÚNG MÃ ĐÓ LÀM TIỀN TỐ GỐC, TUYỆT ĐỐI KHÔNG TỰ BỊA THÊM SỐ TỪ ẢNH (như 1650460).
   - Mã biến thể màu: Ghép mã gốc + ký tự màu HNC (Đen -> 'JHA165D', Nâu -> 'JHA165N', Bò -> 'JHA165B', Kem -> 'JHA165K', Trắng -> 'JHA165T', Vàng -> 'JHA165V', Xám -> 'JHA165X').

2. BẮT BUỘC TÁCH ĐỦ TẤT CẢ CÁC MÀU THÀNH TỪNG SẢN PHẨM TRONG JSON ARRAY:
   - Nếu trong ghi chú có nhắc đến NHIỀU MÀU (ví dụ: 'Đen e còn... Nâu sz từ...'), BẮT BUỘC TẠO ĐỦ CÁC OBJECT SẢN PHẨM TƯƠNG ỨNG CHO TỪNG MÀU trong JSON Array (kể cả trong ảnh chỉ chụp 1 màu đơn).
   - Ví dụ: Ghi chú có 'Đen' và 'Nâu' -> BẮT BUỘC trả về mảng 2 object: 1 cho Đen (JHA165D) và 1 cho Nâu (JHA165N).

3. Bóc tách dải size và số lượng (unroll size list lặp lại theo số lượng):
   - Cú pháp nhân số lượng: '39/2đ 40/2đ 41/2đ 42/2đ' -> sizes = ["39", "39", "40", "40", "41", "41", "42", "42"]
   - Cú pháp viết tắt xưởng nam: '889901123' -> sizes = ["38", "38", "39", "39", "40", "41", "41", "42", "43"]
   - Cú pháp viết tắt xưởng nữ: '55677890' -> sizes = ["35", "35", "36", "37", "37", "38", "39", "40"]
   - Cú pháp dải size: 'sz từ 38-42' hoặc '38-42' -> sizes = ["38", "39", "40", "41", "42"]
   - Nếu không có ghi chú số lượng size cụ thể: nam mặc định ["38", "39", "40", "41", "42", "43"], nữ mặc định ["35", "36", "37", "38", "39"].

DỮ LIỆU BẮT BUỘC KHÓA (CHỈ ĐƯỢC CHỌN TỪ DANH SÁCH DƯỚI ĐÂY):
- category_name: Chọn 1 trong [{cat_list}]
- feature: Chọn 1 trong [{feat_list}]
- brand: Chọn 'Hải Nancy' hoặc 'Yen Leather' (mặc định 'Hải Nancy')
- material: Chọn 1 trong [{mat_list}] (mặc định 'da bò' nếu là đồ da)
- highlight: Chọn 1 trong [{hl_list}]
- strap_material: Chọn 1 trong [{strap_list}]
- sole_material: Chọn 1 trong [{sole_list}]
- inner_lining: Chọn 1 trong [{lining_list}]
- insole_surface: Chọn 1 trong [{insole_list}]
- toe_shape: Chọn 1 trong [{toe_list}]
- bottom_part: Chọn 1 trong [{bottom_list}]
- outfit_match: Chọn 1 trong [{outfit_list}]
- usage: Chọn 1 trong [{usage_list}]
- supplier: Khớp với 1 trong [{sup_list}] nếu người dùng có ghi chú, hoặc điền theo ghi chú.

QUY TẮC MÀU SẮC & MÃ SẢN PHẨM:
- product_color: Tên màu sắc tiếng Việt (ví dụ: 'Đen', 'Nâu', 'Bò', 'Kem', 'Trắng', 'Vàng', 'Xám', 'Xanh', 'Đỏ')
- color_code: Ký tự màu chuẩn HNC ('D': Đen, 'N': Nâu, 'B': Bò, 'K': Kem, 'T': Trắng, 'V': Vàng, 'X': Xám)
- product_code: Mã biến thể. Ghép [Mã xưởng/Mã cha] + [color_code].
- product_name: Tên sản phẩm thương mại chuẩn SEO (Ví dụ: 'Giày Tây Nam Da Bò Hải Nancy JHA165D').
- purchase_price: Giá mua (số nguyên) lấy từ ghi chú hoặc OCR tem. Mặc định 0 nếu không có.
- product_price: Giá bán niêm yết (số nguyên). Mặc định nếu mua 300k thì bán ~600k-700k.
- invoice_price: Giá hóa đơn (số nguyên). Thường bằng hoặc cao hơn giá mua 1 ít.
- unit: 'Đôi' (cho giày/dép/sandal) hoặc 'Cái' (cho ví/thắt lưng/túi).
- origin: 'Việt Nam'

GHI CHÚ BỔ SUNG TỪ NGƯỜI DÙNG:
\"\"\"{user_notes}\"\"\"

Hãy trả về duy nhất 1 JSON Array chứa các object sản phẩm có đầy đủ các trường trên."""

    parts.append({"text": prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    # Kiểm SSL đầy đủ; Python.org trên Mac có thể thiếu kho chứng chỉ → dùng certifi trong venv (18/10)
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()

    preferred_models = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash"
    ]
    raw_text = None
    used_model = None

    for model_name in preferred_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"  # khoá đi qua header, không nằm trong URL (lọt log)
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key}
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    if raw_text:
                        used_model = model_name
                        break
            except urllib.error.HTTPError as http_err:
                err_msg = http_err.read().decode("utf-8", errors="ignore")
                if http_err.code in [503, 429] and attempt == 0:
                    time.sleep(2)
                    continue
                break
            except Exception:
                break
        if raw_text:
            break

    if not raw_text:
        raise RuntimeError("Không nhận được phản hồi từ tất cả các mô hình Gemini Multimodal API.")

    if HAS_RICH:
        console.print(f"[dim green]⚡ Đã phân tích thành công bằng mô hình: [bold cyan]{used_model}[/bold cyan][/dim green]")
    else:
        print(f"⚡ Đã phân tích thành công bằng mô hình: {used_model}")

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)

    parsed = json.loads(raw_text)
    if isinstance(parsed, dict):
        raw_products = [parsed]
    elif isinstance(parsed, list):
        raw_products = [p for p in parsed if isinstance(p, dict)]
    else:
        raw_products = []

    products = []
    for data in raw_products:
        data.setdefault('brand', 'Hải Nancy')
        data.setdefault('unit', 'Đôi')
        data.setdefault('origin', 'Việt Nam')
        data.setdefault('purchase_price', 0)
        data.setdefault('product_price', 0)
        data.setdefault('invoice_price', 0)

        # Xác định giới tính
        cat_lower = str(data.get('category_name', '')).lower()
        if 'nữ' in cat_lower or 'gót' in cat_lower or 'búp bê' in cat_lower or 'xuồng' in cat_lower:
            data['gender'] = 'female'
        elif 'ví' in cat_lower or 'thắt lưng' in cat_lower or 'túi' in cat_lower or 'ba lô' in cat_lower:
            data['gender'] = 'unisex'
            data['unit'] = 'Cái'
        else:
            data['gender'] = 'male'

        # Chuẩn hóa dải size thông qua parser chuyên biệt
        raw_sz = data.get('sizes')
        data['sizes'] = parse_vietnamese_shoe_sizes(raw_sz, data['gender'])
        products.append(data)

    return products


def check_and_enrich_product(product, product_info_map):
    """Kiểm tra mã sản phẩm đã tồn tại trong SANPHAM chưa để tự động kích hoạt chế độ Restock và lấy giá/tên chuẩn."""
    pcode = str(product.get('product_code', '')).strip().upper()
    product['product_code'] = pcode

    if pcode in product_info_map:
        product['is_restock'] = True
        existing = product_info_map[pcode]
        product['existing_info'] = existing

        # BẮT BUỘC ĐỒNG BỘ 100% THÔNG TIN GỐC TỪ SHEET SANPHAM KHI LÀ RESTOCK
        if existing.get('product_name'):
            product['product_name'] = str(existing['product_name']).strip()
        if existing.get('product_color'):
            product['product_color'] = str(existing['product_color']).strip()
        if existing.get('supplier'):
            product['supplier'] = str(existing['supplier']).strip()

        # Lấy đúng Giá bán gốc từ SANPHAM
        if existing.get('product_price') is not None and str(existing.get('product_price')).strip() != '':
            try:
                p_val = str(existing['product_price']).replace(',', '').replace('.', '').strip()
                if p_val.isdigit():
                    product['product_price'] = int(p_val)
                else:
                    product['product_price'] = int(float(existing['product_price']))
            except Exception:
                pass

        # Lấy đúng Giá mua gốc từ SANPHAM
        if existing.get('purchase_price') is not None and str(existing.get('purchase_price')).strip() != '':
            try:
                p_val = str(existing['purchase_price']).replace(',', '').replace('.', '').strip()
                if p_val.isdigit():
                    product['purchase_price'] = int(p_val)
                else:
                    product['purchase_price'] = int(float(existing['purchase_price']))
            except Exception:
                pass

        # Lấy đúng Giá hóa đơn gốc từ SANPHAM
        if existing.get('invoice_price') is not None and str(existing.get('invoice_price')).strip() != '':
            try:
                p_val = str(existing['invoice_price']).replace(',', '').replace('.', '').strip()
                if p_val.isdigit():
                    product['invoice_price'] = int(p_val)
                else:
                    product['invoice_price'] = int(float(existing['invoice_price']))
            except Exception:
                pass
    else:
        product['is_restock'] = False

    return product


def interactive_review_and_edit_batch(products, sub_dict, product_info_map):
    """Giao diện Terminal hiển thị rõ ràng từng sản phẩm, nổi bật phím bấm [1-9] và hỗ trợ Restock."""
    total = len(products)
    confirmed_products = []

    idx = 0
    while idx < total:
        data = products[idx]
        data = check_and_enrich_product(data, product_info_map)
        is_restock = data.get('is_restock', False)

        while True:
            os.system('clear' if os.name == 'posix' else 'cls')

            size_display_text = format_size_display(data.get('sizes', []))
            price_buy = f"{int(data.get('purchase_price', 0)):,}"
            price_sell = f"{int(data.get('product_price', 0)):,}"
            price_inv = f"{int(data.get('invoice_price', 0)):,}"

            if is_restock:
                title_text = f"📦 [SẢN PHẨM {idx+1}/{total}] NHẬP THÊM HÀNG VỀ (MÃ ĐÃ CÓ TRONG SANPHAM)"
                border_color = "bold cyan"
            else:
                title_text = f"🆕 [SẢN PHẨM {idx+1}/{total}] TẠO MỚI SẢN PHẨM & NHẬP KHO (52 CỘT CHUẨN)"
                border_color = "bold green"

            table = Table(title=title_text, border_style=border_color, show_header=True)
            table.add_column("PHÍM", style="bold bright_yellow", min_width=6, justify="center")
            table.add_column("TRƯỜNG DỮ LIỆU", style="bold bright_cyan", min_width=24)
            table.add_column("GIÁ TRỊ HIỆN TẠI", style="bold white", min_width=45)

            if is_restock:
                table.add_row("[1]", "Mã sản phẩm (product_code)", f"[bold green]{data.get('product_code', '')}[/bold green]  [italic yellow](Đã có trong SANPHAM)[/italic yellow]")
                table.add_row("[2]", "Tên sản phẩm (product_name)", data.get('product_name', ''))
                table.add_row("[3]", "Màu sắc", data.get('product_color', ''))
                table.add_row("[4]", "Giá mua / Giá bán", f"Mua: {price_buy}đ  ➔  Bán: {price_sell}đ (HĐ: {price_inv}đ)")
                table.add_row("[5]", "Dải Size nhập đợt này", size_display_text)
            else:
                attrs_preview = f"{data.get('material', '')}, {data.get('sole_material', '')}, Mũi {data.get('toe_shape', '')}, {data.get('bottom_part', '')}, Lót {data.get('inner_lining', '')}"
                table.add_row("[1]", "Mã sản phẩm (product_code)", f"[bold green]{data.get('product_code', '')}[/bold green]")
                table.add_row("[2]", "Tên sản phẩm (product_name)", data.get('product_name', ''))
                table.add_row("[3]", "Tên ngành hàng", f"[bold yellow]{data.get('category_name', '')}[/bold yellow]")
                table.add_row("[4]", "Màu sắc & Mã màu", f"{data.get('product_color', '')} (Mã màu: {data.get('color_code', '')})")
                table.add_row("[5]", "Nhà cung cấp (NCC)", data.get('supplier', ''))
                table.add_row("[6]", "Giá mua / Giá bán", f"Mua: {price_buy}đ  ➔  Bán: {price_sell}đ (HĐ: {price_inv}đ)")
                table.add_row("[7]", "Dải Size nhập đợt này", size_display_text)
                table.add_row("[8]", "Đặc điểm / Kiểu buộc", data.get('feature', ''))
                table.add_row("[9]", "Thuộc tính cấu tạo", attrs_preview)

            if HAS_RICH:
                console.print(table)
                if is_restock:
                    console.print("[dim italic yellow]📌 Chế độ Restock: Chỉ tạo các dòng trong tab NHAP (KHO trống, SL 1). Không tạo thêm dòng SANPHAM.[/dim italic yellow]\n")
                else:
                    console.print("[dim italic green]📌 Chế độ Mới: Tạo 1 dòng 52 cột ở tab SANPHAM + Tạo các dòng size ở tab NHAP.[/dim italic green]\n")

                console.print("[bold green]👉 Nhấn [ENTER] [/bold green]: Xác nhận sản phẩm này & Tiếp tục")
                if is_restock:
                    console.print("[bold yellow]👉 Gõ [1 - 5] [/bold yellow]: Chỉnh sửa trường tương ứng")
                else:
                    console.print("[bold yellow]👉 Gõ [1 - 9] [/bold yellow]: Chỉnh sửa trường tương ứng")
                console.print("[bold cyan]👉 Gõ [S]     [/bold cyan]: Bỏ qua sản phẩm này (Skip)")
                console.print("[bold red]👉 Gõ [C]     [/bold red]: Hủy bỏ toàn bộ tiến trình")
                choice = Prompt.ask("\n[bold bright_white]Lựa chọn của bạn[/bold bright_white]", default="")
            else:
                print(f"\n[ENTER] Xác nhận | Gõ số để sửa | [S] Bỏ qua | [C] Hủy")
                choice = input("Lựa chọn của bạn: ").strip()

            if choice == "":
                confirmed_products.append(data)
                break
            elif choice.upper() == "S":
                break
            elif choice.upper() == "C":
                return None
            elif choice == "1":
                val = input(f"✏️ Nhập Mã sản phẩm mới [{data.get('product_code')}]: ").strip()
                if val:
                    data['product_code'] = val.upper()
                    data = check_and_enrich_product(data, product_info_map)
                    is_restock = data.get('is_restock', False)
            elif choice == "2":
                val = input(f"✏️ Nhập Tên sản phẩm mới [{data.get('product_name')}]: ").strip()
                if val: data['product_name'] = val
            elif choice == "3" and not is_restock:
                print("\nDanh sách Ngành Hàng hợp lệ:")
                for i, cat in enumerate(sub_dict['categories'], 1):
                    print(f"  [{i:2d}] {cat}")
                c_idx = input(f"Chọn số thứ tự ngành hàng [1-{len(sub_dict['categories'])}]: ").strip()
                if c_idx.isdigit() and 1 <= int(c_idx) <= len(sub_dict['categories']):
                    data['category_name'] = sub_dict['categories'][int(c_idx)-1]
            elif choice == "3" and is_restock:
                val = input(f"✏️ Màu sắc [{data.get('product_color')}]: ").strip()
                if val: data['product_color'] = val
            elif choice == "4" and not is_restock:
                c_name = input(f"✏️ Tên màu sắc [{data.get('product_color')}]: ").strip()
                c_code = input(f"✏️ Ký tự mã màu [{data.get('color_code')}]: ").strip()
                if c_name: data['product_color'] = c_name
                if c_code: data['color_code'] = c_code.upper()
            elif (choice == "4" and is_restock) or (choice == "6" and not is_restock):
                p_buy = input(f"✏️ Giá mua [{data.get('purchase_price')}]: ").strip().replace(',', '').replace('.', '')
                p_sell = input(f"✏️ Giá bán [{data.get('product_price')}]: ").strip().replace(',', '').replace('.', '')
                p_inv = input(f"✏️ Giá hóa đơn [{data.get('invoice_price')}]: ").strip().replace(',', '').replace('.', '')
                if p_buy.isdigit(): data['purchase_price'] = int(p_buy)
                if p_sell.isdigit(): data['product_price'] = int(p_sell)
                if p_inv.isdigit(): data['invoice_price'] = int(p_inv)
            elif (choice == "5" and is_restock) or (choice == "7" and not is_restock):
                val = input(f"✏️ Nhập dải size (VD: 889901123, 39/2đ 40/2đ, 38-42, 38,39...): ").strip()
                if val: data['sizes'] = parse_vietnamese_shoe_sizes(val, data.get('gender', 'male'))
            elif choice == "5" and not is_restock:
                val = input(f"✏️ Nhà cung cấp [{data.get('supplier')}]: ").strip()
                if val: data['supplier'] = val
            elif choice == "8" and not is_restock:
                val = input(f"✏️ Đặc điểm / Kiểu buộc [{data.get('feature')}]: ").strip()
                if val: data['feature'] = val
            elif choice == "9" and not is_restock:
                mat = input(f"✏️ Chất liệu [{data.get('material')}]: ").strip()
                sole = input(f"✏️ Chất liệu đế [{data.get('sole_material')}]: ").strip()
                toe = input(f"✏️ Dáng mũi [{data.get('toe_shape')}]: ").strip()
                if mat: data['material'] = mat
                if sole: data['sole_material'] = sole
                if toe: data['toe_shape'] = toe

        idx += 1

    return confirmed_products


def col_to_letter(col_idx):
    """Chuyển đổi 0-indexed column sang chữ cái Excel/Google Sheets (0->A, 22->W, 51->AZ, etc.)."""
    return gspread.utils.rowcol_to_a1(1, col_idx + 1).rstrip('0123456789')


NHAP_COT_CAN = ('Ngày chứng từ (*)', 'Số chứng từ (*)', 'product_code', 'product_color', 'KHO', 'item_size', 'Số lượng (*)', 'FSKU')


def batch_commit_ingestion(loader, confirmed_products):
    """Ghi hàng loạt sản phẩm mới vào SANPHAM và toàn bộ dòng nhập kho vào NHAP (Quét Header Động)."""
    from tools.tach_cot_sanpham import tach as tach_cot
    if not confirmed_products:
        return {'sp_added': 0, 'restock_count': 0, 'nhap_rows': 0}
    for data in confirmed_products:
        data['product_code'] = clean_code(data.get('product_code', '')).upper()

    today_str = datetime.now().strftime("%d/%m/%Y")
    doc_no = f"PN_{datetime.now().strftime('%Y%m%d_%H%M')}"

    # 1. Chuẩn bị dòng cho SANPHAM (chỉ cho các sản phẩm mới)
    df_sp, _ = loader.load_sheet('SANPHAM')
    start_sp_row = len(df_sp) + 1
    var_idx_sp, map_sp = DynamicHeaderScanner.scan_data_headers(df_sp)
    num_sp_cols = len(df_sp.columns)
    head_sp = [str(x).strip() for x in df_sp.iloc[var_idx_sp].values]

    # Cột theo tên hàng 2 (luật 4) — thiếu cột thì DỪNG, không ghi sang cột khác
    idx_parent = DynamicHeaderScanner.get_col_idx(map_sp, 'parent_product_code', 'Mã hàng hóa cha')
    idx_cat = DynamicHeaderScanner.get_col_idx(map_sp, 'Tên Ngành Hàng', 'Tên nhóm hàng hóa', 'category_name')
    idx_feat = DynamicHeaderScanner.get_col_idx(map_sp, 'Đặc điểm', 'feature')
    idx_brand = DynamicHeaderScanner.get_col_idx(map_sp, 'Thương hiệu', 'brand')
    idx_gender = DynamicHeaderScanner.get_col_idx(map_sp, 'Giới tính', 'gender')
    idx_sizeplus = DynamicHeaderScanner.get_col_idx(map_sp, 'Size Plus', 'size_plus')
    idx_size = DynamicHeaderScanner.get_col_idx(map_sp, 'Size', 'Kích thước')
    idx_mat = DynamicHeaderScanner.get_col_idx(map_sp, 'Chất liệu', 'material')
    idx_hl = DynamicHeaderScanner.get_col_idx(map_sp, 'Nhấn mạnh', 'highlight')
    idx_strap = DynamicHeaderScanner.get_col_idx(map_sp, 'Chất liệu quai: ', 'Chất liệu quai:', 'Chất liệu quai')
    idx_sole = DynamicHeaderScanner.get_col_idx(map_sp, 'Chất liệu đế: ', 'Chất liệu đế:', 'Chất liệu đế')
    idx_lining = DynamicHeaderScanner.get_col_idx(map_sp, 'Lót trong: ', 'Lót trong:', 'Lót trong')
    idx_insole = DynamicHeaderScanner.get_col_idx(map_sp, 'Mặt lót đế: ', 'Mặt lót đế:', 'Mặt lót đế')
    idx_toe = DynamicHeaderScanner.get_col_idx(map_sp, 'Dáng giày mũi: ', 'Dáng giày mũi:', 'Dáng giày mũi')
    idx_bottom = DynamicHeaderScanner.get_col_idx(map_sp, 'Phần dưới giày: ', 'Phần dưới giày:', 'Phần dưới giày')
    idx_outfit = DynamicHeaderScanner.get_col_idx(map_sp, 'Kết hợp trang phục: ', 'Kết hợp trang phục:', 'Kết hợp trang phục')
    idx_usage = DynamicHeaderScanner.get_col_idx(map_sp, 'Sử dụng: ', 'Sử dụng:', 'Sử dụng')
    idx_bonus = DynamicHeaderScanner.get_col_idx(map_sp, 'Bonus:', 'Bonus')
    idx_con_name = DynamicHeaderScanner.get_col_idx(map_sp, 'CON_NAME')
    idx_con_des = DynamicHeaderScanner.get_col_idx(map_sp, 'CON_DES')
    idx_code = DynamicHeaderScanner.get_col_idx(map_sp, 'product_code', 'Mã sản phẩm')
    idx_name = DynamicHeaderScanner.get_col_idx(map_sp, 'product_name', 'Tên sản phẩm')
    idx_price = DynamicHeaderScanner.get_col_idx(map_sp, 'product_price', 'Giá bán')
    idx_unit = DynamicHeaderScanner.get_col_idx(map_sp, 'product_unit', 'ĐVT')
    idx_origin = DynamicHeaderScanner.get_col_idx(map_sp, 'product_origin', 'Xuất xứ')
    idx_color = DynamicHeaderScanner.get_col_idx(map_sp, 'product_color', 'Màu sắc')
    idx_cat_id = DynamicHeaderScanner.get_col_idx(map_sp, 'product_category_id', 'Mã danh mục')
    idx_desc = DynamicHeaderScanner.get_col_idx(map_sp, 'product_description', 'Mô tả sản phẩm')
    idx_purch = DynamicHeaderScanner.get_col_idx(map_sp, 'purchase_price', 'Giá mua')
    idx_inv = DynamicHeaderScanner.get_col_idx(map_sp, 'invoice_price', 'Đơn giá')
    idx_sup = DynamicHeaderScanner.get_col_idx(map_sp, 'supplier', 'Nhà cung cấp')

    can = {'Tên Ngành Hàng': idx_cat, 'Đặc điểm': idx_feat, 'Thương hiệu': idx_brand, 'Giới tính': idx_gender, 'Size Plus': idx_sizeplus,
           'Size': idx_size, 'Chất liệu': idx_mat, 'Nhấn mạnh': idx_hl, 'Chất liệu quai:': idx_strap, 'Chất liệu đế:': idx_sole,
           'Lót trong:': idx_lining, 'Mặt lót đế:': idx_insole, 'Dáng giày mũi:': idx_toe, 'Phần dưới giày:': idx_bottom,
           'Kết hợp trang phục:': idx_outfit, 'Sử dụng:': idx_usage, 'Bonus:': idx_bonus, 'CON_NAME': idx_con_name, 'CON_DES': idx_con_des,
           'product_code': idx_code, 'product_name': idx_name, 'product_price': idx_price, 'product_unit': idx_unit, 'product_color': idx_color}
    thieu = [n for n, i in can.items() if i is None]
    if thieu:
        raise RuntimeError(f"Tab SANPHAM thiếu cột {thieu} (hàng 2) — đã DỪNG, chưa ghi.")
    _, map_nhap_truoc = DynamicHeaderScanner.scan_data_headers(loader.load_sheet('NHAP')[0].head(4))
    thieu = [n for n in NHAP_COT_CAN if n not in map_nhap_truoc]
    if thieu:
        raise RuntimeError(f"Tab NHAP thiếu cột {thieu} — đã DỪNG, chưa ghi SANPHAM / NHAP.")
    # Cột đếm trùng mã (=countif) không có tên: nhận theo công thức ở dòng dữ liệu cuối, không thấy thì bỏ qua
    idx_countif = None
    if start_sp_row > 3 and loader.spreadsheet is not None:
        f_last = loader.spreadsheet.worksheet('SANPHAM').row_values(start_sp_row - 1, value_render_option='FORMULA')
        idx_countif = next((i for i, f in enumerate(f_last) if str(f).strip().lower().startswith('=countif(')), None)

    # Dynamic Column Letters
    c_cat = col_to_letter(idx_cat) if idx_cat is not None else 'B'
    c_feat = col_to_letter(idx_feat) if idx_feat is not None else 'C'
    c_brand = col_to_letter(idx_brand) if idx_brand is not None else 'D'
    c_gender = col_to_letter(idx_gender) if idx_gender is not None else 'E'
    c_sizeplus = col_to_letter(idx_sizeplus) if idx_sizeplus is not None else 'F'
    c_size = col_to_letter(idx_size) if idx_size is not None else 'G'
    c_mat = col_to_letter(idx_mat) if idx_mat is not None else 'H'
    c_hl = col_to_letter(idx_hl) if idx_hl is not None else 'I'
    c_strap = col_to_letter(idx_strap) if idx_strap is not None else 'J'
    c_sole = col_to_letter(idx_sole) if idx_sole is not None else 'K'
    c_lining = col_to_letter(idx_lining) if idx_lining is not None else 'L'
    c_insole = col_to_letter(idx_insole) if idx_insole is not None else 'M'
    c_toe = col_to_letter(idx_toe) if idx_toe is not None else 'N'
    c_bottom = col_to_letter(idx_bottom) if idx_bottom is not None else 'O'
    c_outfit = col_to_letter(idx_outfit) if idx_outfit is not None else 'P'
    c_usage = col_to_letter(idx_usage) if idx_usage is not None else 'Q'
    c_bonus = col_to_letter(idx_bonus) if idx_bonus is not None else 'R'
    c_con_name = col_to_letter(idx_con_name) if idx_con_name is not None else 'T'
    c_con_des = col_to_letter(idx_con_des) if idx_con_des is not None else 'U'
    c_code = col_to_letter(idx_code) if idx_code is not None else 'W'
    c_unit = col_to_letter(idx_unit) if idx_unit is not None else 'Z'

    sp_new_rows = []
    sp_added_count = 0
    for data in confirmed_products:
        if not data.get('is_restock', False):
            cur_sp_row = start_sp_row + sp_added_count
            row_values = [""] * num_sp_cols

            if idx_parent is not None: row_values[idx_parent] = f'=LEFT({c_code}{cur_sp_row}; LEN({c_code}{cur_sp_row})-1)'
            if idx_cat is not None: row_values[idx_cat] = data.get('category_name', '')
            if idx_feat is not None: row_values[idx_feat] = data.get('feature', '')
            if idx_brand is not None: row_values[idx_brand] = data.get('brand', 'Hải Nancy')
            if idx_gender is not None: row_values[idx_gender] = f'=IF(REGEXMATCH({c_cat}{cur_sp_row}; "nam"); "male"; "female")'
            if idx_sizeplus is not None: row_values[idx_sizeplus] = ""
            if idx_size is not None: row_values[idx_size] = f'=IF({c_unit}{cur_sp_row}="Đôi"; CONCATENATE(if({c_gender}{cur_sp_row}="male";"38,39,40,41,42,43";if({c_gender}{cur_sp_row}="female";"35,36,37,38,39,40";""));if({c_sizeplus}{cur_sp_row}="";"";",");{c_sizeplus}{cur_sp_row});"")'
            if idx_mat is not None: row_values[idx_mat] = data.get('material', 'da bò')
            if idx_hl is not None: row_values[idx_hl] = data.get('highlight', 'cao cấp')
            if idx_strap is not None: row_values[idx_strap] = data.get('strap_material', 'da bò cao cấp')
            if idx_sole is not None: row_values[idx_sole] = data.get('sole_material', 'cao su')
            if idx_lining is not None: row_values[idx_lining] = data.get('inner_lining', 'da heo')
            if idx_insole is not None: row_values[idx_insole] = data.get('insole_surface', 'mềm êm, có độ đàn hồi')
            if idx_toe is not None: row_values[idx_toe] = data.get('toe_shape', 'tròn')
            if idx_bottom is not None: row_values[idx_bottom] = data.get('bottom_part', 'gót 3cm')
            if idx_outfit is not None: row_values[idx_outfit] = data.get('outfit_match', 'tây, jean, khaki...')
            if idx_usage is not None: row_values[idx_usage] = data.get('usage', 'hằng ngày, dự tiệc...')
            if idx_bonus is not None: row_values[idx_bonus] = ""
            if idx_countif is not None and idx_countif < num_sp_cols: row_values[idx_countif] = f'=countif(${c_code}:${c_code};{c_code}{cur_sp_row})'
            if idx_con_name is not None: row_values[idx_con_name] = f'=TEXTJOIN(" ";TRUE;{c_cat}{cur_sp_row};{c_feat}{cur_sp_row};{c_brand}{cur_sp_row};{c_mat}{cur_sp_row};{c_hl}{cur_sp_row};{c_code}{cur_sp_row})'  # bỏ ô trống (bộ chuẩn 29/10, khớp web ghepTen)
            if idx_con_des is not None: row_values[idx_con_des] = f'=CONCATENATE({c_con_name}{cur_sp_row};". ";${c_strap}$2;{c_strap}{cur_sp_row};". ";${c_sole}$2;{c_sole}{cur_sp_row};". ";${c_lining}$2;{c_lining}{cur_sp_row};". ";${c_insole}$2;{c_insole}{cur_sp_row};". ";${c_toe}$2;{c_toe}{cur_sp_row};". ";${c_bottom}$2;{c_bottom}{cur_sp_row};". ";${c_outfit}$2;{c_outfit}{cur_sp_row};". ";${c_usage}$2;{c_usage}{cur_sp_row};". ";{c_bonus}{cur_sp_row})'
            if idx_code is not None: row_values[idx_code] = data.get('product_code', '')
            if idx_name is not None: row_values[idx_name] = f'={c_con_name}{cur_sp_row}'
            if idx_price is not None: row_values[idx_price] = data.get('product_price', 0)
            if idx_unit is not None: row_values[idx_unit] = data.get('unit', 'Đôi')
            if idx_origin is not None: row_values[idx_origin] = data.get('origin', 'Việt Nam')
            if idx_color is not None: row_values[idx_color] = data.get('product_color', '')
            if idx_cat_id is not None: row_values[idx_cat_id] = f'=index(SUB!$B$2:$B$126;match({c_cat}{cur_sp_row};SUB!$A$2:$A$126;0);1)'
            if idx_desc is not None: row_values[idx_desc] = f'={c_con_des}{cur_sp_row}'
            if idx_purch is not None: row_values[idx_purch] = data.get('purchase_price', 0)
            if idx_inv is not None: row_values[idx_inv] = data.get('invoice_price', 0)
            if idx_sup is not None: row_values[idx_sup] = data.get('supplier', '')
            # Bộ chuẩn 29/10 (chạy song song): cột mới BA–BO điền từ chữ cột cũ vừa ghi, cùng bảng gộp GĐ B (tools/tach_cot_sanpham.py)
            for ten, (moi, _, tt) in tach_cot([str(x) for x in row_values], head_sp).items():
                if tt == 'dien' and ten in head_sp:
                    row_values[head_sp.index(ten)] = moi
            if 'gioi_tinh' in head_sp:  # cột cũ "Giới tính" là công thức REGEXMATCH(ngành; "nam") → cùng luật
                row_values[head_sp.index('gioi_tinh')] = 'nam' if re.search('nam', str(data.get('category_name', ''))) else 'nữ'

            sp_new_rows.append(row_values)
            sp_added_count += 1

    if sp_new_rows:
        if not loader.insert_rows_with_exact_range('SANPHAM', sp_new_rows, start_sp_row):
            raise RuntimeError("Ghi tab SANPHAM thất bại — đã DỪNG, chưa ghi tab NHAP.")

    # 2. Chuẩn bị dòng cho NHAP (cho TẤT CẢ các sản phẩm)
    df_nhap, _ = loader.load_sheet('NHAP')
    start_nhap_row = len(df_nhap) + 1
    var_idx_nhap, map_nhap = DynamicHeaderScanner.scan_data_headers(df_nhap)
    num_nhap_cols = len(df_nhap.columns)

    idx_n_date = DynamicHeaderScanner.get_col_idx(map_nhap, 'Ngày chứng từ (*)')
    idx_n_doc = DynamicHeaderScanner.get_col_idx(map_nhap, 'Số chứng từ (*)')
    idx_n_code = DynamicHeaderScanner.get_col_idx(map_nhap, 'product_code')
    idx_n_color = DynamicHeaderScanner.get_col_idx(map_nhap, 'product_color')
    idx_n_kho = DynamicHeaderScanner.get_col_idx(map_nhap, 'KHO')
    idx_n_size = DynamicHeaderScanner.get_col_idx(map_nhap, 'item_size')
    idx_n_qty = DynamicHeaderScanner.get_col_idx(map_nhap, 'Số lượng (*)')
    idx_n_fsku = DynamicHeaderScanner.get_col_idx(map_nhap, 'FSKU')
    thieu = [n for n in NHAP_COT_CAN if n not in map_nhap]
    if thieu:  # đã kiểm trước khi ghi SANPHAM; còn thiếu là tiêu đề NHAP vừa bị đổi
        raise RuntimeError(f"Tab NHAP thiếu cột {thieu} — đã ghi SANPHAM, DỪNG trước khi ghi NHAP.")
    idx_n_madong = DynamicHeaderScanner.get_col_idx(map_nhap, 'ma_dong')  # P0: chỉ ghi khi Sheet có cột (khớp bot rowSrcFields_)
    idx_n_nguon = DynamicHeaderScanner.get_col_idx(map_nhap, 'nguon')
    idx_n_price = DynamicHeaderScanner.get_col_idx(map_nhap, 'don_gia_phieu')  # giá nhập SANPHAM khi chưa có giá phiếu (anh Kha 19/10, khớp bot appendNhap_)

    c_n_kho = col_to_letter(idx_n_kho) if idx_n_kho is not None else 'E'
    c_n_code = col_to_letter(idx_n_code) if idx_n_code is not None else 'C'
    c_n_size = col_to_letter(idx_n_size) if idx_n_size is not None else 'F'

    nhap_new_rows = []
    nhap_count = 0
    for data in confirmed_products:
        pcode = data.get('product_code', '')
        pcolor = data.get('product_color', '')
        sizes = data.get('sizes', [''])
        for sz in sizes:
            cur_nhap_row = start_nhap_row + nhap_count
            row = [""] * num_nhap_cols
            if idx_n_date is not None: row[idx_n_date] = today_str
            if idx_n_doc is not None: row[idx_n_doc] = doc_no
            if idx_n_code is not None: row[idx_n_code] = pcode
            if idx_n_color is not None: row[idx_n_color] = pcolor
            if idx_n_kho is not None: row[idx_n_kho] = ""
            if idx_n_size is not None: row[idx_n_size] = sz
            if idx_n_qty is not None: row[idx_n_qty] = 1
            if idx_n_fsku is not None: row[idx_n_fsku] = f'=CONCATENATE({c_n_kho}{cur_nhap_row}; {c_n_code}{cur_nhap_row}; {c_n_size}{cur_nhap_row})'
            if idx_n_price is not None and parse_number(data.get('purchase_price')) > 0: row[idx_n_price] = int(parse_number(data.get('purchase_price')))
            if idx_n_madong is not None: row[idx_n_madong] = f"MAC-{MAC_RUN_ID}#{nhap_count + 1}"  # duy nhất theo lần chạy (LuatKho.maDong 'mac')
            if idx_n_nguon is not None: row[idx_n_nguon] = 'mac'
            nhap_new_rows.append(row)
            nhap_count += 1

    if nhap_new_rows:
        if not loader.insert_rows_with_exact_range('NHAP', nhap_new_rows, start_nhap_row):
            raise RuntimeError(f"Ghi tab NHAP thất bại — tab SANPHAM ĐÃ ghi {sp_added_count} sản phẩm mới, cần kiểm tra và bổ sung {len(nhap_new_rows)} dòng NHAP.")

    restock_count = len(confirmed_products) - sp_added_count
    return {
        'sp_added': sp_added_count,
        'restock_count': restock_count,
        'nhap_rows': len(nhap_new_rows)
    }


def read_multiline_input(prompt_text, hint_text=""):
    """Hứng trọn vẹn nhiều dòng văn bản khi dán từ Zalo/Xưởng vào Terminal."""
    if HAS_RICH:
        console.print(f"\n[bold yellow]{prompt_text}[/bold yellow]")
        if hint_text:
            console.print(f"[dim]{hint_text}[/dim]")
    else:
        print(f"\n{prompt_text}")
        if hint_text:
            print(hint_text)

    lines = []
    while True:
        try:
            line = input()
            stripped = line.strip()
            # Nếu người dùng bấm Enter ngay từ đầu khi chưa nhập gì -> Bỏ qua
            if not stripped and not lines:
                break
            # Nếu gõ lệnh kết thúc
            if stripped.lower() in ('xong', 'end', 'done', 'q'):
                break
            # Nếu bấm Enter trên dòng trống sau khi đã có nội dung dán -> Kết thúc nhập
            if not stripped and lines:
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break
    return "\n".join(lines).strip()


@sync_hint_after
def process_ai_product_ingestion(loader):
    """Quy trình toàn diện AI Tự Động Nhập Hàng Từ Hình Ảnh (Hỗ trợ Đa Sản Phẩm & Restock)."""
    if HAS_RICH:
        console.print(Panel("""📸 [bold white]AI TỰ ĐỘNG NHẬP SẢN PHẨM MỚI TỪ HÌNH ẢNH (GEMINI MULTIMODAL ENGINE)[/bold white]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👉 Hỗ trợ dán tin nhắn Zalo / Ghi chú xưởng (Mã gốc, dải size, màu sắc, giá...).
👉 Hỗ trợ kéo thả 1 hoặc NHIỀU ảnh sản phẩm / tem mác / mẫu khác nhau.
👉 Tự động nhận diện Sản Phẩm MỚI (52 cột) hoặc ĐÃ CÓ (Chỉ nhập thêm kho)!""", border_style="bold green"))
    else:
        print("\n=== AI TỰ ĐỘNG NHẬP SẢN PHẨM MỚI TỪ HÌNH ẢNH ===")

    # 1. Nhập thông tin / Tin nhắn đặt hàng / Ghi chú (Hỗ trợ dán nhiều dòng)
    user_notes = read_multiline_input(
        "✍️ Dán tin nhắn đặt hàng / Ghi chú (Mã, màu, size, giá, NCC...):",
        "(Dán xong bấm Enter thêm 1 lần hoặc gõ 'xong' để tiếp tục | Bấm Enter ngay nếu không có ghi chú)"
    )

    # 2. Nhập đường dẫn ảnh (Bổ trợ kiểu dáng / chất liệu)
    if HAS_RICH:
        img_input = Prompt.ask("\n[bold cyan]📸 Kéo thả 1 hoặc nhiều File Ảnh (hoặc Enter nếu không có ảnh)[/bold cyan]", default="").strip()
    else:
        img_input = input("\n📸 Kéo thả 1 hoặc nhiều File Ảnh (hoặc Enter nếu không có ảnh): ").strip()

    img_paths = parse_image_paths(img_input) if img_input else []
    if not user_notes and not img_paths:
        msg = "❌ Bạn cần nhập ít nhất Tin nhắn đặt hàng/Ghi chú HOẶC File ảnh sản phẩm để AI phân tích!"
        if HAS_RICH: console.print(f"[bold red]{msg}[/bold red]")
        else: print(msg)
        return

    if img_paths:
        if HAS_RICH:
            console.print(f"[dim]📸 Đã nhận diện [bold cyan]{len(img_paths)} ảnh bổ trợ[/bold cyan]: {', '.join([os.path.basename(p) for p in img_paths])}[/dim]")

    # 3. Tải từ điển SUB, thông tin SANPHAM và phân tích AI
    if HAS_RICH:
        console.print("\n[bold green]🔍 Đang tải dữ liệu chuẩn từ Google Sheet & Gọi Gemini AI phân tích...[/bold green]")
    else:
        print("\n🔍 Đang tải dữ liệu chuẩn từ Google Sheet & Gọi Gemini AI phân tích...")

    try:
        sub_dict = load_sub_dictionary(loader)
        product_info_map = get_product_info_map(loader)
        analyzed_products = analyze_product_with_gemini(img_paths, user_notes, sub_dict)
    except Exception as e:
        msg = f"❌ Lỗi khi phân tích AI: {e}"
        if HAS_RICH: console.print(Panel(msg, title="[bold red]LỖI AI VISION[/bold red]", border_style="red"))
        else: print(msg)
        return

    if not analyzed_products:
        msg = "⚠️ Gemini AI không tìm thấy dữ liệu sản phẩm nào từ hình ảnh!"
        if HAS_RICH: console.print(f"[yellow]{msg}[/yellow]")
        else: print(msg)
        return

    # 4. Review và Chỉnh sửa tương tác theo lô
    confirmed_products = interactive_review_and_edit_batch(analyzed_products, sub_dict, product_info_map)
    if not confirmed_products:
        if HAS_RICH: console.print("[yellow]⚠️ Đã hủy bỏ thao tác nhập sản phẩm.[/yellow]")
        else: print("⚠️ Đã hủy bỏ thao tác nhập sản phẩm.")
        return

    # 5. Ghi vào SANPHAM & NHAP
    if HAS_RICH:
        console.print("\n[bold green]📝 Đang ghi dữ liệu vào tab SANPHAM và tab NHAP trên Google Sheet...[/bold green]")
    else:
        print("\n📝 Đang ghi dữ liệu vào tab SANPHAM và tab NHAP trên Google Sheet...")

    try:
        stats = batch_commit_ingestion(loader, confirmed_products)
        success_msg = f"""🎉 TẠO SẢN PHẨM & NHẬP KHO THÀNH CÔNG!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Tab SANPHAM: Đã thêm mới [bold green]{stats['sp_added']} sản phẩm[/bold green] (52 cột công thức đầy đủ).
✅ Nhập thêm  : [bold cyan]{stats['restock_count']} sản phẩm đã có sẵn[/bold cyan] (Bỏ qua SANPHAM để tránh trùng).
✅ Tab NHAP   : Đã tự động tạo [bold yellow]{stats['nhap_rows']} dòng nhập kho[/bold yellow] theo từng size (KHO để trống, SL = 1)."""
        if HAS_RICH:
            console.print(Panel(success_msg, title="[bold green]HOÀN TẤT 100%[/bold green]", border_style="green"))
        else:
            print(f"\n{success_msg}\n")
    except Exception as e:
        msg = f"❌ Lỗi khi ghi Google Sheet: {e}"
        if HAS_RICH: console.print(Panel(msg, title="[bold red]LỖI GHI SHEET[/bold red]", border_style="red"))
        else: print(msg)


def print_main_menu():
    """Hiển thị Giao diện Menu Chính theo 6 Nền Tảng với Màu Sáng Cao Cấp"""
    menu_text = """===================================================================
             🚀 [bold white]HNC CONTROL CENTER - MAC MINI M4 ENGINE[/bold white]
  [yellow]Dự phòng — không chạy cùng lúc với nút trên web (/admin/san, Xuất MISA)[/yellow]
===================================================================
  [1] [bold #FFD700]🏷️ TEM & KHO (in tem mã hàng, đồng bộ mã hàng vào Kho 15E / Kho Y3C)[/bold #FFD700]
  [2] [bold #FF6E40]🛍️  SHOPEE[/bold #FF6E40]
  [3] [bold #00E5FF]🎵 TIKTOK[/bold #00E5FF] [bold #FF1744]SHOP[/bold #FF1744]
  [4] [bold #29B6F6]📊 MISA eSHOP[/bold #29B6F6]
  [5] [bold #A7FFEB]📁 QUẢN LÝ MEDIA (TƯ LIỆU SẢN PHẨM)[/bold #A7FFEB]
  [6] [bold #69F0AE]📸 AI TỰ ĐỘNG THÊM HÀNG HOÁ MỚI TỪ ẢNH[/bold #69F0AE]
  [7] 🧭 Chế độ sổ gốc: sổ bán / kho / tồn / hàng hoá — DỰ PHÒNG (Mac, bot ghi Sheet) ↔ WEB (web ghi)
  [8] ↩️ Trả hàng / Đổi hàng (dự phòng khi web hỏng — cùng dòng như web / bot)
  -----------------------------------------------------------------
  [0] [bold red]❌ Thoát ứng dụng[/bold red]
==================================================================="""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="bright_white"))
    else:
        print(menu_text)


def print_submenu_website():
    """Hiển thị Sub-Menu 1: Tem & Kho (tác vụ website cũ đã ẩn)"""
    menu_text = """-------------------------------------------------------------------
             [bold #FFD700]🏷️ SUB-MENU: TEM & KHO[/bold #FFD700]
-------------------------------------------------------------------
  [dim](Đã ẩn [1] đăng SP web cũ, [2] tồn web cũ, [3] cào ảnh web cũ — web mới đọc thẳng Sheet)[/dim]
  [4] 🖨️  In Tem Mã Hàng theo kho / phiếu (IN_15E.csv / IN_Y3C.csv + IN.csv; đánh dấu khi in xong)
  [5] 🔄 Đồng Bộ Mã Hàng Mới Vào Kho 15E / Kho Y3C (chỉ dự phòng — bot đã tự thêm lúc ghi phiếu nhập kho)
  -----------------------------------------------------------------
  [0] ⬅️  Quay lại Menu chính
-------------------------------------------------------------------"""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="#FFD700"))
    else:
        print(menu_text)


def print_submenu_shopee():
    """Hiển thị Sub-Menu 2: Shopee"""
    menu_text = """-------------------------------------------------------------------
             [bold #FF6E40]🛍️  SUB-MENU: SHOPEE[/bold #FF6E40]
-------------------------------------------------------------------
  [1] 🛒 Xuất File Đăng Hàng Hoá Mới (Shopee Mass Upload)
  [2] ⚡ Xuất File Cập Nhật Giá Bán / Tồn Kho (Shopee Mass Update)
  -----------------------------------------------------------------
  [0] ⬅️  Quay lại Menu chính
-------------------------------------------------------------------"""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="#FF6E40"))
    else:
        print(menu_text)


def print_submenu_tiktok():
    """Hiển thị Sub-Menu 3: TikTok Shop"""
    menu_text = """-------------------------------------------------------------------
             [bold #00E5FF]🎵[/bold #00E5FF] [bold #FF1744]SUB-MENU: TIKTOK SHOP[/bold #FF1744]
-------------------------------------------------------------------
  [1] 🎵 Xuất File Đăng Hàng Hoá Mới (TikTok Mass Upload - 38 Cột chuẩn)
  [2] ⚡ Xuất File Cập Nhật (TikTok Mass Update: Giá Bán, Tồn Kho hoặc Tất cả)
  -----------------------------------------------------------------
  [0] ⬅️  Quay lại Menu chính
-------------------------------------------------------------------"""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="#00E5FF"))
    else:
        print(menu_text)


def print_submenu_misa():
    """Hiển thị Sub-Menu 4: MISA eShop"""
    menu_text = """-------------------------------------------------------------------
             [bold #29B6F6]📊 SUB-MENU: MISA eSHOP[/bold #29B6F6]
-------------------------------------------------------------------
  [1] 📊 Xuất File Danh Mục Hàng Hoá (MISA: Mẫu → Mã hàng)
  [2] 📥 Xuất File Phiếu Nhập Kho (MISA, tách Kho 15E / Kho Y3C, giá theo hoá đơn mua hàng)
  -----------------------------------------------------------------
  [0] ⬅️  Quay lại Menu chính
-------------------------------------------------------------------"""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="#29B6F6"))
    else:
        print(menu_text)


def print_submenu_media():
    """Hiển thị Sub-Menu 5: Quản Lý Media & Tư Liệu Sản Phẩm"""
    menu_text = """-------------------------------------------------------------------
             [bold #A7FFEB]📁 SUB-MENU: QUẢN LÝ MEDIA & TƯ LIỆU[/bold #A7FFEB]
-------------------------------------------------------------------
  [1] 🔄 Gom File Tự Động (Từ Photoroom & Downloads) + Đồng Bộ Sheet
  [2] 📊 Chỉ Quét & Đồng Bộ Trạng Thái Media Lên Sheet (Không di chuyển file)
  -----------------------------------------------------------------
  [0] ⬅️  Quay lại Menu chính
-------------------------------------------------------------------"""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="#A7FFEB"))
    else:
        print(menu_text)


def handle_submenu_website(loader):
    """Xử lý điều hướng trong Sub-menu Website Hải Nancy"""
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_submenu_website()
        
        if HAS_RICH:
            sub_choice = Prompt.ask("[bold cyan]Mời chọn tác vụ [0/4/5][/bold cyan]", default="0")
        else:
            sub_choice = input("Mời chọn tác vụ [0/4/5]: ").strip()

        if sub_choice == "0":
            break
        elif sub_choice in ("1", "2", "3"):
            # Website cũ (WEB_PRODUCTS / WEB_STOCK / cào ảnh): ẩn từ 15/10/2026, giữ code tới khi chuyển tên miền xong rồi xoá.
            # Tác vụ gốc: process_export_task(1 | 5 | 11, loader).
            msg = "ℹ️ Tác vụ website cũ đã ẩn — web mới giayhainancy.vn đọc thẳng Sheet."
            if HAS_RICH: console.print(f"[bold yellow]{msg}[/bold yellow]")
            else: print(msg)
        elif sub_choice == "4":
            process_export_task(10, loader)
        elif sub_choice == "5":
            process_export_task(9, loader)
        else:
            if HAS_RICH: console.print("[bold red]❌ Lựa chọn không hợp lệ![/bold red]")

        if HAS_RICH: Prompt.ask("\n[dim]Nhấn Enter để quay lại Sub-Menu...[/dim]")
        else: input("\nNhấn Enter để quay lại Sub-Menu...")


def handle_submenu_shopee(loader):
    """Xử lý điều hướng trong Sub-menu Shopee"""
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_submenu_shopee()
        
        if HAS_RICH:
            sub_choice = Prompt.ask("[bold yellow]Mời chọn tác vụ Shopee [0-2][/bold yellow]", default="0")
        else:
            sub_choice = input("Mời chọn tác vụ Shopee [0-2]: ").strip()

        if sub_choice == "0":
            break
        elif sub_choice == "1":
            process_export_task(2, loader)
        elif sub_choice == "2":
            process_export_task(6, loader)
        else:
            if HAS_RICH: console.print("[bold red]❌ Lựa chọn không hợp lệ![/bold red]")

        if HAS_RICH: Prompt.ask("\n[dim]Nhấn Enter để quay lại Sub-Menu...[/dim]")
        else: input("\nNhấn Enter để quay lại Sub-Menu...")


def handle_submenu_tiktok(loader):
    """Xử lý điều hướng trong Sub-menu TikTok Shop"""
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_submenu_tiktok()
        
        if HAS_RICH:
            sub_choice = Prompt.ask("[bold magenta]Mời chọn tác vụ TikTok [0-2][/bold magenta]", default="0")
        else:
            sub_choice = input("Mời chọn tác vụ TikTok [0-2]: ").strip()

        if sub_choice == "0":
            break
        elif sub_choice == "1":
            process_export_task(3, loader)
        elif sub_choice == "2":
            process_export_task(7, loader)
        else:
            if HAS_RICH: console.print("[bold red]❌ Lựa chọn không hợp lệ![/bold red]")

        if HAS_RICH: Prompt.ask("\n[dim]Nhấn Enter để quay lại Sub-Menu...[/dim]")
        else: input("\nNhấn Enter để quay lại Sub-Menu...")


def handle_submenu_misa(loader):
    """Xử lý điều hướng trong Sub-menu MISA eShop"""
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_submenu_misa()
        
        if HAS_RICH:
            sub_choice = Prompt.ask("[bold blue]Mời chọn tác vụ MISA [0-2][/bold blue]", default="0")
        else:
            sub_choice = input("Mời chọn tác vụ MISA [0-2]: ").strip()

        if sub_choice == "0":
            break
        elif sub_choice == "1":
            process_export_task(4, loader)
        elif sub_choice == "2":
            process_export_task(8, loader)
        else:
            if HAS_RICH: console.print("[bold red]❌ Lựa chọn không hợp lệ![/bold red]")

        if HAS_RICH: Prompt.ask("\n[dim]Nhấn Enter để quay lại Sub-Menu...[/dim]")
        else: input("\nNhấn Enter để quay lại Sub-Menu...")


def handle_submenu_media(loader):
    """Xử lý điều hướng trong Sub-menu Quản Lý Media"""
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_submenu_media()
        
        if HAS_RICH:
            sub_choice = Prompt.ask("[bold #A7FFEB]Mời chọn tác vụ Media [0-2][/bold #A7FFEB]", default="0")
        else:
            sub_choice = input("Mời chọn tác vụ Media [0-2]: ").strip()

        if sub_choice == "0":
            break
        elif sub_choice == "1":
            process_media_management(loader, auto_ingest=True)
        elif sub_choice == "2":
            process_media_management(loader, auto_ingest=False)
        else:
            if HAS_RICH: console.print("[bold red]❌ Lựa chọn không hợp lệ![/bold red]")

        if HAS_RICH: Prompt.ask("\n[dim]Nhấn Enter để quay lại Sub-Menu...[/dim]")
        else: input("\nNhấn Enter để quay lại Sub-Menu...")


def set_meta(loader, pairs):
    """Ghi các khoá vào tab META (key | value | updated_at) theo tên cột; chưa có dòng thì thêm (cùng luật bot metaSet_)."""
    ws = loader.spreadsheet.worksheet('META')
    rows = ws.get_all_values()
    head = [str(h).strip() for h in rows[0]]
    for c in ('key', 'value', 'updated_at'):
        if c not in head:
            raise RuntimeError(f"Tab META thiếu cột {c}")
    ck, cv, cu = head.index('key'), head.index('value'), head.index('updated_at')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    nxt = len(rows) + 1
    cells = []
    for k, v in pairs.items():
        r = next((i + 1 for i in range(1, len(rows)) if len(rows[i]) > ck and rows[i][ck].strip() == k), None)
        if r is None:
            r = nxt
            nxt += 1
            cells.append(gspread.Cell(r, ck + 1, k))
        cells += [gspread.Cell(r, cv + 1, v), gspread.Cell(r, cu + 1, now)]
    ws.update_cells(cells, value_input_option='RAW')
    loader._che_do = None
    loader.__dict__.pop('_modes', None)


# 4 sổ đổi được — cùng bảng với bot CHE_DO_SO (số 2k-1 = về Dự phòng, 2k = sang Web)
CHE_DO_SO = [
    {'key': 'che_do', 'ten': 'Sổ bán', 'moc': {'du_phong_hang': 'BAN'}, 'tu': 'du_phong_tu'},
    {'key': 'che_do_kho', 'ten': 'Sổ kho', 'moc': {'du_phong_nhap_hang': 'NHAP', 'du_phong_xuat_hang': 'XUAT'}, 'tu': 'du_phong_kho_tu'},
    {'key': 'che_do_ton', 'ten': 'Tồn kho', 'moc': {}, 'tu': 'du_phong_ton_tu'},
    {'key': 'che_do_hh', 'ten': 'Hàng hoá + giá', 'moc': {}, 'tu': 'du_phong_hh_tu'},
]


@sync_hint_after
def tra_doi_hang(loader):
    """[8] Trả / Đổi hàng dự phòng (26/10, luật 15): cùng dòng như web nút Đổi / Trả và bot tra_hang — tools/tra_doi.py."""
    from tools.tra_doi import TraDoi
    kieu = input("[1] Trả hàng (khách trả, nhập lại kho)  [2] Đổi hàng (trả + bán mã khác)  [Enter] thôi: ").strip()
    if kieu not in ('1', '2'):
        return
    if loader.che_do_kho() == 'web' or (kieu == '2' and loader.che_do() == 'web'):
        print("⛔ Sổ kho / sổ bán đang ở Web — đổi trả trên app (nút Đổi / Trả). Web hỏng: đổi sổ về Dự phòng ở [7] rồi làm lại.")
        return
    kho = {'1': '15E', '2': 'Y3C'}.get(input("Kho [1] 15E  [2] Y3C: ").strip(), '')
    if not kho:
        print("❌ Chưa chọn kho.")
        return
    t = TraDoi(loader, MAC_RUN_ID)
    try:
        code = input("Mã hàng KHÁCH TRẢ (vd TH2040D): ").strip().upper()
        size = input("Size: ").strip()
        qty = int(input("Số lượng [1]: ").strip() or 1)
        chu = input("Hàng của hộ nào? [Enter] = tự tìm theo lần bán gần nhất, hoặc gõ 15E / Y3C: ").strip().upper()
        t.tra(code, size, kho, qty, chu)
        if kieu == '2':
            code2 = input("Mã hàng KHÁCH LẤY (vd TH2040D): ").strip().upper()
            size2 = input("Size: ").strip()
            gia = int(''.join(ch for ch in input("Giá bán [Enter] = giá SANPHAM: ") if ch.isdigit()) or 0)
            tt = {'1': 'Tiền mặt', '2': 'Chuyển khoản', '3': 'Thẻ'}.get(input("Thanh toán [1] Tiền mặt  [2] Chuyển khoản  [3] Thẻ: ").strip(), 'Tiền mặt')
            t.ban(code2, size2, kho, qty, gia, tt)
            # Tiền chênh (web bb3d576, 27/10): = tổng giá món mới − giá phiếu gốc. Món mới rẻ hơn → mặc định KHÔNG hoàn;
            # chỉ Chủ được chọn hoàn. Hoàn hay không chỉ ghi ở phiếu đổi trả trên web (xu_ly), Sheet không thêm dòng nào.
            goc = int(''.join(ch for ch in input(f"Giá phiếu gốc món trả [Enter] = giá SANPHAM {t.sp(code)['gia']:,}đ: ".replace(',', '.')) if ch.isdigit()) or t.sp(code)['gia'])
            moi = (gia or t.sp(code2)['gia']) * qty
            chenh = moi - goc * qty
            if chenh > 0:
                print(f"💰 Khách trả thêm {chenh:,}đ".replace(',', '.'))
            elif chenh < 0:
                hoan = input(f"Món mới rẻ hơn {-chenh:,}đ. Hoàn tiền phần thừa? (chỉ Chủ) [y/Enter = không hoàn]: ".replace(',', '.')).strip().lower() == 'y'
                t.ghi_chu.append(("💸 HOÀN " if hoan else "Không hoàn ") + f"{-chenh:,}đ phần thừa".replace(',', '.') +
                                 " — Sheet không ghi dòng nào cho khoản này; web lên lại thì Chủ ghi vào phiếu Đổi / Trả trên app (xu_ly = "
                                 + ("hoan_tien" if hoan else "khong_hoan") + ").")
    except (RuntimeError, ValueError) as e:
        print(f"⛔ {e}")
        return
    print("\nSẽ ghi:")
    for mo_ta, _ in t.ops:
        print("  • " + mo_ta)
    for g in t.ghi_chu:
        print("  " + g)
    if input("Ghi vào Sheet? (y/Enter = không): ").strip().lower() != 'y':
        print("Chưa ghi gì.")
        return
    try:
        t.ghi()
        print(f"✅ Đã ghi {len(t.ops)} thay đổi.")
    except RuntimeError as e:
        print(f"⛔ {e} — kiểm Sheet trước khi làm lại (có thể đã ghi một phần).")


def change_che_do(loader):
    """Menu [7]: xem / đổi 4 sổ (bán, kho, tồn, hàng hoá) Dự phòng ↔ Web, gõ lại số mới đổi — cùng luật lệnh Zalo "che do"."""
    lab = lambda v: 'WEB (web ghi)' if v == 'web' else 'DỰ PHÒNG (Mac / bot ghi Sheet)'
    for m in CHE_DO_SO:
        print(f"🧭 {m['ten']}: {lab(loader.meta_mode(m['key']))}")
    if SPREADSHEET_ID != SPREADSHEET_ID_THAT:
        print("   (SHEET BẢN THỬ)")
    print('  ' + ' · '.join(f"[{2 * i + 1}] {m['ten']} → Dự phòng  [{2 * i + 2}] → Web" for i, m in enumerate(CHE_DO_SO)))
    pick = input("Chọn số (Enter = giữ nguyên): ").strip()
    if not pick.isdigit() or not 1 <= int(pick) <= 2 * len(CHE_DO_SO):
        print("👌 Giữ nguyên.")
        return
    m, want = CHE_DO_SO[(int(pick) - 1) // 2], ('master' if int(pick) % 2 == 1 else 'web')
    if want == loader.meta_mode(m['key']):
        print("👌 Đang đúng chế độ đó rồi.")
        return
    if input(f"⚠️ Gõ lại {pick} để đổi {m['ten']} sang {want.upper()}: ").strip() != pick:
        print("👌 Không đổi.")
        return
    luc = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pairs = {m['key']: want, m['key'] + '_luc': luc, m['key'] + '_boi': f'mac {MAC_RUN_ID}'}
    if want == 'master':  # mốc như web: dòng ghi sau mốc được web nhập bù
        for k, tab in m['moc'].items():
            v = loader.spreadsheet.worksheet(tab).get_all_values()
            ic = [str(h).strip() for h in v[0]].index('product_code')
            pairs[k] = str(max(i + 1 for i, r in enumerate(v) if i == 0 or (len(r) > ic and r[ic].strip())))
        pairs[m['tu']] = luc
    set_meta(loader, pairs)
    loader.__dict__.pop('_modes', None)
    loader._mark_sync('META')
    print(f"✅ Đã đổi {m['ten']}: {want.upper()}")


def warn_ton_web(loader):
    """P3: tồn tính ở web mà web còn dòng đang chép → tồn Sheet có thể thiếu; hỏi trước khi xuất tồn sàn / MISA."""
    if loader.is_google_api and loader.che_do_ton() == 'web':
        n = loader.cho_chep()
        if n > 0:
            return input(f"⚠️ Tồn tính ở web, còn {n} dòng web đang chép sang Sheet — tồn có thể thiếu. Vẫn làm tiếp? (y/Enter = không): ").strip().lower() == 'y'
    return True


MAC_LOCK_PATH = '/tmp/hnc_main_py.lock'
MAC_RUN_ID = datetime.now().strftime('%y%m%d-%H%M%S')  # mã lần mở menu → ma_dong MAC-<lần chạy>#n


def acquire_mac_lock():
    """Khoá chống chạy menu Mac 2 cửa sổ cùng lúc (P0 mục 5): khoá file, tự nhả khi tắt menu / máy khởi động lại."""
    import fcntl
    fh = open(MAC_LOCK_PATH, 'w')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def main():
    lock = acquire_mac_lock()
    if lock is None:
        print("⛔ Menu HNC đang mở ở cửa sổ khác — dùng cửa sổ đó (tránh 2 cửa sổ cùng ghi Sheet).")
        return
    loader = EngineDataLoader()
    if SPREADSHEET_ID != SPREADSHEET_ID_THAT:
        print(f"🧪 ĐANG DÙNG SHEET BẢN THỬ ({SPREADSHEET_ID}) — không phải sổ thật.")
    if loader.is_google_api and loader.che_do() == 'web':
        print("🌐 Chế độ Web: sổ bán ở web — menu Mac không ghi tab BAN (kho / nhập / MISA vẫn như cũ).")

    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_main_menu()
        
        if HAS_RICH:
            mode_str = f"🌐 Google Sheets Connected: [bold green]{SPREADSHEET_NAME}[/bold green]" if loader.is_google_api else "[bold red]❌ Chưa kết nối Google Sheets API[/bold red]"
            console.print(f"[dim]Trạng thái: {mode_str}[/dim]")
            choice_input = Prompt.ask("[bold cyan]Mời chọn tác vụ [0-6][/bold cyan]", default="0")
        else:
            choice_input = input("Mời chọn tác vụ [0-6]: ").strip()

        if choice_input == "0":
            if HAS_RICH:
                console.print("[bold green]Cảm ơn bạn đã sử dụng HNC Control Center! Tạm biệt! 👋[/bold green]")
            else:
                print("Cảm ơn bạn đã sử dụng HNC Control Center! Tạm biệt! 👋")
            sys.exit(0)
        elif choice_input == "1":
            handle_submenu_website(loader)
        elif choice_input in ("2", "3", "4") and not warn_ton_web(loader):
            continue
        elif choice_input == "2":
            handle_submenu_shopee(loader)
        elif choice_input == "3":
            handle_submenu_tiktok(loader)
        elif choice_input == "4":
            handle_submenu_misa(loader)
        elif choice_input == "5":
            handle_submenu_media(loader)
        elif choice_input == "8":
            tra_doi_hang(loader)
            input("\nNhấn Enter để quay lại Menu chính...")
        elif choice_input == "7":
            change_che_do(loader)
            input("\nNhấn Enter để quay lại Menu chính...")
        elif choice_input == "6":
            process_ai_product_ingestion(loader)
            if HAS_RICH: Prompt.ask("\n[dim]Nhấn Enter để quay lại Menu chính...[/dim]")
            else: input("\nNhấn Enter để quay lại Menu chính...")
        else:
            if HAS_RICH:
                console.print("[bold red]❌ Lựa chọn không hợp lệ! Vui lòng nhập số từ 0 đến 6.[/bold red]")
                Prompt.ask("[dim]Nhấn Enter để tiếp tục...[/dim]")
            else:
                input("❌ Lựa chọn không hợp lệ! Nhấn Enter để tiếp tục...")


if __name__ == "__main__":
    main()
