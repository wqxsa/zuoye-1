"""个人记账与预算分析系统。Python 3.10+，仅使用标准库。"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from decimal import Decimal, InvalidOperation
from datetime import date
import sqlite3, json, csv, io, os, re

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('ACCOUNT_DB', str(ROOT / 'accounts.db')))
CATEGORIES = ['餐饮', '交通', '购物', '学习', '娱乐', '其他', '工资', '生活费']

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, day TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL, cents INTEGER NOT NULL, note TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS budgets(month TEXT PRIMARY KEY, cents INTEGER NOT NULL)')
    return con

def money(value):
    """转换为整数分，避免二进制浮点数累计误差。"""
    try:
        x = Decimal(str(value))
        if not x.is_finite() or x <= 0 or x > 100000000 or x.as_tuple().exponent < -2:
            raise ValueError('金额须大于0、最多两位小数且不超过一亿元')
        return int(x * 100)
    except (InvalidOperation, TypeError):
        raise ValueError('金额格式错误')

def check_month(month):
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ValueError('月份格式应为YYYY-MM')
    date.fromisoformat(month + '-01')
    return month

def add_record(data):
    day = str(data.get('day', ''))
    date.fromisoformat(day)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('日期格式应为YYYY-MM-DD')
    kind, category = data.get('kind'), data.get('category')
    if kind not in ['收入', '支出'] or category not in CATEGORIES:
        raise ValueError('收支类型或分类无效')
    cents, note = money(data.get('amount')), str(data.get('note', '')).strip()
    if len(note) > 200:
        raise ValueError('备注最多200字')
    with connect() as con:
        return con.execute('INSERT INTO records(day,kind,category,cents,note) VALUES(?,?,?,?,?)', (day,kind,category,cents,note)).lastrowid

def summary(month):
    check_month(month)
    with connect() as con:
        rows = [dict(r) for r in con.execute('SELECT * FROM records WHERE substr(day,1,7)=? ORDER BY day DESC,id DESC', (month,))]
        b = con.execute('SELECT cents FROM budgets WHERE month=?', (month,)).fetchone()
    inc = sum(r['cents'] for r in rows if r['kind'] == '收入')
    exp = sum(r['cents'] for r in rows if r['kind'] == '支出')
    cats = {}
    for r in rows:
        if r['kind'] == '支出': cats[r['category']] = cats.get(r['category'], 0) + r['cents']
    budget = b['cents'] if b else 0
    tips = ['尚未设置预算，建议先设置本月支出上限。'] if not budget else [f'本月预算使用率为{exp / budget * 100:.1f}%。']
    if budget and exp > budget: tips.append(f'已超预算{(exp-budget)/100:.2f}元，请检查非必要支出。')
    elif budget and exp >= budget * .8: tips.append('预算使用率已达到80%，请留意剩余支出。')
    if cats:
        top = max(cats, key=cats.get)
        tips.append(f'支出最多的分类为{top}，合计{cats[top]/100:.2f}元。')
    return dict(rows=rows, income=inc, expense=exp, balance=inc-exp, budget=budget, categories=cats, tips=tips)

class Handler(BaseHTTPRequestHandler):
    def send(self, value, status=200, mime='application/json; charset=utf-8'):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ['/', '/static/app.js', '/static/style.css']:
                f = ROOT / ('static/index.html' if u.path == '/' else u.path.lstrip('/'))
                mime = {'html':'text/html', 'js':'text/javascript', 'css':'text/css'}[f.suffix[1:]]
                return self.send(f.read_bytes(), mime=mime+'; charset=utf-8')
            month = parse_qs(u.query).get('month', [date.today().strftime('%Y-%m')])[0]
            if u.path == '/api/summary': return self.send(summary(month))
            if u.path == '/api/export':
                out = io.StringIO(); w = csv.writer(out); w.writerow(['日期','类型','分类','金额','备注'])
                for r in summary(month)['rows']:
                    # 防止导出的备注在电子表格中作为公式执行。
                    note = r['note']; note = "'" + note if note.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else note
                    w.writerow([r['day'],r['kind'],r['category'],f"{r['cents']/100:.2f}",note])
                return self.send(out.getvalue().encode('utf-8-sig'), mime='text/csv; charset=utf-8')
            self.send({'error':'接口不存在'},404)
        except ValueError as e: self.send({'error':str(e)},400)
    def do_POST(self):
        try:
            n = int(self.headers.get('Content-Length',0))
            if n <= 0 or n > 16384: raise ValueError('请求大小无效')
            d = json.loads(self.rfile.read(n))
            if not isinstance(d, dict): raise ValueError('请求必须为JSON对象')
            if self.path == '/api/records': return self.send({'id':add_record(d)},201)
            if self.path == '/api/budget':
                month, cents = check_month(str(d.get('month',''))), money(d.get('amount'))
                with connect() as c: c.execute('INSERT INTO budgets VALUES(?,?) ON CONFLICT(month) DO UPDATE SET cents=excluded.cents',(month,cents))
            elif self.path == '/api/delete':
                record_id = d.get('id')
                if type(record_id) is not int or record_id <= 0: raise ValueError('记录编号无效')
                with connect() as c:
                    if c.execute('DELETE FROM records WHERE id=?',(record_id,)).rowcount != 1:
                        return self.send({'error':'记录不存在'},404)
            else: return self.send({'error':'接口不存在'},404)
            self.send({'ok':True})
        except (ValueError, TypeError, KeyError) as e: self.send({'error':str(e)},400)
        except sqlite3.Error: self.send({'error':'数据库操作失败'},500)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()

    # 云平台指定端口，本地运行默认使用8000。
    port = int(os.environ.get('PORT', args.port))

    connect().close()

    print(f'服务启动，监听端口：{port}', flush=True)

    ThreadingHTTPServer(
        ('0.0.0.0', port),
        Handler
    ).serve_forever()