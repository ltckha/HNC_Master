"""Tự gom video sản phẩm (anh Kha "làm" 30/10): .mp4 / .mov ở ~/Downloads, tên = mã có trong SANPHAM → /Volumes/Media/HNC_Master/<MÃ>/,
1 mã nhiều video (<MÃ>.mp4, <MÃ>_2.mp4…; trùng tên thì số kế tiếp, không ghi đè), ghi content_path / content_files các mã vừa gom. Cùng hàm menu 5 › 1 (main.process_media_management, luật 15).
Chạy bởi launchd vn.giayhainancy.hnc.gomvideo (WatchPaths ~/Downloads + dự phòng 13:00 hằng ngày). Không có video / ổ Media không cắm → không làm gì.

  venv/bin/python tools/gom_video.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402

if __name__ == '__main__':
    if not main.video_moi_trong_tai_ve():
        sys.exit(0)  # không có video: không mở Sheet
    main.process_media_management(main.EngineDataLoader(), auto_ingest=True, chi_video=True)
