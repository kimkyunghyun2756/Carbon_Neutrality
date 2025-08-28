from functools import lru_cache
from sqlalchemy import create_engine

from utils.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

@lru_cache(maxsize=1)
def get_engine():
    url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, pool_pre_ping=True, future=True)
