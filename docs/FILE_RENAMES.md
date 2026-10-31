# Đổi tên file sang tiếng Anh (luật chung 20, anh Kha "làm" 31/10)

Đổi bằng `git mv` ngày 31/10. Bảng từ chung: `Ecosystem-Hub/docs/research/2026-10-31_english_file_names.md`.

## Việc tự chạy (launchd) và mã sổ trực ca
| Cũ | Mới |
|---|---|
| nhãn `vn.giayhainancy.hnc.intem` · mã sổ `hnc.intem` | `vn.giayhainancy.hnc.label_print` · `hnc.label_print` (đổi 31/10 sau khi Điều phối sửa scheduled_jobs.json) (script giữ `tools/label_print.py`) |
| nhãn `vn.giayhainancy.hnc.gomvideo` · mã sổ `hnc.gomvideo` | `vn.giayhainancy.hnc.collect_videos` · `hnc.collect_videos` (đổi 31/10) |
| nhãn `vn.giayhainancy.hnc.goiygia` (không cài từ 28/10) | `vn.giayhainancy.hnc.price_suggest` |

File log giữ tên cũ (`~/Library/Logs/hnc_in_tem.log`, `hnc_gom_video.log`, `hnc_goi_y_gia.log`) để không mất lịch sử.

## Nút bấm đúp
| Cũ | Mới |
|---|---|
| `run.command` | `HNC_Menu.command` (mở menu Mac) |
| `commands/bot_deploy.command` | `commands/Deploy_Bot.command` |

## Script, module, test
| Cũ | Mới | Việc |
|---|---|---|
| `tools/gom_video.py` | `tools/collect_videos.py` | gom video Tải về → Media/<MÃ>/ (launchd) |
| `tools/goi_y_gia.py` | `tools/price_suggest.py` | gợi ý giá tem mã chờ duyệt (chạy tay) |
| `tools/truc_ca.py` | `tools/health_log.py` | ghi sổ trực ca |
| `tools/web_lenh.py` | `tools/web_commands.py` | Mac gửi lệnh / cờ lên web |
| `tools/lien_ket_san.py` | `tools/marketplace_links.py` | đọc file Liên kết Shopee / TikTok |
| `tools/luat_kho_node.py` | `tools/stock_rules_node.py` | gọi luật kho chung qua node |
| `tools/mac_dinh_nganh.py` | `tools/category_defaults.py` | mặc định thuộc tính theo ngành |
| `tools/tra_doi.py` | `tools/returns_exchanges.py` | trả / đổi hàng dự phòng |
| `tools/so_misa_nhap.py` | `tools/compare_misa_receipts.py` | so file MISA nhập kho HNC – web |
| `tools/kiem_hop_dong.py` | `tools/check_data_contract.py` | kiểm hợp đồng dữ liệu khớp Sheet |
| `tools/ghi_moc_du_phong.py` | `tools/write_fallback_marker.py` | ghi mốc dự phòng META |
| `tools/dien_tap_ban.py` · `dien_tap_kho.py` | `tools/drill_sales.py` · `drill_stock.py` | diễn tập dự phòng |
| `tools/tu_dien_sanpham.py` | `tools/product_dictionary.py` | bộ chuẩn SANPHAM GĐ A (từ điển) |
| `tools/tach_cot_sanpham.py` | `tools/split_product_columns.py` | tách cột cũ sang cột mới |
| `tools/them_tu_dien.py` | `tools/add_dictionary_value.py` | thêm giá trị TU_DIEN |
| `tools/chon_nhieu.py` | `tools/set_multi_select.py` | cột chọn nhiều |
| `tools/dien_theo_cha.py` | `tools/fill_from_parent.py` | điền theo mẫu cha |
| `tools/dien_theo_nganh.py` | `tools/fill_by_category.py` | điền theo đa số ngành |
| `tools/dien_tu_du_lieu.py` | `tools/fill_from_data.py` | điền từ dữ liệu có sẵn |
| `tools/suy_trong_ma.py` | `tools/infer_within_code.py` | suy trong cùng mã |
| `tools/tu_ten.py` | `tools/attributes_from_name.py` | thuộc tính đọc từ tên hàng |
| `tools/nhom_trong.py` | `tools/group_empty_cells.py` | gom nhóm ô trống |
| `tools/nhom_mem_em.py` | `tools/group_soft_insole.py` | nhóm "mềm êm" mặt lót |
| `tools/do_om_chuan.py` | `tools/set_default_fit.py` | độ ôm / chọn size mặc định |
| `tools/kieu_de_nam.py` | `tools/fix_men_sole_type.py` | kiểu đế giày nam |
| `tools/doi_ten_thuoc_tinh.py` | `tools/rename_attribute_values.py` | đổi tên giá trị thuộc tính |
| `tools/doi_ten_video_1.py` | `tools/rename_first_videos.py` | đổi tên 1 lần <MÃ>.mp4 → <MÃ>_1.mp4 (đã chạy 30/10) |
| `tools/launchd/cai_in_tem.sh` · `cai_gom_video.sh` · `cai_goi_y_gia.sh` | `install_label_print.sh` · `install_collect_videos.sh` · `install_price_suggest.sh` | cài job launchd |
| `shared/luat_gia.js` | `shared/pricing_rules.js` | luật gợi ý giá |
| `shared/luat_kho.js` · `shared/ca_mau_luat_kho.json` · `shared/hop_dong_du_lieu.json` | `shared/stock_rules.js` · `shared/stock_rules_cases.json` · `shared/data_contract.json` | luật kho chung, ca mẫu, hợp đồng dữ liệu (đổi 31/10 cùng lúc với web, web chép bằng luat:sync) |
| `tests/test_luat_kho.js` | `tests/test_stock_rules.js` | test luật kho |
| `tests/test_luat_gia.js` · `tests/test_p5b_mac.py` | `tests/test_pricing_rules.js` · `tests/test_web_commands.py` | test |

## Tài liệu, thư mục
| Cũ | Mới |
|---|---|
| `docs/KIEN_TRUC.md` | `docs/ARCHITECTURE.md` |
| `docs/DEPLOY_P2_P4.md` | `docs/LEDGER_SWITCH_RUNBOOK.md` |
| `docs/mau_tem_A.png` | `docs/label_template_A.png` |
| `docs/luu_tru/` · `tests/luu_tru/` | `docs/archive/` · `tests/archive/` |
| `docs/sanpham_chuan/` | `docs/product_standard/` (file dữ liệu sinh ra bên trong giữ tên) |

## Giữ tên, có lý do
- `zalo_bot/` (Apps Script): đổi tên đi kèm deploy bot, để gói sau.
- `main.py`, `hnc_paths.py`, `tools/label_print.py`, `tools/label_render.py`, `tools/spec_fill.py`, test `test_label*.py`, `test_pending_info.py`, `test_sale_images.py`, `test_sync_hint.py`, `requirements.txt`, README / CLAUDE.

## Tên cũ còn chuyển tiếp tạm (xoá khi bên gọi đã đổi)
- `run.command`: chuyển sang `HNC_Menu.command`. Hướng dẫn Hub (`rebuild_after_new_mac.md`) và thói quen bấm của anh còn dùng.
- `commands/bot_deploy.command`: chuyển sang `commands/Deploy_Bot.command`. Bản đồ hệ thống Hub còn nhắc.
