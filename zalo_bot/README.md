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
| `nhap TH2040D 40 15E tra hang` | **Khách trả hàng / huỷ đơn đã bán**: ghi 1 dòng NHAP với Số chứng từ `TRA-<ddMMyy>`, cột `web_stock` / `web_label` / `misa_stock` = `Tra_hang`, nên không xuất phiếu nhập MISA và web không tính là hàng mới về. Nhận cả `trả hàng`, `tra lai`, `khach tra`; dùng được trong tin nhiều dòng |
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
  "channel": "cua_hang",                  // cua_hang (ghi ô trống) | web | shopee | tiktok | lazada | zalo | facebook
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

**Ghi vào BAN:** mỗi dòng phiếu = 1 dòng BAN (Ngày, product_code, product_color tự lấy, Giá, item_size, item_quantity, KHO, `channel`, `seller`). **Quy ước kênh (anh Kha chốt 16/10):** ô `channel` **trống** = bán tại cửa hàng theo KHO (Y3C = cửa hàng 3C, 15E = cửa hàng 15E). Chỉ ghi `channel` khi bán ngoài cửa hàng: `web`, `shopee`, `tiktok`. Dữ liệu cũ ghi `cua_hang` vẫn được hiểu là cửa hàng. Lệnh `ban` qua Zalo: bán tại quầy để trống `channel`; thêm chữ `shopee` / `tiktok` (`tt`) / `web` / `lazada` / `zalo` / `facebook` (`fb`) trong tin (vd `ban BT01D 40 YEN shopee`) thì ghi kênh đó. Cửa ghi bán của app nhận `cua_hang` nhưng ghi ô trống. `seller` = tên Zalo người nhắn. Nếu tab BAN chưa có cột `channel` / `seller` thì bot bỏ qua 2 cột đó, phần còn lại ghi bình thường.

**Chạy thử trong Apps Script:** chạy hàm `testSale` (luôn dry-run, không ghi Sheet).

## Cửa "kho" cho app điện thoại (API)

Các thao tác kho từ app đi qua bot, dùng lại đúng hàm của lệnh Zalo: cùng kiểm tra, cùng cảnh báo tồn âm, cùng cách ghi Sheet theo tên cột.

**Khoá:** `STOCK_KEY` trong Script Properties, ≥ 16 ký tự, khác các khoá khác. Không dùng chung `SALE_KEY`, vì thao tác kho (xuất, chuyển kho, huỷ) quyền mạnh hơn ghi bán, nên cần khoá / đổi được độc lập. Web giữ cùng giá trị bằng `wrangler secret put STOCK_KEY`.

**Gọi:** `POST {WEBAPP_URL}?stock_key=<STOCK_KEY>`, body JSON. Mọi thao tác đều có `action`, `ticket_id` (1-64 ký tự chữ / số / `_ . : -`, chống ghi trùng 30 ngày), `seller` (email người dùng app), `dry_run` (tuỳ chọn).

| action | Trường thêm | Ghi vào |
|---|---|---|
| `nhap` | `lines: [{code, size, qty, warehouse}]` | NHAP (dấu `Zalo_Update`, giống lệnh `nhap`) |
| `tra_hang` | như `nhap` | NHAP, Số chứng từ `TRA-<ddMMyy>`, dấu `Tra_hang` (không xuất phiếu nhập MISA) |
| `xuat` | `lines: [{code, size, qty, warehouse}]` | XUAT |
| `chuyen_kho` | `from`, `to` + `lines: [{code, size, qty}]` | XUAT ở kho nguồn + NHAP ở kho đích |
| `chuyen_vi_tri` | `warehouse`, `location` + `lines: [{code, size?}]` | `product_location` tab KHO. Vị trí dạng `K12` / `B2` / `T4` / `S1` / `TH2` (K kệ, B bàn, T tủ, S sọc, TH thùng). Bỏ `size` = mọi size của mã |
| `huy` | `undo_ticket_id` | Huỷ thao tác có `ticket_id` đó, **chỉ của chính `seller`**, trong ≤ 10 phút. Kiểm lại từng dòng như lệnh `huy`; dòng đã bị sửa / NHAP đã đồng bộ kho thì từ chối |

- `warehouse` / `from` / `to`: `15E` / `Y3C` (nhận cả `TBH`, `YEN`, `3C`). `size` bỏ trống với hàng không size. `qty` 1-99, mặc định 1. Tối đa 50 dòng.
- Mã phải có trong SANPHAM hoặc tab KHO.
- Kiểm hết các dòng trước (chạy thử); có dòng lỗi thì **không ghi dòng nào**.

**Ví dụ:**
```json
{ "action": "xuat", "ticket_id": "APP-K-20261016-0001", "seller": "nv@giayhainancy.vn",
  "lines": [{ "code": "TH2040D", "size": 41, "qty": 1, "warehouse": "Y3C" }], "dry_run": true }
```
Trả về:
```json
{ "ok": true, "action": "xuat", "ticket_id": "APP-K-20261016-0001", "dry_run": false,
  "results": [{ "line": 1, "code": "TH2040D", "size": "41", "qty": 1, "warehouse": "Y3C", "ok": true,
                "warnings": ["size 41 kho Y3C: tồn 0, xuất 1 → tồn sẽ âm. Kiểm tra lại kho."], "rows": ["XUAT!2560"] }],
  "undo_until": "2026-10-16T03:15:00.000Z" }
```
- **Lỗi** (`ok: false`):
  - `unauthorized` / `chưa cấu hình STOCK_KEY…`.
  - `action phải là…`, `ticket_id không hợp lệ`, `thiếu seller`.
  - `Có dòng lỗi, chưa ghi dòng nào` kèm `results[].error`: `mã không hợp lệ`, `mã không có trong SANPHAM / KHO`, `size không hợp lệ`, `qty…`, `warehouse…`, `from / to…`, `vị trí phải dạng…`, `Thiếu size…`.
  - `duplicate: true` (gửi lại cùng `ticket_id`, không ghi thêm); `partial: true` (ghi dở, **không gửi lại**).
  - Với `huy`: `không có thao tác để huỷ…`, `chỉ huỷ được thao tác của chính mình`, `Không huỷ được vì dữ liệu đã thay đổi…`.
- Ghi xong (kể cả huỷ), bot tự báo web chép lại đúng tab (NHAP / XUAT / KHO… kèm KHO15E, KHOY3C).

## Nhập từ phiếu nhà cung cấp (API cho web /admin + app)

Luồng: chụp / tải ảnh phiếu trên web /admin hoặc app → Gemini đọc (1 lượt / phiếu) → **phiếu nháp** → chia mã (tách màu) × kho × size khi đếm hàng thật → xác nhận → (mã mới: tạo SANPHAM + KHO) → ghi NHAP bằng đúng hàm `nhap`. Bản V2, anh Kha "LÀM" 16/10: **không nhận ảnh phiếu qua Zalo**.

- **Khoá:** dùng chung `STOCK_KEY` (cùng màn Kho của app, cùng quyền nhập kho). Gọi `POST {WEBAPP_URL}?stock_key=<STOCK_KEY>` với `action` dưới đây. Cần thêm Script Properties `GEMINI_API_KEY`.
- **Lưu phiếu:** Drive riêng tư `Phiếu mua hàng` (theo ID `PN_FOLDER_ID`, mặc định thư mục có sẵn).
  - Chưa chia kho: `Chưa chia/<NCC>/<mã>.jpg + <mã>.json`.
  - Xác nhận xong: chuyển sang `<hộ>/<NCC>/` (Hải Nancy = 15E, Yen Leather = Y3C; chia cả 2 kho thì hộ thứ 2 có bản sao ảnh).
  - Chỉ mục ở Script Properties `pnx_<mã>`.
- **Giá / NCC chỉ HNC giữ:** mọi trả về cho web KHÔNG có đơn giá. Riêng `xem_nhap` có `kem_gia: true` thì trả giá (chỉ dùng cho HNC).

| action | Gửi | Trả |
|---|---|---|
| `doc_phieu` | `anh_base64` (≤ 8 MB, nên nén ~2 MB), `mime`, `nguon` ("app" / "web"), `nguoi` (email) | `{ok, id, ncc_ten, so_phieu, ngay, so_dong, so_doi, trang_thai:"cho_chia", model}`. Lỗi Gemini: `{ok:false, error}` (hết lượt miễn phí thì báo rõ) |
| `ds_nhap` | `limit?` (50), `tat_ca?` (hiện cả phiếu đã bỏ) | `{ok, phieu:[{id, ncc_ten, so_phieu, ngay, so_dong, so_doi, trang_thai}]}`, mới nhất trước. `trang_thai`: `cho_chia` / `da_ghi` / `huy` |
| `xem_nhap` | `id`, `kem_anh?` | `{…đầu phiếu, dong:[{dong, ma_ncc, mo_ta, sl_phieu, goi_y_ma_hnc?}], da_ghi?, anh_mime?, anh_base64?}` |
| `xac_nhan` | `id`, `ticket_id`, `nguoi`, `dry_run?`, `dong:[{dong, ma_hnc, kho, sizes:{"39":2,"40":1}, sl?, ly_do?, ghi_chu?}]`, `ma_moi?:[{ma_hnc, ma_goc?, mau, day_size?, ten_tam?, nganh?}]` | Giống cửa kho: `{ok, results:[…, dong_phieu], canh_bao:[…], tao_moi:{sanpham:[mã], kho:["15E 32837D 38",…]}, undo_until}` |
| `huy_nhap` | `ticket_id` (của `xac_nhan`), `nguoi` | `{ok, id}`. Chỉ của chính `nguoi`, ≤ 10 phút; phiếu về `cho_chia` |
| `bo_nhap` | `id`, `nguoi` | `{ok, trang_thai:"huy"}`. Chỉ phiếu `cho_chia` (quyền "Chủ" do app kiểm) |

- **`xac_nhan`:**
  - Mỗi dòng phiếu: tổng `sizes` (hàng không size dùng `sl` hoặc khoá `""`) phải bằng `sl_phieu`. Lệch thì bắt buộc `ly_do`: `thieu` / `du` / `loi_tra_lai` / `khac`, ghi vào `canh_bao` và lưu kèm phiếu. Không nhận dòng nào thì gửi `sizes` rỗng + `ly_do`.
  - **Tách màu:** 1 dòng phiếu gửi nhiều phần tử `dong` (cùng số `dong`), mỗi phần tử 1 mã × 1 kho (15E / Y3C) × `sizes`. Tổng mọi mã / kho / size so với `sl_phieu`.
  - Mã phải có trong SANPHAM / KHO, hoặc khai trong `ma_moi`. Mã trong `ma_moi` mà đã có thì nhập như mã cũ (có `canh_bao`).
  - **Mã mới (`ma_moi`):** `ma_hnc` = mã gốc + chữ màu (`ma_goc` mặc định bỏ ký tự cuối), `mau` bắt buộc, `day_size` = dãy size của mẫu (cộng thêm size đang nhập), `ten_tam` mặc định mô tả dòng phiếu, `nganh` tuỳ chọn.
    - SANPHAM: thêm 1 dòng sau dòng cuối, chép công thức của dòng cuối (mã cha, giới tính, size, ngành…), điền mã, màu, `product_name` = "CẦN BỔ SUNG - <tên tạm>", `supplier` = NCC; thuộc tính chữ (ngành, chất liệu, đơn vị…) lấy từ dòng cùng mã cha nếu có. **Không ghi giá.** Cột đăng sàn / MISA để trống.
    - KHO: thêm dòng tồn đầu 0 cho **cả 2 kho × day_size** (công thức FSKU + tồn hiện tại dựng theo tên cột NHAP / XUAT / BAN, giống menu HNC "Đồng bộ SKU").
    - Mã cũ nhập size / kho chưa có dòng KHO: thêm dòng KHO đó luôn (lấy vị trí kệ của dòng cùng mã).
    - Ghi xong gửi sync-hint `SANPHAM`, `KHO15E`, `KHOY3C`, `NHAP` (gom 60 giây như mọi lần ghi).
    - Mã còn "CẦN BỔ SUNG" tự bị **bỏ qua** khi menu HNC xuất web cũ / Shopee / TikTok / MISA (danh mục + phiếu nhập; in 1 dòng "Bỏ qua n mã chưa bổ sung", trạng thái để trống để xuất sau) và khi cổng `mark_exported` đánh dấu (trả `chua_bo_sung`). In tem, đồng bộ kho vẫn chạy. Bổ sung xong: sửa `product_name` (bỏ chữ "CẦN BỔ SUNG"), điền giá / thuộc tính.
  - Tồn hiện tại và các màu của mã gốc: web tự lấy từ D1, không có API tra.
  - Kiểm hết trước: có dòng lỗi (`loi_dong` hoặc `results[].error`) thì không ghi dòng nào.
- **Dòng NHAP:**
  - Như nhập thường (anh Kha 16/10): không đánh dấu `Zalo_Update`, nên menu HNC in tem, đồng bộ kho, xuất phiếu nhập MISA.
  - `Số chứng từ (*)` = mã phiếu (`PN<yyMMdd>-XXXX`); `Ngày chứng từ` = ngày xác nhận.
  - Bot học bảng ghép (mã NCC / mô tả → mã HNC; dòng tách nhiều màu thì nhớ mã gốc) để gợi ý lần sau.
- **Huỷ (`huy_nhap`, ≤ 10 phút):** xoá các dòng NHAP vừa ghi; dòng SANPHAM / KHO tạo mới cũng xoá (cả ô công thức). Nếu mã mới (kho × size) đã có giao dịch khác (NHAP khác, bán, xuất) thì **không huỷ gì**, báo để sửa tay.
- **Hoá đơn NCC:** dòng NHAP có `Số chứng từ` = mã phiếu thì phiếu × kho lấy NCC theo phiếu, và câu nhắn ghi "theo phiếu xuất <số phiếu NCC>".
- **Gemini:** thử `gemini-2.5-flash` trước (khoá miễn phí nhiều lượt nhất), lỗi thì 3.6 → 3.8 Flash; mọi model báo 429 thì trả lỗi "hết lượt miễn phí". Model đã dùng lưu trong phiếu (`model`).
- **Zalo chỉ báo tin:** đọc phiếu xong bot nhắn `OWNER_CHAT_ID` "📄 Có phiếu chờ chia: <NCC> <số> · n dòng · m đôi → <web>/admin/app#phieu-<mã>". Link lấy từ `APP_URL`, mặc định gốc của `SYNC_HINT_URL` + `/admin/app`. Bot **không** nhận ảnh phiếu qua Zalo (ảnh gửi vào bot bị bỏ qua, ghi Nhật ký).

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

## Theo dõi hoá đơn nhà cung cấp (lệnh `hoadon`)

Không thêm tab hay cột nào vào Sheet; bot tự tính từ dữ liệu sẵn có.

- **Phiếu** = ngày nhập + nhà cung cấp + kho, gom từ tab NHAP.
  - Nhà cung cấp lấy theo mã ở cột `supplier` của SANPHAM; mã NCC và tên pháp lý lấy ở SUB.
  - **2 kho = 2 hộ kinh doanh**, mỗi hộ 1 hoá đơn riêng. Mã phiếu dạng `260925-TP-15E` (ngày yyMMdd, mã NCC bỏ chữ "NCC", kho).
  - Dòng NHAP chưa có KHO (chưa chia hàng) thì chưa đòi hoá đơn. Bỏ dòng trả hàng (`TRA-`) và dòng SL 0.
  - Tiền = SL × `invoice_price` (đơn giá hoá đơn trong SANPHAM).
- **Hoá đơn đã về:** bot tự đọc thư mục Drive `Hoá đơn 2026/<hộ>/<nhà cung cấp>/<yyyymmdd>/` (tìm theo ID; trước ở `Thue2026`, nay `HNC/Thue/2026`) (thư mục ngày có file).
  - Hộ "Hải Nancy" = kho **15E**, "Yen Leather" = kho **Y3C**.
  - Mỗi thư mục ngày được ghép với **phiếu gần nhất chưa ghép** có ngày nhập ≤ ngày hoá đơn.
  - Đổi thư mục (vd năm 2027): đặt `INVOICE_FOLDER_ID`.
- **Lệnh:**
  - `hoadon`: danh sách phiếu từ 01/09/2026 chưa có hoá đơn, nhóm theo nhà cung cấp; ⏰ = quá 7 ngày.
  - `hoadon <mã phiếu>`: trạng thái + **câu nhắn soạn sẵn** gửi nhà cung cấp: tên / MST / địa chỉ của hộ kinh doanh, hàng gom gọn theo **mã cha** (cùng mẫu khác màu cộng lại, vd `CT2637 x 6`), dòng `Tổng: N sản phẩm`, không ghi tên / giá.
  - `hoadon <mã phiếu> da` / `khong` / `chua`: sửa tay, thắng kết quả tự ghép. Mã phiếu gõ một phần thì áp cho mọi phiếu khớp (vd `hoadon 260925-TP da` = cả 2 kho). Lưu ở Script Properties `hdon_<mã>`.
- **Nhắc tuần:** trigger `weeklyInvoiceReminder` 8:00 sáng thứ Hai gửi `OWNER_CHAT_ID` các phiếu quá 7 ngày chưa có hoá đơn, kèm câu nhắn soạn sẵn (tối đa 10 câu).
- **Cấu hình** (Script Properties):
  - `HKD_15E`, `HKD_Y3C` = `Tên | MST | Địa chỉ`.
  - Chạy lại `setupChangeTrigger` để thêm trigger nhắc tuần.
  - Lần đầu Google sẽ hỏi quyền đọc Drive.
  - `checkConfig` báo HKD, thư mục Drive và trigger. `testInvoice` in danh sách + tin nhắc mà không gửi Zalo.

## Cửa "đánh dấu đã xuất file sàn" (API, web gọi)

Web cũng xuất file Shopee / TikTok, chạy song song với menu HNC. Web xuất xong thì gọi cửa này để cờ trên Sheet khớp với menu HNC.

**Cấu hình:** Script Properties `EXPORT_KEY`: ≥ 16 ký tự, khác `WEBHOOK_KEY` / `SALE_KEY` / `WEB_NOTIFY_KEY` / `SYNC_HINT_KEY`. Đặt cùng giá trị vào secret của web.

**Gọi:**
```
POST {WEBAPP_URL}?export_key=<EXPORT_KEY>
{ "action": "mark_exported", "channel": "shopee" | "tiktok", "kind": "upload" | "update",
  "codes": ["TH2040D", ...], "at": "2026-10-15T03:05:00Z", "dry_run": true }
```
- **`kind: "upload"`:** ghi tab SANPHAM, cột `shopee_upload` / `tiktok_upload` = `Done - yyyy-MM-dd HH:mm` (giờ VN, cùng định dạng main.py) cho các mã trong `codes`. Mã không có trong SANPHAM → trả trong `not_found`. Tối đa 3.000 mã / lần.
- **`kind: "update"`:** ghi mốc "lần cập nhật tồn/giá gần nhất" vào **tab `META`** (cột `key` | `value` | `updated_at`), dòng key = `shopee_last_update` / `tiktok_last_update`: `value` = giờ xuất (`yyyy-MM-dd HH:mm`), `updated_at` = giờ ghi. Tìm dòng theo key; chưa có dòng thì thêm dòng mới. Menu HNC cũng ghi vào đúng dòng này mỗi lần xuất `SHOPEE_UPDATE` / `TIKTOK_UPDATE`. Chưa có tab META thì báo lỗi, không tự tạo. Mốc này nghĩa là **lần cập nhật TỒN gần nhất**: file không có cột tồn (vd mẫu TikTok `All_Information`) thì gửi `"stock_included": false`, bot trả lỗi "mẫu không có cột tồn" và không ghi. Menu HNC cũng chỉ ghi mốc khi file có ghi tồn.
- `at` bỏ trống = giờ hiện tại.
- **Trả về:** `{"ok":true,"kind":…,"written":N,"not_found":[…],"dry_run":…}`. Gửi lại đúng nội dung cũ thì trả `duplicate:true` và không ghi lần nữa (nhớ 30 ngày). Ghi xong, bot báo web chép lại SANPHAM (hoặc META).

## Báo web chép lại Sheet khi Sheet đổi

Khi tab `SANPHAM`, `KHO15E`, `KHOY3C`, `BAN`, `NHAP`, `XUAT` hoặc `SUB` thay đổi, bot báo web giayhainancy.vn chép lại Sheet, không phải chờ vòng chép mỗi giờ.

- **Nguồn báo:**
  - Trigger cài đặt `onEdit` + `onChange`, bắt khi người sửa trên Sheet.
  - Bot tự báo sau khi ghi BAN / NHAP / XUAT / vị trí: lệnh Zalo, `huy`, cửa ghi bán.
- **Gộp:** tên tab vào hàng chờ, mỗi phút gửi **tối đa 1 lần**: `POST SYNC_HINT_URL?key=SYNC_HINT_KEY`, body `{"tabs":[...]}`. Đổi BAN / NHAP / XUAT thì gửi kèm `KHO15E`, `KHOY3C`. Trigger mỗi phút gửi phần còn lại trong hàng chờ.
- **Web trả:** 202 ok · 403 sai khoá · 503 web chưa đặt khoá · 429 quá 60 lần/giờ. Lỗi chỉ ghi Nhật ký, không gửi dồn lại.
- **Ghi từ `main.py`** (AI nhập SP, đồng bộ kho, cột trạng thái, cào ảnh): Google không chạy trigger cho ghi qua Sheets API. Vì vậy `main.py` tự gửi 1 báo gộp sau mỗi tác vụ có ghi. Cấu hình `SYNC_HINT_URL`, `SYNC_HINT_KEY` trong `HNC_Master/.env` (mẫu ở `.env.example`). Thiếu cấu hình hoặc lỗi thì chỉ in cảnh báo.

**Cài (anh làm 1 lần):**
1. Script Properties:
   - `SYNC_HINT_URL` = `https://giayhainancy-web.giayhainancy-web.workers.dev/api/sync-hint`
   - `SYNC_HINT_KEY` = cùng giá trị với secret bên web.
2. Chạy hàm `setupChangeTrigger`, cho phép quyền khi Google hỏi. Hàm tạo 3 trigger, chạy lại cũng không tạo trùng.
3. Chạy `checkConfig`: 2 thuộc tính mới và 3 trigger đều ✅.
4. Chạy `testSyncHint`: trả `202` là web đã nhận.

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
