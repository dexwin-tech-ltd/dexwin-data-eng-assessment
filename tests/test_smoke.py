from pathlib import Path

from pipeline.config import RAW_DIR, REPORTING_CCY, REPORTING_TZ


def test_raw_files_present():
    expected = {
        "customers.csv",
        "products.csv",
        "fx_rates.csv",
        "orders_2026-03-10.csv",
        "orders_2026-03-11.csv",
    }
    present = {path.name for path in RAW_DIR.glob("*") if path.is_file()}
    assert expected <= present


def test_no_real_pii_in_customer_file():
    text = Path(RAW_DIR / "customers.csv").read_text()
    assert "@example.com" in text
    assert "gmail.com" not in text
    assert "yahoo.com" not in text


def test_reporting_contract_is_documented_in_config():
    assert REPORTING_TZ == "Africa/Nairobi"
    assert REPORTING_CCY == "GHS"


def test_pipeline_package_imports():
    from pipeline import extract, load, transform  # noqa: F401
