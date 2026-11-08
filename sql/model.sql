-- All timestamps are source local timestamps with unspecified timezone.
-- Convert source BRL values to integer centavos before aggregating.
CREATE UNIQUE INDEX order_pk ON orders(order_id);
CREATE UNIQUE INDEX item_pk ON items(order_id, order_item_id);
CREATE UNIQUE INDEX customer_pk ON customers(customer_id);
CREATE UNIQUE INDEX product_pk ON products(product_id);
CREATE UNIQUE INDEX seller_pk ON sellers(seller_id);
CREATE UNIQUE INDEX translation_pk ON translation(product_category_name);
CREATE UNIQUE INDEX payment_pk ON payments(order_id, payment_sequential);
CREATE INDEX review_order ON reviews(order_id);

CREATE TABLE item_fact AS
SELECT i.order_id, CAST(i.order_item_id AS INTEGER) AS item_no, i.seller_id,
       i.product_id, COALESCE(t.product_category_name_english, p.product_category_name,
                              'Unclassified') AS category,
       CAST(ROUND(CAST(i.price AS REAL)*100) AS INTEGER) AS item_cents,
       CAST(ROUND(CAST(i.freight_value AS REAL)*100) AS INTEGER) AS freight_cents
FROM items i
LEFT JOIN products p USING(product_id)
LEFT JOIN translation t USING(product_category_name);
CREATE UNIQUE INDEX item_fact_pk ON item_fact(order_id, item_no);

CREATE TABLE order_fact AS
WITH category_value AS (
    SELECT order_id, category, SUM(item_cents) AS merchandise
    FROM item_fact GROUP BY order_id, category
), category_rank AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY order_id ORDER BY merchandise DESC, category ASC
    ) AS category_rank
    FROM category_value
), item_totals AS (
    SELECT order_id, SUM(item_cents) AS item_cents, SUM(freight_cents) AS freight_cents,
           COUNT(*) AS item_count, COUNT(DISTINCT seller_id) AS seller_count,
           COUNT(DISTINCT category) AS category_count
    FROM item_fact GROUP BY order_id
), payment_totals AS (
    SELECT order_id, SUM(CAST(ROUND(CAST(payment_value AS REAL)*100) AS INTEGER)) AS payment_cents
    FROM payments GROUP BY order_id
), review_rank AS (
    SELECT order_id, CAST(review_score AS INTEGER) AS score,
           ROW_NUMBER() OVER (PARTITION BY order_id
               ORDER BY review_answer_timestamp DESC, review_creation_date DESC,
                        review_id ASC, CAST(review_score AS INTEGER) ASC) AS review_rank
    FROM reviews WHERE CAST(review_score AS INTEGER) BETWEEN 1 AND 5
), base AS (
    SELECT o.order_id, o.order_purchase_timestamp AS purchase_ts,
           SUBSTR(o.order_purchase_timestamp,1,7) AS month,
           COALESCE(c.customer_state,'Unknown') AS state,
           COALESCE(cr.category,'No items') AS category, o.order_status AS status,
           o.order_delivered_carrier_date AS carrier_ts,
           o.order_delivered_customer_date AS delivered_ts,
           o.order_estimated_delivery_date AS promised_ts,
           COALESCE(i.item_cents,0) AS item_cents, COALESCE(i.freight_cents,0) AS freight_cents,
           COALESCE(i.item_count,0) AS item_count, COALESCE(i.seller_count,0) AS seller_count,
           COALESCE(i.category_count,0) AS category_count,
           p.payment_cents, r.score AS review_score
    FROM orders o
    LEFT JOIN customers c USING(customer_id)
    LEFT JOIN item_totals i USING(order_id)
    LEFT JOIN payment_totals p USING(order_id)
    LEFT JOIN category_rank cr ON o.order_id=cr.order_id AND cr.category_rank=1
    LEFT JOIN review_rank r ON o.order_id=r.order_id AND r.review_rank=1
)
SELECT *,
    CASE WHEN status='delivered' AND DATE(delivered_ts) IS NOT NULL
         AND DATE(promised_ts) IS NOT NULL AND delivered_ts>=purchase_ts THEN 1 ELSE 0 END AS eligible,
    CASE WHEN status='delivered' AND DATE(delivered_ts) IS NOT NULL
         AND DATE(promised_ts) IS NOT NULL AND delivered_ts>=purchase_ts
         THEN DATE(delivered_ts)>DATE(promised_ts) END AS late,
    CASE WHEN status='delivered' AND delivered_ts>=purchase_ts
         THEN JULIANDAY(delivered_ts)-JULIANDAY(purchase_ts) END AS delivery_days,
    CASE WHEN status='delivered' AND carrier_ts>=purchase_ts AND delivered_ts>=carrier_ts
         THEN JULIANDAY(carrier_ts)-JULIANDAY(purchase_ts) END AS pre_carrier_days,
    CASE WHEN status='delivered' AND carrier_ts>=purchase_ts AND delivered_ts>=carrier_ts
         THEN JULIANDAY(delivered_ts)-JULIANDAY(carrier_ts) END AS post_carrier_days
FROM base;
CREATE UNIQUE INDEX order_fact_pk ON order_fact(order_id);
