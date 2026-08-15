# 🚀 HNC CONTROL CENTER - MAC MINI M4 ENGINE

Hệ thống điều phối dữ liệu sản phẩm, quản lý tồn kho đa nền tảng và xuất dữ liệu chuyên biệt dành cho thương hiệu **Hải Nancy**.

---

## 🌟 TÍNH NĂNG CỐT LÕI (4 NỀN TẢNG)

### 1. 👠 WEBSITE HẢI NANCY
- **Xuất File Đăng Sản Phẩm Mới**: Sinh file tab-delimited chuẩn hóa để import lên Website.
- **Xuất File Tồn Kho (Stock Import)**: Tự động tách kho 15E / Y3C.
  - Hỗ trợ xuất theo **Phiếu Nhập mới** (từ tab `NHAP`).
  - Hỗ trợ xuất **FULL Toàn Bộ Tồn Kho Realtime** (quét từ `KHO15E` & `KHOY3C`).
- **Tự động Cào Link Ảnh Web**: Quét và cào tối đa 10 ảnh chất lượng cao chuẩn theo `product_code`.
- **In Tem Barcode & QR Code**: Sinh danh sách in tem và tự động ghi đè file `IN.csv`.
- **Đồng Bộ SKU Mới Vào 2 Kho**: Quét các dòng hàng mới từ tab `NHAP` và tự động thêm dòng tính tồn kho vào `KHO15E` / `KHOY3C` với công thức tự động.

### 2. 🛍️ SHOPEE
- **Xuất File Đăng Sản Phẩm Mới**: Mass Upload chuẩn mẫu ngành hàng Shopee.
- **Xuất File Cập Nhật Giá / Tồn Kho (Shopee Mass Update)**:
  - Cập nhật số lượng tồn kho (Kho 15E + Y3C, an toàn $\ge 0$).
  - Cập nhật giá bán ($\text{product\_price} \times 140\%$).
  - Cập nhật cả hai (Giá bán & Tồn kho Realtime).

### 3. 🎵 TIKTOK SHOP
- **Xuất File Đăng Sản Phẩm Mới (38 Cột Chuẩn)**: Điền đầy đủ hình ảnh, size chart, kích thước, trọng lượng và 10 trường thuộc tính chi tiết (Xuất xứ, Chất liệu, Mùa, Dịp, Mũi, Gót, Tên & Địa chỉ tổ chức chịu trách nhiệm...).
- **Xuất File Cập Nhật (TikTok Mass Update)**: Hỗ trợ cập nhật Tồn kho, Giá bán hoặc **Cập nhật TẤT CẢ dữ liệu sản phẩm**.

### 4. 📊 MISA ESHOP
- **Xuất File Danh Mục Hàng Hóa**: Phân tầng Cha - Con tự động cho MISA eShop.
- **Xuất File Nhập Kho Mua Hàng**: Tự động tính toán 22 cột hóa đơn chứng từ, chiết khấu, thuế GTGT và phân tách kho `15E` / `3C`.

---

## 🛠️ CÀI ĐẶT & CHẠY ỨNG DỤNG

### 1. Yêu cầu hệ thống
- Python 3.9+
- macOS / Linux / Windows

### 2. Cài đặt thư viện
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Cấu hình Google Sheets API
1. Đặt file khóa Service Account Google Cloud vào thư mục gốc với tên `credentials.json`.
2. Chia sẻ quyền chỉnh sửa (Editor) trên Google Sheet `HNC_Control_Center` cho email Service Account.

### 4. Khởi chạy
```bash
python main.py
# hoặc click chạy file run.command trên macOS
```

---

## 🔒 BẢO MẬT & QUY TẮC
- File `credentials.json` và các dữ liệu kinh doanh cá nhân được cấu hình trong `.gitignore` để đảm bảo an toàn tuyệt đối, không bao giờ bị đẩy lên kho mã nguồn Git công khai.
