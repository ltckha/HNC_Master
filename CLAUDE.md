# CLAUDE.md — HNC_Master (HNC Control Center)

> Claude cùng anh Kha Lưu (chủ dự án) vận hành HNC Control Center cho **Hiệu giày Hải Nancy**.
> Luật chung mọi repo: `~/Developer/Ecosystem-Hub/docs/LUAT_CHUNG.md` (nạp qua `~/.claude/CLAUDE.md`). Lệch nhau thì **luật chung thắng**. File này chỉ giữ luật riêng của HNC.

---

## 1. Luật chung áp vào HNC (chỉ trỏ, không chép lại)
- Git: luật 1 (commit cục bộ, đẩy khi anh nhắn "đẩy" hoặc lịch tự động 2:30; luôn `git add` từng file).
- Mỗi repo 1 phiên Thực thi, việc repo khác thì nhắn phiên đó: luật 2. HNC: Điều phối lập kế hoạch, phiên **"Thực thi – HNC_Master"** (Mac mini M4) sửa code, chạy lệnh, xuất file, ghi Sheet.
- Tri thức brand chỉ lấy từ Auto-Video-Factory (tab `brands`), không viết cứng danh sách brand: luật 3.
- Đọc / ghi cột theo tên tiêu đề: luật 4 (SANPHAM: tên kỹ thuật ở **hàng 2**). Thiếu cột bắt buộc thì báo lỗi rõ, không ghi sang cột khác.
- Việc mới phải có "làm" của anh; sửa nhỏ trong việc đã cho làm thì cứ làm: luật 10.
- Đường dự phòng trên Mac luôn khớp web / bot: luật 15.

## 2. Luật riêng HNC
1. **Không tự đoán** cột tính toán tài chính, giá, tồn kho; chưa rõ thì hỏi anh Kha.
2. **Ghi Sheet thật và deploy bot thật** cần anh xác nhận tại phiên Thực thi – HNC_Master.
3. **Từ 21/10/2026 web là sổ gốc** (4 sổ bán / kho / tồn / hàng hoá). Bot Zalo và menu Mac là dự phòng, đọc khoá META `che_do*` (`web` | `master`) để biết được ghi gì. Sổ tay chuyển / lùi: `docs/DEPLOY_P2_P4.md`.
4. **Thư mục Drive hệ thống chỉ chứa dữ liệu:** `My Drive/HNC/He_thong` (khai ở `hnc_paths.py`) chỉ có `HNC_Templates`, `HNC_Exported_Files`, `Outputs`, `HNC_Control_Center.xlsx`. Mã nguồn và tài liệu nằm ở repo.

## 3. Hệ thống (tóm tắt — chi tiết ở `docs/KIEN_TRUC.md`, bot ở `zalo_bot/README.md`)
- **Menu Mac** (`main.py`): in tem + đồng bộ SKU 2 kho; Shopee / TikTok đăng mới + cập nhật giá / tồn; MISA danh mục + nhập kho; tư liệu sản phẩm; AI nhập từ ảnh. Việc Website (đăng, tồn, cào ảnh) đã ẩn vì web mới tự làm.
- **Bot Zalo** (Apps Script, `zalo_bot/`): bán / kho / tồn, phiếu NCC, hoá đơn NCC, in tem QL-700, đồng bộ web.
- **Luật kho chung** (`shared/luat_kho.js`) dùng cho bot, Mac và web.

## 4. Lệnh & cấu hình
```bash
source venv/bin/activate
python main.py          # hoặc nhấp đúp run.command
```
- File xuất: `My Drive/HNC/He_thong/HNC_Exported_Files/` (`hnc_paths.py`; không thấy thì báo lỗi, không dùng thư mục local). Chứng từ thuế: `My Drive/HNC/Thue/<năm>/`.
- `.env` (khoá Gemini, `SYNC_HINT_*`), `credentials.json` (service account Google Sheets). Media: `/Volumes/Media/HNC_Master/`.
