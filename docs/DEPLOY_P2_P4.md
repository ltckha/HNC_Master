# Deploy bot thật bản P2–P4 (trước ngày chuyển 4 sổ 1 ngày)

Bot thật đang @37 (deploy 20/10 13:4x, commit ee87f54). Bản mới = HEAD của zalo_bot/Code.gs. Cả 4 sổ để **master**: bot chạy như hôm nay, chỉ thêm các phần dưới. Anh Kha duyệt deploy tại phiên Thực thi – HNC_Master.

## Bản mới đổi gì khi vẫn master
- Ghi `ma_dong` / `nguon` ở BAN / NHAP / XUAT (app: `<ticket>#n`, Zalo: `Z-<message_id>#n`, phiếu NCC: `<phieu_id>#n`).
- Số NK không lùi: số mới = max(META `nk_cuoi_<kho>`, số lớn nhất trong NHAP) + 1; cấp xong nâng `nk_cuoi_<kho>`. Số của phiếu đã huỷ không dùng lại.
- Nhập vào kho chưa có dòng mã + size → tự tạo dòng KHO có công thức trước (trước đây chờ menu Mac đồng bộ).
- Bỏ qua dòng `TRA-` / `KK-` / `DOI-` ở in tem, hoá đơn mua hàng, xuất MISA (`DOI-` để trống misa_stock — anh làm tay).
- Thanh toán `COD` (giao thu hộ) tách khỏi "Chuyển khoản".
- Đơn giá phiếu trống → giá nhập SANPHAM (đã có từ 19/10, giữ).
- Lệnh Zalo `che do` (Chủ, nhắn số 2 lần): 1–8 đổi 4 sổ Dự phòng ↔ Web, ghi mốc dự phòng.
- Khi sổ nào = web (chưa bật): bán bị chặn "Đang bán trên app"; lệnh kho chuyển `/api/bot-lenh` (loai kho / phieu_ncc); tồn hỏi web (loai ton); hàng hoá chặn tạo / sửa SANPHAM; mã đã đổi hỏi web (loai ma).
- Đo thời gian trigger / ngày (`do_trigger`), xac_nhan `web_ghi`, `tao_ma`, `kq_in_tem`, `in_bu`, hoá đơn `trang_thai` / `tin`.

## Trước khi deploy (Thực thi – HNC_Master)
1. Kiểm: `node zalo_bot/tests/test_zalo_bot.js` (≥ 342 đạt) · `node tests/test_luat_kho.js` (74/74) · `venv/bin/python tools/kiem_hop_dong.py` (khớp) · các test Python trong `tests/`.
2. Đọc META Sheet thật: che_do / che_do_kho / che_do_ton / che_do_hh đều master hoặc chưa có; `cho_chep` = 0.
3. Khởi tạo META thật (anh duyệt cùng lần deploy): `nk_cuoi_15E`, `nk_cuoi_Y3C` = số NK lớn nhất hiện có của từng kho (20/10: 15E NK000027, Y3C NK000041 — đọc lại lúc làm).
4. Web bản chính kiểm chữ ký `/api/bot-lenh` bằng **WEB_NOTIFY_KEY** (bot thật chưa có BOT_CALLBACK_KEY) — Thực thi Website xác nhận.

## Deploy
```
cd zalo_bot && clasp push --force && clasp create-deployment -i <deployment_id trong deploy.json> -d "HNC <ngày> <hash> P2-P4 master"
```

## Tối hôm trước ngày chuyển (sau đóng cửa) — anh duyệt tại phiên Thực thi – HNC_Master
- Ghi mốc dự phòng lên Sheet chính (giờ đó + hàng cuối BAN / NHAP / XUAT), để web nhập bù đúng dòng bot / Mac ghi sau mốc:
  `venv/bin/python tools/ghi_moc_du_phong.py --sheet that` (chạy thử, xem số) → `… --sheet that --ghi`.
- Bài học diễn tập 20/10: thiếu mốc thì web không nhập bù được dòng ghi lúc Dự phòng.

## Kiểm khoá ký trước khi đổi Sổ kho → Web (ngày chuyển, sau bước 1 web deploy)
- Anh nhắn Zalo `thu web` (Chủ, chỉ đọc): bot gửi `/api/bot-lenh {loai:"ma", body:{ma:"THUKHOA"}}` ký WEB_NOTIFY_KEY → "✓ Web nhận khoá (200)" thì đổi sổ được; "⚠ Web từ chối (403)…" thì DỪNG, không đụng sổ.

## Kiểm ngay sau deploy
- Web gọi cửa stock_key `do_trigger` → JSON ok (bot sống).
- Anh nhắn Zalo `che do` → 4 dòng "Sổ bán / Sổ kho / Tồn kho / Hàng hoá + giá: DỰ PHÒNG" (nhắn `0` để thoát, KHÔNG nhắn số đổi).
- Lần bán / nhập thật đầu tiên: dòng mới có `ma_dong` + `nguon`; phiếu NCC đầu tiên ra số = nk_cuoi + 1 và META nâng theo.
- Máy in tem QL-700 in bình thường (không liên quan, kiểm cho chắc).

## Lùi bản
```
cd zalo_bot && clasp deployments   # xem số bản
clasp create-deployment -i <deployment_id> -V 37 -d "lui ve @37"
```
(@37 = bản trước, cùng deployment id nên Zalo / web không phải đổi gì.)
