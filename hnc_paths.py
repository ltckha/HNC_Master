"""Đường dẫn Google Drive của HNC — khai 1 chỗ cho main.py và tools/.

Thư mục hệ thống (HNC_Templates, HNC_Exported_Files, Outputs), tìm theo thứ tự:
  1. My Drive/HNC/He_thong      (chỗ mới, anh Kha gom thư mục 16/10/2026)
  2. My Drive/Spark/HNC_Master  (chỗ cũ, trước khi kéo)
Không thấy cả 2 → báo lỗi rõ, KHÔNG lặng lẽ dùng thư mục local.
"""
import glob
import os

SYSTEM_DIR_CANDIDATES = [("HNC", "He_thong"), ("Spark", "HNC_Master")]
IN_CSV_SUBPATH = ("IN Mini Code", "IN.csv")  # file tem cố định cho Brother P-touch (không nằm trong thư mục gom)
PREFERRED_ACCOUNT = "GoogleDrive-ltckha@gmail.com"


def drive_roots():
    """Các thư mục 'My Drive' của Google Drive for desktop, tài khoản ltckha trước."""
    roots = sorted(glob.glob(os.path.expanduser("~/Library/CloudStorage/GoogleDrive-*/My Drive")))
    roots.sort(key=lambda p: os.path.basename(os.path.dirname(p)) != PREFERRED_ACCOUNT)  # đúng tên, không lấy bản sao cũ "(06-06-2023 …)"
    return roots


def find_system_dir():
    tried = []
    for sub in SYSTEM_DIR_CANDIDATES:
        for root in drive_roots():
            path = os.path.join(root, *sub)
            tried.append(path)
            if os.path.isdir(path):
                return path
    raise FileNotFoundError(
        "Không tìm thấy thư mục hệ thống HNC trên Google Drive. Đã thử:\n  " + ("\n  ".join(tried) or "(không có Google Drive for desktop)")
        + "\nKiểm tra Google Drive đã mở / đồng bộ chưa, hoặc thư mục đã kéo về My Drive/HNC/He_thong chưa."
    )


def in_csv_path():
    roots = drive_roots()
    if not roots:
        raise FileNotFoundError("Không thấy Google Drive for desktop để ghi IN.csv")
    return os.path.join(roots[0], *IN_CSV_SUBPATH)
