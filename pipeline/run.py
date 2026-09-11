"""CLI entrypoint: extract → transform → load."""

from __future__ import annotations

import argparse
import sys

from pipeline.config import RAW_DIR, STAGING_DIR
from pipeline.db import connect
from pipeline.extract import (
    extract_customers,
    extract_fx_rates,
    extract_orders,
    extract_products,
    write_staging,
)
from pipeline.load import load_warehouse
from pipeline.transform import (
    transform_customers,
    transform_fx_rates,
    transform_orders,
    transform_products,
)


def run_pipeline(raw_dir=None, staging_dir=None) -> dict:
    raw_dir = raw_dir or RAW_DIR
    staging_dir = staging_dir or STAGING_DIR

    customers_raw = extract_customers(raw_dir)
    products_raw = extract_products(raw_dir)
    fx_raw = extract_fx_rates(raw_dir)
    orders_raw = extract_orders(raw_dir)

    write_staging("customers", customers_raw, staging_dir)
    write_staging("products", products_raw, staging_dir)
    write_staging("fx_rates", fx_raw, staging_dir)
    write_staging("orders", orders_raw, staging_dir)

    customers = transform_customers(customers_raw)
    products = transform_products(products_raw)
    fx = transform_fx_rates(fx_raw)
    orders = transform_orders(orders_raw, fx)

    write_staging("orders_transformed", orders, staging_dir)

    conn = connect()
    try:
        counts = load_warehouse(conn, customers, products, orders)
    finally:
        conn.close()

    print("Loaded", counts)
    print(f"Order rows sent to warehouse: {len(orders)}")
    return {"counts": counts, "order_rows": len(orders)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the DexMart nightly warehouse load")
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="Override data/raw",
    )
    args = parser.parse_args(argv)
    try:
        run_pipeline(raw_dir=args.raw_dir)
    except Exception as exc:  # noqa: BLE001 — surface whatever the batch hits
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    return 0
