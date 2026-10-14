# 🚀 HNC MASTER ENGINE - BẢNG THEO DÕI TIẾN ĐỘ & TRẠNG THÁI TÁC VỤ (PROJECT STATUS)

> **Cập nhật lần cuối:** 11/10/2026  
> **Nền tảng:** Mac mini M4 - Python 3 Engine (Google Sheets API & Excel Offline)  
> **Trạng thái tổng thể:** ✅ **HOÀN TẤT & ĐÃ KIỂM THỬ 100% HOẠT ĐỘNG ỔN ĐỊNH**

---

## 📊 1. BẢNG TỔNG HỢP TRẠNG THÁI KIỂM THỬ TỪNG TÁC VỤ

| STT | Nền Tảng | Tên Tác Vụ | File Xuất Chuẩn | Trạng Thái | Ghi Chú Tính Năng Đã Hoàn Thiện |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **1** | 👠 **Website** | 🌐 **Website Product Upload** | `WEB_PRODUCTS_*.csv` | ✅ **ĐÃ OK** | Xuất tab-delimited UTF-8-SIG theo mẫu `tpl_web_upload.csv` (1 dòng/mã SP, chuẩn 9 cột). |
| **2** | 👠 **Website** | 📦 **Website Stock Import** | `WEB_STOCK_15E_*.csv`<br>`WEB_STOCK_Y3C_*.csv` | ✅ **ĐÃ OK** | Tự động tách 2 kho. Hỗ trợ **[1] Theo phiếu NHAP** hoặc **[2] Xuất FULL toàn bộ tồn kho**. |
| **3** | 👠 **Website** | 🖼️ **Tự Động Cào Ảnh Web** | Cập nhật trực tiếp Sheet | ✅ **ĐÃ OK** | Quét đúng `product_code`, điền `image_01` ➔ `image_10`, ghi cờ `get_images`. |
| **4** | 👠 **Website** | 🖨️ **In Tem Barcode & QR Code** | `WEB_LABEL_*.csv`<br>`IN.csv` (ghi đè) | ✅ **ĐÃ OK** | Xuất lịch sử + tự động ghi đè file cố định `/IN Mini Code/IN.csv`. |
| **5** | 👠 **Website** | 🔄 **Đồng Bộ SKU Vào 2 Kho** | Cập nhật `KHO15E` & `KHOY3C` | ✅ **ĐÃ OK** | Quét theo cờ `kho_sync`, phân đúng kho `15E` vào `KHO15E`, `Y3C` vào `KHOY3C` với công thức tự động. |
| **6** | 🛍️ **Shopee** | 🛒 **Shopee Upload Mới** | `SHOPEE_UPLOAD_*.xlsx` | ✅ **ĐÃ OK** | Template Shopee 2026, tự nhân 140% giá, unroll size, link ảnh. |
| **7** | 🛍️ **Shopee** | ⚡ **Shopee Cập Nhật Giá/Tồn** | `SHOPEE_UPDATE_*.xlsx` | ✅ **ĐÃ OK** | 3 chế độ: `[1] Chỉ Tồn Kho`, `[2] Chỉ Giá 140%`, `[3] Cả Hai`. |
| **8** | 🎵 **TikTok** | 🎵 **TikTok Upload Mới** | `TIKTOK_UPLOAD_*.xlsx` | ✅ **ĐÃ OK** | 38 cột chuẩn, điền 10 thuộc tính chi tiết, xuất xứ Việt Nam, tổ chức chịu trách nhiệm. |
| **9** | 🎵 **TikTok** | ⚡ **TikTok Cập Nhật** | `TIKTOK_UPDATE_*.xlsx` | ✅ **ĐÃ OK** | 3 chế độ: `[1] Chỉ Tồn Kho`, `[2] Chỉ Giá 140%`, `[3] Cập Nhật TẤT CẢ Dữ Liệu`. |
| **10** | 📊 **MISA** | 📊 **MISA Danh Mục Hàng Hóa** | `MISA_PRODUCTS_NEW_*.xlsx`<br>`MISA_PRODUCTS_UPDATE_*.xlsx` | ✅ **ĐÃ OK** | Tự động phân loại: Mã cha mới xuất `MISA_PRODUCTS_NEW`, mã cha đã tồn tại (thêm màu mới) tự động xuất `MISA_PRODUCTS_UPDATE`. |
| **11** | 📊 **MISA** | 📥 **MISA Nhập Kho** | `MISA_STOCK_15E_*.xlsx`<br>`MISA_STOCK_3C_*.xlsx` | ✅ **ĐÃ OK** | Tự động 22 cột, tính chiết khấu/thuế từ `SUB`, tự phân kho `15E` / `3C`, Strict QA. Dòng NHAP có Số chứng từ `TRA-…` (trả hàng / huỷ đơn) luôn bỏ qua, ghi "Bỏ qua - trả hàng". |
| **12** | 📁 **Media** | 🎬 **Quản Lý Media & Tư Liệu SP** | `/Volumes/Media/HNC_Master/` | ✅ **ĐÃ OK** | Quét đệ quy gom file từ Photoroom & Downloads, tự động cập nhật 3 cột `content_path`, `content_url`, `content_files` (Kiểu 3: `VIDEO, IMG` / để trống khi không có file). |
| **13** | 📸 **AI Vision** | 🤖 **AI Tự Động Nhập SP Từ Ảnh** | Cập nhật trực tiếp `SANPHAM` & `NHAP` | ✅ **ĐÃ OK** | Gemini Multimodal REST API, hỗ trợ Kéo thả nhiều ảnh/nhiều sản phẩm (Batch Ingestion), Smart Restock (mã đã có chỉ nhập thêm NHAP, không tạo trùng SANPHAM), bảng CLI số nổi bật [1-9]. |
| **14** | 💬 **Zalo** | 🤖 **Bot Zalo Quản Lý Bán Hàng & Kho** | Ghi trực tiếp `BAN`, `NHAP`, `XUAT`, `product_location` (KHO15E/KHOY3C) | ✅ **ĐÃ OK** | Google Apps Script gắn vào HNC_Control_Center (`zalo_bot/`), thay flow n8n cũ (11/10/2026). Kiểm hàng, Bán/Nhập/Xuất, Chuyển kho, Chuyển vị trí; YEN→Y3C, TBH→15E; chặn theo `ALLOWED_CHAT_IDS`, chống ghi trùng, dòng NHAP đánh dấu `Zalo_Update`. |

---

## 🛡️ 2. QUY CHUẨN ĐẶT TÊN FILE & ĐƯỜNG DẪN XUẤT

- **Thư mục xuất chính**: `My Drive/Spark/HNC_Master/HNC_Exported_Files/` (ưu tiên; fallback `My Drive/HNC_Master/HNC_Exported_Files/`, cuối cùng là `./HNC_Exported_Files` local).
- **Quy chuẩn tên file ngắn gọn kèm timestamp**:
  - `WEB_PRODUCTS_YYYYMMDD_HHMMSS.csv`
  - `WEB_STOCK_15E_YYYYMMDD_HHMMSS.csv` & `WEB_STOCK_Y3C_YYYYMMDD_HHMMSS.csv`
  - `WEB_STOCK_15E_FULL_YYYYMMDD_HHMMSS.csv` & `WEB_STOCK_Y3C_FULL_YYYYMMDD_HHMMSS.csv`
  - `SHOPEE_UPLOAD_YYYYMMDD_HHMMSS.xlsx`
  - `SHOPEE_UPDATE_{STOCK_ONLY|PRICE_ONLY|FULL}_YYYYMMDD_HHMMSS.xlsx`
  - `TIKTOK_UPLOAD_YYYYMMDD_HHMMSS.xlsx`
  - `TIKTOK_UPDATE_{STOCK_ONLY|PRICE_ONLY|FULL_ALL_INFO}_YYYYMMDD_HHMMSS.xlsx`
  - `MISA_PRODUCTS_YYYYMMDD_HHMMSS.xlsx` *(khi chỉ có mã cha mới)*
  - `MISA_PRODUCTS_NEW_YYYYMMDD_HHMMSS.xlsx` & `MISA_PRODUCTS_UPDATE_YYYYMMDD_HHMMSS.xlsx` *(khi có cả mã mới và mã cập nhật)*
  - `MISA_STOCK_15E_YYYYMMDD_HHMMSS.xlsx` & `MISA_STOCK_3C_YYYYMMDD_HHMMSS.xlsx`
  - `WEB_LABEL_YYYYMMDD_HHMMSS.csv` *(và file ghi đè cố định `/IN Mini Code/IN.csv`)*
  - `channel_links.csv` *(tên cố định, ghi đè mỗi lần xuất SHOPEE_UPDATE / TIKTOK_UPDATE; cột product_code, channel, item_id, shopid, url; xuất kênh này giữ nguyên dòng của kênh kia; web đọc để ra link đúng SP)*

---

## ⚙️ 3. NGUYÊN TẮC CỐT LÕI CỦA DỰ ÁN

1. **Thảo luận trước khi thực hiện**: Luôn luôn phân tích, đề xuất phương án và nhận xác nhận từ User trước khi sửa code (`.agents/rules/always_discuss_first.md`).
2. **Không tự ý thao tác Git**: Tuyệt đối không tự ý chạy lệnh push hoặc yêu cầu User đẩy code lên Git (`.agents/rules/never_push_git.md`).
3. **Giao tiếp 2 chiều với Spark 100% qua Google Drive API v3**: Toàn bộ dữ liệu, blueprint và nhật ký trao đổi giữa Antigravity và Gemini Spark đều thông qua Google Drive API v3, hoàn toàn độc lập và không phụ thuộc vào đường dẫn đồng bộ cục bộ trên macOS (`.agents/rules/spark_gdrive_api_v3_protocol.md`).
4. **Dò quét Header Động (Dynamic Scanner)**: Dò quét an toàn theo tên biến/cột hiển thị ở cả Hàng 1 và Hàng 2 với cơ chế alias tiếng Việt, tuyệt đối không đoán mò số cột (`.agents/rules/always_map_columns_by_header.md`).
5. **Google Sheets Cloud Native**: Dữ liệu đọc/ghi trực tiếp qua Google Sheets API, đảm bảo một nguồn dữ liệu chuẩn xác duy nhất (Single Source of Truth).
6. **Cơ chế Kiểm soát Chất lượng (Strict QA Gate)**: Khi thiếu các trường bắt buộc, tự động bỏ qua không xuất file và gắn cờ cảnh báo cụ thể lên Sheet.

---

## 💡 4. SỔ TAY Ý TƯỞNG & LỘ TRÌNH TƯƠNG LAI
- Toàn bộ kế hoạch tái cấu trúc module (Giai đoạn 2) và các ý tưởng mở rộng sàn (Lazada, Zalo, Webhook, AI) được lưu trữ đầy đủ tại: [`IDEAS_AND_ROADMAP.md`](file:///Users/khan/Developer/HNC_Master/IDEAS_AND_ROADMAP.md).
