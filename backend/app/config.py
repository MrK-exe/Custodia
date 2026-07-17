import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CORPUS_DIR = DATA_DIR / "corpus"
HISTORICAL_SAMPLE_DIR = DATA_DIR / "historical_sample"
CHROMA_DIR = BACKEND_DIR / "chroma"
DB_PATH = DATA_DIR / "app.sqlite"

load_dotenv(BACKEND_DIR / ".env")

SAHMK_API_KEY = os.getenv("SAHMK_API_KEY", "")

EMBEDDING_MODEL = "intfloat/multilingual-e5-large"

WATCHLIST = ["2222", "1120", "7010", "2010", "1180", "2280", "4013", "1211"]
