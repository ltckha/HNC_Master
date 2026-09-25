# Quy Tắc Dự Án: Giao Tiếp & Trao Đổi Dữ Liệu Hai Chiều 100% Qua Google Drive API v3 (Cloud-First Architecture)

## 🚨 NGUYÊN TẮC BẮT BUỘC (CRITICAL MANDATE)

1. **100% Giao tiếp & Trao đổi dữ liệu qua Google Drive API v3**:
   - Toàn bộ hoạt động giao tiếp hai chiều, truyền nhận dữ liệu, đọc/ghi Blueprints kỹ thuật, Style Profiles, Báo cáo, Sổ tay ý tưởng (`IDEAS.md`), Nhật ký điều hành (`anti-spark_*.md`), Templates và dữ liệu giữa **Antigravity (IDE Engine)** và **Gemini Spark (Cloud Architect)** phải được thực hiện **100% thông qua Google Drive API v3** (sử dụng Service Account `credentials.json`).
   - **HOÀN TOÀN ĐỘC LẬP VÀ KHÔNG PHỤ THUỘC** vào đường dẫn thư mục đồng bộ cục bộ của Google Drive for Desktop trên macOS (`/Users/khan/Library/CloudStorage/...`).

2. **Lý do kiến trúc & Lợi ích vận hành**:
   - **Tính độc lập & Di động cao (Platform Independent)**: Hệ thống có thể vận hành ổn định trên bất kỳ môi trường nào (Mac mini M4, MacBook, Linux Server, Docker container, CI/CD) mà không đòi hỏi phải cài đặt hay kích hoạt ứng dụng Google Drive for Desktop.
   - **Đồng bộ thời gian thực (Zero Sync Latency)**: Tương tác trực tiếp với Cloud API của Google, loại bỏ hoàn toàn độ trễ đồng bộ file ngầm của hệ điều hành.
   - **Toàn vẹn dữ liệu (Single Source of Truth)**: Tránh triệt để các lỗi xung đột file cục bộ, file rác `.DS_Store`, hoặc sự cố file bị khóa do ứng dụng desktop đang sync dở.

3. **Quy chuẩn thực thi bắt buộc đối với Antigravity**:
   - Mọi module giao tiếp, nạp dữ liệu từ Spark, cập nhật trạng thái tác vụ, xuất file chia sẻ chung đều tương tác trực tiếp qua Google Drive API v3.
   - Mã nguồn phát triển (`/Users/khan/Developer/HNC_Master`) được quản lý độc lập tại máy phát triển, tách biệt hoàn toàn với hạ tầng lưu trữ đám mây.
