import unittest, tempfile
from pathlib import Path
import app
class AccountingTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); app.DB=Path(self.tmp.name)/'test.db'
    def tearDown(self): self.tmp.cleanup()
    def add(self,amount='12.34',kind='支出',day='2026-11-01',note='测试'):
        return app.add_record(dict(day=day,kind=kind,category='餐饮',amount=amount,note=note))
    def test_exact_cents(self):
        self.add('0.10'); self.add('0.20'); self.assertEqual(app.summary('2026-11')['expense'],30)
    def test_month_and_balance(self):
        self.add('100','收入'); self.add('30'); self.add('9',day='2026-10-01')
        d=app.summary('2026-11');self.assertEqual(d['balance'],7000);self.assertEqual(len(d['rows']),2)
    def test_invalid_amount(self):
        for x in ['-1','0','NaN','Infinity','1.001','abc','100000001']:
            with self.subTest(x=x),self.assertRaises(ValueError):self.add(x)
    def test_invalid_date(self):
        with self.assertRaises(ValueError):self.add(day='2026-02-30')
    def test_budget_thresholds(self):
        with app.connect() as c:c.execute('INSERT INTO budgets VALUES(?,?)',('2026-11',10000))
        self.add('85');self.assertIn('80%', ''.join(app.summary('2026-11')['tips']))
        self.add('20');self.assertIn('已超预算5.00元',''.join(app.summary('2026-11')['tips']))
    def test_note_stored_as_text(self):
        self.add(note="<script>alert(1)</script>' OR 1=1")
        self.assertEqual(len(app.summary('2026-11')['rows']),1)
    def test_empty_month(self):
        self.assertEqual(app.summary('2026-11')['categories'],{})
if __name__=='__main__':unittest.main()
