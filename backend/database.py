from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://kiln_user:kiln_password@db:5432/kiln_db"
    SCAN_INTERVAL_MINUTES: int = 1

    class Config:
        env_file = ".env"

settings = Settings()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
