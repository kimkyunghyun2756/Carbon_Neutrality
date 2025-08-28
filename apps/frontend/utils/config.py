import os
from dotenv import load_dotenv

try:
    load_dotenv()
except Exception:
    pass

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
TABLE = os.getenv("CSV_TABLE")
