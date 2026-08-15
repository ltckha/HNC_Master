# 🚀 HNC MASTER ENGINE - BẢNG THEO DÕI TIẾN ĐỘ & TRẠNG THÁI TÁC VỤ (PROJECT STATUS)

> **Cập nhật lần cuối:** 15/08/2026  
> **Nền tảng:** Mac mini M4 - Python 3 Engine (Google Sheets API & Excel Offline)  
> **Trạng thái tổng thể:** ✅ **HOÀN TẤT & ĐÃ KIỂM THỬ 100% HOẠT ĐỘNG ỔN ĐỊNH**

---

## 📊 1. BẢNG TỔNG HỢP TRẠNG THÁI KIỂM THỬ TỪNG TÁC VỤ

| STT | Nền Tảng | Tên Tác Vụ | File Xuất Chuẩn | Trạng Thái | Ghi Chú Tính Năng Đã Hoàn Thiện |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **1** | 👠 **Website** | 🌐 **Website Product Upload** | `WEB_PRODUCTS_*.csv` | ✅ **ĐÃ OK** | Xuất tab-delimited UTF-8-SIG, unroll size, mô tả HTML, link ảnh. |
| **2** | 👠 **Website** | 📦 **Website Stock Import** | `WEB_STOCK_15E_*.csv`<br>`WEB_STOCK_Y3C_*.csv` | ✅ **ĐÃ OK** | Tự động tách 2 kho. Hỗ trợ **[1] Theo phiếu NHAP** hoặc **[2] Xuất FULL toàn bộ tồn kho**. |
| **3** | 👠 **Website** | 🖼️ **Tự Động Cào Ảnh Web** | Cập nhật trực tiếp Sheet | ✅ **ĐÃ OK** | Quét đúng `product_code`, điền `image_01` ➔ `image_10`, ghi cờ `get_images`. |
| **4** | 👠 **Website** | 🖨️ **In Tem Barcode & QR Code** | `WEB_LABEL_*.csv`<br>`IN.csv` (ghi đè) | ✅ **ĐÃ OK** | Xuất lịch sử + tự động ghi đè file cố định `/IN Mini Code/IN.csv`. |
| **5** | 👠 **Website** | 🔄 **Đồng Bộ SKU Vào 2 Kho** | Cập nhật `KHO15E` & `KHOY3C` | ✅ **ĐÃ OK** | Quét theo cờ `kho_sync`, phân đúng kho `15E` vào `KHO15E`, `Y3C` vào `KHOY3C` với công thức tự động. |
| **6** | 🛍️ **Shopee** | 🛒 **Shopee Upload Mới** | `SHOPEE_UPLOAD_*.xlsx` | ✅ **ĐÃ OK** | Template Shopee 2026, tự nhân 140% giá, unroll size, link ảnh. |
| **7** | 🛍️ **Shopee** | ⚡ **Shopee Cập Nhật Giá/Tồn** | `SHOPEE_UPDATE_*.xlsx` | ✅ **ĐÃ OK** | 3 chế độ: `[1] Chỉ Tồn Kho`, `[2] Chỉ Giá 140%`, `[3] Cả Hai`. |
| **8** | 🎵 **TikTok** | 🎵 **TikTok Upload Mới** | `TIKTOK_UPLOAD_*.xlsx` | ✅ **ĐÃ OK** | 38 cột chuẩn, điền 10 thuộc tính chi tiết, xuất xứ Việt Nam, tổ chức chịu trách nhiệm. |
| **9** | 🎵 **TikTok** | ⚡ **TikTok Cập Nhật** | `TIKTOK_UPDATE_*.xlsx` | ✅ **ĐÃ OK** | 3 chế độ: `[1] Chỉ Tồn Kho`, `[2] Chỉ Giá 140%`, `[3] Cập Nhật TẤT CẢ Dữ Liệu`. |
| **10** | 📊 **MISA** | 📊 **MISA Danh Mục Hàng Hóa** | `MISA_PRODUCTS_*.xlsx` | ✅ **ĐÃ OK** | Hàng cha - con, unroll size, mã SKU, nhóm ngành hàng, Strict QA. |
| **11** | 📊 **MISA** | 📥 **MISA Nhập Kho** | `MISA_STOCK_15E_*.xlsx`<br>`MISA_STOCK_3C_*.xlsx` | ✅ **ĐÃ OK** | Tự động 22 cột, tính chiết khấu/thuế từ `SUB`, tự phân kho `15E` / `3C`, Strict QA. |

---

## 🛡️ 2. QUY CHUẨN ĐẶT TÊN FILE & ĐƯỜNG DẪN XUẤT

- **Thư mục xuất chính**: `My Drive/HNC_Master/HNC_Exported_Files/` (và thư mục local dự phòng).
- **Quy chuẩn tên file ngắn gọn kèm timestamp**:
  - `WEB_PRODUCTS_YYYYMMDD_HHMMSS.csv`
  - `WEB_STOCK_15E_YYYYMMDD_HHMMSS.csv` & `WEB_STOCK_Y3C_YYYYMMDD_HHMMSS.csv`
  - `WEB_STOCK_15E_FULL_YYYYMMDD_HHMMSS.csv` & `WEB_STOCK_Y3C_FULL_YYYYMMDD_HHMMSS.csv`
  - `SHOPEE_UPLOAD_YYYYMMDD_HHMMSS.xlsx`
  - `SHOPEE_UPDATE_YYYYMMDD_HHMMSS.xlsx`
  - `TIKTOK_UPLOAD_YYYYMMDD_HHMMSS.xlsx`
  - `TIKTOK_UPDATE_YYYYMMDD_HHMMSS.xlsx`
  - `MISA_PRODUCTS_YYYYMMDD_HHMMSS.xlsx`
  - `MISA_STOCK_15E_YYYYMMDD_HHMMSS.xlsx` & `MISA_STOCK_3C_YYYYMMDD_HHMMSS.xlsx`
  - `WEB_LABEL_YYYYMMDD_HHMMSS.csv` *(và file ghi đè cố định `/IN Mini Code/IN.csv`)*

---

## ⚙️ 3. NGUYÊN TẮC CỐT LÕI CỦA DỰ ÁN

1. **Thảo luận trước khi thực hiện**: Luôn luôn phân tích, đề xuất phương án và nhận xác nhận từ User trước khi sửa code (`.gemini/rules/always_discuss_first.md`).
2. **Không tự ý thao tác Git**: Tuyệt đối không tự ý chạy lệnh push hoặc yêu cầu User đẩy code lên Git (`.gemini/rules/never_push_git.md`).
3. **Dò quét Header Động (Dynamic Scanner)**: Dò quét theo tên biến/cột hiển thị ở cả Hàng 1 và Hàng 2, tuyệt đối không cố định chỉ số cột.
4. **Cơ chế Kiểm soát Chất lượng (Strict QA Gate)**: Khi thiếu các trường bắt buộc, tự động bỏ qua không xuất file và gắn cờ cảnh báo cụ thể lên Sheet.
