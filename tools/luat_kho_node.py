"""Gọi luật kho chung shared/luat_kho.js từ Python (main.py, công cụ Mac) qua node — luật 15: Mac ra cùng kết quả với bot / web.
Dùng: from tools.luat_kho_node import goi; goi('banTachChuHang', '15E', 2, 1) → {'phan': [...], 'doi_cot': [...]}"""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUAT = os.path.join(ROOT, 'shared', 'luat_kho.js')


LUAT_GIA = os.path.join(ROOT, 'shared', 'luat_gia.js')


def goi(ham, *args, luat=LUAT):
    js = ("const L = require(process.argv[1]); const a = JSON.parse(process.argv[2]);"
          "process.stdout.write(JSON.stringify(L[a.ham].apply(null, a.args)));")
    out = subprocess.run(['node', '-e', js, luat, json.dumps({'ham': ham, 'args': list(args)})],
                         capture_output=True, text=True, timeout=20, check=True)
    return json.loads(out.stdout)


def goi_gia(ham, *args):
    """Luật gợi ý giá chung shared/luat_gia.js (Agent đăng SP GĐ3b)."""
    return goi(ham, *args, luat=LUAT_GIA)
