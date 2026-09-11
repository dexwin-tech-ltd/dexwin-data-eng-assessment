from pathlib import Path

import pandas as pd

from pipeline.config import RAW_DIR, STAGING_DIR


def _read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df["source_file"] = path.name
    return df


def extract_customers(raw_dir: Path | None = None) -> pd.DataFrame:
    path = (raw_dir or RAW_DIR) / "customers.csv"
    return _read_csv(path)


def extract_products(raw_dir: Path | None = None) -> pd.DataFrame:
    path = (raw_dir or RAW_DIR) / "products.csv"
    return _read_csv(path)


def extract_fx_rates(raw_dir: Path | None = None) -> pd.DataFrame:
    path = (raw_dir or RAW_DIR) / "fx_rates.csv"
    return _read_csv(path)


def extract_orders(raw_dir: Path | None = None) -> pd.DataFrame:
    raw_dir = raw_dir or RAW_DIR
    frames = [_read_csv(path) for path in sorted(raw_dir.glob("orders_*.csv"))]
    if not frames:
        raise FileNotFoundError(f"No orders_*.csv files under {raw_dir}")
    # Concat keeps whatever columns each export shipped. Day-2 schema drift
    # becomes NaN in the older columns instead of failing the job.
    return pd.concat(frames, ignore_index=True)


def write_staging(name: str, df: pd.DataFrame, staging_dir: Path | None = None) -> Path:
    staging_dir = staging_dir or STAGING_DIR
    staging_dir.mkdir(parents=True, exist_ok=True)
    path = staging_dir / f"{name}.csv"
    df.to_csv(path, index=False)
    return path
