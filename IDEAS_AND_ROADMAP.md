# 💡 HNC MASTER ENGINE - SỔ TAY Ý TƯỞNG & LỘ TRÌNH PHÁT TRIỂN (IDEAS & ROADMAP)

Tài liệu này lưu trữ toàn bộ các ý tưởng kiến trúc, kế hoạch nâng cấp và hướng mở rộng tương lai cho hệ thống **HNC Master Control Center**. Khi có nhu cầu mở rộng hoặc phát triển thêm tính năng, chúng ta sẽ mở tài liệu này để triển khai.

---

## 🏛️ 1. KẾ HOẠCH TÁCH MODULE (MODULAR ARCHITECTURE - GIAI ĐOẠN 2)

### 🎯 Mục tiêu:
Chuyển đổi từ cấu trúc đơn file (`main.py`) sang cấu trúc đa module chuyên biệt trong thư mục `app/` để dễ bảo trì, dễ mở rộng tính năng mới và viết unit test mà không làm xáo trộn hệ thống.

### 🛡️ Chiến lược triển khai an toàn 100% (Zero-Risk Parallel Testing):
1. **Giữ nguyên 100% file `main.py` hiện tại**: Bản gốc phục vụ công việc bán hàng hàng ngày không hề bị xóa hay sửa đổi.
2. **Xây dựng module mới song song trong `app/`**:
   - `app/core/config.py`: Quản lý đường dẫn Google Drive, màu sắc giao diện, tham số chung.
   - `app/data/loader.py`: Xử lý kết nối Google Sheets API và Dynamic Header Scanner an toàn.
   - `app/engines/stock.py`: Tính toán tồn kho realtime (15E + Y3C).
   - `app/engines/pricing.py`: Tính giá bán đa kênh (Shopee 140%, TikTok 140%).
   - `app/engines/image.py`: Cào ảnh sản phẩm từ web giayhainancy.vn.
   - `app/engines/qa.py`: Kiểm soát chất lượng dữ liệu (Strict QA Gate).
   - `app/platforms/website.py`: Xử lý Product Upload, Stock Import, In Tem, Đồng bộ kho.
   - `app/platforms/shopee.py`: Xử lý Upload mới và Cập nhật giá/tồn Shopee.
   - `app/platforms/tiktok.py`: Xử lý Upload mới (38 cột) và Cập nhật TikTok.
   - `app/platforms/misa.py`: Xử lý Danh mục và Nhập kho MISA (22 cột).
   - `app/cli/menu.py`: Giao diện dòng lệnh (Terminal Menu).
3. **Kiểm thử đối chiếu (Diff Check)**: Chạy đối chiếu song song giữa bản cũ và bản mới, đảm bảo kết quả xuất file khớp nhau từng ký tự trước khi chuyển đổi chính thức.

---

## 🚀 2. Ý TƯỞNG MỞ RỘNG TÍNH NĂNG TƯƠNG LAI (FEATURE IDEAS)

### 🛍️ A. Mở rộng thêm Nền tảng Bán hàng mới:
- [ ] **Lazada Upload & Update**: Thêm adapter xuất template chuẩn cho sàn Lazada.
- [ ] **Facebook Shop & Zalo Mini App Catalog**: Xuất định dạng Product Feed (CSV/XML) để đồng bộ sản phẩm tự động lên gian hàng Zalo và Facebook/Instagram.

### 🤖 B. Tự động hóa & Tích hợp (Automation & Integrations):
- [ ] **Kết nối Webhook / n8n**: Tự động kích hoạt cào ảnh hoặc đồng bộ tồn kho theo lịch trình (cron job) không cần bấm menu thủ công.
- [ ] **AI Description Generator**: Tự động dùng AI tạo nội dung mô tả sản phẩm (HTML SEO) hấp dẫn từ bảng thuộc tính chất liệu, kiểu dáng ở tab `SUB`.

### 🧾 C. Tự động Xuất File Yêu Cầu Hóa Đơn cho Nhà Cung Cấp (Supplier Invoice Request):
- [ ] **Bảng kê yêu cầu hóa đơn tự động theo 2 MST (Kho 15E & Kho Y3C)**:
  - Khi nhập hàng ở tab `NHAP`, hàng hóa được phân chia về 2 kho tương ứng với 2 Mã số thuế (MST) / Pháp nhân khác nhau.
  - Tự động gom nhóm theo từng Nhà cung cấp (NCC) và từng Kho/MST.
  - Xuất ra file Excel/PDF bảng kê chuẩn gửi cho NCC:
    - Thông tin đơn vị mua hàng (Tên công ty, MST, Địa chỉ xuất HĐ của Kho 15E hoặc Kho Y3C).
    - Danh sách hàng hóa: Tên sản phẩm, ĐVT, Số lượng thực nhập, Đơn giá hóa đơn (`invoice_price` từ `SANPHAM`).
    - Tính toán Thành tiền, % Chiết khấu, % Thuế GTGT (VAT) và Tổng tiền thanh toán (lấy từ `SUB`).
  - Giúp NCC xuất hóa đơn điện tử chính xác 100%, không bị nhầm lẫn giữa 2 pháp nhân/địa điểm.

### 📈 D. Phân tích Mặt Hàng Bán Chạy & Cảnh Báo Đặt Bù Số (Smart Inventory & Sales Analytics):
- [ ] **Phân tích Vận tốc Bán hàng (Best-Sellers Ranking)**:
  - Phân tích dữ liệu xuất bán từ tab `BAN` theo chu kỳ 7 ngày / 30 ngày / 90 ngày.
  - Xếp hạng Top mặt hàng bán chạy nhất theo từng Danh mục, Màu sắc và từng Size (ví dụ: Mẫu nào đang có lượng tiêu thụ đột biến ở size 36, 37 hoặc 39, 40).
  - So sánh hiệu quả bán hàng giữa các kênh (Website, Shopee, TikTok Shop, Cửa hàng MISA).
- [ ] **Cảnh báo Đứt hàng & Tự động Lập Phiếu Đặt Bù Số (Restock & PO Suggestion)**:
  - Tính toán số ngày tồn kho còn lại (`Days of Inventory` = `Tồn kho hiện tại` / `Tốc độ bán trung bình/ngày`).
  - Cảnh báo sớm các mã hàng/size sắp đứt hàng (chạm ngưỡng an toàn).
  - Tự động tạo **Bảng Đề Xuất Đặt Hàng Bù Số** gom theo từng Nhà cung cấp (NCC), ghi rõ số lượng từng size cần đặt bù để tối ưu hóa vốn lưu động và không bị mất doanh thu vì hết size.
- [ ] **Cảnh báo Hàng Chậm Luân Chuyển (Slow-moving / Deadstock Alert)**:
  - Nhận diện các mã hàng tồn lâu (> 60-90 ngày không bán được) để gợi ý chiến dịch giảm giá, Flash Sale xả tồn.

### ⚙️ E. Tập trung hóa Business Rules (Master Configuration):
- [ ] Chuyển các thông tin doanh nghiệp (Tên brand TikTok, địa chỉ tổ chức, mã nhà cung cấp, thông tin 2 MST của 2 kho) ra file cấu hình độc lập `config.json` hoặc đọc 100% từ tab `SUB`.

---

> 📌 **Ghi chú**: Mọi nâng cấp trong danh mục này đều phải tuân thủ nguyên tắc **"Thảo luận trước khi làm"** và **"Kiểm thử song song an toàn"**.
