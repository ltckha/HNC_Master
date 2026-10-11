# HNC Zalo Bot (Google Apps Script)

Bot Zalo quản lý bán hàng / kho, ghi thẳng vào **HNC_Control_Center**. Thay cho flow n8n cũ "QLBH Hải Nancy - Zalo", vốn ghi vào 2 Sheet cũ "Bán hàng 3C TBH" và "Bán hàng 15E TBH".

- Chạy 24/7 trên Google, không cần n8n, không cần bật Mac.
- Dùng lại bot Zalo cũ: chỉ đổi webhook, không tạo bot mới.
- Mọi đọc/ghi đều theo **tên cột hàng 1**.

## Bot hiểu những tin gì

| Nhắn | Bot làm |
|---|---|
| `AP0408D 40` hoặc `AP0408D` | Kiểm hàng ở KHOY3C + KHO15E (tồn, vị trí) |
| `bán AP0408D 40 YEN 450k` | Thêm dòng vào tab `BAN` |
| `nhập AP0408D 38/2 39 TBH` | Thêm dòng vào tab `NHAP` (38 × 2 đôi, 39 × 1 đôi) |
| `xuất AP0408D 41 15E` | Thêm dòng vào tab `XUAT` |
| `chuyển kho AP0408D 40 từ kho YEN đến kho TBH` | `XUAT` ở Y3C + `NHAP` ở 15E |
| `chuyển vị trí AP0408D YEN đến K12` | Sửa `product_location` trong tab KHO (không ghi size = đổi mọi size) |

- **Kho:** `YEN` / `3C` / `Y3C` → **Y3C**; `TBH` / `15E` → **15E**.
- **Size:** `40` = 1 đôi; `40/2` = 2 đôi.
- **Giá:** `450k`, `450000`, `450.000đ`.
- **Màu:** không cần ghi, bot tự lấy từ tab KHO. Có thể ghi `màu Đen`.
- Dòng NHAP ghi từ Zalo được điền `Zalo_Update` vào `web_stock`, `web_label`, `misa_stock` (HNC bỏ qua khi xuất web / tem / MISA). Cột `kho_sync` để trống, để tác vụ đồng bộ kho tự thêm SKU mới.
- FSKU: tab `BAN` và `XUAT` tự tính bằng ARRAYFORMULA có sẵn; tab `NHAP` thì bot ghi công thức từng dòng.

## Cài đặt (làm 1 lần)

### Bước 1 — Dán code
1. Mở Sheet **HNC_Control_Center** → **Tiện ích mở rộng → Apps Script**.
2. Xoá nội dung `Code.gs` mặc định, dán toàn bộ file `zalo_bot/Code.gs`.
3. **Cài đặt dự án** (bánh răng) → tick **Hiện tệp kê khai "appsscript.json"** → mở `appsscript.json`, dán nội dung file `zalo_bot/appsscript.json`.
4. Bấm **Lưu**.

### Bước 2 — Điền cấu hình
**Cài đặt dự án → Thuộc tính tập lệnh → Thêm thuộc tính:**

| Thuộc tính | Giá trị |
|---|---|
| `BOT_TOKEN` | Mã bot Zalo (lấy từ node "Edit Fields" trong flow n8n cũ) |
| `WEBHOOK_KEY` | Một chuỗi bí mật tự đặt, chỉ chữ và số, ví dụ 24 ký tự ngẫu nhiên |
| `DRY_RUN` | `true` (chạy thử, chưa ghi Sheet) |
| `ALLOWED_CHAT_IDS` | `0` lúc đầu (ô này không nhận giá trị trống; `0` = chưa cho ai dùng) |

### Bước 3 — Chạy thử không ghi Sheet
1. Chọn hàm **`testMessages`** → **Chạy**. Lần đầu Google sẽ hỏi cấp quyền → Cho phép.
2. Xem **Nhật ký thực thi**: mỗi tin mẫu hiện kết quả phân tích và câu trả lời của bot. Không có gì được ghi vào Sheet.

### Bước 4 — Triển khai Web App
1. **Triển khai → Tùy chọn triển khai mới → Loại: Ứng dụng web**.
2. *Thực thi dưới dạng:* **Tôi**. *Người có quyền truy cập:* **Bất kỳ ai**.
3. Bấm **Triển khai**, copy link kết thúc bằng `/exec`.
4. Thêm thuộc tính `WEBAPP_URL` = link vừa copy.

### Bước 5 — Chuyển bot sang Apps Script
1. Chạy hàm **`setupWebhook`** → Nhật ký phải báo `200` và `"ok":true`.
2. Chạy **`checkWebhook`** để xác nhận bot đã trỏ về link `/exec`.
3. Vào n8n → **tắt (Inactive)** flow "QLBH Hải Nancy - Zalo".

### Bước 6 — Cấp quyền nhân viên
1. Mỗi nhân viên nhắn bot 1 tin bất kỳ → bot trả lời "chưa được cấp quyền, chat_id của bạn: …".
2. Thay `0` trong `ALLOWED_CHAT_IDS` bằng các chat_id, cách nhau bằng dấu phẩy.

### Bước 7 — Chạy thật
1. Nhắn thử vài tin khi `DRY_RUN` = `true`: bot trả lời "🧪 CHẠY THỬ" kèm nội dung sẽ ghi.
2. Thấy đúng → đổi `DRY_RUN` thành `false`.
3. Nhắn 1 tin bán thử → kiểm tra dòng mới ở tab `BAN` và `current_quantity` trong tab KHO.

## Khi sửa code
Dán code mới vào Apps Script → **Triển khai → Quản lý triển khai → ✏️ → Phiên bản: Phiên bản mới → Triển khai**. Link `/exec` giữ nguyên, không cần chạy lại `setupWebhook`.

## Ghi chú kỹ thuật
- Chặn người lạ: chỉ chat_id trong `ALLOWED_CHAT_IDS` mới dùng được. Link webhook phải có `?key=WEBHOOK_KEY` (Apps Script không đọc được header bí mật của Zalo).
- Chống ghi trùng: mỗi `message_id` chỉ xử lý 1 lần trong 6 giờ.
- Ghi tuần tự bằng LockService. Dòng mới ghi ngay sau dòng cuối có `product_code`; hết lưới thì tự thêm 100 dòng.
- Thiếu cột theo tên → bot báo lỗi, không ghi sai cột.
