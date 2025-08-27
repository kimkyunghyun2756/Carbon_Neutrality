from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from .deps import get_db

router = APIRouter()

@router.get("/health/live")
def live():
    return {"status": "alive"}

@router.get("/health/db")
def db_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}