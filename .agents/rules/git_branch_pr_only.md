# Quy Tắc Dự Án: Chỉ Push Nhánh Riêng + Pull Request (Branch + PR Only)

## 🚨 NGUYÊN TẮC BẮT BUỘC (luật chung 4 repo, chốt 11/10/2026)

1. **Chỉ push lên nhánh riêng và mở Pull Request**; **TUYỆT ĐỐI KHÔNG** push thẳng `main`.
2. `main` chỉ thay đổi khi anh Kha bấm **Merge** trên GitHub (= lệnh push của anh Kha).
3. **Trước khi push**: rà diff, không để lọt `.env`, `credentials.json`, token, cookie.
4. **Cấm `git commit -am` / `git add -A` / `git add .`**: luôn `git add` từng file.
5. Chỉ phiên "Thực thi – HNC_Master" được commit/push trong repo này.
