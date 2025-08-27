from contextlib import contextmanager
from sqlalchemy.orm import Session
from apps.backend.services.db import SessionLocal

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()