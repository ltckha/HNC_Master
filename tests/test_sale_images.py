"""Test: ảnh file sàn lấy từ web mới /img/<mã>/<n>.jpg, thiếu thì ảnh cũ trong Sheet. Không gọi mạng (giả requests.head).
Chạy: venv/bin/python tests/test_sale_images.py  → thoát mã 1 nếu có ca sai."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hnc_paths  # noqa: E402

hnc_paths.find_system_dir = lambda: "/tmp"
import main  # noqa: E402

fail = 0


def eq(name, got, want):
    global fail
    if got != want:
        fail += 1
        print(f"❌ {name}\n   got:  {got!r}\n   want: {want!r}")


WEB = {"GT1783D": 3, "OLD1D": 0}  # số ảnh mỗi mã trên web mới
CALLS = []


class Resp:
    def __init__(self, ok):
        self.status_code = 200 if ok else 404
        self.headers = {"content-type": "image/jpeg" if ok else "text/plain"}


def fake_head(url, timeout=None, allow_redirects=None):
    CALLS.append(url)
    if "DOWN" in url:
        raise main.requests.ConnectionError("x")
    code, n = url.split("/img/")[1].split("/")
    return Resp(int(n.split(".")[0]) <= WEB.get(code, 0))


main.requests.head = fake_head
base = main.WEB_IMG_BASE
old = ["https://static.vnappmob.com/a.jpg", "https://static.vnappmob.com/b.jpg", math.nan, None, "", "", "", "", ""]

pics = main.sale_images("gt1783d", old)
eq("web mới có 3 ảnh → dùng link web mới, đủ 9 ô", pics, [f"{base}/img/GT1783D/{n}.jpg" for n in (1, 2, 3)] + [""] * 6)
eq("dò tới ảnh đầu tiên không có (4 lượt)", len(CALLS), 4)
main.sale_images("GT1783D", old)
eq("mã đã dò thì không gọi lại", len(CALLS), 4)
eq("web mới chưa có ảnh → ảnh cũ trong Sheet, bỏ NaN / None", main.sale_images("OLD1D", old),
   ["https://static.vnappmob.com/a.jpg", "https://static.vnappmob.com/b.jpg"] + [""] * 7)
eq("mặc định gốc ảnh = web mới workers.dev (đổi bằng WEB_IMG_BASE)", base.startswith("https://") and "/img" not in base, True)
eq("web không gọi được → ảnh cũ, không dò tiếp mã khác", (main.sale_images("DOWN1", old)[0], main.web_image_urls("NEW2D")),
   ("https://static.vnappmob.com/a.jpg", None))

print("❌ có ca sai" if fail else "✅ test_sale_images đạt")
sys.exit(1 if fail else 0)
