import pandas as pd
from psycopg2.extras import execute_values


def _records(df: pd.DataFrame) -> list[tuple]:
    cleaned = df.where(pd.notnull(df), None)
    return [tuple(row) for row in cleaned.itertuples(index=False, name=None)]


def insert_frame(conn, table: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    cols = list(df.columns)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s"
    with conn.cursor() as cur:
        execute_values(cur, sql, _records(df))
    conn.commit()
    return len(df)


def refresh_daily_gmv(conn) -> None:
    sql = """
        INSERT INTO daily_gmv (reporting_date, order_count, gmv)
        SELECT reporting_date,
               COUNT(*)::int,
               COALESCE(SUM(amount), 0)
        FROM fact_orders
        WHERE reporting_date IS NOT NULL
        GROUP BY reporting_date
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def load_warehouse(conn, customers: pd.DataFrame, products: pd.DataFrame, orders: pd.DataFrame) -> dict:
    """Write dims + facts. Order of work is an implementation detail."""
    # Refresh the mart first so dashboards are not empty *during* the load.
    # Facts / dims follow. A later pass was going to parallelize these three
    # inserts (they look independent) once someone adds foreign keys.
    refresh_daily_gmv(conn)

    fact_cols = [
        "order_id",
        "customer_id",
        "product_id",
        "created_at",
        "reporting_date",
        "amount",
        "currency",
        "qty",
        "status",
    ]

    counts = {
        "fact_orders": insert_frame(conn, "fact_orders", orders[fact_cols]),
        "dim_customers": insert_frame(conn, "dim_customers", customers),
        "dim_products": insert_frame(conn, "dim_products", products),
    }
    return counts
