"""Thứ tự mô hình Gemini chung + ghi lỗi Gemini (anh Kha làm 02/11).
Thứ tự nằm ở shared/gemini_models.json; bot Code.gs RECEIPT_MODELS giữ bản chép, test bot kiểm khớp (luật 15).
Mỗi lỗi Gemini ghi 1 dòng vào ~/Library/Logs/hnc_gemini.log: ngày giờ, luồng, mô hình, mã lỗi.
"""
import json
import os
from datetime import datetime

MODELS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared', 'gemini_models.json')
LOG_FILE = os.path.expanduser('~/Library/Logs/hnc_gemini.log')
RETRY_CODES = (429, 503, 504)  # chờ rồi thử lại 1 lần cùng mô hình; 504 xử lý như 503


def models():
    with open(MODELS_FILE, encoding='utf-8') as f:
        return list(json.load(f)['models'])


def log_error(luong, model, code):
    """Không bao giờ ném lỗi (ghi log hỏng thì bỏ qua)."""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M}\t{luong}\t{model}\t{code}\n")
    except OSError:
        pass
