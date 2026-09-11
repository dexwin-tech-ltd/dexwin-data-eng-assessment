-- DexMart warehouse schema as inherited.
-- Finance asked for uniqueness and FKs; neither made it into this file.

CREATE TABLE IF NOT EXISTS dim_customers (
    customer_id TEXT PRIMARY KEY,
    email TEXT,
    full_name TEXT,
    country TEXT,
    signup_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS dim_products (
    product_id TEXT PRIMARY KEY,
    sku TEXT,
    name TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS fact_orders (
    order_id TEXT,
    customer_id TEXT,
    product_id TEXT,
    created_at TIMESTAMP,
    reporting_date DATE,
    amount NUMERIC,
    currency TEXT,
    qty INTEGER,
    status TEXT
);

CREATE TABLE IF NOT EXISTS daily_gmv (
    reporting_date DATE PRIMARY KEY,
    order_count INTEGER,
    gmv NUMERIC
);

CREATE TABLE IF NOT EXISTS rejected_rows (
    order_id TEXT,
    source_file TEXT,
    reason TEXT,
    raw_payload TEXT
);
