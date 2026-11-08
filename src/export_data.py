"""Export cleaned source tables and reconciled analytical facts."""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

HASH = '967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784'
ORDER_QUERY = """
WITH dimensions AS (
  SELECT order_id,
         GROUP_CONCAT(DISTINCT seller_id) AS seller_ids,
         GROUP_CONCAT(DISTINCT product_id) AS product_ids
  FROM (SELECT * FROM item_fact ORDER BY order_id,item_no) GROUP BY order_id
), payment_methods AS (
  SELECT order_id, GROUP_CONCAT(DISTINCT payment_type) AS payment_types,
         COUNT(*) AS payment_rows FROM payments GROUP BY order_id
), review_counts AS (
  SELECT order_id, COUNT(*) AS review_rows FROM reviews GROUP BY order_id
)
SELECT f.*, o.customer_id,c.customer_unique_id,c.customer_city,c.customer_zip_code_prefix,
       o.order_approved_at, d.seller_ids,d.product_ids,p.payment_types,
       COALESCE(p.payment_rows,0) AS payment_rows,COALESCE(r.review_rows,0) AS review_rows,
       CASE WHEN f.late=1 THEN CAST(JULIANDAY(DATE(delivered_ts)) -
                                    JULIANDAY(DATE(promised_ts)) AS INTEGER) END AS overdue_days
FROM order_fact f JOIN orders o USING(order_id) LEFT JOIN customers c USING(customer_id)
LEFT JOIN dimensions d USING(order_id) LEFT JOIN payment_methods p USING(order_id)
LEFT JOIN review_counts r USING(order_id)
ORDER BY f.purchase_ts,f.order_id
"""
ITEM_QUERY = """
SELECT i.*, f.purchase_ts, f.month, f.state AS customer_state, c.customer_city,
       s.seller_state,s.seller_city,p.product_weight_g,p.product_length_cm,
       p.product_height_cm,p.product_width_cm,raw.shipping_limit_date,f.status AS order_status,
       f.eligible AS order_eligible,f.late AS order_late
FROM item_fact i JOIN order_fact f USING(order_id)
JOIN orders o USING(order_id) LEFT JOIN customers c USING(customer_id)
LEFT JOIN sellers s USING(seller_id) LEFT JOIN products p USING(product_id)
JOIN items raw ON i.order_id=raw.order_id AND i.item_no=CAST(raw.order_item_id AS INTEGER)
ORDER BY i.order_id,i.item_no
"""
MONEY = {'price', 'freight_value', 'payment_value'}
EXACT_FIELDS = {'review_comment_title', 'review_comment_message'}

def clean_value(col, value):
    if col in EXACT_FIELDS:
        return value
    value = value.strip()
    if not value:
        return ''
    if col in MONEY:
        amount = Decimal(value)
        assert amount.is_finite() and amount == amount.quantize(Decimal('.01'))
        return f'{amount:.2f}'
    if col.endswith(('_timestamp','_date','_at')):
        return datetime.fromisoformat(value).isoformat(sep=' ')
    if col.endswith('zip_code_prefix'):
        assert value.isascii() and value.isdigit() and len(value) <= 5
        return value.zfill(5)
    return value

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    with args.zip.open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest() == HASH
    for sub in ['tabel_bersih','siap_impor']:
        (args.out/sub).mkdir(parents=True,exist_ok=True)
    counts = {}
    with ZipFile(args.zip) as archive:
        assert archive.testzip() is None
        for name in sorted(archive.namelist()):
            with archive.open(name) as source, (args.out/'tabel_bersih'/name).open('w',encoding='utf-8-sig',newline='') as target:
                reader = csv.reader(io.TextIOWrapper(source,encoding='utf-8-sig',newline=''))
                fields = next(reader)
                writer = csv.writer(target)
                writer.writerow(fields)
                n = 0
                for row in reader:
                    assert len(row) == len(fields)
                    writer.writerow([clean_value(k,v) for k,v in zip(fields,row)])
                    n += 1
                counts[name] = n
    audit = {'sha256_zip_asli': HASH, 'baris_tabel_bersih':counts}
    with sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro', uri=True) as db:
        for name, query in [('Olist_Pesanan_Gabungan',ORDER_QUERY),('Olist_Item_Gabungan',ITEM_QUERY)]:
            rows = db.execute(query)
            with (args.out/'siap_impor'/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as target:
                fields = [c[0] for c in rows.description]
                writer = csv.writer(target)
                writer.writerow(fields)
                seen = set()
                money = [0,0]
                for row in rows:
                    key = tuple(row[:2]) if name.endswith('Item_Gabungan') else row[0]
                    assert key not in seen
                    seen.add(key)
                    for i,col in enumerate(['item_cents','freight_cents']):
                        money[i] += row[fields.index(col)]
                    if name.endswith('Pesanan_Gabungan'):
                        row = list(row)
                        i = fields.index('customer_zip_code_prefix')
                        if row[i] is not None:
                            row[i] = row[i].zfill(5)
                    writer.writerow(row)
                assert len(seen) == (99441 if name.endswith('Pesanan_Gabungan') else 112650)
                assert tuple(money) == db.execute('SELECT SUM(item_cents),SUM(freight_cents) FROM item_fact').fetchone()
                audit[name] = {'baris_unik':len(seen),'item_cents':money[0],'freight_cents':money[1]}
    (args.out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')

if __name__=='__main__':
    main()
