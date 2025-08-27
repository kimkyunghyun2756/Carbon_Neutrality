import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def _env(k, d=None):
    v = os.getenv(k, d)
    if v is None:
        raise RuntimeError(f"Missing env: {k}")
    return v

# DATABASE_URL 직접 쓰거나, 개별 변수로 조합
DB_URL = os.getenv("DATABASE_URL") or \
    f"postgresql+psycopg://{_env('DB_USER')}:{_env('DB_PASSWORD')}@" \
    f"{_env('DB_HOST')}:{_env('DB_PORT','5432')}/{_env('DB_NAME')}"

engine = create_engine(
    DB_URL,
    future=True,
    pool_pre_ping=True,
    pool_size=5,         # 트래픽에 맞춰 조정
    max_overflow=5,
    pool_recycle=1800,   # 커넥션 오래되면 재생성
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)