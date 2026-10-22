# HNC Zalo Bot (Google Apps Script)

Bot Zalo quản lý bán hàng / kho, ghi thẳng vào **HNC_Control_Center**. Thay cho flow n8n cũ "QLBH Hải Nancy - Zalo", vốn ghi vào 2 Sheet cũ "Bán hàng 3C TBH" và "Bán hàng 15E TBH".

- Chạy 24/7 trên Google, không cần n8n, không cần bật Mac.
- Dùng lại bot Zalo cũ: chỉ đổi webhook, không tạo bot mới.
- Mọi đọc/ghi đều theo **tên cột hàng 1**.

## Tin bot tự gửi (anh Kha 18/10: hạn chế tự động nhắn)

Chỉ còn 3 loại tự lên Zalo: **đơn web mới** và **doanh thu năm hộ chạm mốc** (đều qua cửa notify, web tự lọc) và **nhắc hoá đơn NCC thứ Hai 8:00**. Tin trả lời lệnh của anh / nhân viên giữ nguyên.
Đã tắt (chỉ ghi Nhật ký): phiếu nhập chờ chia (`pn`), MISA cuối ngày (`misa_ngay`, trigger 21:00 đã gỡ 22/10 — chỉ chạy tay), tin hoá đơn MISA khi khách lấy HĐ (`misa_hd`), tin "❌ HUỶ phiếu" (`misa_huy`), báo web lỗi / chạy lại (`web_loi`), lệch giá hoá đơn (`hd_lech` — web vẫn nhận `lech_gia` / `sua_misa` trong kết quả `hoa_don ghi`). Bật lại loại nào: Script Property `AUTO_ZALO` = các mã trên, cách nhau dấu phẩy.

## Điều khiển bằng số (anh Kha "làm" 17/10, như bot xưởng)

- Nhắn `menu` / `m` (hoặc chữ bot không hiểu) → menu số kèm số việc chờ (N). Tin 1 chữ số trả lời câu hỏi bot gửi sau cùng cho người đó (nhớ 720 phút, Script Property `ask_<chat_id>`). Không có câu hỏi đang mở → bot gửi menu, không đoán. `0` = để sau, `9` = về menu.
- Menu: 1 Kiểm hàng (bot hỏi mã) · 2 Báo cáo bán (1 hôm nay · 2 hôm qua · 3 tuần này) · 3 Phiếu nhập chờ chia (duyệt lần lượt, 1 = gửi link app chia size) · 4 Hoá đơn NCC chưa có quá 7 ngày (duyệt lần lượt kèm câu nhắn gửi NCC: 1 đã có · 2 không lấy · 3 chưa, tuần sau nhắc · 0 để sau) · 5 Mã cần bổ sung (danh sách + link web) · 6 Huỷ thao tác vừa rồi (nhắn 6 hai lần trong 10 phút) · 9 Hướng dẫn lệnh chữ.
- Nhân viên thấy 1, 2, 6, 9; Chủ (`OWNER_CHAT_ID`) thấy thêm 3, 4, 5. Lệnh chữ cũ giữ nguyên (`hd` vẫn là hướng dẫn).
- Tin tự gửi kết bằng dòng "Nhắn số: …": phiếu chờ chia (1 mở app), nhắc hoá đơn thứ Hai (gộp 1 tin, 4 duyệt từng phiếu) và đơn web (9 menu).

## Dự phòng khi web / app lỗi (anh Kha "làm" 17/10)

- **Báo web gửi lại:** sync-hint lỗi thì bot giữ hàng chờ, thử lại sau 5′ / 15′ / rồi mỗi 1 giờ (Script Property `sync_retry`). Lỗi lần 2 → nhắn Chủ kèm bảng dự phòng; web chạy lại → nhắn "✅ Web chạy lại".
- **Nhập có số chứng từ:** `nhap TH2040D 38/2 TBH NK000045` (hoặc chữ `misa` để bot lấy số NK theo kho, cùng kho + NCC + ngày thì dùng chung) → dòng NHAP như phiếu thường (không đánh dấu `Zalo_Update`) → vào tem + file nhập kho MISA. Không có số → `Zalo_Update` như cũ. App: dòng / phiếu `nhap` nhận `so_chung_tu` hoặc `misa: true`.
- **Bán qua Zalo:** thêm `tm` (mặc định) / `ck` / `the` và `sdt 09…` (hoặc số điện thoại trần). Ghi BAN cột `payment_method` (Tiền mặt / Chuyển khoản / Thẻ — trùng danh sách MISA) và `customer_phone`. Cửa ghi bán của app cũng ghi 2 cột này (từ `thanh_toan`, `khach.sdt`).
- **Chủ huỷ dòng bán** (2 ngày, Zalo của Chủ): `huy TH2040D 40 [kho] [17/10]` → bot liệt kê dòng khớp → nhắn số dòng để huỷ (xoá ô BAN, tồn tự cộng, trả sổ ký gửi nếu là hàng ký gửi). `huy` không kèm mã vẫn là huỷ lệnh vừa gõ (10 phút).
- **`du phong`** (hoặc menu 8): bảng cú pháp ngắn bán / tra / nhập / trả / huỷ / bc.
- **Chọn bằng số sau lệnh ghi** (anh Kha 17/10): bán xong bot hỏi "1 Tiền mặt · 2 Chuyển khoản · 3 Thẻ" (đổi cột payment_method của dòng vừa bán) và "6 Huỷ lệnh này". Menu 6 của Chủ: 1 = lệnh vừa rồi (nhắn 1 lần nữa), 2–9 = các dòng bán 2 ngày gần nhất (chọn là huỷ). Chỉ mã / size / giá / số điện thoại là phải gõ.

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
  "khach": { "ten": "Chị B", "sdt": "0909…" },               // tuỳ chọn, dùng cho tin MISA
  "lay_hoa_don": { "ten_cty": "…", "mst": "0312345678", "dia_chi": "…", "email": "…" },  // tuỳ chọn: khách lấy hoá đơn
  "thanh_toan": "CK Techcombank",          // tuỳ chọn: tiền mặt / CK vào TK nào / COD / sàn
  "phi_ship": 30000,                       // tuỳ chọn
  "dry_run": true                         // tuỳ chọn: chỉ kiểm tra, không ghi
}
```
- `warehouse`: `15E` / `Y3C` (nhận cả `TBH`, `YEN`, `3C`). `size` bỏ trống với hàng không size. `qty` 1-99, mặc định 1. `price` tuỳ chọn.
- Apps Script trả lời qua 1 lần chuyển hướng (302). Bên gọi phải **đi theo chuyển hướng** (`fetch` mặc định đã theo; `curl` cần `-L`).

**Trả về (JSON):**
- `{"ok":true,"ticket_id":...,"dry_run":false,"rows":N,"results":[{"line":1,"code":...,"size":...,"qty":...,"warehouse":...,"stock_before":...,"row":...,"rows"?:[..],"phan":[{"chu_hang":"15E","qty":1}],"chu_hang":"15E","warning"?:...}], "misa"?:{...}}`
- `phan` / `chu_hang` (cả chạy thử): chủ hàng theo sổ ký gửi (xem mục "Sổ ký gửi"). Dòng lẫn 2 chủ → `chu_hang` = "" và bot ghi 2 dòng BAN (`rows`).
- `lay_hoa_don`: cần `ten_cty` hoặc `mst` (10 số, 10 số-3 số, hoặc 12 số); sai → lỗi, không ghi. Có thì `misa` = `{se_gui:[hộ]}` (chạy thử) / `{da_gui:n}` (số tin đã gửi).
- Có dòng lỗi → `{"ok":false,"error":"Có dòng lỗi, chưa ghi dòng nào","results":[...{"ok":false,"error":"..."}]}`. **Không ghi dòng nào.**
- Gửi lại cùng `ticket_id` → `{"ok":true,"duplicate":true,...}`, không ghi thêm. Mã phiếu được nhớ 30 ngày.
- Ghi dở do lỗi giữa chừng → `{"ok":false,"partial":true,"rows":<đã ghi>}`. **Không gửi lại**, kiểm tra tab `BAN`.
- Sai khoá → `{"ok":false,"error":"unauthorized"}`.
- Cảnh báo (vẫn ghi): bán quá tồn (`tồn X < bán Y → tồn âm`), SKU chưa có trong tab KHO.

**Ghi vào BAN:** mỗi dòng phiếu = 1 dòng BAN (Ngày, product_code, product_color tự lấy, Giá, item_size, item_quantity, KHO, `channel`, `seller`). **Quy ước kênh (anh Kha chốt 16/10):** ô `channel` **trống** = bán tại cửa hàng theo KHO (Y3C = cửa hàng 3C, 15E = cửa hàng 15E). Chỉ ghi `channel` khi bán ngoài cửa hàng: `web`, `shopee`, `tiktok`. Dữ liệu cũ ghi `cua_hang` vẫn được hiểu là cửa hàng. Lệnh `ban` qua Zalo: bán tại quầy để trống `channel`; thêm chữ `shopee` / `tiktok` (`tt`) / `web` / `lazada` / `zalo` / `facebook` (`fb`) trong tin (vd `ban BT01D 40 YEN shopee`) thì ghi kênh đó. Cửa ghi bán của app nhận `cua_hang` nhưng ghi ô trống. `seller` = tên Zalo người nhắn. Nếu tab BAN chưa có cột `channel` / `seller` thì bot bỏ qua 2 cột đó, phần còn lại ghi bình thường.

**Huỷ phiếu bán:** `POST ?sale_key=` `{action:"huy_ban", ticket_id, nguoi, chu?, dry_run?}`.
- Người ghi phiếu (`seller` lúc bán = `nguoi`) huỷ được trong 10 phút; Chủ (`chu: true` và `nguoi` thuộc `OWNER_EMAILS`) huỷ được tới 2 ngày.
- Xoá ô các dòng BAN của phiếu (tồn KHO tự cộng lại theo công thức), trả sổ ký gửi về như trước. Dòng đã xoá không vào tin MISA cuối ngày; phiếu đã gửi tin hoá đơn MISA thì bot gửi thêm tin "❌ HUỶ phiếu …".
- Chặn khi dòng BAN đã bị sửa hoặc sổ ký gửi đã có giao dịch khác sau phiếu (`loi:[…]`).
- Trả `{ok, ticket_id, so_dong, kho:[…], chu, misa_huy?}`; phiếu ghi trước bản 17 không huỷ được bằng cửa này.

**Chạy thử trong Apps Script:** chạy hàm `testSale` (luôn dry-run, không ghi Sheet).

## Ký gửi ở cột KHO (anh Kha "làm" 18/10, thay tab KYGUI)

- `KHO15E.cua_Y3C` = số đôi trong kho 15E là hàng của Y3C; `KHOY3C.cua_15E` ngược lại. Trống = 0. Luật bán / chuyển / trả / huỷ như dưới, chỉ đổi chỗ ghi (chưa có dòng KHO cho mã + size thì bot thêm dòng tồn đầu 0).
- `BAN.ky_gui_tru`: dòng đã trừ ký gửi ("bot <giờ>" lúc bot / app ghi bán; "soat <giờ>" khi bot soát dòng gõ tay). `BAN.chu_hang` có ô chọn 15E / Y3C.
- Gõ tay BAN chọn `chu_hang` = hộ kia (ngày từ 18/10): bot soát mỗi 5 phút (chạy cùng trigger `flushSyncHints`), trừ cột `cua_…`, ghi `ky_gui_tru`; thiếu ký gửi ghi thêm "(thiếu n)". Không nhắn Zalo.
- Tab KYGUI cũ đổi tên `KYGUI_cu`, ẩn, giữ 7 ngày.

## Sổ ký gửi giữa 2 hộ (tab KYGUI, anh Kha "làm" 17/10)

Chuyển hàng giữa 2 hộ (15E = Hải Nancy, Y3C = Yen Leather) không xuất hoá đơn, chỉ ghi ký gửi: hàng của hộ này đang nằm ở kho hộ kia.
- **Tab `KYGUI`** (hàng 1): `product_code` · `item_size` · `chu_hang` (15E / Y3C) · `kho_dang_o` · `so_luong` · `cap_nhat`. Dòng về 0 vẫn giữ. Chưa có tab → tính năng tắt (chủ hàng = kho).
- **Chuyển A → B** (`chuyen_kho` app / lệnh `chuyen kho` Zalo): trừ trước KYGUI(chủ B, ở A) (trả về chủ), phần còn lại cộng KYGUI(chủ A, ở B). App nhận `results[].ky_gui = [{size, chu_hang, qty, loai: tra_ve_chu | thanh_ky_gui}]`.
- **Bán ở kho K** (cửa ghi bán, lệnh `ban` Zalo): bán trước hàng ký gửi của hộ kia đang ở K → `BAN.chu_hang` = hộ kia; còn lại `chu_hang` = K. Lẫn 2 chủ → 2 dòng BAN. Dòng BAN cũ trống `chu_hang` = chủ theo KHO.
- **Trả hàng** (`tra_hang`): về đúng chủ: `chu_hang` gửi kèm dòng, không có thì theo dòng BAN gần nhất cùng mã / size / kho. Chủ khác kho → cộng lại KYGUI.
- **Cảnh báo** (không chặn): ký gửi đang ở kho > tồn kho đó.
- Huỷ 10 phút trả KYGUI về như trước. Đổi KYGUI gửi sync-hint `KYGUI`.

## Tin Zalo MISA (anh Kha "làm" 17/10)

Bot soạn sẵn để nhập MISA ở quầy, theo **chủ hàng** (tính ký gửi). Gửi tới Script Property `MISA_CHAT_IDS` (nhiều chat cách nhau dấu phẩy), mặc định `OWNER_CHAT_ID`. Tên hộ lấy từ `HKD_15E` / `HKD_Y3C`.
- **Đơn khách lấy hoá đơn** (`lay_hoa_don` trong phiếu bán): gửi ngay 1 tin / hộ: hộ, ngày, số CT (`ticket_id`), kênh, người bán, khách, công ty, MST, địa chỉ, email; từng dòng mã MISA (mã + size, như danh mục con HNC xuất), tên, ĐVT, SL × đơn giá = thành tiền; thuế (GTGT 1%, TNCN 0,5% theo danh mục MISA); tổng, thanh toán, ship.
- **Còn lại** (chạy tay, trigger 21:00 gỡ 22/10 — bot @41 tự gỡ trigger cũ ở lần chạy đầu): `dailyMisaSummary` gửi 1 tin tổng / hộ từ các dòng BAN hôm nay (mọi kênh, cả lệnh Zalo / nhập tay), bỏ dòng đã gửi riêng vì lấy hoá đơn; tin dài tự cắt nhiều tin. Chạy thử: `dailyMisaSummary(true)` chỉ ghi Nhật ký.
- Trigger mới: chạy `setupChangeTrigger` 1 lần sau khi triển khai. File nhập đơn MISA (mẫu `HNC_Templates/Nhap_khau_don_hang.xlsx`) do web làm vì web giữ thông tin khách / hoá đơn / thanh toán; bot chỉ soạn tin Zalo.

## In tem theo kho (V34, anh Kha "làm" 18/10)

- `in_tem` (cửa `?stock_key`): `{so_chung_tu, kho}` hoặc `{ngay: "dd/mm/yyyy", kho}` (lấy cả dòng nhập Zalo không số chứng từ) hoặc `{dong:[số hàng NHAP], kho}`. Bỏ phiếu trả hàng TRA-. Ghi `My Drive/IN Mini Code/IN_15E.csv` / `IN_Y3C.csv` và chép thành `IN.csv` (mẫu P-touch cũ). Cột / luật như menu Mac task 10 (`LABEL_COLUMNS`: QR code · Tên · Màu · Size · Size Color · F6 (= số tem = số lượng) · Code128 (= mã hàng) · Gía). Trả `{ok, kho, so_dong, so_tem, rows:[{dong, ma_hang, so_tem, da_in}], file, link}`; `dry_run` không ghi file.
- `da_in_tem` (cùng bộ lọc): ghi `web_label = "Done - <giờ>"`. Chỉ lúc này mới tính đã in (tạo file chưa tính). Trả `{ok, so_dong}`. Từ V34 mục 6 đây là nút dự phòng (Mac tự đánh dấu khi in xong).
- **In tự động trên Brother QL-700 (V34 mục 6):** `in_tem` / `in_bu` ghi lệnh (JSON: kho, luc, nguoi, so_chung_tu, ngay, dong[], in_bu, so_tem, cot, tem[][]) vào ô `lenh` của tab ẩn `in_tem_lenh` (1 dòng / kho: kho | lenh | ket_qua | cap_nhat) và trả `tu_in: true, luc` (`tu_in: false` = chỉ ghi CSV). Mac mini (launchd `vn.giayhainancy.hnc.intem`, `tools/label_print.py` chạy liên tục, đọc tab mỗi 4 giây 7:00–22:00) in cả đợt qua USB, cắt 1 lần cuối, in xong mới ghi `web_label = Done` cho đúng dòng, ghi ô `ket_qua`, xoá ô `lenh`. Lỗi trước khi tới máy in → giữ lệnh thử lại; đã gửi máy in thì không gửi lại; lệnh quá 30 phút thì bỏ. Bot vẫn ghi `IN_<kho>.csv` lên Drive cho P-touch dự phòng (từ 18/10 không qua Drive nữa vì chờ đồng bộ ~2 phút).
- `in_tem` thêm `chon:[{dong, so_tem}]` (app xem trước): chỉ in dòng so_tem > 0, đúng số tem đó; Mac chỉ đánh dấu các dòng này. Mỗi row trả `ma_hang, ten, mau, size, gia, so_tem`.
- `in_bu` `{kho, items:[{ma_hang (mã + size), so_tem}], tu_in?, dry_run?}`: in thêm tem theo mã, lấy thông tin SANPHAM, không đụng `web_label`. Mã không có trong SANPHAM → `ok:false`, `rows[].loi`, không in dòng nào. Nhật ký: `IN Mini Code/IN_BU_nhat_ky.csv`. Kết quả đọc bằng `kq_in_tem`. Menu Mac task 10 → [2] In bù theo mã hàng (cùng luật). Mẫu tem: `docs/mau_tem_A.png`.
- **Bán trùng trong "bc" (19/10, cùng luật web `allsales.ts`):** dòng BAN gõ tay (seller không có "@") trùng ngày + mã + size + kho với dòng bot ghi từ app / đơn web (seller là email) → thêm dòng "⚠️ Có thể bán trùng: N dòng (dòng Sheet …)". Chỉ báo, vẫn cộng tổng, không xoá, không gửi Zalo tự động. Bỏ qua khoá "Không phải trùng" (`ngày|mã|size|kho|dòng`) đọc từ web: POST `<gốc web>/api/bot-callback` body `{loai:"ds_ban_khong_trung", luc}` ký HMAC như callback → web trả `{ok:true, keys:[…]}`; nhớ 10 phút. Không đọc được thì vẫn báo, kèm ghi chú.
- `kq_in_tem` `{kho}` → `{ok, kho, dang_cho_in, ket_qua}`; `ket_qua` = ô `ket_qua` của tab `in_tem_lenh`: `{luc, kho, yeu_cau_luc, so_chung_tu, ngay, so_tem, so_tem_da_in, ok, loi, dong_da_danh_dau[]}`. App so `yeu_cau_luc` với `luc` của lần bấm In tem để biết kết quả đúng lần đó.
- Menu Mac [1] › [4]: chọn kho + số chứng từ / ngày (Enter = mọi dòng chưa in), ghi IN.csv (+ IN_<kho>.csv), hỏi "đã in xong" rồi mới đánh dấu. Menu [5] đồng bộ mã hàng vào kho chỉ còn là dự phòng.

## Xuất file MISA qua bot (web /admin/san, anh Kha "làm" 17/10)

`POST ?stock_key=` `{action:"xuat_misa", loai, nguoi, dry_run?}`, giống menu HNC mục 4 (web không giữ giá nhập / thuế nên chạy qua bot).
- `loai`: `danh_muc` (TASK 4: mã cha mới → `MISA_PRODUCTS_…` theo `tpl_misa_upload`, mã cha đã lên MISA / thêm màu → `MISA_PRODUCTS_UPDATE_…` theo `tpl_misa_update`) · `nhap_kho_15e` / `nhap_kho_3c` (TASK 8: `MISA_STOCK_15E_…` / `MISA_STOCK_3C_…` theo `tpl_misa_stock_15e` / `_y3c`).
- Lấy dòng chưa có cờ (`misa_upload` ở SANPHAM; `misa_stock` ở NHAP), bỏ mã "cần bổ sung" (`bo_qua`), dòng `TRA-…` ghi "Bỏ qua - trả hàng". Kiểm thiếu dữ liệu như menu (dòng thiếu → ghi lý do vào cờ, trả `canh_bao`). Nhập kho chỉ lấy dòng của kho đã chọn; dòng kho kia để nguyên.
- Đơn giá nhập kho = `invoice_price`, trống thì `purchase_price` (anh Kha 17/10; menu Mac cũng vậy). Hoá đơn NCC (`hoadon`) cũng tính như vậy.
- File: điền vào mẫu gốc trong `HNC/He_thong/HNC_Templates` bằng cách sửa XML của xlsx (giữ nguyên định dạng, danh sách chọn của MISA), lưu `HNC/He_thong/HNC_Exported_Files` (theo ID thư mục `He_thong`, đổi bằng `SYSTEM_FOLDER_ID`).
- Trả `{ok, files:[{ten, url, so_dong}], so_hop_le, so_loi, canh_bao:[…], bo_qua:[mã]}`. `dry_run`: chỉ đếm, không tạo file, không ghi cờ. Ghi thật thì gửi sync-hint SANPHAM / NHAP.
- Thử trong trình soạn thảo: `thuXuatMisa` tạo 3 file **không ghi cờ**, link ở Nhật ký.

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
- **Giá / NCC chỉ HNC giữ:** mọi trả về cho web KHÔNG có đơn giá. Riêng `xem_nhap` có `kem_gia: true` **và** `nguoi` là Chủ (Script Property `OWNER_EMAILS`, mặc định ltckha@gmail.com, giayhainancy@gmail.com) thì trả `dong[].don_gia` (đồng); người khác nhận `canh_bao` và không có giá. Web chỉ gửi `kem_gia` cho Chủ, không lưu / log / cache.

| action | Gửi | Trả |
|---|---|---|
| `doc_phieu` | `anh_base64` (≤ 8 MB, nên nén ~2 MB), `mime`, `nguon` ("app" / "web"), `nguoi` (email) | `{ok, id, ncc_ten, so_phieu, ngay, so_dong, so_doi, trang_thai:"cho_chia", model}`. Lỗi Gemini: `{ok:false, error}` (hết lượt miễn phí thì báo rõ) |
| `ds_nhap` | `limit?` (50), `tat_ca?` (hiện cả phiếu đã bỏ) | `{ok, phieu:[{id, ncc_ten, so_phieu, ngay, so_dong, so_doi, trang_thai}]}`, mới nhất trước. `trang_thai`: `cho_chia` / `da_ghi` / `huy` |
| `xem_nhap` | `id`, `kem_anh?` | `{…đầu phiếu, dong:[{dong, ma_ncc, mo_ta, sl_phieu, goi_y_ma_hnc?}], da_ghi?, anh_mime?, anh_base64?}` |
| `xac_nhan` | `id`, `ticket_id`, `nguoi`, `dry_run?`, `dong:[{dong, ma_hnc, kho, sizes:{"39":2,"40":1}, sl?, ly_do?, ghi_chu?}]`, `ma_moi?:[{ma_hnc, ma_goc?, mau, gia_ban, day_size?, ten_tam?, nganh?}]` | Giống cửa kho: `{ok, results:[…, dong_phieu], canh_bao:[…], tao_moi:{sanpham:[mã], kho:["15E 32837D 38",…]}, so_chung_tu:{"15E":"NK000027"}, undo_until}` |
| `huy_nhap` | `ticket_id` (của `xac_nhan`), `nguoi`, `id?`, `chu?` | `{ok, id, so_dong}`. Người ghi: ≤ 10 phút. **Chủ** (`chu: true` + `id` phiếu; web kiểm quyền): quá 10 phút vẫn huỷ được. Phiếu về `cho_chia` |
| `bo_sung_sp` | `product_code`, `nguoi`, `dry_run?`, `cot:{"Tên Ngành Hàng": …, "Đặc điểm": …}`, `product_price?` | `{ok, da_ghi:[cột], canh_bao:[…], can_bo_sung}`. Form "Bổ sung thông tin mã mới" (xem dưới) |
| `bo_nhap` | `id`, `nguoi` | `{ok, trang_thai:"huy"}`. Chỉ phiếu `cho_chia` (quyền "Chủ" do app kiểm) |

- **`xac_nhan`:**
  - Mỗi dòng phiếu: tổng `sizes` (hàng không size dùng `sl` hoặc khoá `""`) phải bằng `sl_phieu`. Lệch thì bắt buộc `ly_do`: `thieu` / `du` / `loi_tra_lai` / `khac`, ghi vào `canh_bao` và lưu kèm phiếu. Không nhận dòng nào thì gửi `sizes` rỗng + `ly_do`.
  - **Tách màu:** 1 dòng phiếu gửi nhiều phần tử `dong` (cùng số `dong`), mỗi phần tử 1 mã × 1 kho (15E / Y3C) × `sizes`. Tổng mọi mã / kho / size so với `sl_phieu`.
  - Mã phải có trong SANPHAM / KHO, hoặc khai trong `ma_moi`. Mã trong `ma_moi` mà đã có thì nhập như mã cũ (có `canh_bao`).
  - **Mã mới (`ma_moi`):** `ma_hnc` = mã gốc + chữ màu (`ma_goc` mặc định bỏ ký tự cuối), `mau` bắt buộc, `gia_ban` bắt buộc (đồng, ≥ 1.000; app nhập), `day_size` = dãy size của mẫu (cộng thêm size đang nhập), `nganh` tuỳ chọn (phải có trong SUB), `ten_tam` chỉ lưu trong phiếu.
    - SANPHAM: thêm 1 dòng sau dòng cuối, chép công thức của dòng cuối (mã cha, tên `product_name`, CON_NAME / CON_DES, mô tả…), điền mã, màu, `product_price` = `gia_ban`, `purchase_price` = đơn giá dòng phiếu (`invoice_price` để anh điền, anh Kha 16/10), `Size` = dãy size, `supplier` = NCC, `product_unit` "Đôi", `product_origin` "Việt Nam".
    - Cột thông tin mẫu (Tên Ngành Hàng, Đặc điểm, Chất liệu, Nhấn mạnh, Chất liệu quai / đế, Lót trong, Mặt lót đế, Dáng giày mũi, Phần dưới giày, Kết hợp trang phục, Sử dụng, Bonus) + Thương hiệu, đơn vị, xuất xứ: chép từ dòng cùng mã cha nếu có, không có thì để trống.
    - Ngành trống → `Giới tính`, `product_category_id` để trống (không ra "female" / #N/A); bổ sung ngành qua `bo_sung_sp` thì công thức tự chép lại. Cột đăng sàn / MISA để trống.
    - KHO: thêm dòng tồn đầu 0 cho **cả 2 kho × day_size** (công thức FSKU + tồn hiện tại dựng theo tên cột NHAP / XUAT / BAN, giống menu HNC "Đồng bộ SKU").
    - Mã cũ nhập size / kho chưa có dòng KHO: thêm dòng KHO đó luôn (lấy vị trí kệ của dòng cùng mã).
    - Ghi xong gửi sync-hint `SANPHAM`, `KHO15E`, `KHOY3C`, `NHAP` (gom 60 giây như mọi lần ghi).
    - **Mã "cần bổ sung"** = dòng SANPHAM trống `Tên Ngành Hàng` hoặc giá bán (`product_price` ≤ 0). Tự bị **bỏ qua** khi menu HNC xuất web cũ / Shopee / TikTok / MISA (danh mục + phiếu nhập; in 1 dòng "Bỏ qua n mã chưa bổ sung", trạng thái để trống để xuất sau) và khi cổng `mark_exported` đánh dấu (trả `chua_bo_sung`). In tem, đồng bộ kho vẫn chạy. Web ẩn mã theo cùng dấu hiệu.
  - Tồn hiện tại và các màu của mã gốc: web tự lấy từ D1, không có API tra.
  - Kiểm hết trước: có dòng lỗi (`loi_dong` hoặc `results[].error`) thì không ghi dòng nào.
- **Dòng NHAP:**
  - Như nhập thường (anh Kha 16/10): không đánh dấu `Zalo_Update`, nên menu HNC in tem, đồng bộ kho, xuất phiếu nhập MISA.
  - `Số chứng từ (*)` = `NK` + 6 số, **chạy theo từng kho** (như Sheet đang dùng): cùng kho + cùng NCC + cùng ngày đã có số thì dùng chung, khác thì số lớn nhất của kho đó + 1. NCC của dòng cũ: theo phiếu nếu dòng thuộc phiếu NCC, còn lại theo `supplier` SANPHAM. Mã phiếu `PN…` chỉ giữ nội bộ (vé, huỷ, hoá đơn; chỉ mục `pnx_` lưu `nk` theo kho).
  - `Ngày chứng từ` = ngày xác nhận.
  - Bot học bảng ghép (mã NCC / mô tả → mã HNC; dòng tách nhiều màu thì nhớ mã gốc) để gợi ý lần sau.
- **Huỷ (`huy_nhap`):** xoá các dòng NHAP vừa ghi; dòng SANPHAM / KHO tạo mới cũng xoá (cả ô công thức). Nếu mã mới (kho × size) đã có giao dịch khác (NHAP khác, bán, xuất) thì **không huỷ gì**, báo để sửa tay. Người ghi ≤ 10 phút; Chủ (`chu: true`, kèm `id`) lúc nào cũng được (thao tác lưu trong dữ liệu phiếu).
- **Hoá đơn NCC:** dòng NHAP có `Số chứng từ` NK… của một phiếu NCC thì phiếu × kho lấy NCC theo phiếu, và câu nhắn ghi "theo phiếu xuất <số phiếu NCC>".
- **`bo_sung_sp` (form "Bổ sung thông tin mã mới" trên web):** chỉ ghi các cột thông tin mẫu ở trên (theo tên cột hàng 2, khoảng trắng / dấu ":" cuối tên không quan trọng) + `product_price`. Cột khác → lỗi, không ghi gì. `Tên Ngành Hàng` phải có trong SUB, không được trống. Không đụng `product_name` / công thức; có ngành thì chép lại công thức `Giới tính`, `product_category_id` từ dòng gần nhất phía trên. `can_bo_sung` = mã còn trống ngành / giá bán không. Ghi xong gửi sync-hint `SANPHAM`.
- **Gemini:** thử `gemini-2.5-flash` trước (khoá miễn phí nhiều lượt nhất), lỗi thì 3.6 → 3.8 Flash; mọi model báo 429 thì trả lỗi "hết lượt miễn phí". Model đã dùng lưu trong phiếu (`model`).
- **Zalo chỉ báo tin:** đọc phiếu xong bot nhắn `OWNER_CHAT_ID` "📄 Có phiếu chờ chia: <NCC> <số> · n dòng · m đôi → <web>/admin/app#phieu-<mã>". Link lấy từ `APP_URL`, mặc định gốc của `SYNC_HINT_URL` + `/admin/app`. Bot **không** nhận ảnh phiếu qua Zalo (ảnh gửi vào bot bị bỏ qua, ghi Nhật ký).

## Cửa "báo đơn web" (API)

**Câu hỏi chọn số (luật 14, 17/10):** body thêm `options` 1–8 `{so, nhan ≤40, hanh_dong: url | callback | ghi_nhan, url?, callback?: {loai, id, data?}, xac_nhan_2_lan?}` và `han_phut` 1–720 (mặc định 720). Bot nối "Nhắn số: …" vào tin, nhớ câu hỏi cho Chủ. Chọn `url` → gửi link (https, tên miền web hoặc `URL_ALLOW`); `ghi_nhan` → chỉ trả lời; `callback` → POST `WEB_CALLBACK_URL` (mặc định `<gốc web>/api/bot-callback`) ký HMAC, không gửi khoá: header `x-bot-time` (= `luc`) và `x-bot-sig` = hex HMAC-SHA256(khoá, `x-bot-time` + "." + body thô); khoá = `BOT_CALLBACK_KEY` nếu có, không thì `WEB_NOTIFY_KEY`; body `{order_id, so, loai, id, data, nguoi, luc}`, web trả `{ok, text?}`. `xac_nhan_2_lan` phải nhắn 2 lần trong 10 phút. options sai → `{ok:false, error:"options: …"}`, không gửi tin.

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

## Giá nhập theo lô + hoá đơn NCC (anh Kha "làm" 17/10)

- **NHAP thêm cột** `don_gia_phieu` (bot ghi lúc `xac_nhan` phiếu NCC, đơn giá dòng phiếu đã đọc), `don_gia_hd`, `so_hd`, `ngay_hd`.
- **Cửa `?stock_key` `hoa_don`** (chỉ Chủ, `nguoi` thuộc `OWNER_EMAILS`): `che_do: "ds"` danh sách phiếu (theo ngày × NCC × kho) · `"xem"` + `phieu` → dòng kèm giá phiếu / HĐ · `"ghi"` + `phieu` (1 mã hoặc mảng — 1 HĐ nhiều phiếu), `so_hd`, `ngay_hd?` (dd/mm/yyyy, trống = hôm nay), `dung_nhu_phieu: true` hoặc `dong: [{dong, don_gia_hd}]`. Ghi xong: phiếu = đã có HĐ, `SANPHAM.invoice_price` = giá HĐ gần nhất, lệch giá phiếu / đã xuất MISA giá tạm → nhắn Chủ. Trả `{ok, so_dong, so_hd, ngay_hd, lech_gia}`; dòng chưa có giá phiếu mà không gửi giá → `loi`.
- `xem` trả thêm `tin_xin_hd` (tin xin hoá đơn soạn sẵn, không giá; như `hoadon <mã>`) và `thieu_mst` (true → `tin_xin_hd` rỗng, `loi_tin` ghi lý do). `xac_nhan` (nhập từ phiếu) nhận `ncc_xuat_hd` (mặc định true); `false` → phiếu hoá đơn = không lấy ngay (không đòi / nhắc).
- **Menu 4 bot:** 1 Có HĐ, giá đúng như phiếu → gõ số HĐ (kèm ngày nếu khác hôm nay) · 2 Không lấy · 3 Chưa · 4 Giá khác → mở app.
- **File nhập kho MISA (bot `xuat_misa` + menu Mac [4]):** đơn giá `don_gia_hd` → `don_gia_phieu` → giá theo mã (`invoice_price`, rồi `purchase_price`, ghi "giá cũ theo mã"). Dòng chưa có `so_hd` chờ 3 ngày (`cho_hd` trong kết quả), quá hạn xuất "giá tạm". Số / ngày HĐ ghi vào cột Diễn giải (mẫu MISA không có cột Số hoá đơn); cờ `misa_stock` thêm "· giá tạm" / "· giá cũ theo mã".
- **`hoadon`:** chỉ Chủ; đổi trạng thái phải đúng mã phiếu (nhiều mã trước chữ trạng thái = 1 HĐ nhiều phiếu); `hoadon <mã> tudong` bỏ trạng thái đặt tay; dòng nhập Zalo_Update không số NK không bị đòi HĐ; thiếu MST hộ (`HKD_<kho>`) thì không soạn tin xin HĐ. Kho nhận thêm `15ETBH` / `3CTBH`.

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
- **Gộp:** tên tab vào hàng chờ, mỗi phút gửi **tối đa 1 lần**: `POST SYNC_HINT_URL`, header `x-sync-key: SYNC_HINT_KEY` (không để khoá trong URL), body `{"tabs":[...]}`. Đổi BAN / NHAP / XUAT thì gửi kèm `KHO15E`, `KHOY3C`. Trigger mỗi phút gửi phần còn lại trong hàng chờ.
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
