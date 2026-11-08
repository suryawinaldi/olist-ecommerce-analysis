"""Build reproducible SQLite, audit tables and a standalone BI report from Olist's ZIP."""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASH = '967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784'
FILES = {
    'orders': 'olist_orders_dataset.csv',
    'items': 'olist_order_items_dataset.csv',
    'payments': 'olist_order_payments_dataset.csv',
    'reviews': 'olist_order_reviews_dataset.csv',
    'customers': 'olist_customers_dataset.csv',
    'products': 'olist_products_dataset.csv',
    'sellers': 'olist_sellers_dataset.csv',
    'translation': 'product_category_name_translation.csv',
    'geolocation': 'olist_geolocation_dataset.csv',
}
EXPECTED = [99441,112650,103886,99224,99441,32951,3095,71,1000163]
WINDOW = "month BETWEEN '2017-01' AND '2018-08'"

def load(db, archive, table, filename):
    with archive.open(filename) as binary:
        reader = csv.reader(io.TextIOWrapper(binary, encoding='utf-8-sig', newline=''))
        columns = next(reader)
        # Keep ratings and dates. Review free text has no role in this analysis.
        indexes = [i for i, col in enumerate(columns) if not col.startswith('review_comment')]
        columns = [columns[i] for i in indexes]
        rows = (tuple(row[i] or None for i in indexes) for row in reader)
        if table == 'geolocation':
            return sum(1 for _ in rows)
        schema = ','.join(f'"{col}" TEXT' for col in columns)
        db.execute(f'CREATE TABLE {table}({schema})')
        db.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in columns)})', rows)
        return db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

def export(db, out, name, query):
    cursor = db.execute(query)
    fields = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    with (out / f'{name}.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)
    return fields, rows

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--zip', type=Path, required=True)
    cli.add_argument('--out', type=Path, default=ROOT / 'outputs')
    cli.add_argument('--database', type=Path, help='Optional SQLite output. Path must be new.')
    cli.add_argument('--dashboard', type=Path, default=ROOT / 'Olist_Dashboard.html')
    args = cli.parse_args()
    with args.zip.open('rb') as source:
        fingerprint = hashlib.file_digest(source, 'sha256').hexdigest()
    if fingerprint != HASH:
        cli.error(f'Unexpected source SHA-256: {fingerprint}')
    if args.database and args.database.exists():
        cli.error('Use a new database path to preserve existing files.')
    args.out.mkdir(parents=True, exist_ok=True)

    # Build in memory and write an optional database after reconciliation succeeds.
    with sqlite3.connect(':memory:') as db, zipfile.ZipFile(args.zip) as archive:
        counts = {table: load(db, archive, table, name) for table, name in FILES.items()}
        assert list(counts.values()) == EXPECTED, counts
        db.executescript((ROOT / 'sql/model.sql').read_text(encoding='utf-8'))
        scalar = lambda sql: db.execute(sql).fetchone()[0]
        assert scalar('SELECT COUNT(*) FROM order_fact') == counts['orders']
        assert scalar('SELECT COUNT(*) FROM item_fact') == counts['items']
        for table in ('item_fact','payments','reviews'):
            assert scalar(f'SELECT COUNT(*) FROM {table} x LEFT JOIN orders o USING(order_id) WHERE o.order_id IS NULL') == 0
        for col, source_col in [('item_cents','price'),('freight_cents','freight_value')]:
            assert scalar(f'SELECT SUM({col}) FROM order_fact') == scalar(
                f'SELECT SUM(CAST(ROUND(CAST({source_col} AS REAL)*100) AS INTEGER)) FROM items')
        assert scalar('SELECT SUM(payment_cents) FROM order_fact') == scalar(
            'SELECT SUM(CAST(ROUND(CAST(payment_value AS REAL)*100) AS INTEGER)) FROM payments')
        assert scalar('SELECT COUNT(*) FROM order_fact WHERE DATE(purchase_ts) IS NULL') == 0
        assert scalar('SELECT COUNT(*) FROM order_fact WHERE late=1 AND eligible<>1') == 0

        fields, cube = export(db, args.out, 'dashboard_cube', (ROOT/'sql/cube.sql').read_text())
        idx = {name: index for index, name in enumerate(fields)}
        assert sum(row[idx['orders']] for row in cube) == counts['orders']
        assert sum(row[idx['eligible']] for row in cube) == scalar('SELECT SUM(eligible) FROM order_fact')
        assert sum(row[idx['late']] for row in cube) == scalar('SELECT SUM(late) FROM order_fact')
        assert sum(row[idx['gmv_cents']] for row in cube) == scalar(
            "SELECT SUM(item_cents) FROM order_fact WHERE status='delivered'")
        export(db, args.out, 'monthly_status', '''
            SELECT month,status,COUNT(*) AS orders FROM order_fact
            GROUP BY month,status ORDER BY month,status''')
        export(db, args.out, 'item_sales_by_category', f'''
            SELECT i.category,COUNT(*) AS item_rows,SUM(i.item_cents) AS gmv_cents
            FROM item_fact i JOIN order_fact o USING(order_id)
            WHERE o.status='delivered' AND {WINDOW}
            GROUP BY i.category ORDER BY gmv_cents DESC,i.category''')
        export(db, args.out, 'priority_segments', f'''
            SELECT state,category,SUM(eligible) AS eligible,SUM(late) AS late,
                   1.0*SUM(late)/SUM(eligible) AS late_rate,
                   SUM(CASE WHEN late=1 THEN item_cents ELSE 0 END) AS late_gmv_cents
            FROM order_fact WHERE {WINDOW}
            GROUP BY state,category HAVING SUM(eligible)>=100
            ORDER BY late DESC,state,category''')
        export(db, args.out, 'state_delivery', f'''
            SELECT state,SUM(eligible) AS eligible,SUM(late) AS late,
                   1.0*SUM(late)/SUM(eligible) AS late_rate
            FROM order_fact WHERE {WINDOW}
            GROUP BY state ORDER BY late DESC,state''')
        export(db, args.out, 'priority_sensitivity', f'''
            WITH segments AS (
                SELECT state,category,SUM(eligible) AS eligible,SUM(late) AS late,
                       SUM(CASE WHEN late=1 THEN item_cents ELSE 0 END) AS late_gmv_cents
                FROM order_fact WHERE {WINDOW} GROUP BY state,category
            ), cutoffs AS (SELECT 50 AS min_orders UNION ALL SELECT 100 UNION ALL SELECT 250),
            ranked AS (
                SELECT min_orders,state,category,eligible,late,1.0*late/eligible AS late_rate,
                       late_gmv_cents,
                       ROW_NUMBER() OVER (PARTITION BY min_orders ORDER BY late DESC,state,category) AS volume_rank,
                       ROW_NUMBER() OVER (PARTITION BY min_orders ORDER BY 1.0*late/eligible DESC,state,category) AS rate_rank,
                       ROW_NUMBER() OVER (PARTITION BY min_orders ORDER BY late_gmv_cents DESC,state,category) AS value_rank
                FROM segments CROSS JOIN cutoffs WHERE eligible>=min_orders
            ) SELECT * FROM ranked WHERE MIN(volume_rank,rate_rank,value_rank)<=5
              ORDER BY min_orders,volume_rank''')
        # Build the report's default totals from the same cube as the dashboard.
        window = [row for row in cube if '2017-01' <= row[0] <= '2018-08']
        totals = {col: sum(row[idx[col]] for row in window) for col in fields[3:]}
        audit = {
            'source_sha256': fingerprint, 'source_rows': counts,
            'purchase_first': scalar('SELECT MIN(purchase_ts) FROM order_fact'),
            'purchase_last': scalar('SELECT MAX(purchase_ts) FROM order_fact'),
            'full_delivered_with_both_dates': scalar("SELECT COUNT(*) FROM order_fact WHERE status='delivered' AND delivered_ts IS NOT NULL AND promised_ts IS NOT NULL"),
            'full_eligible': scalar('SELECT SUM(eligible) FROM order_fact'),
            'full_bad_delivery_sequence': scalar("SELECT COUNT(*) FROM order_fact WHERE status='delivered' AND delivered_ts<purchase_ts"),
            'multi_seller_orders': scalar('SELECT COUNT(*) FROM order_fact WHERE seller_count>1'),
            'multi_category_orders': scalar('SELECT COUNT(*) FROM order_fact WHERE category_count>1'),
            'review_extra_rows': counts['reviews']-scalar('SELECT COUNT(DISTINCT order_id) FROM reviews'),
            'dashboard_window': ['2017-01','2018-08'],
            'window_totals': totals,
        }
        (args.out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
        if args.database:
            with sqlite3.connect(args.database) as target:
                db.backup(target)

    template = (ROOT/'bi/dashboard_template.html').read_text(encoding='utf-8')
    payload = json.dumps({'fields':fields,'rows':cube},ensure_ascii=False,separators=(',',':'))
    args.dashboard.write_text(template.replace('__OLIST_CUBE__',payload.replace('<','\\u003c')),encoding='utf-8')
    print(json.dumps(audit, indent=2))

if __name__ == '__main__':
    main()
