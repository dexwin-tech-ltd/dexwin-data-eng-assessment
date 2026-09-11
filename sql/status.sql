-- Quick warehouse pulse. Run: make status
-- or: docker compose exec -T postgres psql -U dexmart -d warehouse -f - < sql/status.sql

SELECT 'dim_customers' AS table_name, COUNT(*) AS n FROM dim_customers
UNION ALL
SELECT 'dim_products', COUNT(*) FROM dim_products
UNION ALL
SELECT 'fact_orders', COUNT(*) FROM fact_orders
UNION ALL
SELECT 'daily_gmv', COUNT(*) FROM daily_gmv
UNION ALL
SELECT 'rejected_rows', COUNT(*) FROM rejected_rows;

SELECT order_id, COUNT(*) AS copies
FROM fact_orders
GROUP BY order_id
HAVING COUNT(*) > 1
ORDER BY order_id;

SELECT order_id, created_at, reporting_date, amount, currency, status
FROM fact_orders
ORDER BY order_id, created_at NULLS LAST;

SELECT * FROM daily_gmv ORDER BY reporting_date;
