"""Ghi sổ trực ca cho job launchd HNC (Bước 2 · Trực ca, anh Kha "làm" 31/10).
Gọi ~/Developer/Ecosystem-Hub/commands/log_health.sh <ma> ok|loi "<ghi chú>"; mã theo Ecosystem-Hub/docs/scheduled_jobs.json (hnc.label_print, hnc.collect_videos).
Job chạy dày / luôn bật: 'ok' chỉ ghi dòng đầu tiên mỗi ngày; 'loi' cùng ghi chú chỉ ghi 1 lần / giờ (mất mạng không làm đầy sổ).
Không bao giờ raise, không làm hỏng việc chính. Ghi chú không chứa bí mật.
"""
import os
import subprocess
import time
from datetime import date

SCRIPT = os.path.expanduser('~/Developer/Ecosystem-Hub/commands/log_health.sh')
MOC_DIR = os.path.expanduser('~/Library/Logs/he_thong')
LOI_LAP_LAI_GIAY = 3600


def _moc(ma, loai):
    return os.path.join(MOC_DIR, f'.{ma}.{loai}')


def ghi(ma, kq, ghi_chu=''):
    try:
        ghi_chu = str(ghi_chu or '')[:150]
        p, gia_tri = (_moc(ma, 'ok'), date.today().isoformat()) if kq == 'ok' else (_moc(ma, 'loi'), ghi_chu)
        con_han = os.path.exists(p) and (kq == 'ok' or time.time() - os.path.getmtime(p) < LOI_LAP_LAI_GIAY)
        if con_han:
            with open(p, encoding='utf-8') as f:
                if f.read() == gia_tri:
                    return
        subprocess.run(['/bin/bash', SCRIPT, ma, kq, ghi_chu], timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.makedirs(MOC_DIR, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(gia_tri)
    except Exception:
        pass
