"""tools/product_name.py ra đúng tên như hàm web ghepTen (ca chung shared/product_name_cases.json, luật 15)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.product_name import ghep_ten  # noqa: E402

CA = json.load(open(os.path.join(ROOT, 'shared', 'product_name_cases.json'), encoding='utf-8'))['ca']


class TestProductName(unittest.TestCase):
    def test_khop_web(self):
        for c in CA:
            with self.subTest(c['mo_ta']):
                self.assertEqual(ghep_ten(c['dong']), c['ten'])

    def test_so_tu_sheet(self):  # Sheet trả số 6.0 / 5.5
        self.assertEqual(ghep_ten({'Tên Ngành Hàng': 'Giày tây nam tăng chiều cao', 'tang_cao_cm': 6.0, 'product_code': 'A1'}), 'Giày tây nam tăng chiều cao 6cm A1')
        self.assertEqual(ghep_ten({'Tên Ngành Hàng': 'Giày tây nam tăng chiều cao', 'tang_cao_cm': 5.5, 'product_code': 'A1'}), 'Giày tây nam tăng chiều cao 5,5cm A1')


if __name__ == '__main__':
    unittest.main()
