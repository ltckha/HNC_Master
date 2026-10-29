"""1 lệnh điền ô trống hàng cũ "từ dữ liệu có sẵn" (anh Kha 29/10: điền được ô nào thì điền, còn không bỏ trống):
1) tools/tu_ten.py — từ khoá rõ nghĩa trong tên hàng / Bonus / Nhấn mạnh; 2) tools/dien_theo_nganh.py — đa số trong ngành (≥ 95%, ≥ 20 mã).
Chạy theo thứ tự (bước 2 đọc lại Sheet sau bước 1). Cùng cờ: [--ghi] [--sheet ID].
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import tu_ten  # noqa: E402

if __name__ == '__main__':
    # Bước 2 (đa số ngành) ĐÃ BỎ: anh Kha 29/10 "không phải điền theo ngành mà từ thuộc tính đã có của chính mã" — 2008 ô đã trả lại
    # (tools/suy_trong_ma.py). Giữ dien_theo_nganh.py để tham khảo, không chạy.
    sys.exit(tu_ten.main())
