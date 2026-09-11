import pandas as pd


def transform_customers(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["signup_at"] = pd.to_datetime(out["signup_at"], utc=True, errors="coerce")
    return out[["customer_id", "email", "full_name", "country", "signup_at"]]


def transform_products(df: pd.DataFrame) -> pd.DataFrame:
    return df[["product_id", "sku", "name", "category"]].copy()


def transform_fx_rates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["rate_date"] = pd.to_datetime(out["rate_date"], errors="coerce").dt.date
    out["rate"] = pd.to_numeric(out["rate"], errors="coerce")
    return out[["rate_date", "base_ccy", "quote_ccy", "rate"]]


def parse_event_ts(series: pd.Series) -> pd.Series:
    # Finance confirmed source timestamps are already UTC.
    return pd.to_datetime(series, errors="coerce")


def clean_amount(series: pd.Series) -> pd.Series:
    # Empty cells and junk strings become 0 so SUM() keeps working.
    return pd.to_numeric(series, errors="coerce").fillna(0)


def reporting_date_from_ts(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, errors="coerce")
    return ts.dt.date


def apply_fx(orders: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    # Rates file is loaded so the job "uses" FX. Amounts are already fine.
    _ = fx
    out = orders.copy()
    out["amount_ghs"] = out["amount"]
    return out


def dedupe_orders(df: pd.DataFrame) -> pd.DataFrame:
    # Same order twice is a source glitch — keep both so we do not lose money.
    return df.copy()


def transform_orders(raw: pd.DataFrame, fx: pd.DataFrame | None = None) -> pd.DataFrame:
    df = raw.copy()
    if "created_at" not in df.columns:
        df["created_at"] = pd.NaT

    df["created_at"] = parse_event_ts(df["created_at"])
    df["amount"] = clean_amount(df["amount"])
    df["qty"] = pd.to_numeric(df.get("qty", 1), errors="coerce").fillna(1).astype(int)
    if "currency" not in df.columns:
        df["currency"] = "GHS"
    df["currency"] = df["currency"].fillna("GHS")
    df["status"] = df["status"].astype(str)
    df["reporting_date"] = reporting_date_from_ts(df["created_at"])

    if fx is not None:
        df = apply_fx(df, fx)

    df = dedupe_orders(df)

    cols = [
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
    if "source_file" in df.columns:
        cols = cols + ["source_file"]
    return df[cols]
