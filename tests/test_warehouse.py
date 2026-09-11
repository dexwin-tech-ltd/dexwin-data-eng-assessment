import pandas as pd
import pytest

from pipeline.db import connect
from pipeline.extract import extract_fx_rates, extract_orders
from pipeline.run import run_pipeline
from pipeline.transform import transform_fx_rates, transform_orders


def _fetchall(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


@pytest.fixture
def clean_warehouse(db_ready):
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("TRUNCATE fact_orders, daily_gmv, rejected_rows, dim_customers, dim_products")
    conn.commit()
    yield conn
    conn.close()


@pytest.mark.integration
def test_day2_orders_are_loaded_with_event_times(clean_warehouse):
    run_pipeline()
    rows = _fetchall(
        clean_warehouse,
        """
        SELECT order_id, created_at, reporting_date
        FROM fact_orders
        WHERE order_id IN ('ORD-1010', 'ORD-1011', 'ORD-1012')
        ORDER BY order_id
        """,
    )
    assert {row[0] for row in rows} == {"ORD-1010", "ORD-1011", "ORD-1012"}
    assert all(row[1] is not None for row in rows), "Day-2 event times must not be null"


@pytest.mark.integration
def test_fact_orders_has_unique_order_ids(clean_warehouse):
    run_pipeline()
    dupes = _fetchall(
        clean_warehouse,
        """
        SELECT order_id, COUNT(*)
        FROM fact_orders
        GROUP BY order_id
        HAVING COUNT(*) > 1
        ORDER BY order_id
        """,
    )
    assert dupes == []


@pytest.mark.integration
def test_restated_order_keeps_the_later_amount(clean_warehouse):
    run_pipeline()
    rows = _fetchall(
        clean_warehouse,
        "SELECT amount FROM fact_orders WHERE order_id = 'ORD-1004'",
    )
    assert len(rows) == 1
    assert float(rows[0][0]) == pytest.approx(10.00)


@pytest.mark.integration
def test_invalid_amounts_do_not_land_as_zero_revenue(clean_warehouse):
    run_pipeline()
    rows = _fetchall(
        clean_warehouse,
        "SELECT order_id, amount FROM fact_orders WHERE order_id IN ('ORD-1006', 'ORD-1007')",
    )
    for order_id, amount in rows:
        assert amount is None or float(amount) != 0, f"{order_id} was loaded as zero revenue"


@pytest.mark.integration
def test_unknown_product_is_not_dropped(clean_warehouse):
    run_pipeline()
    rows = _fetchall(
        clean_warehouse,
        "SELECT 1 FROM fact_orders WHERE order_id = 'ORD-1002'",
    )
    assert rows, "ORD-1002 references missing product P-15 and must still load"


@pytest.mark.integration
def test_daily_gmv_is_refreshed_from_loaded_facts(clean_warehouse):
    run_pipeline()
    rows = _fetchall(
        clean_warehouse,
        "SELECT reporting_date, order_count, gmv FROM daily_gmv ORDER BY reporting_date",
    )
    assert rows, "daily_gmv must be rebuilt after facts land, not before"


@pytest.mark.integration
def test_reload_is_idempotent(clean_warehouse):
    run_pipeline()
    first = _fetchall(clean_warehouse, "SELECT COUNT(*) FROM fact_orders")[0][0]
    run_pipeline()
    second = _fetchall(clean_warehouse, "SELECT COUNT(*) FROM fact_orders")[0][0]
    assert first == second
    dupes = _fetchall(
        clean_warehouse,
        """
        SELECT order_id FROM fact_orders
        GROUP BY order_id
        HAVING COUNT(*) > 1
        """,
    )
    assert dupes == []


def test_full_extract_includes_both_export_days():
    raw = extract_orders()
    assert "orders_2026-03-10.csv" in set(raw["source_file"])
    assert "orders_2026-03-11.csv" in set(raw["source_file"])
    fx = transform_fx_rates(extract_fx_rates())
    out = transform_orders(raw, fx)
    assert "ORD-1012" in set(out["order_id"])
    day2 = out.loc[out["order_id"] == "ORD-1012"].iloc[0]
    ts = day2["created_at"] if "created_at" in out.columns else day2.get("event_ts")
    assert ts is not None and not pd.isna(ts)
