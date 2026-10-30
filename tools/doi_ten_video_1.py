"""Đổi tên 1 lần (anh Kha "làm" 30/10): video đầu tiên của mỗi mã /Volumes/Media/HNC_Master/<MÃ>/<MÃ>.mp4 (.mov…) → <MÃ>_1.mp4.
Chỉ đổi tên, không xoá; đã có <MÃ>_1.<đuôi> thì bỏ qua + báo. Mặc định CHẠY THỬ (in danh sách); --that để đổi thật
(chạy cùng lúc Video-Post cập nhật Master — Phân tích · Xưởng video báo).

  venv/bin/python tools/doi_ten_video_1.py [--that]
"""
import os
import sys

MEDIA_DEST_DIR = "/Volumes/Media/HNC_Master"  # như main.MEDIA_DEST_DIR

DUOI = ('.mp4', '.mov', '.m4v', '.avi', '.mkv')


def ke_hoach(goc=MEDIA_DEST_DIR):
    """→ (đổi [(cũ, mới)], bỏ qua [(cũ, lý do)])."""
    doi, bo = [], []
    for ma in sorted(os.listdir(goc)):
        d = os.path.join(goc, ma)
        if ma.startswith(('.', '_')) or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            b, e = os.path.splitext(f)
            if f.startswith('.') or e.lower() not in DUOI or b.upper() != ma.upper():
                continue
            moi = os.path.join(d, f"{ma}_1{e}")
            if os.path.exists(moi):
                bo.append((os.path.join(d, f), f"đã có {ma}_1{e}"))
            else:
                doi.append((os.path.join(d, f), moi))
    return doi, bo


def main():
    that = '--that' in sys.argv
    if not os.path.isdir(MEDIA_DEST_DIR):
        print(f"❌ Không thấy {MEDIA_DEST_DIR} (ổ Media chưa cắm)")
        return 1
    doi, bo = ke_hoach()
    for cu, moi in doi:
        print(f"  {os.path.relpath(cu, MEDIA_DEST_DIR)} → {os.path.basename(moi)}")
        if that:
            os.rename(cu, moi)
    for cu, ly_do in bo:
        print(f"  ⚠️ bỏ qua {os.path.relpath(cu, MEDIA_DEST_DIR)}: {ly_do}")
    print(f"{'✅ Đã đổi' if that else 'CHẠY THỬ — sẽ đổi'} {len(doi)} file · bỏ qua {len(bo)}" + ('' if that else ' (thêm --that để đổi thật)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
