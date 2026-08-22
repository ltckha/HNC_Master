#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===================================================================
             🚀 HNC CONTROL CENTER - MAC MINI M4 ENGINE
===================================================================
Automated E-Commerce & Inventory Management System for HNC Master
Installed at: /Users/khan/Developer/HNC_Master
Synced with Google Drive: /Users/khan/Library/CloudStorage/GoogleDrive-ltckha@gmail.com/My Drive/HNC_Master
"""

import os
import sys
import re
import glob
import time
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

# Paths Configuration
LOCAL_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def detect_gdrive_dir():
    """Tự động nhận diện thư mục Google Drive linh hoạt trên máy macOS"""
    default_path = "/Users/khan/Library/CloudStorage/GoogleDrive-ltckha@gmail.com/My Drive/HNC_Master"
    if os.path.exists(default_path):
        return default_path
    
    # Dò tìm thư mục GoogleDrive-* trong CloudStorage của user
    home_cloud = os.path.expanduser("~/Library/CloudStorage")
    if os.path.exists(home_cloud):
        for item in os.listdir(home_cloud):
            if item.startswith("GoogleDrive-"):
                cand = os.path.join(home_cloud, item, "My Drive", "HNC_Master")
                if os.path.exists(cand):
                    return cand
    return LOCAL_BASE_DIR

GDRIVE_DIR = detect_gdrive_dir()

CREDENTIALS_PATH = os.path.join(LOCAL_BASE_DIR, "credentials.json")
if not os.path.exists(CREDENTIALS_PATH) and os.path.exists(os.path.join(GDRIVE_DIR, "credentials.json")):
    CREDENTIALS_PATH = os.path.join(GDRIVE_DIR, "credentials.json")

if os.path.exists(os.path.join(GDRIVE_DIR, "HNC_Templates")):
    TEMPLATES_DIR = os.path.join(GDRIVE_DIR, "HNC_Templates")
else:
    TEMPLATES_DIR = os.path.join(LOCAL_BASE_DIR, "HNC_Templates")

if os.path.exists(GDRIVE_DIR):
    EXPORT_DIR = os.path.join(GDRIVE_DIR, "HNC_Exported_Files")
else:
    EXPORT_DIR = os.path.join(LOCAL_BASE_DIR, "HNC_Exported_Files")

os.makedirs(EXPORT_DIR, exist_ok=True)
SPREADSHEET_NAME = "HNC_Control_Center"

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


def safe_write_cell(ws, row, col, value):
    """Ghi dữ liệu an toàn vào ô openpyxl, bỏ qua nếu là MergedCell."""
    try:
        cell = ws.cell(row=row, column=col)
        if type(cell).__name__ != 'MergedCell':
            cell.value = value
    except Exception:
        pass


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

        for idx in range(min(5, len(df))):
            vals = [str(v).strip() for v in df.iloc[idx].values if pd.notna(v)]
            if 'product_code' in vals or 'item_size' in vals or 'get_images' in vals:
                var_row_idx = idx
                break

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
        self._init_connection()

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
            self.spreadsheet = self.gc.open(SPREADSHEET_NAME)
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

    def update_status(self, sheet_name, row_indices, col_idx, status_text_or_list):
        """Cập nhật chữ 'Done - YYYY-MM-DD HH:mm' hoặc danh sách trạng thái riêng từng dòng lên Google Sheet."""
        if not row_indices:
            return True

        if isinstance(status_text_or_list, list):
            status_list = status_text_or_list
        else:
            status_list = [status_text_or_list] * len(row_indices)

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
                        if i + 100 < len(cell_updates):
                            time.sleep(0.5)
                return True
            except Exception as e:
                print(f"[!] Lỗi khi ghi Google Sheet API ({sheet_name}): {e}")
        return False

    def update_batch_image_results(self, sheet_name, batch_records):
        """Batch update tất cả các dòng ảnh cào được vào Google Sheet (tránh vượt quota API)."""
        if not batch_records:
            return True

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
                    time.sleep(0.5)
                return True
            except Exception as e:
                print(f"[!] Lỗi khi batch update Google Sheet API: {e}")
        return False

    def append_rows_to_sheet(self, sheet_name, new_rows):
        """Append các dòng mới vào cuối bảng Google Sheet (với công thức USER_ENTERED)."""
        if not new_rows:
            return True

        if self.is_google_api:
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
                ws.append_rows(new_rows, value_input_option='USER_ENTERED')
                return True
            except Exception as e:
                print(f"[!] Lỗi khi append Google Sheet API ({sheet_name}): {e}")
        return False


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


def map_tiktok_attributes(sub_info):
    """Ánh xạ tự động các thuộc tính bổ sung của TikTok Shop từ tab SUB."""
    origin = "Việt Nam"

    # Chất liệu
    mat_raw = str(sub_info.get('Chất liệu', '')).lower()
    if 'bò' in mat_raw or 'da' in mat_raw:
        material = 'Da'
    elif 'vải' in mat_raw or 'lưới' in mat_raw or 'bố' in mat_raw:
        material = 'Vải'
    else:
        material = 'Da'

    # Dịp
    use_raw = str(sub_info.get('Sử dụng:', '')).lower()
    if 'tiệc' in use_raw or 'cưới' in use_raw:
        occasion = 'Lễ cưới'
    elif 'công sở' in use_raw or 'kinh doanh' in use_raw:
        occasion = 'Kinh doanh'
    else:
        occasion = 'Thông thường'

    season = "Bốn mùa"

    # Hình dáng ngón chân
    toe_raw = str(sub_info.get('Mũi giày:', '')).lower()
    if 'nhọn' in toe_raw:
        toe_shape = 'Mũi nhọn'
    elif 'vuông' in toe_raw:
        toe_shape = 'Mũi vuông'
    elif 'hở' in toe_raw or 'xỏ ngón' in toe_raw:
        toe_shape = 'Mũi hở'
    else:
        toe_shape = 'Mũi tròn'

    # Chiều cao gót
    heel_raw = str(sub_info.get('Gót giày:', '')).lower()
    if '5' in heel_raw or '7' in heel_raw or 'cao' in heel_raw:
        heel_height = 'Gót vừa (3-5 cm)'
    elif '2' in heel_raw or '3' in heel_raw or 'thấp' in heel_raw:
        heel_height = 'Gót thấp (1-3 cm)'
    else:
        heel_height = 'Gót phẳng (1 cm trở xuống)'

    # Loại buộc
    feat_raw = str(sub_info.get('Đặc điểm', '')).lower()
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

                    product_map[pcode] = {
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

            if link_val and str(link_val).startswith("http") and "done" not in status_val.lower() and "no image" not in status_val.lower():
                if HAS_RICH:
                    console.print(f"🔎 Đang cào ảnh chuẩn cho dòng {rel_idx + 1} (Mã: {pcode_val}): {link_val}...")
                else:
                    print(f"🔎 Đang cào ảnh chuẩn cho dòng {rel_idx + 1} (Mã: {pcode_val}): {link_val}...")

                imgs = fetch_web_images(link_val, pcode_val)
                if imgs:
                    status_text = f"Done - {now_str}"
                    batch_records.append({
                        'row_idx': rel_idx,
                        'img_col_indices': img_col_indices,
                        'img_urls': imgs,
                        'status_col_idx': status_col_idx,
                        'status_text': status_text
                    })
                else:
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
        pending_row_indices = []
        pending_records = []

        for r in range(2, len(df_nhap)):
            row_data = df_nhap.iloc[r]
            st_val = row_data[status_col_idx] if status_col_idx is not None else None
            is_done = pd.notna(st_val) and str(st_val).strip().lower().startswith("done")
            if not is_done:
                pending_row_indices.append(r)
                rec = {}
                for k, idx in col_map_nhap.items():
                    rec[k] = row_data[idx] if idx < len(row_data) else ""
                pending_records.append(rec)

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
        exported_filepath = os.path.join(EXPORT_DIR, f"SHOPEE_UPDATE_{mode_label}_{timestamp_file}.xlsx")
        wb.save(exported_filepath)
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
            attrs = map_tiktok_attributes(sub_info)

            pic1 = str(row[col_map_sp.get('image_01')] if col_map_sp.get('image_01') is not None else row[col_map_sp.get('Pic 1', 0)] or '').strip()
            pic2 = str(row[col_map_sp.get('image_02', 0)] or '').strip()
            pic3 = str(row[col_map_sp.get('image_03', 0)] or '').strip()
            pic4 = str(row[col_map_sp.get('image_04', 0)] or '').strip()
            pic5 = str(row[col_map_sp.get('image_05', 0)] or '').strip()
            pic6 = str(row[col_map_sp.get('image_06', 0)] or '').strip()
            pic7 = str(row[col_map_sp.get('image_07', 0)] or '').strip()
            pic8 = str(row[col_map_sp.get('image_08', 0)] or '').strip()
            pic9 = str(row[col_map_sp.get('image_09', 0)] or '').strip()

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
                'pic1': pic1,
                'pic2': pic2,
                'pic3': pic3,
                'pic4': pic4,
                'pic5': pic5,
                'pic6': pic6,
                'pic7': pic7,
                'pic8': pic8,
                'pic9': pic9,
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
            warn_t = "⚠️ Template hiện tại không có cột số lượng tồn kho ('quantity'). Vui lòng dùng mẫu Kho hàng (Inventory) nếu muốn cập nhật tồn kho!"
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
                if pic1_col and pdata['pic1']: safe_write_cell(ws_tpl, r, pic1_col, pdata['pic1'])
                if pic2_col and pdata['pic2']: safe_write_cell(ws_tpl, r, pic2_col, pdata['pic2'])
                if pic3_col and pdata['pic3']: safe_write_cell(ws_tpl, r, pic3_col, pdata['pic3'])
                if pic4_col and pdata['pic4']: safe_write_cell(ws_tpl, r, pic4_col, pdata['pic4'])
                if pic5_col and pdata['pic5']: safe_write_cell(ws_tpl, r, pic5_col, pdata['pic5'])
                if pic6_col and pdata['pic6']: safe_write_cell(ws_tpl, r, pic6_col, pdata['pic6'])
                if pic7_col and pdata['pic7']: safe_write_cell(ws_tpl, r, pic7_col, pdata['pic7'])
                if pic8_col and pdata['pic8']: safe_write_cell(ws_tpl, r, pic8_col, pdata['pic8'])
                if pic9_col and pdata['pic9']: safe_write_cell(ws_tpl, r, pic9_col, pdata['pic9'])
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
        exported_filepath = os.path.join(EXPORT_DIR, f"TIKTOK_UPDATE_{mode_label}_{timestamp_file}.xlsx")
        wb.save(exported_filepath)
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
        if "done" not in status_val.lower():
            pending_row_indices.append(rel_idx)
            rec = {}
            for var_name, c_idx in col_map.items():
                rec[var_name] = row[c_idx] if pd.notna(row[c_idx]) else ""
            pending_records.append(rec)

    if not pending_records:
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

            pic1 = str(rec.get('image_01') or rec.get('Pic 1', '')).strip()
            pic2 = str(rec.get('image_02', '')).strip()
            pic3 = str(rec.get('image_03', '')).strip()
            pic4 = str(rec.get('image_04', '')).strip()
            pic5 = str(rec.get('image_05', '')).strip()
            pic6 = str(rec.get('image_06', '')).strip()
            pic7 = str(rec.get('image_07', '')).strip()
            pic8 = str(rec.get('image_08', '')).strip()
            pic9 = str(rec.get('image_09', '')).strip()

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

            pic1 = str(rec.get('image_01') or rec.get('Pic 1', '')).strip()
            pic2 = str(rec.get('image_02', '')).strip()
            pic3 = str(rec.get('image_03', '')).strip()
            pic4 = str(rec.get('image_04', '')).strip()
            pic5 = str(rec.get('image_05', '')).strip()
            pic6 = str(rec.get('image_06', '')).strip()
            pic7 = str(rec.get('image_07', '')).strip()
            pic8 = str(rec.get('image_08', '')).strip()
            pic9 = str(rec.get('image_09', '')).strip()

            # Lấy dải Size chuẩn từ cột Size
            all_sizes = unroll_sizes(rec.get('Size', ''))

            # Ánh xạ thuộc tính bổ sung TikTok
            attr_dict = map_tiktok_attributes(sub_info)

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
            desc = str(rec.get('product_description') or rec.get('CON_DES', '')).strip()
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

            row_num = 6
            for vrec in new_records:
                # Ghi dòng hàng hóa cha
                safe_write_cell(ws_new, row_num, 3, "Hàng hóa cha ")
                safe_write_cell(ws_new, row_num, 4, vrec['parent_code'])
                safe_write_cell(ws_new, row_num, 7, vrec['pname'])
                safe_write_cell(ws_new, row_num, 8, vrec['pprice'])
                safe_write_cell(ws_new, row_num, 9, vrec['punit'])
                safe_write_cell(ws_new, row_num, 11, "Không")
                safe_write_cell(ws_new, row_num, 12, vrec['brand'])
                safe_write_cell(ws_new, row_num, 13, vrec['hnc_cat'])
                safe_write_cell(ws_new, row_num, 15, vrec['weight'])
                safe_write_cell(ws_new, row_num, 19, 1)
                safe_write_cell(ws_new, row_num, 20, 0.5)
                safe_write_cell(ws_new, row_num, 22, '101-Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);')
                safe_write_cell(ws_new, row_num, 45, vrec['desc'])
                row_num += 1

                # Ghi các dòng hàng hóa con
                valid_sizes = [str(s).strip() for s in vrec['all_sizes'] if s and str(s).strip()]
                if valid_sizes:
                    for sz in valid_sizes:
                        sku = f"{vrec['pcode']}{sz}"
                        safe_write_cell(ws_new, row_num, 3, "Hàng hóa con theo thuộc tính")
                        safe_write_cell(ws_new, row_num, 4, sku)
                        safe_write_cell(ws_new, row_num, 5, sku)
                        safe_write_cell(ws_new, row_num, 6, vrec['parent_code'])
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
                    safe_write_cell(ws_new, row_num, 3, "Hàng hóa con theo thuộc tính")
                    safe_write_cell(ws_new, row_num, 4, sku)
                    safe_write_cell(ws_new, row_num, 5, sku)
                    safe_write_cell(ws_new, row_num, 6, vrec['parent_code'])
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

            row_up = 3
            for vrec in update_records:
                # Ghi dòng cha
                safe_write_cell(ws_up, row_up, 1, vrec['parent_code'])
                safe_write_cell(ws_up, row_up, 2, "")
                safe_write_cell(ws_up, row_up, 3, "")
                safe_write_cell(ws_up, row_up, 7, vrec['pname'])
                safe_write_cell(ws_up, row_up, 8, vrec['hnc_cat'])
                safe_write_cell(ws_up, row_up, 9, vrec['punit'])
                safe_write_cell(ws_up, row_up, 10, vrec['pprice'])
                safe_write_cell(ws_up, row_up, 11, 1)
                safe_write_cell(ws_up, row_up, 12, vrec['brand'] if vrec['brand'] else 'Hải nancy')
                safe_write_cell(ws_up, row_up, 13, vrec['weight'])
                safe_write_cell(ws_up, row_up, 16, 1)
                safe_write_cell(ws_up, row_up, 17, 0.5)
                safe_write_cell(ws_up, row_up, 18, '101 - Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);')
                row_up += 1

                # Ghi các dòng con thêm màu mới
                valid_sizes = [str(s).strip() for s in vrec['all_sizes'] if s and str(s).strip()]
                if valid_sizes:
                    for sz in valid_sizes:
                        sku = f"{vrec['pcode']}{sz}"
                        child_name = f"{vrec['pname']} ({vrec['pcolor']}/{sz})" if vrec['pcolor'] else f"{vrec['pname']} (Size {sz})"
                        safe_write_cell(ws_up, row_up, 1, sku)
                        safe_write_cell(ws_up, row_up, 2, vrec['parent_code'])
                        safe_write_cell(ws_up, row_up, 3, sku)
                        safe_write_cell(ws_up, row_up, 7, child_name)
                        safe_write_cell(ws_up, row_up, 9, vrec['punit'])
                        safe_write_cell(ws_up, row_up, 10, vrec['pprice'])
                        row_up += 1
                else:
                    sku = vrec['pcode']
                    child_name = f"{vrec['pname']} ({vrec['pcolor']})" if vrec['pcolor'] else vrec['pname']
                    safe_write_cell(ws_up, row_up, 1, sku)
                    safe_write_cell(ws_up, row_up, 2, vrec['parent_code'])
                    safe_write_cell(ws_up, row_up, 3, sku)
                    safe_write_cell(ws_up, row_up, 7, child_name)
                    safe_write_cell(ws_up, row_up, 9, vrec['punit'])
                    safe_write_cell(ws_up, row_up, 10, vrec['pprice'])
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
            raw_inv = sp_info.get('invoice_price', '')
            inv_num = parse_number(raw_inv)
            qty = parse_number(rec.get('Số lượng (*)') or rec.get('item_quantity', 0))

            kho_raw = str(rec.get('KHO', '')).strip().upper()

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
            row_status_list.append(f"Done - {now_str}")
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
            records_by_kho[kho_key].append(rec_valid)

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
                safe_write_cell(ws_tpl, row_num, 6, f"Nhập kho mua hàng từ {ten_dt}" if ten_dt else "Nhập kho mua hàng") # Cột F (6): Diễn giải
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
        product_map = get_product_info_map(loader)
        out_rows = []
        for rec in pending_records:
            pcode = str(rec.get('product_code', '')).strip()
            sz = str(rec.get('item_size', '')).strip()
            if sz.endswith('.0'): sz = sz[:-2]

            sp_info = product_map.get(pcode, {})
            pname = sp_info.get('product_name') or rec.get('Tên', '')
            pcolor = str(rec.get('product_color') or sp_info.get('product_color') or rec.get('Màu', '')).strip()
            scolor = f"{pcolor} (Size {sz})" if sz and pcolor else (pcolor or f"Size {sz}")

            # Số lượng tem in lấy từ cột Số lượng (*) hoặc item_quantity
            qty_raw = rec.get('item_quantity') or rec.get('Số lượng (*)') or rec.get('F6', 1)
            try:
                f6 = int(float(qty_raw))
            except Exception:
                f6 = 1

            code128 = f"{pcode}{sz}" if sz else pcode

            # Định dạng giá bán VND hiển thị đẹp (ví dụ: 450.000 đ)
            raw_price = sp_info.get('product_price') or rec.get('Giá', '')
            try:
                num_p = parse_number(raw_price)
                price_str = f"{int(num_p):,} đ".replace(",", ".") if num_p > 0 else str(raw_price)
            except Exception:
                price_str = str(raw_price)

            qr = sp_info.get('web_url') or rec.get('QR code', '')

            out_rows.append({
                'QR code': qr,
                'Tên': pname,
                'Màu': pcolor,
                'Size': sz,
                'Size Color': scolor,
                'F6': f6,
                'Code128': code128,
                'Gía': price_str
            })

        out_df = pd.DataFrame(out_rows)
        exported_filepath = os.path.join(EXPORT_DIR, f"WEB_LABEL_{timestamp_file}.csv")
        out_df.to_csv(exported_filepath, index=False)

        # Ghi đè trực tiếp vào file IN.csv cố định
        in_fixed_path = "/Users/khan/Library/CloudStorage/GoogleDrive-ltckha@gmail.com/My Drive/IN Mini Code/IN.csv"
        try:
            os.makedirs(os.path.dirname(in_fixed_path), exist_ok=True)
            out_df.to_csv(in_fixed_path, index=False)
            exported_filepath += f"\n📁 (Đã ghi đè) {in_fixed_path}"
        except Exception as e:
            print(f"[!] Không thể ghi đè file IN.csv: {e}")

    # ==================== TASK 9: ĐỒNG BỘ SKU TAB NHAP VÀO 2 KHO ====================
    elif choice == 9:
        df_15e, _ = loader.load_sheet('KHO15E')
        df_y3c, _ = loader.load_sheet('KHOY3C')
        sub_dict = get_sub_info(loader)

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
            pcode = str(rec.get('product_code', '')).strip()
            color = str(rec.get('product_color', '')).strip()
            sz = str(rec.get('item_size', '')).strip()
            if sz.endswith('.0'): sz = sz[:-2]
            sku = f"{pcode}{sz}" if sz else pcode
            kho = str(rec.get('KHO', '')).strip().upper()

            if not pcode or not sz:
                continue

            # Tra cứu vị trí kệ từ tab SUB
            sub_info = sub_dict.get(pcode.lower()) or {}
            loc_15e = str(sub_info.get('15E_product_location', '')).strip()
            loc_y3c = str(sub_info.get('Y3C_product_location', '')).strip()

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


def print_main_menu():
    """Hiển thị Giao diện Menu Chính theo 4 Nền Tảng với Màu Sáng Cao Cấp"""
    menu_text = """===================================================================
             🚀 [bold white]HNC CONTROL CENTER - MAC MINI M4 ENGINE[/bold white]
===================================================================
  [1] [bold #FFD700]👠 WEBSITE HẢI NANCY[/bold #FFD700]
  [2] [bold #FF6E40]🛍️  SHOPEE[/bold #FF6E40]
  [3] [bold #00E5FF]🎵 TIKTOK[/bold #00E5FF] [bold #FF1744]SHOP[/bold #FF1744]
  [4] [bold #29B6F6]📊 MISA eSHOP[/bold #29B6F6]
  -----------------------------------------------------------------
  [0] [bold red]❌ Thoát ứng dụng[/bold red]
==================================================================="""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="bright_white"))
    else:
        print(menu_text)


def print_submenu_website():
    """Hiển thị Sub-Menu 1: Website Hải Nancy"""
    menu_text = """-------------------------------------------------------------------
             [bold #FFD700]👠 SUB-MENU: WEBSITE HẢI NANCY[/bold #FFD700]
-------------------------------------------------------------------
  [1] 🌐 Xuất File Đăng Sản Phẩm Mới (Tab-delimited Product Import)
  [2] 📦 Xuất File Tồn Kho (Website Stock Import - Tự động tách 15E / Y3C)
  [3] 🖼️  Tự động Cào Link Ảnh Web (image_01 ➔ image_10)
  [4] 🖨️  In Tem Barcode & QR Code (Ghi đè file IN.csv)
  [5] 🔄 Đồng Bộ SKU Mới từ NHAP vào 2 Kho (KHO15E & KHOY3C)
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
  [1] 🛒 Xuất File Đăng Sản Phẩm Mới (Shopee Mass Upload)
  [2] ⚡ Xuất File Cập Nhật Giá / Tồn Kho (Shopee Mass Update)
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
  [1] 🎵 Xuất File Đăng Sản Phẩm Mới (TikTok Mass Upload - 38 Cột chuẩn)
  [2] ⚡ Xuất File Cập Nhật (TikTok Mass Update: Giá, Tồn kho hoặc Tất cả)
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
  [1] 📊 Xuất File Danh Mục Hàng Hóa (MISA Import Danh Mục 2 tầng Cha - Con)
  [2] 📥 Xuất File Nhập Kho Mua Hàng (MISA Nhập Kho - Tự động tách 15E / 3C)
  -----------------------------------------------------------------
  [0] ⬅️  Quay lại Menu chính
-------------------------------------------------------------------"""
    if HAS_RICH:
        console.print(Panel(menu_text, border_style="#29B6F6"))
    else:
        print(menu_text)


def handle_submenu_website(loader):
    """Xử lý điều hướng trong Sub-menu Website Hải Nancy"""
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_submenu_website()
        
        if HAS_RICH:
            sub_choice = Prompt.ask("[bold cyan]Mời chọn tác vụ Website [0-5][/bold cyan]", default="0")
        else:
            sub_choice = input("Mời chọn tác vụ Website [0-5]: ").strip()

        if sub_choice == "0":
            break
        elif sub_choice == "1":
            process_export_task(1, loader)
        elif sub_choice == "2":
            process_export_task(5, loader)
        elif sub_choice == "3":
            process_export_task(11, loader)
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


def main():
    loader = EngineDataLoader()

    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_main_menu()
        
        if HAS_RICH:
            mode_str = f"🌐 Google Sheets Connected: [bold green]{SPREADSHEET_NAME}[/bold green]" if loader.is_google_api else "[bold red]❌ Chưa kết nối Google Sheets API[/bold red]"
            console.print(f"[dim]Trạng thái: {mode_str}[/dim]")
            choice_input = Prompt.ask("[bold cyan]Mời chọn nền tảng [0-4][/bold cyan]", default="0")
        else:
            choice_input = input("Mời chọn nền tảng [0-4]: ").strip()

        if choice_input == "0":
            if HAS_RICH:
                console.print("[bold green]Cảm ơn bạn đã sử dụng HNC Control Center! Tạm biệt! 👋[/bold green]")
            else:
                print("Cảm ơn bạn đã sử dụng HNC Control Center! Tạm biệt! 👋")
            sys.exit(0)
        elif choice_input == "1":
            handle_submenu_website(loader)
        elif choice_input == "2":
            handle_submenu_shopee(loader)
        elif choice_input == "3":
            handle_submenu_tiktok(loader)
        elif choice_input == "4":
            handle_submenu_misa(loader)
        else:
            if HAS_RICH:
                console.print("[bold red]❌ Lựa chọn không hợp lệ! Vui lòng nhập số từ 0 đến 4.[/bold red]")
                Prompt.ask("[dim]Nhấn Enter để tiếp tục...[/dim]")
            else:
                input("❌ Lựa chọn không hợp lệ! Nhấn Enter để tiếp tục...")


if __name__ == "__main__":
    main()
