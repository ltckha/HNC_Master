# Kiến trúc HNC_Master (HNC Control Center)
Cập nhật 16/10/2026 (Thực thi – HNC_Master). Đổi cấu trúc thì sửa file này cùng commit. Chi tiết bot: `zalo_bot/README.md`. Trạng thái + việc sau: mục cuối file này (bản cũ ở `docs/archive/`).

## Sơ đồ
```mermaid
flowchart LR
  subgraph IN[Đầu vào]
    ANH[Anh Kha / nhân viên]
    ZALO[Zalo bot<br/>tin nhắn lệnh]
    WEB[Web giayhainancy.vn<br/>/admin + app]
    PHIEU[Ảnh phiếu NCC]
    MEDIA[Ảnh SP: Photoroom NAS,<br/>Downloads]
  end

  subgraph AS[Apps Script – bot HNC<br/>gắn Sheet HNC_Control_Center]
    BOT[doPost: webhook Zalo<br/>+ cửa sale / stock / export / notify]
    PN[Nhập từ phiếu<br/>Gemini đọc → nháp → xác nhận]
    TRG[Trigger: onEdit / onChange,<br/>flushSyncHints mỗi phút,<br/>nhắc hoá đơn T2 8:00]
  end

  subgraph MAC[Mac mini – main.py]
    MENU[Menu: tem & kho, Shopee,<br/>TikTok, MISA, media, AI từ ảnh]
    SPEC[tools/spec_fill.py]
  end

  SH[(Google Sheet<br/>HNC_Control_Center)]
  DRV[(Drive My Drive/HNC/…)]

  ZALO --> BOT
  WEB -->|?sale_key ?stock_key ?export_key ?notify_key| BOT
  PHIEU --> WEB
  BOT --> SH
  PN --> SH
  PN --> DRV
  BOT -->|tin nhắn| ZALO
  TRG -->|sync-hint, header x-sync-key| WEB
  ANH --> MENU
  MEDIA --> MENU
  MENU <--> SH
  MENU -->|file xuất, IN.csv, channel_links.csv| DRV
  MENU -->|sync-hint| WEB
  SPEC <--> SH
  DRV -->|anh tải lên| SAN[Shopee / TikTok / MISA eShop]
  WEB -.chỉ đọc Sheet.-> SH
```

## Chạy ở đâu
| Phần | Nơi chạy | Cách chạy |
|---|---|---|
| Bot HNC (`zalo_bot/Code.gs`) | Google Apps Script, gắn Sheet | Web App `/exec` (1 bản triển khai, link giữ nguyên). Cập nhật: `commands/Deploy_Bot.command` (test → `clasp push` → cập nhật đúng bản triển khai) |
| Trigger bot | Apps Script | `onSheetEditHint` (onEdit), `onSheetChangeHint` (onChange), `flushSyncHints` mỗi 1 phút, `weeklyInvoiceReminder` thứ Hai 8:00. Tạo bằng hàm `setupChangeTrigger`. Tin MISA 21:00 bỏ 22/10 (bot @41; `dailyMisaSummary` chỉ chạy tay) |
| Menu HNC (`main.py`) | Mac mini, `venv` | Bấm đúp `run.command`. Không có lịch tự chạy |
| `tools/spec_fill.py` | Mac mini | `plan` / `ai` / `apply` (điền thông số còn trống trong SANPHAM) |
| Media | NAS `/Volumes/Media/HNC_Master/` | Menu 5 gom ảnh từ Photoroom (NAS) và Downloads |

Menu main.py: 1 Tem & kho (in tem `IN.csv`, đồng bộ SKU NHAP → 2 kho), 2 Shopee (đăng mới, cập nhật giá / tồn), 3 TikTok (đăng mới, cập nhật), 4 MISA (danh mục cha – con, nhập kho mua hàng), 5 Media, 6 AI nhập sản phẩm từ ảnh (Gemini). Các tác vụ web cũ (WEB_PRODUCTS / WEB_STOCK, cào ảnh) đang ẩn.

## Đọc / ghi gì
**Sheet `HNC_Control_Center`** (đọc / ghi theo tên cột; SANPHAM tên cột ở **hàng 2**, các tab khác hàng 1):
- `SANPHAM`: danh mục SP. Bot thêm dòng mã mới từ phiếu, `bo_sung_sp`, cờ `shopee_upload` / `tiktok_upload` (mark_exported). main.py ghi cờ `*_upload`, `get_images`, ảnh.
- `KHO15E`, `KHOY3C`: tồn = `opening_quantity` + NHAP − XUAT − BAN (công thức SUMIF theo FSKU). Bot / main.py thêm dòng SKU mới, bot sửa `product_location`.
- `NHAP` (hàng 2 là tiêu đề kỹ thuật), `XUAT`, `BAN` (`channel`, `seller`, `chu_hang`): bot ghi; main.py đánh dấu `web_stock`, `web_label`, `misa_stock`, `kho_sync`.
- Ký gửi giữa 2 hộ (18/10): cột `KHO15E.cua_Y3C`, `KHOY3C.cua_15E` (thay tab KYGUI, nay là `KYGUI_cu`); `BAN.ky_gui_tru` đánh dấu dòng đã trừ; bot soát dòng gõ tay mỗi 5 phút.
- `SUB`: ngành hàng, NCC (Mã / Tên đối tượng, thuế), % giá sàn, kích thước. Chỉ đọc. Cột `loai_dong` (19/10): `nganh` = ngành của tiệm (44 dòng), `shopee` = ngành Shopee lẻ "1000xx - …" chỉ để tra mã (96 dòng); danh sách ngành (bot `productCategories_`, main.py `load_sub_dictionary`, form web) bỏ dòng `shopee`.
- `META` (key / value / updated_at): `shopee_last_update`, `tiktok_last_update`.

**Drive** (`hnc_paths.py` khai 1 chỗ):
- `My Drive/HNC/He_thong/` (cũ: `Spark/HNC_Master`): `HNC_Templates` (tpl_*), `HNC_Exported_Files` (file xuất, `channel_links.csv`, SPEC_FILL_AI_*), `Outputs`. Không thấy thì main.py dừng, không dùng thư mục local.
- `My Drive/IN Mini Code/`: `IN.csv` / `IN_<kho>.csv` (P-touch dự phòng), `IN_BU_nhat_ky.csv`. In tem khi bấm QL-700 (chỉ in khi có người bấm In tem, không tự in): bot ghi lệnh vào tab ẩn `in_tem_lenh` → Mac mini (launchd `vn.giayhainancy.hnc.label_print` → `tools/label_print.py`, chạy liên tục, đọc mỗi 4 giây lúc 7:00–22:00, ngoài giờ 30 giây; cài bằng `tools/launchd/install_label_print.sh`) in qua USB, dựng tem `tools/label_render.py` (dùng chung với main.py task 10), tự ghi `web_label` + ô `ket_qua`. Cần: QL-700 đèn nguồn sáng, cắm USB, đèn Editor Lite tắt. In liền cả đợt, cắt 1 lần cuối (`CAT`).
- `My Drive/HNC/Thue/2026/`: `Hoá đơn 2026` (bot đọc theo ID `INVOICE_FOLDER_ID`), `Phiếu mua hàng` (bot ghi theo ID `PN_FOLDER_ID`: `Chưa chia/<NCC>/`, rồi `<hộ>/<NCC>/`).

## Lịch chạy nền trên Mac mini (launchd, kiểm 31/10)
Plist + bộ cài ở `tools/launchd/`. Xem đang cài: `launchctl list | grep giayhainancy.hnc`.
| Nhãn | Cài? | Chạy khi | Việc | Log (`~/Library/Logs/`) |
|---|---|---|---|---|
| `vn.giayhainancy.hnc.label_print` | ✅ đang chạy | liên tục (4 giây lúc 7:00–22:00, ngoài giờ 30 giây) | `tools/label_print.py`: in tem khi bấm — chờ lệnh ở tab `in_tem_lenh`, chỉ in khi có người bấm In tem | `hnc_in_tem.log` |
| `vn.giayhainancy.hnc.collect_videos` | ✅ (30/10) | khi `~/Downloads` đổi + dự phòng 13:00 hằng ngày | `tools/collect_videos.py`: video tên `<MÃ>.mp4` / `<MÃ>_N.mp4` → `/Volumes/Media/HNC_Master/<MÃ>/` đặt `<MÃ>_1`, `_2`… không ghi đè; ghi `content_*` các mã vừa gom (cùng hàm menu tư liệu) | `hnc_gom_video.log` |
| `vn.giayhainancy.hnc.price_suggest` | ❌ gỡ 28/10 (anh chọn "Tắt", nhân viên tự gõ giá) | (13:30 nếu cài lại bằng `install_price_suggest.sh`) | `tools/price_suggest.py`: gợi ý giá tem cho mã chờ duyệt → web; chạy tay được | `hnc_goi_y_gia.log` (chỉ 1 lượt chạy thử 28/10) |

Đổi lịch / cài / gỡ job là việc cần anh xác nhận; báo Điều phối bằng dòng `ĐỔI:`.

## Cửa của bot (doPost)
| Tham số URL | Ai gọi | Việc |
|---|---|---|
| `?key=WEBHOOK_KEY` | Zalo | Menu số (`menu`, tin 1 chữ số theo câu hỏi đang mở) + lệnh chat: kiểm hàng, bán, nhập, xuất, chuyển kho / vị trí, huỷ, `bc`, `hoadon` |
| `?sale_key=` | Web / app | Ghi BAN theo phiếu (chủ hàng theo ký gửi, tin MISA), chống trùng 30 ngày; `huy_ban` huỷ phiếu (10 phút / Chủ 2 ngày) |
| `?stock_key=` | Web / app | `nhap`, `tra_hang`, `xuat`, `chuyen_kho`, `chuyen_vi_tri`, `huy`; nhập từ phiếu `doc_phieu`, `ds_nhap`, `xem_nhap`, `xac_nhan`, `huy_nhap`, `bo_nhap`; `bo_sung_sp`; `xuat_misa` (file MISA danh mục / nhập kho vào HNC_Exported_Files) |
| `?export_key=` | Web | `mark_exported`: cờ `*_upload` SANPHAM hoặc mốc META |
| `?notify_key=` | Web | Chỉ nhắn Zalo anh (đơn web), không ghi Sheet |

Hoá đơn NCC: bot gom NHAP theo ngày × NCC × kho, so với thư mục `Hoá đơn 2026/<hộ>/<NCC>/`; lệnh `hoadon` và nhắc thứ Hai 8:00.

## Khoá & bí mật (không ghi giá trị)
- `.env` (Mac, git bỏ qua): `GEMINI_API_KEY` (khoá riêng HNC), `SYNC_HINT_URL`, `SYNC_HINT_KEY`, `WEB_IMG_BASE` (tuỳ chọn).
- `credentials.json` (Mac, git bỏ qua): service account Google Sheets cho main.py / spec_fill.
- Script Properties bot (tuỳ chọn thêm `MISA_CHAT_IDS`): `BOT_TOKEN`, `WEBHOOK_KEY`, `WEBAPP_URL`, `ALLOWED_CHAT_IDS`, `OWNER_CHAT_ID`, `DRY_RUN`, `SALE_KEY`, `STOCK_KEY`, `EXPORT_KEY`, `WEB_NOTIFY_KEY`, `SYNC_HINT_URL`, `SYNC_HINT_KEY`, `GEMINI_API_KEY`, `HKD_15E`, `HKD_Y3C`; tuỳ chọn `INVOICE_FOLDER_ID`, `PN_FOLDER_ID`, `APP_URL`, `OWNER_EMAILS`. Kiểm bằng hàm `checkConfig`.
- Đặt khoá Gemini: chỉ dùng `~/Developer/Ecosystem-Hub/commands/dat_khoa_gemini.command` (chọn 3 = HNC).
- Sổ quỹ dự phòng (03/11, GĐ1 thay MISA, luật 15): menu Mac [4] MISA › [3] → `tools/cash_book.py`. Quỹ + phiếu tay + số dư đầu kỳ đọc web act `so_quy_ds` (`/api/tach-nen/mac`, khoá `~/.hnc_mac_key.json`; bản chính từ 03/11), mỗi lần đọc lưu bản sao `HNC_Exported_Files/cash_book_copy/` (giữ 30, web hỏng thì dùng bản gần nhất). Tiền bán tự tính từ tab BAN theo luật web `cash_book.ts`; báo nếu đầu kỳ lệch web. Ra 1 file `So_quy_<quỹ>_<tháng>.xlsx` mỗi quỹ như nút "Tải Excel". Test `tests/test_cash_book.py`.
- Công nợ NCC dự phòng (03/11): menu Mac [4] MISA › [4] → `tools/supplier_debt.py`. Dữ liệu gốc đọc act `cong_no_ds` (cùng khoá, bản sao trong `cash_book_copy/`), "Đã trả" = phiếu PC có ncc của `so_quy_ds`. Tính theo luật web `congNo`, ra `Cong_no_NCC_<ngày>.xlsx`. Test `tests/test_supplier_debt.py`.
- Đơn bán MISA dự phòng (03/11): menu Mac [4] MISA › [5] → `tools/misa_orders.py`. Đơn đọc act `misa_don_ds {ho, tu, den}` (cùng hàm màn web Đơn bán MISA: từ mốc MISA, chưa đánh dấu, đã trừ số đôi Không xuất MISA), ghi vào tệp mẫu `HNC_Templates/Nhap_khau_don_hang <hộ>.xlsx` sheet "Danh sách đơn hàng" từ hàng 4, ra `MISA_DON_HANG_<hộ>_<từ>_<đến>_<lúc>.xlsx`. Đánh dấu "đã nhập lên MISA" vẫn bấm trên web. Test `tests/test_misa_orders.py`.
- Khoá sổ tháng (04/11, như web `book_lock.ts` d10686ac): hết ngày 5 tháng sau thì sổ tháng trước khoá. `tools/book_lock.py` + chốt `_lock_ok` trong `main.py` (mọi lệnh thêm dòng tab BAN): dòng có Ngày thuộc tháng khoá thì không ghi, báo "mở lại 24 giờ trên web". Tháng mở lại đọc `so_mo` trong `so_quy_ds` (khi web gửi). Mac không ghi phiếu quỹ. Test `tests/test_book_lock.py`.
- Nhãn Không xuất MISA theo mã (03/11): [4][1] hàng hoá mới (nhãn hộ 15E) và [4][2] nhập kho (nhãn theo hộ của kho) đọc act `khong_misa_ds`, bỏ mã-size có nhãn, ghi cờ "Bỏ qua - không xuất MISA". Bot `xuat_misa` lọc theo danh sách `khong_misa` web gửi kèm (không gửi → không lọc, có cảnh báo).
- Thứ tự mô hình Gemini chung (02/11): `shared/gemini_models.json` (3.8 → 3.6 → 2.5, bỏ 3.7 ngày 03/11; 2.5 ngừng 23/12/2026), đọc qua `tools/gemini_models.py` (main.py AI nhập SP, spec_fill); bot giữ bản chép `RECEIPT_MODELS`, test bot kiểm khớp. 429 / 503 / 504 chờ rồi thử lại 1 lần; 404 và lỗi khác sang mô hình kế. Mỗi lỗi ghi 1 dòng: Mac `~/Library/Logs/hnc_gemini.log`, bot nhật ký Executions (`Gemini lỗi …`).

## Nối với project khác
- **Website-giayhainancy** gọi bot (5 cửa trên), đọc Sheet bằng service account chỉ xem, đọc `channel_links.csv` trên Drive, lấy ảnh cho file sàn: main.py dùng `<WEB_IMG_BASE>/img/<mã>/<n>.jpg`.
- **Bot / main.py gọi web**: `POST SYNC_HINT_URL` (header `x-sync-key`) báo tab vừa đổi, gom 60 giây.
- **Zalo Bot API** (`bot-api.zapps.me`), **Gemini** (đọc phiếu, AI từ ảnh, spec_fill).
- Tri thức brand: nguồn duy nhất `Auto-Video-Factory/knowledge/brands/` (tab `brands`); repo này không giữ danh sách brand.

## Chỗ hay nhầm
- `~/.zshrc` có `GEMINI_API_KEY` dùng chung các repo; main.py nạp `.env` với `override=True` nên khoá HNC thắng. Bot dùng Script Property riêng, xem 8 ký tự sha256 trong `checkConfig`.
- SANPHAM tên cột ở hàng 2; NHAP hàng 2 là tiêu đề kỹ thuật, dữ liệu từ hàng 3.
- Mã "cần bổ sung" = SANPHAM trống `Tên Ngành Hàng` hoặc `product_price`; xuất sàn / MISA và `mark_exported` bỏ qua. `product_name` là công thức, đừng ghi đè.
- NHAP từ phiếu NCC: `Số chứng từ` = `NK` + 6 số chạy theo kho; mã `PN…` chỉ là nội bộ của bot.
- Cửa web → bot phải để khoá trong URL (Apps Script không đọc được header); chiều bot → web dùng header.
- Chủ hàng ≠ kho xuất: hàng ký gửi (KYGUI) bán ở kho hộ kia thì tiền / hoá đơn / tin MISA thuộc `BAN.chu_hang`, không theo `KHO`.

## Tình trạng & việc sau (gộp PROJECT_STATUS + IDEAS_AND_ROADMAP, 21/10)
- **Từ 21/10 web là sổ gốc** (4 sổ bán / kho / tồn / hàng hoá = web); bot + menu Mac là dự phòng theo khoá META. P5b (hoá đơn, cờ qua web) có trên bot thử, chờ lên bản chính. Sổ tay: `docs/LEDGER_SWITCH_RUNBOOK.md`.
- **Menu Mac đang dùng:** in tem + đồng bộ SKU 2 kho; Shopee / TikTok đăng mới + cập nhật giá / tồn; MISA danh mục + nhập kho; tư liệu sản phẩm (`/Volumes/Media/HNC_Master/`); AI nhập từ ảnh. **Đã ẩn:** đăng / tồn / cào ảnh Website (web mới tự làm).
- **Bot Zalo:** bán / kho / tồn, phiếu NCC → nháp → chia size, hoá đơn NCC, in tem QL-700, đồng bộ web.
- **Bot Nhập hàng (@58–@60, 04/11):** ảnh / tin Chủ chia sẻ → lô → web `/api/bot/dat-ncc`; số 4 = ảnh chuyển khoản NCC vào phiếu NH-x (`che: ck`, `ck_phieu`); file PDF Zalo không chuyển được → bot chỉ sang 🧾 Thả hoá đơn trên web; nhật ký `nhap hang log`. Chi tiết `zalo_bot/README.md`. Mac công nợ NCC [4][4] / sổ quỹ [4][3] đọc phiếu chi Trả NCC đặt cọc / có ảnh như web (đặt cọc vẫn vào Đã trả).
- **Tên file xuất:** `<LOAI>_YYYYMMDD_HHMMSS.<csv|xlsx>` trong `HNC_Exported_Files` (`hnc_paths.py`); `IN.csv` và `channel_links.csv` tên cố định, ghi đè.
- **Ý tưởng chưa làm** (cần kế hoạch + "làm" của anh): sàn Lazada / feed Facebook – Zalo; báo bán chạy + gợi ý đặt bù số + hàng chậm; tách main.py thành module (chạy song song bản cũ khi thử); gom thông tin doanh nghiệp (brand, MST 2 hộ, NCC) về 1 chỗ; mô tả hàng da Yen (Y6, chờ ảnh). Đã làm xong từ danh sách cũ: tin xin hoá đơn NCC, thư mục tư liệu SP, AI đọc phiếu.
