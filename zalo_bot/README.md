# HNC Zalo Bot (Google Apps Script)

Bot Zalo quản lý bán hàng / kho, ghi thẳng vào **HNC_Control_Center**. Thay cho flow n8n cũ "QLBH Hải Nancy - Zalo", vốn ghi vào 2 Sheet cũ "Bán hàng 3C TBH" và "Bán hàng 15E TBH".

- Chạy 24/7 trên Google, không cần n8n, không cần bật Mac.
- Dùng lại bot Zalo cũ: chỉ đổi webhook, không tạo bot mới.
- Mọi đọc/ghi đều theo **tên cột hàng 1**.

## Bot hiểu những tin gì

| Nhắn | Bot làm |
|---|---|
| `TH2040D 40` hoặc `TH2040D` | Kiểm hàng ở KHOY3C + KHO15E: giá bán (từ SANPHAM), tồn từng size (xếp tăng dần), vị trí |
| `TH2040` (mã không màu) | Kiểm hàng tất cả các màu TH2040D, TH2040N… |
| `ban TH2040D 40 YEN 800k` | Thêm dòng vào tab `BAN` |
| `nhap TH2040D 38/2 39 TBH` | Thêm dòng vào tab `NHAP` |
| `xuat TH2040D 41 15E` | Thêm dòng vào tab `XUAT` |
| `chuyen kho TH2040D 40 tu YEN den TBH` | `XUAT` ở Y3C + `NHAP` ở 15E |
| `chuyen vi tri TH2040D YEN den K12` | Sửa `product_location` trong tab KHO (không ghi size = đổi mọi size) |
| `huy` | Huỷ thao tác ghi gần nhất của chính người nhắn, trong 10 phút |
| `bc` / `bc hom qua` / `bc 10/10` | Báo cáo bán trong ngày: số đôi + doanh thu theo kho (tab `BAN`, Giá × số lượng) |
| `hd` / `?` / `huong dan` | Bảng hướng dẫn. Tin không hiểu cũng được trả lời bằng bảng này |

- **Kho:** `YEN` / `3C` / `Y3C` → **Y3C**; `TBH` / `15E` → **15E**.
- **Nhiều dòng:** 1 tin có nhiều dòng → mỗi dòng bắt đầu bằng `ban` / `nhap` / `xuat` là 1 lệnh, dòng khác (tên khách, ghi chú) bỏ qua. Bot trả kết quả từng dòng; `huy` huỷ cả lô. Cảnh báo tồn tính dồn trong lô. Tin 1 dòng chạy như cũ. Dùng để chuyển tiếp nguyên tin báo đơn web cho bot ghi.
- **Hàng không size, số lượng > 1:** `ban AROMAX60T x2 YEN 70k`, cũng nhận `x 2`, `*2`, `/2`, `sl 2`, `sl2`, `2 cái`, `2 đôi`.
- **Size / số lượng:** `40` (1 đôi), `40/2`, `40.2`, `40x2`, `40*2`, `40:2`, `40-2`, `40 x2`, `40 2 đôi`, `40 sl 2`, `2 đôi 40`, `38,39,40`, dải `38-43` (mỗi size 1 đôi). Size trùng thì cộng dồn.
- **Giá:** `800k`, `800000`, `800.000đ`, `800,000`, `1tr2`, `1.5tr`. Không ghi giá thì cột Giá để trống (giá bán có thể khác giá niêm yết).
- **Mã:** bot so với danh sách mã thật trong tab KHO trước (nhận được mã không có số như `CXED`, mã ngắn như `T1D`, mã giống giá như `119K`). Mã mới chưa có trong KHO thì đoán theo mẫu chữ + số + chữ màu.
- **Gõ không dấu** vẫn hiểu (`ban`, `nhap`, `xuat`, `chuyen kho`, `huy`, `bao cao`). "bạn" không bị nhầm là "bán".
- **Màu:** không cần ghi, bot tự lấy từ tab KHO. Có thể ghi `màu Đen`.
- **Cảnh báo:** bán / xuất quá tồn → vẫn ghi nhưng báo "⚠️ tồn sẽ âm". SKU chưa có trong KHO → báo tồn không trừ. Thiếu size khi mã có size → bot hỏi lại kèm danh sách size.
- **Huỷ:** bot kiểm tra lại từng dòng trước khi huỷ; dòng đã bị sửa hoặc dòng NHAP đã đồng bộ kho (`kho_sync`) thì từ chối. Huỷ chỉ xoá các ô bot đã ghi, không xoá dòng.
- Dòng NHAP ghi từ Zalo được điền `Zalo_Update` vào `web_stock`, `web_label`, `misa_stock` (HNC bỏ qua khi xuất web / tem / MISA). Cột `kho_sync` để trống, để tác vụ đồng bộ kho tự thêm SKU mới.
- FSKU: tab `BAN` và `XUAT` tự tính bằng ARRAYFORMULA có sẵn; tab `NHAP` thì bot ghi công thức từng dòng.

## Cửa "ghi bán" cho app bán hàng (API)

App bán hàng (và sau này web) ghi đơn vào tab `BAN` qua cửa riêng. Cửa này **không** dùng chung khoá với webhook Zalo.

**Cấu hình:** thêm thuộc tính `SALE_KEY` vào Script Properties: chuỗi ngẫu nhiên ≥ 16 ký tự, **khác** `WEBHOOK_KEY`. Không gửi khoá qua chat; anh tự đặt khoá ở phía app/Worker (vd `wrangler secret put SALE_KEY`). Lộ khoá → đổi `SALE_KEY` ngay (đổi xong không cần triển khai lại).

**Gọi:**
```
POST {WEBAPP_URL}?sale_key=<SALE_KEY>
Content-Type: application/json   (hoặc text/plain)

{
  "ticket_id": "APP-20261014-0001",      // mã phiếu duy nhất: 1-64 ký tự chữ/số/_ . : -
  "channel": "cua_hang",                  // cua_hang | web | shopee | tiktok
  "seller": "Tên người bán",              // ≤ 50 ký tự
  "lines": [                              // 1-50 dòng
    { "code": "TH2040D", "size": 40, "qty": 1, "warehouse": "15E", "price": 800000 }
  ],
  "dry_run": true                         // tuỳ chọn: chỉ kiểm tra, không ghi
}
```
- `warehouse`: `15E` / `Y3C` (nhận cả `TBH`, `YEN`, `3C`). `size` bỏ trống với hàng không size. `qty` 1-99, mặc định 1. `price` tuỳ chọn.
- Apps Script trả lời qua 1 lần chuyển hướng (302). Bên gọi phải **đi theo chuyển hướng** (`fetch` mặc định đã theo; `curl` cần `-L`).

**Trả về (JSON):**
- `{"ok":true,"ticket_id":...,"dry_run":false,"rows":N,"results":[{"line":1,"code":...,"size":...,"qty":...,"warehouse":...,"stock_before":...,"row":...,"warning"?:...}]}`
- Có dòng lỗi → `{"ok":false,"error":"Có dòng lỗi, chưa ghi dòng nào","results":[...{"ok":false,"error":"..."}]}`. **Không ghi dòng nào.**
- Gửi lại cùng `ticket_id` → `{"ok":true,"duplicate":true,...}`, không ghi thêm. Mã phiếu được nhớ 30 ngày.
- Ghi dở do lỗi giữa chừng → `{"ok":false,"partial":true,"rows":<đã ghi>}`. **Không gửi lại**, kiểm tra tab `BAN`.
- Sai khoá → `{"ok":false,"error":"unauthorized"}`.
- Cảnh báo (vẫn ghi): bán quá tồn (`tồn X < bán Y → tồn âm`), SKU chưa có trong tab KHO.

**Ghi vào BAN:** mỗi dòng phiếu = 1 dòng BAN (Ngày, product_code, product_color tự lấy, Giá, item_size, item_quantity, KHO, `channel`, `seller`). Lệnh `ban` gõ qua Zalo ghi `channel` = `cua_hang`, `seller` = tên Zalo người nhắn. Nếu tab BAN chưa có cột `channel` / `seller` thì bot bỏ qua 2 cột đó, phần còn lại ghi bình thường.

**Chạy thử trong Apps Script:** chạy hàm `testSale` (luôn dry-run, không ghi Sheet).

## Cửa "báo đơn web" (API)

Web gửi tin báo đơn mới tới **chat Zalo của anh** qua bot. Cửa này **chỉ nhắn tin**: không đọc lệnh, không ghi Sheet.

**Cấu hình** (Script Properties):
- `WEB_NOTIFY_KEY`: chuỗi ngẫu nhiên ≥ 16 ký tự, khác `WEBHOOK_KEY` và `SALE_KEY`. Đặt cùng giá trị vào secret của Worker web. Không gửi qua chat.
- `OWNER_CHAT_ID`: chat_id Zalo của anh. Nhắn bot 1 tin từ một tài khoản chưa được cấp quyền để biết chat_id, hoặc lấy trong `ALLOWED_CHAT_IDS`.

**Gọi:**
```
POST {WEBAPP_URL}?notify_key=<WEB_NOTIFY_KEY>
Content-Type: application/json

{ "order_id": "W-20261015-001", "text": "🛒 Đơn web #W-20261015-001\nKhách: …\nban TH2040D 40 15E 800k" }
```
- `order_id`: 1-64 ký tự chữ / số / `_ . : -`. Gửi lại cùng `order_id` → `{"ok":true,"duplicate":true}`, không nhắn lần 2 (nhớ 30 ngày).
- `text` dài quá 1.800 ký tự thì bị cắt bớt (`"truncated":true`).
- Trả về: `{"ok":true,"order_id":…}`. Lỗi: `unauthorized`, `chưa cấu hình …`, `Zalo không nhận tin` (khi Zalo từ chối, lần sau gửi lại được).
- Gợi ý: để sẵn các dòng `ban …` trong `text`. Anh xác nhận với khách xong thì **chuyển tiếp nguyên tin** cho bot, bot ghi BAN từng dòng.

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
| `WEBHOOK_KEY` | Chuỗi bí mật tự đặt, 8-256 ký tự, chỉ chữ không dấu, số, `_` và `-` (ví dụ ~20 ký tự ngẫu nhiên) |
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

## Cập nhật bot bằng clasp (không cần dán tay)

Bấm đúp `commands/bot_deploy.command`. Lệnh này chạy lần lượt:
1. Test trên máy: `node zalo_bot/tests/test_zalo_bot.js`. Test sai thì dừng, bot thật không đổi.
2. `clasp push --force`: đẩy `Code.gs` và `appsscript.json` lên script. scriptId nằm trong `zalo_bot/.clasp.json`.
3. `clasp create-deployment -i <deployment_id>`: tạo phiên bản mới cho **đúng bản triển khai đang chạy** (trong `zalo_bot/deploy.json`). Link `/exec` giữ nguyên, không cần `setupWebhook` lại.

**Quay về bản cũ:**
```
cd zalo_bot
clasp list-versions                          # xem số phiên bản
clasp create-deployment -i <deployment_id> -V <số phiên bản cũ>
```

**Lưu ý**
- clasp đăng nhập tài khoản ltckha@gmail.com. Khoá lưu ở `~/.clasprc.json`, không bao giờ đưa vào git.
- Trên Google, tệp mã tên là "Mã". `clasp push` thay toàn bộ nội dung script bằng `Code.gs` + `appsscript.json` của repo.
- Vẫn có thể cập nhật tay: dán `Code.gs` vào Apps Script → **Triển khai → Quản lý triển khai → ✏️ → Phiên bản mới**.

## Ghi chú kỹ thuật
- Chặn người lạ: chỉ chat_id trong `ALLOWED_CHAT_IDS` mới dùng được. Link webhook phải có `?key=WEBHOOK_KEY` (Apps Script không đọc được header bí mật của Zalo).
- Chống ghi trùng: mỗi `message_id` chỉ xử lý 1 lần trong 6 giờ.
- Ghi tuần tự bằng LockService. Dòng mới ghi ngay sau dòng cuối có `product_code`; hết lưới thì tự thêm 100 dòng.
- Thiếu cột theo tên → bot báo lỗi, không ghi sai cột.
