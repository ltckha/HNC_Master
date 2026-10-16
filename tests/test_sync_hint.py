"""Test: main.py báo web chép Sheet gửi khoá ở header x-sync-key, không để trong URL. Không gọi mạng.
Chạy: venv/bin/python tests/test_sync_hint.py  → thoát mã 1 nếu có ca sai."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hnc_paths  # noqa: E402

hnc_paths.find_system_dir = lambda: "/tmp"
import main  # noqa: E402

SENT = []


class Resp:
    status_code = 202


def fake_post(url, params=None, headers=None, json=None, timeout=None):
    SENT.append({"url": url, "params": params, "headers": headers or {}, "json": json})
    return Resp()


main.requests.post = fake_post
os.environ["SYNC_HINT_URL"] = "https://web.example/api/sync-hint"
os.environ["SYNC_HINT_KEY"] = "synckey_1234567890"


class Fake:
    _sync_tabs = {"BAN"}


main.EngineDataLoader.flush_sync_hint(Fake())
s = SENT[0] if SENT else {}
got = (len(SENT), s.get("headers", {}).get("x-sync-key"), "synckey" in s.get("url", "") or bool(s.get("params")), (s.get("json") or {}).get("tabs"))
want = (1, "synckey_1234567890", False, ["KHO15E", "KHOY3C", "BAN"])
if got != want:
    print(f"❌ khoá ở header, không ở URL\n   got:  {got!r}\n   want: {want!r}")
    sys.exit(1)
print("✅ test_sync_hint đạt")
