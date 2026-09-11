import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.getenv("RAW_DIR", ROOT / "data" / "raw"))
STAGING_DIR = Path(os.getenv("STAGING_DIR", ROOT / "data" / "staging"))

# Finance reporting calendar. The current transform does not honor this.
REPORTING_TZ = os.getenv("REPORTING_TZ", "Africa/Nairobi")
REPORTING_CCY = os.getenv("REPORTING_CCY", "GHS")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://dexmart:dexmart@localhost:5432/warehouse",
)
