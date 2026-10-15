# 🚀 HNC CONTROL CENTER - MAC MINI M4 ENGINE

Hệ thống điều phối dữ liệu sản phẩm, quản lý tồn kho đa nền tảng và xuất dữ liệu chuyên biệt dành cho thương hiệu **Hải Nancy**.

---

## 🌟 TÍNH NĂNG

Dữ liệu gốc: Google Sheet `HNC_Control_Center` (SANPHAM, NHAP, XUAT, BAN, KHO15E, KHOY3C, SUB, META). Tồn kho = tồn đầu + NHAP − XUAT − BAN, tính bằng công thức theo FSKU (kho + mã + size).

### 1. 🏷️ Tem & kho (menu `main.py` [1])
- **In tem Barcode & QR**: sinh danh sách in và ghi đè `IN.csv` cho Brother P-touch.
- **Đồng bộ SKU mới vào 2 kho**: dòng NHAP mới → thêm dòng tính tồn vào `KHO15E` / `KHOY3C`.
- *Đã ẩn (15/10/2026)*: đăng SP, tồn kho và cào ảnh của **website cũ**; web mới đọc thẳng Sheet. Code giữ tới khi chuyển tên miền.

### 2. 🛍️ Shopee & 🎵 TikTok Shop (menu [2], [3])
- **Đăng mới**: Mass Upload theo mẫu sàn; giá = giá Sheet × hệ số trong SUB; tách size; link ảnh.
- **Cập nhật tồn / giá**: tồn = 15E + Y3C, âm thì về 0. Từ 15/10 xuất hằng ngày trên web `/admin/san`; menu HNC giữ làm dự phòng.
  - Mẫu `HNC_Templates/tpl_*_update.xlsx` đọc theo tên cột hàng 1. Mẫu TikTok cần cột `quantity`.
  - Ghi mốc `META.*_last_update` khi có ghi tồn. Xuất kèm `channel_links.csv` cho web.

### 3. 📊 MISA eShop (menu [4])
- **Danh mục hàng hoá** phân tầng cha – con (`MISA_PRODUCTS_NEW_*` / `MISA_PRODUCTS_UPDATE_*`).
- **Phiếu nhập kho** 22 cột, tách kho `15E` / `3C`. Bỏ qua dòng NHAP từ Zalo (`Zalo_Update`) và dòng trả hàng (`TRA-…`).

### 4. 📁 Media & 📸 AI nhập từ ảnh (menu [5], [6])
- Gom tư liệu Photoroom / Downloads về `/Volumes/Media/HNC_Master/<mã>`.
- AI (Gemini) nhập SP mới / restock từ ảnh vào SANPHAM + NHAP.

### 5. 💬 Bot Zalo HNC (`zalo_bot/`, Google Apps Script gắn vào Sheet)
- **Lệnh nhân viên**: kiểm hàng (giá, tồn, vị trí K/B/T/S/TH), `ban` / `nhap` / `xuat` / `chuyen kho` / `chuyen vi tri`, nhiều dòng trong 1 tin, `huy`, `bc` (báo cáo bán), `hd` (hướng dẫn).
  - Khách trả hàng: `nhap … tra hang` (Số chứng từ `TRA-…`).
- **Hoá đơn nhà cung cấp**: `hoadon`. Bot tự nhận hoá đơn từ thư mục Drive và nhắc sáng thứ Hai.
- **Cửa cho web / app**: ghi bán `?sale_key`, báo đơn web `?notify_key`, đánh dấu đã xuất file sàn `?export_key`.
- **Đồng bộ web**: Sheet đổi thì báo web chép lại (bot qua trigger, `main.py` sau mỗi tác vụ ghi Sheet).
- Chi tiết: [`zalo_bot/README.md`](zalo_bot/README.md). Cập nhật bot: `commands/bot_deploy.command` (test → clasp push → giữ link `/exec`).

---

## 🛠️ CÀI ĐẶT & CHẠY ỨNG DỤNG

### 1. Yêu cầu hệ thống
- Python 3.11 (venv trên Mac mini M4)

### 2. Cài đặt thư viện
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Cấu hình
1. Đặt file khóa Service Account Google Cloud vào thư mục gốc với tên `credentials.json`, rồi chia sẻ quyền Editor của Sheet `HNC_Control_Center` cho email Service Account.
2. Copy `.env.example` thành `.env`, rồi điền `GEMINI_API_KEY`, `SYNC_HINT_URL`, `SYNC_HINT_KEY`.

### 4. Khởi chạy
```bash
python main.py
# hoặc click chạy file run.command trên macOS
```

---

## 🔒 BẢO MẬT & QUY TẮC
- File `credentials.json` và các dữ liệu kinh doanh cá nhân được cấu hình trong `.gitignore` để đảm bảo an toàn tuyệt đối, không bao giờ bị đẩy lên kho mã nguồn Git công khai.
