"""1 lệnh điền ô trống hàng cũ "từ dữ liệu có sẵn" (anh Kha 29/10: điền được ô nào thì điền, còn không bỏ trống):
1) tools/tu_ten.py — từ khoá rõ nghĩa trong tên hàng / Bonus / Nhấn mạnh; 2) tools/dien_theo_nganh.py — đa số trong ngành (≥ 95%, ≥ 20 mã).
Chạy theo thứ tự (bước 2 đọc lại Sheet sau bước 1). Cùng cờ: [--ghi] [--sheet ID].
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import dien_theo_nganh, tu_ten  # noqa: E402

if __name__ == '__main__':
    tu_ten.main()
    sys.exit(dien_theo_nganh.main())
