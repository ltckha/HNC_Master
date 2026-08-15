# 🚀 HNC MASTER ENGINE - BẢNG THEO DÕI TIẾN ĐỘ & TRẠNG THÁI TÁC VỤ (PROJECT STATUS)

> **Cập nhật lần cuối:** 14/08/2026  
> **Nền tảng:** Mac mini M4 - Python 3.11 Engine (Google Sheets API & Excel Offline)

---

## 📊 1. BẢNG TỔNG HỢP TRẠNG THÁI KIỂM THỬ TỪNG TÁC VỤ

| STT | Nhóm Menu | Tên Tác Vụ | File Xuất Chuẩn | Trạng Thái Kiểm Thử | Ghi Chú Tính Năng |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **1** | **Sub-Menu 1** | 🌐 **Website Product Upload** | `WEB_PRODUCTS_*.csv` | ✅ **ĐÃ OK** | Xuất tab-delimited UTF-8-SIG, unroll size, mô tả HTML, link ảnh. |
| **2** | **Sub-Menu 1** | 🛒 **Shopee Upload Mới** | `SHOPEE_UPLOAD_*.xlsx` | ✅ **ĐÃ OK** | Template Shopee 2026, tự nhân 140% giá, unroll size, link ảnh. |
| **3** | **Sub-Menu 1** | 🎵 **TikTok Upload Mới** | `TIKTOK_UPLOAD_*.xlsx` | ⏳ *Chờ kiểm tra* | Template TikTok 2026, unroll size, link ảnh chính `image_01`. |
| **4** | **Sub-Menu 1** | 📊 **MISA Danh Mục Hàng Hóa** | `MISA_PRODUCTS_*.xlsx` | ✅ **ĐÃ OK** | Hàng cha - con, unroll size, mã SKU, nhóm ngành hàng. |
| **5** | **Sub-Menu 1** | 🖼️ **Tự Động Cào Ảnh Web** | Cập nhật trực tiếp Sheet | ✅ **ĐÃ OK** | Quét đúng `product_code`, điền `image_01` ➔ `image_10`, ghi cờ `get_images`. |
| **6** | **Sub-Menu 2** | 📦 **Website Stock Import** | `WEB_STOCK_15E_*.csv`<br>`WEB_STOCK_Y3C_*.csv` | ✅ **ĐÃ OK** | Tự động tách 2 file theo kho, mã gốc sạch, barcode chuẩn. |
| **7** | **Sub-Menu 2** | 🛒 **Shopee Cập Nhật Giá/Tồn** | `SHOPEE_UPDATE_*.xlsx` | ⏳ *Chờ kiểm tra* | Cộng dồn tồn kho `KHO15E + KHOY3C`, khớp SKU Shopee. |
| **8** | **Sub-Menu 2** | 🎵 **TikTok Cập Nhật Giá/Tồn** | `TIKTOK_UPDATE_*.xlsx` | ⏳ *Chờ kiểm tra* | Cộng dồn tồn kho `KHO15E + KHOY3C`, khớp SKU TikTok. |
| **9** | **Sub-Menu 2** | 📥 **MISA Nhập Kho** | `MISA_STOCK_15E_*.xlsx`<br>`MISA_STOCK_3C_*.xlsx` | ✅ **ĐÃ OK** | Tự động 22 cột, tính chiết khấu/thuế từ `SUB`, Strict QA chặn dòng thiếu. |
| **10** | **Menu Chính** | 🖨️ **In Tem Barcode & QR Code** | `WEB_LABEL_*.csv`<br>`IN.csv` (ghi đè) | ✅ **ĐÃ OK** | Xuất lịch sử + ghi đè trực tiếp `/IN Mini Code/IN.csv`. |

---

## 🛡️ 2. QUY CHUẨN ĐẶT TÊN FILE & ĐƯỜNG DẪN XUẤT

- **Thư mục xuất chính**: `My Drive/HNC_Master/HNC_Exported_Files/` (và thư mục local dự phòng).
- **Quy chuẩn tên file**: Đã bỏ hoàn toàn tiền tố `EXPORT_`, tên file ngắn gọn, rõ ràng kèm timestamp:
  - `WEB_PRODUCTS_YYYYMMDD_HHMMSS.csv`
  - `SHOPEE_UPLOAD_YYYYMMDD_HHMMSS.xlsx`
  - `TIKTOK_UPLOAD_YYYYMMDD_HHMMSS.xlsx`
  - `MISA_PRODUCTS_YYYYMMDD_HHMMSS.xlsx`
  - `WEB_STOCK_15E_YYYYMMDD_HHMMSS.csv` & `WEB_STOCK_Y3C_YYYYMMDD_HHMMSS.csv`
  - `SHOPEE_UPDATE_YYYYMMDD_HHMMSS.xlsx`
  - `TIKTOK_UPDATE_YYYYMMDD_HHMMSS.xlsx`
  - `MISA_STOCK_15E_YYYYMMDD_HHMMSS.xlsx` & `MISA_STOCK_3C_YYYYMMDD_HHMMSS.xlsx`
  - `WEB_LABEL_YYYYMMDD_HHMMSS.csv` *(và file ghi đè cố định `/IN Mini Code/IN.csv`)*

---

## ⚙️ 3. NGUYÊN TẮC CỐT LÕI CỦA DỰ ÁN

1. **Thảo luận trước khi thực hiện**: Luôn luôn phân tích, đề xuất phương án và nhận xác nhận từ User trước khi sửa code (`.gemini/rules/always_discuss_first.md`).
2. **Dò quét Header Động (Dynamic Scanner)**: Dò quét theo tên biến/cột hiển thị ở cả Hàng 1 và Hàng 2, tuyệt đối không cố định chỉ số cột.
3. **Cơ chế Kiểm soát Chất lượng (Strict QA Gate)**:
   - Khi thiếu các trường bắt buộc (Số chứng từ, ĐVT, Ngày, Số lượng, Đơn giá, Nhà cung cấp, Kho): **Tự động bỏ qua không xuất file** và **gắn cờ cảnh báo cụ thể** lên Sheet.
   - Chỉ khi đầy đủ dữ liệu 100% mới xuất file và cập nhật trạng thái `Done`.
