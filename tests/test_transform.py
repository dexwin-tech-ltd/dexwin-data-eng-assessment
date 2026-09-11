from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from pipeline.transform import (
    apply_fx,
    clean_amount,
    parse_event_ts,
    reporting_date_from_ts,
    transform_orders,
)


def _fx() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"rate_date": date(2026, 3, 10), "base_ccy": "USD", "quote_ccy": "GHS", "rate": 15.70},
            {"rate_date": date(2026, 3, 11), "base_ccy": "USD", "quote_ccy": "GHS", "rate": 15.82},
            {"rate_date": date(2026, 3, 10), "base_ccy": "GHS", "quote_ccy": "GHS", "rate": 1.0},
            {"rate_date": date(2026, 3, 11), "base_ccy": "GHS", "quote_ccy": "GHS", "rate": 1.0},
        ]
    )


def test_order_ts_alias_is_used_when_created_at_missing():
    raw = pd.DataFrame(
        [
            {
                "order_id": "ORD-9",
                "customer_id": "C-1",
                "product_id": "P-1",
                "order_ts": "2026-03-11T09:00:00Z",
                "amount": "10.00",
                "currency": "USD",
                "qty": "1",
                "status": "paid",
            }
        ]
    )
    out = transform_orders(raw, _fx())
    ts_col = "event_ts" if "event_ts" in out.columns else "created_at"
    assert out[ts_col].notna().all(), "Day-2 `order_ts` must map onto the event timestamp"


def test_missing_and_invalid_amounts_are_not_coerced_to_zero():
    cleaned = clean_amount(pd.Series(["", "N/A", "12.50"]))
    assert pd.isna(cleaned.iloc[0])
    assert pd.isna(cleaned.iloc[1])
    assert float(cleaned.iloc[2]) == 12.50


def test_utc_evening_lands_on_next_nairobi_date():
    # 21:30Z on 10 Mar is 00:30 EAT on 11 Mar.
    ts = parse_event_ts(pd.Series(["2026-03-10T21:30:00Z"]))
    dates = reporting_date_from_ts(ts)
    assert dates.iloc[0] == date(2026, 3, 11)


def test_naive_timestamp_is_interpreted_as_nairobi_not_utc():
    # 23:30 naive must stay 10 Mar in Nairobi, not become 11 Mar via UTC+3.
    ts = parse_event_ts(pd.Series(["2026-03-10 23:30:00"]))
    dates = reporting_date_from_ts(ts)
    assert dates.iloc[0] == date(2026, 3, 10)


def test_offset_timestamp_uses_the_embedded_offset():
    ts = parse_event_ts(pd.Series(["2026-03-10T21:45:00+03:00"]))
    parsed = pd.Timestamp(ts.iloc[0])
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    else:
        parsed = parsed.tz_convert("UTC")
    assert parsed == datetime(2026, 3, 10, 18, 45, tzinfo=ZoneInfo("UTC"))
    assert reporting_date_from_ts(ts).iloc[0] == date(2026, 3, 10)


def test_usd_amount_is_converted_to_ghs_for_the_reporting_date():
    orders = pd.DataFrame(
        [
            {
                "order_id": "ORD-FX",
                "customer_id": "C-1",
                "product_id": "P-1",
                "created_at": "2026-03-10T10:00:00Z",
                "amount": 2.50,
                "currency": "USD",
                "qty": 1,
                "status": "paid",
                "reporting_date": date(2026, 3, 10),
            }
        ]
    )
    converted = apply_fx(orders, _fx())
    amount = (
        converted["amount_ghs"].iloc[0]
        if "amount_ghs" in converted.columns
        else converted["amount"].iloc[0]
    )
    assert amount == pytest.approx(2.50 * 15.70)


def test_duplicate_order_id_keeps_a_single_latest_row():
    raw = pd.DataFrame(
        [
            {
                "order_id": "ORD-1004",
                "customer_id": "C-102",
                "product_id": "P-11",
                "created_at": "2026-03-10T18:00:00Z",
                "amount": "12.00",
                "currency": "USD",
                "qty": "2",
                "status": "paid",
                "source_file": "orders_2026-03-10.csv",
            },
            {
                "order_id": "ORD-1004",
                "customer_id": "C-102",
                "product_id": "P-11",
                "order_ts": "2026-03-11T09:00:00Z",
                "amount": "10.00",
                "currency": "USD",
                "qty": "2",
                "status": "paid",
                "source_file": "orders_2026-03-11.csv",
            },
            {
                "order_id": "ORD-1005",
                "customer_id": "C-104",
                "product_id": "P-14",
                "created_at": "2026-03-10T10:00:00Z",
                "amount": "99.00",
                "currency": "USD",
                "qty": "1",
                "status": "paid",
                "source_file": "orders_2026-03-10.csv",
            },
            {
                "order_id": "ORD-1005",
                "customer_id": "C-104",
                "product_id": "P-14",
                "created_at": "2026-03-10T10:00:00Z",
                "amount": "99.00",
                "currency": "USD",
                "qty": "1",
                "status": "paid",
                "source_file": "orders_2026-03-10.csv",
            },
        ]
    )
    out = transform_orders(raw, _fx())
    assert out["order_id"].nunique() == 2
    assert len(out) == 2
    restated = out.loc[out["order_id"] == "ORD-1004"].iloc[0]
    assert float(restated["amount"]) == pytest.approx(10.00)
