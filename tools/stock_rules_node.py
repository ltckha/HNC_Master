"""Gọi luật kho chung shared/stock_rules.js từ Python (main.py, công cụ Mac) qua node — luật 15: Mac ra cùng kết quả với bot / web.
Dùng: from tools.stock_rules_node import goi; goi('banTachChuHang', '15E', 2, 1) → {'phan': [...], 'doi_cot': [...]}"""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUAT = os.path.join(ROOT, 'shared', 'stock_rules.js')


LUAT_GIA = os.path.join(ROOT, 'shared', 'pricing_rules.js')


def goi(ham, *args, luat=LUAT):
    js = ("const L = require(process.argv[1]); const a = JSON.parse(process.argv[2]);"
          "process.stdout.write(JSON.stringify(L[a.ham].apply(null, a.args)));")
    out = subprocess.run(['node', '-e', js, luat, json.dumps({'ham': ham, 'args': list(args)})],
                         capture_output=True, text=True, timeout=20, check=True)
    return json.loads(out.stdout)


def goi_gia(ham, *args):
    """Luật gợi ý giá chung shared/pricing_rules.js (Agent đăng SP GĐ3b)."""
    return goi(ham, *args, luat=LUAT_GIA)
