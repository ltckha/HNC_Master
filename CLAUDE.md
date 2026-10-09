# 📜 CLAUDE.md - SỔ TAY VẬN HÀNH DỰ ÁN HNC_MASTER (HNC CONTROL CENTER)

> **Chào Claude, bạn đang cùng Kha Lưu (Project Owner) và Antigravity vận hành HNC Control Center.**  
> Tài liệu này là **Hiến pháp tối cao** bắt buộc bạn phải đọc và tuân thủ 100% trong suốt quá trình làm việc trong repository này.

---

## 🚨 1. CÁC QUY TẮC CỐT LÕI HÀNG ĐẦU (STRICT GOVERNANCE RULES)

1. **LUÔN LUÔN THẢO LUẬN & THỐNG NHẤT VỚI ANH KHA TRƯỚC KHI THỰC HIỆN:**
   - Trước khi sửa code, xuất dữ liệu lớn, hay chạy lệnh, **bắt buộc phải trình bày giải pháp kỹ thuật chi tiết và được anh Kha đồng ý trước**.
   - Không tự ý suy đoán cấu trúc cột tính toán tài chính, giá và tồn kho.

2. **TUYỆT ĐỐI KHÔNG TỰ Ý CHẠY `git push`:**
   - Nghiêm cấm chạy `git push` dưới mọi hình thức khi chưa có lệnh trực tiếp từ anh Kha.
   - Chỉ được tạo commit cục bộ (`git commit`) trên máy để lưu tiến độ an toàn.

3. **MÔ HÌNH PHỐI HỢP CẶP BÀI TRÙNG (DUAL-CLAUDE ARCHITECTURE):**
   - **Claude Cowork (Cloud):** Đảm nhận tư duy vĩ mô: Rà soát công thức tính giá, đối chiếu logic nghiệp vụ 4 sàn, quy hoạch tính năng.
   - **Claude Code (Local Mac M4):** Kỹ sư trưởng thực thi hiện trường: Chạy lệnh terminal, kích hoạt môi trường ảo Python `venv`, xuất file dữ liệu, đồng bộ Google Sheets.
   - **Antigravity (IDE Pair-Programmer):** Đồng hành cùng anh Kha tại IDE.

---

## 👠 2. TỔNG QUAN KIẾN TRÚC HNC CONTROL CENTER

Hệ thống điều phối dữ liệu sản phẩm, quản lý tồn kho đa nền tảng và xuất file nghiệp vụ cho thương hiệu **Hiệu Giày Hải Nancy**:

1. **Website Hải Nancy:**
   - Xuất file đăng sản phẩm mới (`WEB_PRODUCTS_*.csv`, tab-delimited UTF-8-SIG).
   - Xuất file tồn kho (`WEB_STOCK_15E_*.csv`, `WEB_STOCK_Y3C_*.csv`) theo phiếu NHAP hoặc FULL tồn kho.
   - Tự động cào link ảnh web chất lượng cao (tối đa 10 ảnh theo `product_code`).
   - In tem Barcode & QR Code (ghi đè `IN.csv`).
   - Đồng bộ SKU mới vào 2 kho `KHO15E` và `KHOY3C`.
2. **Shopee:**
   - Xuất file Mass Upload sản phẩm mới chuẩn template Shopee 2026.
   - Xuất file Mass Update: Tồn kho, Giá bán (nhân 140%), hoặc cả hai.
3. **TikTok Shop:**
   - Xuất file đăng sản phẩm mới chuẩn 38 cột (10 trường thuộc tính chi tiết, xuất xứ Việt Nam).
   - Xuất file cập nhật (Mass Update): Tồn kho, Giá bán, hoặc tất cả dữ liệu.
4. **MISA eShop:**
   - Xuất danh mục hàng hóa phân tầng Cha - Con (`MISA_PRODUCTS_NEW_*.xlsx` và `MISA_PRODUCTS_UPDATE_*.xlsx`).
   - Xuất hóa đơn nhập kho mua hàng 22 cột (chiết khấu, thuế GTGT, tách kho `15E` / `3C`).
5. **AI Vision Ingestion:**
   - Gemini Multimodal API: Nhập tự động sản phẩm mới và restock từ hình ảnh chụp thực tế.

---

## 🛠️ 3. MÔI TRƯỜNG & LỆNH THỰC THI CHUẨN

### 1. Kích hoạt môi trường ảo Python:
```bash
source venv/bin/activate
```

### 2. Các lệnh điều hành chính:
- **Khởi chạy Menu điều khiển:**
  ```bash
  python main.py
  # hoặc nhấp đúp: run.command
  ```
- **File xuất ra:** Nằm tại `My Drive/Spark/HNC_Master/HNC_Exported_Files/` (thứ tự fallback: `My Drive/Spark/HNC_Master` → `My Drive/HNC_Master` → `./HNC_Exported_Files` local).

### 3. Cấu hình & Biến môi trường:
- File cấu hình: `.env` (chứa `GEMINI_API_KEY`).
- File chứng thực Google Sheets: `credentials.json` (Service Account kết nối Google Sheets).
- Thư mục Media: `/Volumes/Media/HNC_Master/`.
