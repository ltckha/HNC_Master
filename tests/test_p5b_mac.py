"""P5b Mac (21/10): tools/web_lenh.py + main.EngineDataLoader._p5b_web — gói co_nhap / co_sp, ký HMAC, Dự phòng → ghi Sheet.
Không gọi mạng, không đụng Sheet thật (Sheet giả + requests.post giả).  venv/bin/python tests/test_p5b_mac.py"""
import hashlib
import hmac
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['HNC_BOT_KEY'] = 'k' * 20
os.environ['HNC_WEB_ORIGIN'] = 'https://beta.example'
os.environ.pop('HNC_BOT_KEY_FILE', None)
import main  # noqa: E402
from tools import web_lenh  # noqa: E402
_env0 = web_lenh._env
web_lenh._env = lambda n: '' if n == 'HNC_BOT_KEY_FILE' else _env0(n)  # .env máy thật có HNC_BOT_KEY_FILE → test dùng khoá giả

fails = 0


def eq(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(('✅ ' if ok else '❌ ') + name + ('' if ok else f'\n   được {got!r}\n   cần  {want!r}'))


class WS:
    def __init__(self, v):
        self.v = v
        self.writes = []

    def get_all_values(self):
        return self.v

    def batch_update(self, chunk):
        self.writes += chunk


class SS:
    def __init__(self, tabs):
        self.tabs = tabs

    def worksheet(self, n):
        return self.tabs[n]


class Resp:
    def __init__(self, code, body):
        self.status_code, self.body = code, body

    def json(self):
        return self.body


SENT, REPLY = [], [200, {'ok': True}]


def fake_post(url, data=None, headers=None, timeout=None):
    SENT.append({'url': url, 'raw': data.decode('utf-8'), 'h': headers})
    return Resp(*REPLY)


web_lenh.requests.post = fake_post

META = WS([['key', 'value', 'updated_at'], ['che_do_kho', 'web', ''], ['che_do_hh', 'web', ''], ['p5b_web', '1', '']])
NHAP = WS([['Số chứng từ (*)', 'product_code', 'item_size', 'misa_stock', 'web_stock', 'ma_dong'],
           ['', 'product_code', 'item_size', 'misa_stock', 'web_stock', 'ma_dong'],
           ['NK1', 'ab12d', '40', '', '', 'PN-x#1'],
           ['NK1', 'CD34N', '41', '', '', '']])
SP = WS([['nhóm'] * 4, ['product_code', 'shopee_upload', 'Chất liệu quai: ', 'purchase_price'], ['AB12D', '', '', '1']])
L = main.EngineDataLoader.__new__(main.EngineDataLoader)
L.is_google_api, L.spreadsheet, L._sync_tabs = True, SS({'META': META, 'NHAP': NHAP, 'SANPHAM': SP}), set()
L._write_ok = lambda *a, **k: True

# co_nhap: misa_stock 2 dòng → 1 gói, ma_dong khi có, ký đúng
r = L.update_status('NHAP', [2, 3], 3, 'Done - x')
p = json.loads(SENT[-1]['raw'])
eq('co_nhap: web ghi, không ghi Sheet', [r, NHAP.writes], [True, []])
eq('co_nhap: gói đúng hợp đồng', [p['loai'], p['nguon'], p['body']['dong']],
   ['co_nhap', 'mac', [{'row': 3, 'code': 'AB12D', 'ma_dong': 'PN-x#1', 'misa_stock': 'Done - x'}, {'row': 4, 'code': 'CD34N', 'misa_stock': 'Done - x'}]])
h = SENT[-1]['h']
eq('ký HMAC = hex(khoá, luc + "." + thân)', [SENT[-1]['url'], h['x-bot-sig'], h['x-bot-time'] == p['luc']],
   ['https://beta.example/api/bot-lenh', hmac.new(b'k' * 20, (h['x-bot-time'] + '.' + SENT[-1]['raw']).encode(), hashlib.sha256).hexdigest(), True])
# web_stock (thêm vào co_nhap 21/10) → gửi web
L.update_status('NHAP', [2], 4, 'Done')
eq('web_stock → co_nhap', json.loads(SENT[-1]['raw'])['body']['dong'][0].get('web_stock'), 'Done')
# cột ngoài hợp đồng (Số chứng từ) → ghi Sheet
n = len(SENT)
L.update_status('NHAP', [2], 0, 'X')
eq('cột ngoài co_nhap → ghi Sheet, không gọi web', [len(SENT) - n, len(NHAP.writes)], [0, 1])
# web lỗi → không ghi Sheet
REPLY[:] = [500, {'error': 'x'}]
NHAP.writes.clear()
eq('web lỗi → False, không ghi Sheet', [L.update_status('NHAP', [2], 3, 'Done'), NHAP.writes], [False, []])
# web Dự phòng → ghi Sheet như cũ
REPLY[:] = [200, {'ok': False, 'du_phong': True}]
eq('web Dự phòng → ghi Sheet', [L.update_status('NHAP', [2], 3, 'Done'), len(NHAP.writes)], [True, 1])
# co_sp: cờ sàn + cột thuộc tính (bỏ dấu cách cuối)
REPLY[:] = [200, {'ok': True}]
r = L.update_status('SANPHAM', [2], 1, 'Done')
eq('co_sp: shopee_upload theo mã', [r, json.loads(SENT[-1]['raw'])['body']], [True, {'ds': [{'code': 'AB12D', 'doi': {'shopee_upload': 'Done'}}]}])
eq('co_sp: cột thuộc tính "Chất liệu quai:" nhận', web_lenh.co_sp([{'code': 'AB12D', 'doi': {'Chất liệu quai: ': 'Da'}}])['ok'], True)
n = len(SENT)
eq('co_sp: cột ngoài hợp đồng (purchase_price) → None, không gọi web', [web_lenh.co_sp([{'code': 'AB12D', 'doi': {'purchase_price': '1'}}]), len(SENT) - n], [None, 0])
# p5b_web tắt → ghi Sheet
META.v = [r for r in META.v if r[0] != 'p5b_web']
n, SP.writes[:] = len(SENT), []
L.update_status('SANPHAM', [2], 1, 'Done')
eq('chưa có p5b_web → ghi Sheet, không gọi web', [len(SENT) - n, len(SP.writes)], [0, 1])
print(('❌ ' if fails else '✅ ') + 'test_p5b_mac ' + ('lỗi ' + str(fails) if fails else 'đạt'))
sys.exit(1 if fails else 0)
